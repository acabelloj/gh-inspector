"""File-backed response cache for ``gh`` CLI results, plus its ``cache`` CLI group.

Each cached entry is one JSON file under a platform cache directory, keyed by a
SHA-256 of the exact ``gh`` argument list. Entries carry the epoch timestamp at
which they were written; a TTL comparison against that stored timestamp (not the
file mtime) decides freshness. This lets the tool be re-run in quick succession
without re-downloading unchanged data, while a ``--no-cache`` run reads fresh and
leaves existing entries untouched.

The ``cache_app`` Typer group at the bottom exposes ``gh-inspector cache
clear|path|info`` for managing this cache directly (no repository scan). Importing
``output`` at module level is safe: ``output`` only imports :class:`ResponseCache`
lazily (inside a method), so there is no load-time cycle.
"""

import hashlib
import json
import os
import time
from pathlib import Path

import typer
from output import (
    DEFAULT_CACHE_TTL,
    DEFAULT_TIMEOUT,
    CacheTtlOption,
    ClearCacheOption,
    NoCacheOption,
    OutputMode,
    OutputOption,
    QuietOption,
    TimeoutOption,
    VerboseOption,
    emit,
    get_ctx,
    resolve_globals,
)


def _cache_dir() -> Path:
    """Return the cache directory, honouring ``XDG_CACHE_HOME``."""
    base = os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")
    return Path(base) / "gh-inspector"


class ResponseCache:
    """Persist successful ``gh`` command output as per-request JSON files.

    When ``enabled`` is ``False`` every :meth:`get` misses and :meth:`set` is a
    no-op, so a disabled cache neither reads nor refreshes stored entries.
    """

    def __init__(self, enabled: bool = True, ttl: int = 3600):
        self.enabled = enabled
        self.ttl = ttl
        self._dir = _cache_dir()

    @property
    def path(self) -> Path:
        """The directory holding the cache entries (may not exist yet)."""
        return self._dir

    def _path(self, args: list[str]) -> Path:
        digest = hashlib.sha256("\x00".join(args).encode()).hexdigest()
        return self._dir / f"{digest}.json"

    def get(self, args: list[str]) -> str | None:
        """Return the cached body for ``args`` if present and unexpired, else ``None``."""
        if not self.enabled:
            return None
        path = self._path(args)
        try:
            entry = json.loads(path.read_text())
            ts, data = entry["ts"], entry["data"]
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError):
            # Unreadable, non-JSON, or wrong-shape (missing/renamed keys) — drop and miss.
            path.unlink(missing_ok=True)
            return None
        if time.time() - ts > self.ttl:
            return None
        return data

    def set(self, args: list[str], data: str) -> None:
        """Write ``data`` for ``args`` atomically. No-op when the cache is disabled."""
        if not self.enabled:
            return
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(args)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"args": args, "ts": time.time(), "data": data}))
        os.replace(tmp, path)

    def clear(self) -> int:
        """Delete all cached entries. Returns the number of entries removed."""
        removed = 0
        for path in self._dir.glob("*.json"):
            path.unlink(missing_ok=True)
            removed += 1
        return removed

    def info(self) -> tuple[int, int]:
        """Return ``(entry_count, total_bytes)`` for the cached entries.

        A missing cache directory yields ``(0, 0)``.
        """
        count = 0
        total = 0
        for path in self._dir.glob("*.json"):
            try:
                total += path.stat().st_size
                count += 1
            except OSError:
                continue
        return count, total


cache_app = typer.Typer(
    name="cache",
    help="Inspect and manage the on-disk response cache.",
    no_args_is_help=True,
)


def _human_size(num_bytes: int) -> str:
    """Format a byte count as a short human-readable string (e.g. '61.0 MB')."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


@cache_app.command("clear")
def _clear(
    ctx: typer.Context,
    output: OutputOption = OutputMode.RICH,
    no_cache: NoCacheOption = False,
    clear_cache: ClearCacheOption = False,
    cache_ttl: CacheTtlOption = DEFAULT_CACHE_TTL,
    timeout: TimeoutOption = DEFAULT_TIMEOUT,
    verbose: VerboseOption = False,
    quiet: QuietOption = False,
):
    """Delete every cached entry."""
    resolve_globals(ctx, output, no_cache, clear_cache, cache_ttl, timeout, verbose, quiet)
    removed = ResponseCache().clear()
    stdout = get_ctx(ctx).stdout_console
    emit(
        ctx,
        {"cleared": removed},
        lambda: stdout.print(f"[green]Cleared {removed} cached entries[/green]", highlight=False),
    )


@cache_app.command("path")
def _path(
    ctx: typer.Context,
    output: OutputOption = OutputMode.RICH,
    no_cache: NoCacheOption = False,
    clear_cache: ClearCacheOption = False,
    cache_ttl: CacheTtlOption = DEFAULT_CACHE_TTL,
    timeout: TimeoutOption = DEFAULT_TIMEOUT,
    verbose: VerboseOption = False,
    quiet: QuietOption = False,
):
    """Print the cache directory."""
    resolve_globals(ctx, output, no_cache, clear_cache, cache_ttl, timeout, verbose, quiet)
    cache_path = str(ResponseCache().path)
    stdout = get_ctx(ctx).stdout_console
    emit(ctx, {"path": cache_path}, lambda: stdout.print(cache_path, highlight=False, soft_wrap=True))


@cache_app.command("info")
def _info(
    ctx: typer.Context,
    output: OutputOption = OutputMode.RICH,
    no_cache: NoCacheOption = False,
    clear_cache: ClearCacheOption = False,
    cache_ttl: CacheTtlOption = DEFAULT_CACHE_TTL,
    timeout: TimeoutOption = DEFAULT_TIMEOUT,
    verbose: VerboseOption = False,
    quiet: QuietOption = False,
):
    """Show the cache directory, entry count, and total size."""
    resolve_globals(ctx, output, no_cache, clear_cache, cache_ttl, timeout, verbose, quiet)
    cache = ResponseCache()
    count, size = cache.info()
    stdout = get_ctx(ctx).stdout_console

    def render() -> None:
        stdout.print(f"[bold]Path:[/bold]    {cache.path}", highlight=False, soft_wrap=True)
        stdout.print(f"[bold]Entries:[/bold] {count}", highlight=False)
        stdout.print(f"[bold]Size:[/bold]    {_human_size(size)}", highlight=False)

    emit(ctx, {"path": str(cache.path), "entries": count, "bytes": size}, render)
