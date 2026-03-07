import threading
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

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

MAX_WORKERS = 6


def scan_repos(
    repos: list[dict],
    fn: Callable[[dict], Any],
    label: str,
    found_label: str,
    gh_client: GitHubClient,
    console: Console,
    max_workers: int = MAX_WORKERS,
) -> Generator[tuple[dict, Any, Callable[[int], None]], None, None]:
    """Run fn(repo) concurrently, yielding (repo, result, update_fn) for each completed repo.

    update_fn(found_count) must be called exactly once per yielded item to advance
    the progress bar. After all repos are processed, prints the total gh API call count.
    """
    in_progress: set[str] = set()
    lock = threading.Lock()

    def _run(repo: dict) -> Any:
        short = repo["nameWithOwner"].split("/")[-1]
        with lock:
            in_progress.add(short)
        try:
            return fn(repo)
        finally:
            with lock:
                in_progress.discard(short)

    with Progress(
        SpinnerColumn(),
        TextColumn(f"[bold cyan]{label}[/bold cyan]"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        TextColumn("• [dim]{task.fields[active]} active[/dim]"),
        TextColumn(f"• [green]✓ {{task.fields[found]}} {found_label}[/green]"),
        TextColumn("• [dim]{task.fields[calls]} gh calls[/dim]"),
        console=console,
    ) as progress:
        task = progress.add_task("", total=len(repos), active=0, found=0, calls=0)

        # Heartbeat: refresh call count and active count while threads are sleeping
        # (e.g. during rate-limit waits), not just when futures complete.
        _stop = threading.Event()

        def _heartbeat() -> None:
            while not _stop.wait(timeout=0.5):
                with lock:
                    active = len(in_progress)
                progress.update(task, active=active, calls=gh_client.call_count)

        hb = threading.Thread(target=_heartbeat, daemon=True)
        hb.start()
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_run, repo): repo for repo in repos}
                for future in as_completed(futures):
                    repo = futures[future]
                    result = future.result()
                    with lock:
                        active = len(in_progress)

                    def make_update(p: Progress, t: Any, a: int) -> Callable[[int], None]:
                        def update(found_count: int) -> None:
                            p.update(t, advance=1, active=a, found=found_count, calls=gh_client.call_count)

                        return update

                    yield repo, result, make_update(progress, task, active)
        finally:
            _stop.set()
            hb.join()

    console.print(f"[dim]Total GitHub API calls: {gh_client.call_count}[/dim]\n")
