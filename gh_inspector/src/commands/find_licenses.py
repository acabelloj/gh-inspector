import json
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import typer
from github_client import GitHubClient
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

console = Console()

MAX_WORKERS = 6


def extract_license_id(repo: dict) -> str | None:
    """Pull license identifier from licenseInfo field, return None if missing/empty.

    gh repo list returns {key, name, nickname}. We use 'spdxId' if present (GraphQL),
    otherwise fall back to 'key'. Returns None when no license is detected.
    """
    license_info = repo.get("licenseInfo") or {}
    license_id = license_info.get("spdxId") or license_info.get("key")
    if not license_id or license_id == "NOASSERTION":
        return None
    return license_id


# --- File-based license parsers ---
# Each parser takes file content (str) and returns a license string or None.

# pyproject.toml: license = "MIT" | license = 'MIT' | license = {text = "MIT"}
_PYPROJECT_LICENSE_RE = re.compile(
    r"""^license\s*=\s*(?:["']([^"']+)["']|\{[^}]*text\s*=\s*["']([^"']+)["'])""",
    re.MULTILINE,
)

# setup.cfg: license = MIT (under [metadata])
_SETUP_CFG_LICENSE_RE = re.compile(r"^\[metadata\](?:\n(?!\[)[^\n]*)*\nlicense\s*=\s*(.+)$", re.MULTILINE)

# Cargo.toml: license = "MIT"
_CARGO_LICENSE_RE = re.compile(r'^license\s*=\s*"([^"]+)"', re.MULTILINE)


def parse_pyproject_toml(content: str) -> str | None:
    match = _PYPROJECT_LICENSE_RE.search(content)
    if match:
        return match.group(1) or match.group(2)
    return None


def parse_setup_cfg(content: str) -> str | None:
    match = _SETUP_CFG_LICENSE_RE.search(content)
    if match:
        return match.group(1).strip()
    return None


def parse_package_json(content: str) -> str | None:
    try:
        data = json.loads(content)
        license_val = data.get("license")
        if isinstance(license_val, str) and license_val:
            return license_val
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def parse_cargo_toml(content: str) -> str | None:
    match = _CARGO_LICENSE_RE.search(content)
    if match:
        return match.group(1)
    return None


