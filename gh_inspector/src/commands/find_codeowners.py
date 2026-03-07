import threading
from collections import defaultdict
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
from rich.tree import Tree

console = Console()

MAX_WORKERS = 6

CODEOWNERS_PATHS = [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"]


def _is_owner(token: str) -> bool:
    """Check if a token is a valid CODEOWNERS owner (@team, @user, or email)."""
    return token.startswith("@") or ("@" in token and "." in token.split("@")[-1])


def parse_codeowners(content: str) -> list[tuple[str, list[str]]]:
    """Parse CODEOWNERS content into a list of (pattern, [owners])."""
    entries = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("["):
            continue
        tokens = stripped.split()
        pattern = tokens[0]
        owners = [t for t in tokens[1:] if _is_owner(t)]
        if owners:
            entries.append((pattern, owners))
    return entries


def find_codeowners_file(gh_client: GitHubClient, repo_name: str, branch: str | None = None) -> str | None:
    """Return the path of the first CODEOWNERS file found, or None."""
    try:
        tree = gh_client.get_repo_tree(repo_name, branch)
    except Exception:
        return None
    paths = {entry["path"] for entry in tree}
    for candidate in CODEOWNERS_PATHS:
        if candidate in paths:
            return candidate
    return None


def process_repo(gh_client: GitHubClient, repo: dict) -> tuple[str, list[tuple[str, list[str]]]] | None:
    """Return (repo_name, parsed_entries) or None if no CODEOWNERS found."""
    repo_name = repo["nameWithOwner"]
    branch = (repo.get("defaultBranchRef") or {}).get("name") or None
    try:
        codeowners_path = find_codeowners_file(gh_client, repo_name, branch)
        if codeowners_path is None:
            return None
        content = gh_client.get_file_content(repo_name, codeowners_path)
        entries = parse_codeowners(content)
        return (repo_name, entries)
    except Exception as e:
        print(f"Error processing {repo_name}: {e}")
        return None


def aggregate_by_owner(
    results: list[tuple[str, list[tuple[str, list[str]]]]],
) -> dict[str, list[tuple[str, list[str]]]]:
    """Invert per-repo entries to per-owner: {owner: [(repo, [patterns])]}."""
    owner_map: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for repo_name, entries in results:
        for pattern, owners in entries:
            for owner in owners:
                owner_map[owner][repo_name].append(pattern)
    return {owner: sorted(repos.items()) for owner, repos in sorted(owner_map.items())}


MAX_PATTERNS_SHOWN = 5


def _format_patterns(patterns: list[str]) -> str:
    if len(patterns) <= MAX_PATTERNS_SHOWN:
        return ", ".join(patterns)
    shown = ", ".join(patterns[:MAX_PATTERNS_SHOWN])
    return f"{shown} + {len(patterns) - MAX_PATTERNS_SHOWN} more"


def display_tree(owner_data: dict[str, list[tuple[str, list[str]]]]) -> None:
    tree = Tree("[bold cyan]CODEOWNERS by Owner[/bold cyan]")
    for owner, repos in owner_data.items():
        branch = tree.add(f"[bold green]{owner}[/bold green]")
        for repo, patterns in repos:
            if patterns == ["*"]:
                branch.add(f"{repo} [dim](entire repo)[/dim]")
            else:
                branch.add(f"{repo} ({_format_patterns(patterns)})")
    console.print(tree)
    console.print()


def display_repo_table(repo_names: list[str]) -> None:
    table = Table(title="Repositories with CODEOWNERS", show_header=True, header_style="bold magenta")
    table.add_column("Repository", style="cyan", no_wrap=False)
    for repo in sorted(repo_names):
        table.add_row(repo)
    console.print(table)
    console.print()


def display_missing_table(missing: list[str]) -> None:
    table = Table(
        title="Repositories without CODEOWNERS",
        show_header=True,
        header_style="bold red",
        border_style="red",
    )
    table.add_column("Repository", style="cyan", no_wrap=False)
    for repo in sorted(missing):
        table.add_row(repo)
    console.print(table)
    console.print()


def find_codeowners(
    org_name: str = typer.Argument(..., help="GitHub organization name"),
    output_format: str = typer.Option(
        "default",
        "--format",
        "-f",
        help="'default' shows a tree grouped by owner; 'only_repo' lists repository names that have CODEOWNERS.",
    ),
    teams: list[str] = typer.Option(
        None,
        "--team",
        "-t",
        help="Filter results to specific owner(s). Can be repeated (e.g. -t @org/backend -t @user). When omitted, all owners are shown.",
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
        help="Do not list repos that lack a CODEOWNERS file.",
    ),
):
    """Find and display CODEOWNERS across repositories of a GitHub organization.

    Examples:

        Show CODEOWNERS tree for all repos:
            gh-inspector find-codeowners my-org

        Filter to a specific team:
            gh-inspector find-codeowners my-org -t @my-org/backend

        Filter to multiple teams:
            gh-inspector find-codeowners my-org -t @my-org/backend -t @my-org/frontend

        List only repo names that have CODEOWNERS:
            gh-inspector find-codeowners my-org -f only_repo

        Only scan Python repos:
            gh-inspector find-codeowners my-org --python-only

        Hide repos without CODEOWNERS:
            gh-inspector find-codeowners my-org --skip-missing
    """
    gh_client = GitHubClient()
    repos = gh_client.get_repos(org_name, not python_only, extra_fields=["defaultBranchRef"])

    found: list[tuple[str, list[tuple[str, list[str]]]]] = []
    missing: list[str] = []
    in_progress: set[str] = set()
    lock = threading.Lock()

    def _run(repo):
        short = repo["nameWithOwner"].split("/")[-1]
        with lock:
            in_progress.add(short)
        try:
            return process_repo(gh_client, repo)
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
        TextColumn("• [green]✓ {task.fields[found]} with CODEOWNERS[/green]"),
        console=console,
    ) as progress:
        task = progress.add_task("", total=len(repos), active=0, found=0)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(_run, repo): repo for repo in repos}
            for future in as_completed(futures):
                result = future.result()
                if result is None:
                    missing.append(futures[future]["nameWithOwner"])
                else:
                    found.append(result)
                with lock:
                    active = len(in_progress)
                progress.update(task, advance=1, active=active, found=len(found))

    if output_format == "only_repo":
        display_repo_table([repo for repo, _ in found])
    else:
        owner_data = aggregate_by_owner(found)
        if teams:
            owner_data = {k: v for k, v in owner_data.items() if k in teams}
        if owner_data:
            display_tree(owner_data)
        else:
            console.print("[yellow]No CODEOWNERS entries found.[/yellow]\n")

    if not skip_missing and missing:
        display_missing_table(missing)
