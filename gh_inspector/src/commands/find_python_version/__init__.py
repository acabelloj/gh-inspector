import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import typer
from github_client import GitHubClient
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion
from packaging.version import parse as parse_version
from rich.console import Console
from rich.table import Table
from scanner import scan_repos

from .extractors import EXTRACTORS, VersionCategory

console = Console()

FILE_WORKERS = 3

FILE_PATTERNS = [pattern for ext in EXTRACTORS for pattern in ext.FILE_PATTERNS]


def matches_pattern(file_path: str, pattern: str) -> bool:
    if "*" in pattern:
        regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
        return re.search(regex_pattern, file_path) is not None
    return file_path.endswith(pattern) or file_path == pattern


def _get_extractor(file_path: str):
    for extractor in EXTRACTORS:
        if any(matches_pattern(file_path, p) for p in extractor.FILE_PATTERNS):
            return extractor
    return None


def extract_versions_for_file(file_path: str, content: str) -> list[tuple[str, VersionCategory]]:
    extractor = _get_extractor(file_path)
    if extractor is None:
        return []
    return [(v, extractor.CATEGORY) for v in extractor.extract(content)]


_ROOT_DIRS = {".github", ".circleci"}
_PROJECT_MARKERS = frozenset({"pyproject.toml", "setup.py", "setup.cfg", "Pipfile", "Pulumi.yaml", "Pulumi.yml"})
_PULUMI_STACK_RE = re.compile(r"^Pulumi\..+\.(yaml|yml)$")


def _find_project_roots(tree: list[dict]) -> set[str]:
    """Return directory paths that contain a project marker file."""
    roots = set()
    for entry in tree:
        path = entry["path"]
        filename = path.rsplit("/", 1)[-1] if "/" in path else path
        if filename in _PROJECT_MARKERS or _PULUMI_STACK_RE.match(filename):
            roots.add(path.rsplit("/", 1)[0] if "/" in path else "")
    return roots


def _project_key(file_path: str, project_roots: set[str]) -> str:
    """Return the sub-project key for a file based on detected project roots.

    Finds the deepest project root directory that is an ancestor of the file.
    CI dirs (.github, .circleci) always belong to the root project.
    Falls back to the first directory component for unmatched files.
    """
    parts = file_path.split("/")
    if parts[0] in _ROOT_DIRS:
        return ""
    file_dir = "/".join(parts[:-1])
    best: str | None = None
    for root in project_roots:
        if root == "" or file_dir == root or file_dir.startswith(root + "/"):
            if best is None or len(root) > len(best):
                best = root
    if best is not None:
        return best
    return parts[0] if len(parts) > 1 else ""


def get_files(gh_client, repo_name, file_patterns, branch=None):
    try:
        tree = gh_client.get_repo_tree(repo_name, branch)
        matched = []
        for file in tree:
            path = file["path"]
            for pattern in file_patterns:
                if matches_pattern(path, pattern):
                    matched.append(path)
                    break
        return matched, _find_project_roots(tree)
    except Exception as e:
        console.print(f"[red]Error retrieving file list for {repo_name}: {e}[/red]")
        return [], set()


def process_repo(gh_client, repo, file_patterns):
    repo_name = repo["nameWithOwner"]
    branch = (repo.get("defaultBranchRef") or {}).get("name") or None
    projects: dict[str, dict[VersionCategory, dict[str, set[str]]]] = defaultdict(
        lambda: {cat: defaultdict(set) for cat in VersionCategory}
    )
    try:
        files, project_roots = get_files(gh_client, repo_name, file_patterns, branch)
        with ThreadPoolExecutor(max_workers=FILE_WORKERS) as file_executor:
            futures = {file_executor.submit(gh_client.get_file_content, repo_name, f): f for f in files}
            for future in as_completed(futures):
                file = futures[future]
                try:
                    content = future.result()
                    project = _project_key(file, project_roots)
                    for version, category in extract_versions_for_file(file, content):
                        projects[project][category][version].add(file)
                except Exception as e:
                    console.print(f"[red]Error processing {file} in {repo_name}: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error processing {repo_name}: {e}[/red]")
    return repo_name, dict(projects)


def version_key(version: str):
    if m := re.search(r"(\d+(?:\.\d+)*)", version):
        try:
            return parse_version(m.group(1))
        except (InvalidVersion, TypeError):
            pass
    return parse_version("0.0")


def _base_version(version_str: str) -> str | None:
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", version_str)
    return m.group(1) if m else None


