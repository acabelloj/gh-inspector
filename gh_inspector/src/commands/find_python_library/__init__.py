import fnmatch
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import typer
from github_client import GitHubClient
from packaging.version import parse as parse_version
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

from .parsers import PARSERS, matches_pattern

console = Console()

MAX_WORKERS = 6
FILE_WORKERS = 3


def get_matching_files(gh_client, repo_name, file_types, branch=None):
    tree = gh_client.get_repo_tree(repo_name, branch)
    results = []
    for entry in tree:
        path = entry["path"]
        filename = path.split("/")[-1]
        if file_types and not any(fnmatch.fnmatch(filename, ft) for ft in file_types):
            continue
        for parser in PARSERS:
            if any(matches_pattern(path, pattern) for pattern in parser.FILE_PATTERNS):
                results.append((path, parser))
                break
    return results


def process_file(gh_client, repo_name, file_path, parser, libraries):
    results = defaultdict(list)
    try:
        content = gh_client.get_file_content(repo_name, file_path)
        for lib_name, version in parser.extract(content, libraries).items():
            results[f"{lib_name}$v{version}"].append(f"{repo_name} ({file_path})")
    except Exception as e:
        print(f"Error processing {file_path} in {repo_name}: {e}")
    return results


def process_repo(gh_client, repo, libraries, file_types):
    repo_name = repo["nameWithOwner"]
    branch = (repo.get("defaultBranchRef") or {}).get("name") or None
    all_results = defaultdict(list)
    try:
        matching = get_matching_files(gh_client, repo_name, file_types, branch)
        with ThreadPoolExecutor(max_workers=FILE_WORKERS) as file_executor:
            futures = {
                file_executor.submit(process_file, gh_client, repo_name, fp, parser, libraries): fp
                for fp, parser in matching
            }
            for future in as_completed(futures):
                for key, values in future.result().items():
                    all_results[key].extend(values)
    except Exception as e:
        print(f"Error processing {repo_name}: {e}")
    return all_results


def print_results(library_versions, libraries, output_format):
    """Print results in the specified format using Rich tables."""
    if output_format == "only_repo":
        repos = {repo_file.split()[0] for _, files in library_versions for repo_file in files}

        table = Table(title="Repositories", show_header=True, header_style="bold magenta")
        table.add_column("Repository", style="cyan", no_wrap=False)

        for repo in sorted(repos):
            table.add_row(repo)

        console.print(table)
    else:
        library_data = defaultdict(lambda: defaultdict(list))
        for lib_version, repo_files in library_versions:
            lib_name, version = lib_version.split("$v")
            library_data[lib_name][version].extend(repo_files)

        console.print(f"\n[bold cyan]Version Usage for libraries:[/bold cyan] {', '.join(libraries)}\n")

        for lib_name in sorted(library_data.keys()):
            table = Table(
                title=f"Library: {lib_name}", show_header=True, header_style="bold green", border_style="blue"
            )
            table.add_column("Version", style="yellow", no_wrap=True, width=15)
            table.add_column("Count", justify="center", style="magenta", width=8)
            table.add_column("Repositories (Files)", style="cyan", no_wrap=False)

            sorted_versions = sorted(library_data[lib_name].keys(), key=parse_version, reverse=True)
            for idx, version in enumerate(sorted_versions):
                repo_files = library_data[lib_name][version]
                count = len(repo_files)
                repos_display = "\n".join(repo_files)
                table.add_row(version, str(count), repos_display)
                if idx < len(sorted_versions) - 1:
                    table.add_section()

            console.print(table)
            console.print()


def find_python_library(
    org_name: str = typer.Argument(..., help="GitHub organization name"),
    libraries: list[str] = typer.Argument(..., help="List of libraries to analyze"),
    output_format: str = typer.Option(
        "default",
        "--format",
        "-f",
        help="'default' shows a version-by-version breakdown per library; 'only_repo' lists just the repository names that use any of the specified libraries.",
    ),
    file_types: list[str] = typer.Option(
        None,
        "--file-types",
        "-t",
        help="Glob patterns for dependency filenames to scan. Can be repeated. Supported file types: requirements*.txt, requirements*.in, uv.lock, poetry.lock, Pipfile.lock, setup.cfg. When omitted, all of the above are scanned.",
    ),
    all_repositories: bool = typer.Option(
        False,
        "--all-repositories",
        "-a",
        help="Scan every repository in the organization. By default only repositories whose primary language is Python are checked.",
    ),
):
    """Analyze library usage across repositories of a GitHub organization.

    Examples:

        Search for a single library in Python repos:
            gh-inspector find-python-library my-org requests

        Search for multiple libraries at once:
            gh-inspector find-python-library my-org requests boto3 django

        List only repository names (no version breakdown):
            gh-inspector find-python-library my-org requests -f only_repo

        Scan only uv.lock files:
            gh-inspector find-python-library my-org requests -t uv.lock

        Scan only requirements files and poetry lock:
            gh-inspector find-python-library my-org requests -t 'requirements*.txt' -t poetry.lock

        Include non-Python repos in the scan:
            gh-inspector find-python-library my-org requests --all-repositories
    """
    gh_client = GitHubClient()

    repos = gh_client.get_repos(org_name, all_repositories, extra_fields=["defaultBranchRef"])
    library_versions = defaultdict(list)
    found_repos: set[str] = set()
    in_progress: set[str] = set()
    lock = threading.Lock()

    def _run(repo):
        short = repo["nameWithOwner"].split("/")[-1]
        with lock:
            in_progress.add(short)
        try:
            return repo["nameWithOwner"], process_repo(gh_client, repo, libraries, file_types)
        finally:
            with lock:
                in_progress.discard(short)

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Scanning repos[/bold cyan]"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        TextColumn("• [dim]{task.fields[active]} active[/dim]"),
        TextColumn("• [green]✓ {task.fields[found]} with matches[/green]"),
        console=console,
    ) as progress:
        task = progress.add_task("", total=len(repos), active=0, found=0)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(_run, repo): repo for repo in repos}
            for future in as_completed(futures):
                repo_name, result = future.result()
                for version, repo_files in result.items():
                    library_versions[version].extend(repo_files)
                if result:
                    found_repos.add(repo_name)
                with lock:
                    active = len(in_progress)
                progress.update(task, advance=1, active=active, found=len(found_repos))

    print_results(library_versions.items(), libraries, output_format)