def parse_license_file(content: str) -> str | None:
    """Extract the first non-empty line of a LICENSE file as label."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


# Ordered list of (filename, parser). Tried in order; first match wins.
FILE_PARSERS: list[tuple[str, Callable[[str], str | None]]] = [
    ("pyproject.toml", parse_pyproject_toml),
    ("setup.cfg", parse_setup_cfg),
    ("package.json", parse_package_json),
    ("Cargo.toml", parse_cargo_toml),
    ("LICENSE", parse_license_file),
    ("LICENSE.md", parse_license_file),
    ("LICENSE.txt", parse_license_file),
]


def _fetch_file_license(gh_client: GitHubClient, repo_name: str) -> tuple[str, str | None]:
    """Try each file parser in order and return the first license found."""
    for filename, parser in FILE_PARSERS:
        try:
            content = gh_client.get_file_content(repo_name, filename)
            license_id = parser(content)
            if license_id:
                return repo_name, license_id
        except Exception:
            continue
    return repo_name, None


def group_by_license(
    repos: list[dict], exclude: list[str] | None = None, skip_missing: bool = False
) -> tuple[dict[str, list[str]], list[str]]:
    """Group repos by license identifier, applying exclude filter.

    Returns (grouped, unlicensed) where grouped is {license_id: [repo_names]}
    and unlicensed is the list of repo names without a detected license.
    """
    exclude_lower = {e.lower() for e in (exclude or [])}
    grouped: dict[str, list[str]] = {}
    unlicensed: list[str] = []

    for repo in repos:
        name = repo["nameWithOwner"]
        license_id = repo.get("_resolved_license") or extract_license_id(repo)
        if license_id is None:
            if not skip_missing:
                unlicensed.append(name)
            continue
        if license_id.lower() in exclude_lower:
            continue
        grouped.setdefault(license_id, []).append(name)

    return grouped, unlicensed


def display_license_table(grouped: dict[str, list[str]]) -> None:
    """Display a Rich table grouping repos by license type."""
    table = Table(title="Licenses by Repository", show_header=True, header_style="bold magenta")
    table.add_column("License", style="green", no_wrap=True)
    table.add_column("Repository", style="cyan", no_wrap=False)

    sorted_licenses = sorted(grouped)
    for i, license_id in enumerate(sorted_licenses):
        if i > 0:
            table.add_section()
        repos = sorted(grouped[license_id])
        table.add_row(license_id, repos[0])
        for repo in repos[1:]:
            table.add_row("", repo)

    console.print(table)
    console.print()


def display_unlicensed_table(repos: list[str]) -> None:
    """Display a Rich table for repos without a detected license."""
    table = Table(
        title="Repositories without a detected license",
        show_header=True,
        header_style="bold red",
        border_style="red",
    )
    table.add_column("Repository", style="cyan", no_wrap=False)
    for repo in sorted(repos):
        table.add_row(repo)
    console.print(table)
    console.print()


def find_licenses(
    org_name: str = typer.Argument(..., help="GitHub organization name"),
    exclude: list[str] = typer.Option(
        None,
        "--exclude",
        "-e",
        help="Exclude repos with these license keys (e.g. mit, apache-2.0, bsd-3-clause). Case-insensitive. Repeatable.",
    ),
    output_format: str = typer.Option(
        "default",
        "--format",
        "-f",
        help="'default' groups repos by license; 'only_repo' lists repo names with non-excluded licenses.",
    ),
    python_only: bool = typer.Option(
        False,
        "--python-only",
        "-p",
        help="Only scan repos whose primary language is Python. By default all repos are scanned.",
    ),
    skip_missing: bool = typer.Option(
        False,
        "--skip-missing",
        help="Do not list repos without a detected license.",
    ),
):
    """Find and display license usage across repositories of a GitHub organization.

    Examples:

        Show licenses for all repos:
            gh-inspector find-licenses my-org

        Exclude common licenses to surface repos needing attention:
            gh-inspector find-licenses my-org -e mit -e apache-2.0

        List only repo names with non-excluded licenses:
            gh-inspector find-licenses my-org -f only_repo

        Only scan Python repos:
            gh-inspector find-licenses my-org --python-only

        Hide repos without a detected license:
            gh-inspector find-licenses my-org --skip-missing
    """
    gh_client = GitHubClient()
    repos = gh_client.get_repos(org_name, not python_only, extra_fields=["licenseInfo"])

    # For repos where GitHub didn't detect a license or detected "other",
    # try to find it in manifest files (pyproject.toml, setup.cfg, package.json, Cargo.toml).
    needs_fallback = [r for r in repos if extract_license_id(r) in (None, "other")]
    if needs_fallback:
        resolved_count = 0
        in_progress: set[str] = set()
        lock = threading.Lock()

        def _run(repo):
            short = repo["nameWithOwner"].split("/")[-1]
            with lock:
                in_progress.add(short)
            try:
                return _fetch_file_license(gh_client, repo["nameWithOwner"])
            finally:
                with lock:
                    in_progress.discard(short)

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]Checking manifest files[/bold cyan]"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            TextColumn("• [dim]{task.fields[active]} active[/dim]"),
            TextColumn("• [green]✓ {task.fields[found]} resolved[/green]"),
            console=console,
        ) as progress:
            task = progress.add_task("", total=len(needs_fallback), active=0, found=0)
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(_run, r): r for r in needs_fallback}
                for future in as_completed(futures):
                    repo_name, license_id = future.result()
                    if license_id:
                        futures[future]["_resolved_license"] = license_id
                        resolved_count += 1
                    with lock:
                        active = len(in_progress)
                    progress.update(task, advance=1, active=active, found=resolved_count)

    grouped, unlicensed = group_by_license(repos, exclude, skip_missing)

    if output_format == "only_repo":
        all_repo_names = sorted(name for names in grouped.values() for name in names)
        if all_repo_names:
            table = Table(title="Repositories with licenses", show_header=True, header_style="bold magenta")
            table.add_column("Repository", style="cyan", no_wrap=False)
            for repo in all_repo_names:
                table.add_row(repo)
            console.print(table)
            console.print()
        else:
            console.print("[yellow]No repositories with non-excluded licenses found.[/yellow]\n")
    else:
        if grouped:
            display_license_table(grouped)
        else:
            console.print("[yellow]No repositories with non-excluded licenses found.[/yellow]\n")

    if unlicensed:
        display_unlicensed_table(unlicensed)