def check_consistency(
    runtime: dict[str, set],
    minimum: dict[str, set],
) -> list[str]:
    issues = []
    runtime_versions = [v for rv in runtime if (v := _base_version(rv))]
    for spec_str in minimum:
        try:
            spec = SpecifierSet(spec_str, prereleases=True)
            for rv in runtime_versions:
                if not spec.contains(rv):
                    issues.append(f"runtime {rv} does not satisfy {spec_str}")
        except InvalidSpecifier:
            base = _base_version(spec_str)
            if base:
                for rv in runtime_versions:
                    try:
                        if parse_version(rv) < parse_version(base):
                            issues.append(f"runtime {rv} below minimum {spec_str}")
                    except (InvalidVersion, TypeError):
                        pass
    return issues


def _fmt(cat_dict: dict[str, set]) -> str:
    if not cat_dict:
        return "—"

    # Use full paths when basenames clash (e.g. two Dockerfiles in different services)
    all_paths = [fp for paths in cat_dict.values() for fp in paths]
    basenames = [p.split("/")[-1] for p in all_paths]
    use_full_path = len(basenames) != len(set(basenames))

    by_version: dict[str, list[str]] = {}
    for version in sorted(cat_dict.keys(), key=version_key):
        if use_full_path:
            sources = sorted(cat_dict[version])
        else:
            sources = sorted({fp.split("/")[-1] for fp in cat_dict[version]})
        by_version[version] = sources

    multiple_versions = len(by_version) > 1
    parts = []
    for version, sources in by_version.items():
        source_str = f"{len(sources)} files" if len(sources) > 2 else ", ".join(sources)
        prefix = "[yellow]⚡[/yellow] " if multiple_versions else ""
        parts.append(f"{prefix}{version} [dim]({source_str})[/dim]")
    return "\n".join(parts)


def _iter_projects(all_repo_results):
    """Yield (display_name, results) for every project across all repos."""
    for repo_name, projects in all_repo_results:
        if not projects:
            yield repo_name, None
            continue
        for project_key, results in sorted(projects.items()):
            display = f"{repo_name} [{project_key}]" if project_key else repo_name
            yield display, results


def display_results(all_repo_results: list[tuple[str, dict]]) -> None:
    runtime_distribution: dict[str, int] = defaultdict(int)
    no_version_repos = []
    inconsistencies = []

    for display_name, results in _iter_projects(all_repo_results):
        if results is None or not any(results[cat] for cat in VersionCategory):
            no_version_repos.append(display_name)
            continue

        for v in results[VersionCategory.RUNTIME]:
            base = _base_version(v)
            if base:
                normalized = ".".join(base.split(".")[:2])
                runtime_distribution[normalized] += 1

        issues = check_consistency(results[VersionCategory.RUNTIME], results[VersionCategory.MINIMUM])
        if issues:
            inconsistencies.append((display_name, issues))

    console.print("\n[bold cyan]Python Version Identification Dashboard[/bold cyan]\n")

    if runtime_distribution:
        total = sum(runtime_distribution.values())
        summary = Table(
            title="Runtime Version Distribution",
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
        )
        summary.add_column("Python Version", style="yellow", width=20)
        summary.add_column("Repos", justify="center", style="magenta", width=8)
        summary.add_column("Percentage", justify="center", style="green", width=12)
        summary.add_column("", style="cyan", width=30)
        sorted_runtime = sorted(runtime_distribution.items(), key=lambda x: version_key(x[0]), reverse=True)
        for idx, (version, count) in enumerate(sorted_runtime):
            pct = (count / total) * 100
            bar = "█" * int((count / total) * 20) + "░" * (20 - int((count / total) * 20))
            summary.add_row(version, str(count), f"{pct:.1f}%", bar)
            if idx < len(sorted_runtime) - 1:
                summary.add_section()
        console.print(summary)
        console.print()

    detail = Table(
        title="Python Versions per Repository",
        show_header=True,
        header_style="bold green",
        border_style="blue",
    )
    detail.add_column("Repository", style="cyan")
    detail.add_column("Runtime", style="yellow")
    detail.add_column("Minimum", style="blue")
    detail.add_column("CI", style="magenta")
    detail.add_column("Status")

    def _status(results):
        issues = check_consistency(results[VersionCategory.RUNTIME], results[VersionCategory.MINIMUM])
        if issues:
            return "[red]⚠ inconsistent[/red]"
        if results[VersionCategory.RUNTIME] or results[VersionCategory.MINIMUM]:
            return "[green]✓[/green]"
        return "—"

    def _add_row(name, results, continuation="│"):
        runtime = _fmt(results[VersionCategory.RUNTIME])
        minimum = _fmt(results[VersionCategory.MINIMUM])
        ci = _fmt(results[VersionCategory.CI])
        max_lines = max(col.count("\n") + 1 for col in (runtime, minimum, ci))
        if max_lines > 1:
            name = "\n".join([name] + [f"[dim]{continuation}[/dim]"] * (max_lines - 1))
        detail.add_row(name, runtime, minimum, ci, _status(results))

    first_row = True
    for repo_name, projects in sorted(all_repo_results, key=lambda x: x[0]):
        if not projects:
            continue
        sub_keys = sorted(k for k in projects if k != "")
        root = projects.get("")

        if not sub_keys:
            # Single-project repo
            if root and any(root[cat] for cat in VersionCategory):
                if not first_row:
                    detail.add_section()
                first_row = False
                _add_row(repo_name, root)
        else:
            # Monorepo — show repo name as header with root data (if any).
            # Use "  │" so continuation aligns with the children's "  ├──" at position 2.
            if not first_row:
                detail.add_section()
            first_row = False
            if root and any(root[cat] for cat in VersionCategory):
                _add_row(f"[bold]{repo_name}[/bold]", root, "  │")
            else:
                detail.add_row(f"[bold]{repo_name}[/bold]", "", "", "", "")

            for i, key in enumerate(sub_keys):
                is_last = i == len(sub_keys) - 1
                prefix = "└── " if is_last else "├── "
                # Continuation aligns with "  ├──" (│ at position 2) for non-last,
                # and uses spaces for the last child (└── has no │ below it).
                continuation = "   " if is_last else "  │"
                results = projects[key]
                if any(results[cat] for cat in VersionCategory):
                    _add_row(f"  {prefix}{key}", results, continuation)

    console.print(detail)
    console.print()

    if inconsistencies:
        inc_table = Table(
            title="Inconsistencies",
            show_header=True,
            header_style="bold red",
            border_style="red",
        )
        inc_table.add_column("Repository", style="cyan")
        inc_table.add_column("Issue", style="yellow")
        for repo_name, issues in inconsistencies:
            for issue in issues:
                inc_table.add_row(repo_name, issue)
        console.print(inc_table)
        console.print()

    if no_version_repos:
        no_ver = Table(
            title="Repositories with No Python Version Found",
            show_header=True,
            header_style="bold red",
            border_style="red",
        )
        no_ver.add_column("Repository", style="cyan")
        for repo in sorted(no_version_repos):
            no_ver.add_row(repo)
        console.print(no_ver)
        console.print()


def find_python_version(
    org_name: str = typer.Argument(..., help="GitHub organization name"),
    file_types: list[str] = typer.Option(
        None,
        "--file-types",
        "-f",
        help=(
            "File patterns to search for Python version declarations. Can be repeated. "
            "Supported: Dockerfile, .python-version, pyproject.toml, setup.py, setup.cfg, "
            ".github/workflows/*.yml, .github/workflows/*.yaml, tox.ini. "
            "When omitted, all of the above are scanned."
        ),
    ),
    all_repositories: bool = typer.Option(
        False,
        "--all-repositories",
        "-a",
        help="Scan every repository in the organization. By default only repositories whose primary language is Python are checked.",
    ),
):
    """Analyze Python version usage across repositories of a GitHub organization.

    Versions are classified by semantic meaning:
      - Runtime: the version the project actually runs (.python-version, Dockerfile)
      - Minimum: the minimum supported version (pyproject.toml, setup.py)
      - CI: versions tested in CI (GitHub Actions workflows, tox.ini)

    Repos where the runtime version does not satisfy the declared minimum are flagged as inconsistent.

    Examples:

        Scan all default file patterns in Python repos:
            gh-inspector find-python-version my-org

        Only look in Dockerfiles and pyproject.toml:
            gh-inspector find-python-version my-org -f Dockerfile -f pyproject.toml

        Include non-Python repos in the scan:
            gh-inspector find-python-version my-org --all-repositories
    """
    gh_client = GitHubClient(console=console)
    file_patterns = file_types if file_types else FILE_PATTERNS
    repos = gh_client.get_repos(org_name, all_repositories, extra_fields=["defaultBranchRef"])
    all_repo_results = []
    found_count = 0

    for repo, projects, update in scan_repos(
        repos,
        lambda r: process_repo(gh_client, r, file_patterns)[1],
        "Scanning repos",
        "with versions",
        gh_client,
        console,
    ):
        repo_name = repo["nameWithOwner"]
        all_repo_results.append((repo_name, projects))
        if projects and any(projects[p][cat] for p in projects for cat in VersionCategory):
            found_count += 1
        update(found_count)

    display_results(all_repo_results)
