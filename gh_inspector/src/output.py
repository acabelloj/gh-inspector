"""Shared output-mode machinery reused by every command.

A single global ``--output`` option selects the encoding (Rich or JSON). Commands
build plain, JSON-serializable data and hand it to :func:`emit`, which either dumps
JSON to stdout or delegates to the command's Rich renderer.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any, NoReturn

import orjson
import typer
from rich.console import Console

if TYPE_CHECKING:
    from cache import ResponseCache


def make_console(*, stderr: bool = False) -> Console:
    """Build a Console, rendering plain (no colour/animation) when ``NO_COLOR`` is set.

    ``NO_COLOR`` alone only drops colour; forcing ``force_terminal=False`` additionally
    disables styles (bold/italic) and the live progress spinner, so snapshot tests
    capture stable plain text. In normal use both default to Rich's auto-detection.
    """
    if os.environ.get("NO_COLOR"):
        return Console(stderr=stderr, no_color=True, force_terminal=False)
    return Console(stderr=stderr)


class OutputMode(str, Enum):
    """How command results are encoded on stdout."""

    RICH = "rich"
    JSON = "json"


# Single definition of the --output option, shared by the root callback and every
# command so the flag is accepted both before and after the subcommand.
OutputOption = Annotated[
    OutputMode,
    typer.Option(
        "--output",
        "-o",
        help="Output encoding: 'rich' (default) for decorated tables; 'json' for machine-readable output.",
    ),
]

# The remaining globals follow the same dual-declaration pattern. Each carries an
# ``envvar`` so precedence is CLI flag > environment variable > built-in default,
# resolved uniformly via ``ctx.get_parameter_source`` in :func:`resolve_globals`.
NoCacheOption = Annotated[
    bool,
    typer.Option(
        "--no-cache",
        envvar="GH_INSPECTOR_NO_CACHE",
        help="Bypass the on-disk cache: fetch fresh data and leave existing cache entries untouched.",
    ),
]

ClearCacheOption = Annotated[
    bool,
    typer.Option(
        "--clear-cache",
        envvar="GH_INSPECTOR_CLEAR_CACHE",
        help="Delete all cached entries before running, then repopulate the cache from this run.",
    ),
]

CacheTtlOption = Annotated[
    int,
    typer.Option(
        "--cache-ttl",
        envvar="GH_INSPECTOR_CACHE_TTL",
        help="How long (seconds) cached responses stay fresh. Default 3600 (1 hour).",
    ),
]

TimeoutOption = Annotated[
    int,
    typer.Option(
        "--timeout",
        envvar="GH_INSPECTOR_TIMEOUT",
        help="Per-request timeout (seconds) for gh calls. Default 30.",
    ),
]

VerboseOption = Annotated[
    bool,
    typer.Option(
        "--verbose",
        envvar="GH_INSPECTOR_VERBOSE",
        help="Log each gh command and cache hit/miss.",
    ),
]

QuietOption = Annotated[
    bool,
    typer.Option(
        "--quiet",
        "-q",
        envvar="GH_INSPECTOR_QUIET",
        help="Suppress the progress bar, totals, and rate-limit logs. Errors still print.",
    ),
]

DEFAULT_CACHE_TTL = 3600
DEFAULT_TIMEOUT = 30


@dataclass
class AppContext:
    """Cross-command state stored on ``ctx.obj`` by the root callback.

    ``stdout_console`` renders Rich output; ``stderr_console`` carries progress
    and logs so that stdout stays pure JSON in ``json`` mode.
    """

    output: OutputMode
    stdout_console: Console
    stderr_console: Console
    banner: str = ""
    no_cache: bool = False
    clear_cache: bool = False
    cache_ttl: int = DEFAULT_CACHE_TTL
    timeout: int = DEFAULT_TIMEOUT
    verbose: bool = False
    quiet: bool = False

    @property
    def is_json(self) -> bool:
        return self.output is OutputMode.JSON

    @property
    def scan_console(self) -> Console:
        """Console for progress bars and scan logs.

        Routed to stderr in json mode to keep stdout parseable; unchanged (stdout)
        in rich mode so existing behaviour is preserved.
        """
        return self.stderr_console if self.is_json else self.stdout_console

    def cache(self) -> "ResponseCache":
        """Build a :class:`ResponseCache` honouring the resolved cache settings.

        With ``--clear-cache``, wipe existing entries once before returning so this run
        repopulates them. ``--no-cache`` wins over ``--clear-cache``: it means "leave
        the stored cache untouched", so the destructive clear is skipped when combined.
        """
        from cache import ResponseCache  # noqa: PLC0415 — avoid an import cycle at module load

        cache = ResponseCache(enabled=not self.no_cache, ttl=self.cache_ttl)
        if self.clear_cache and not self.no_cache:
            removed = cache.clear()
            if not self.quiet:
                self.scan_console.log(f"[dim]🗑 Cleared {removed} cached entries[/dim]")
        return cache


def get_ctx(ctx: typer.Context) -> AppContext:
    """Return the :class:`AppContext` attached to the Typer context."""
    return ctx.obj


def resolve_output(ctx: typer.Context, output: OutputMode) -> None:
    """Settle the effective output mode for a command.

    ``--output`` is declared on both the root callback and each command, so it may
    appear before or after the subcommand. The command-level value wins only when
    the user actually passed it; otherwise the root value (already on ``ctx.obj``)
    stands. The resolved mode is written back so :func:`emit` and
    ``AppContext.scan_console`` observe it.

    Every command calls this once at entry, before any output. In rich mode it
    also prints the app banner, deferred to here so it honours a ``-o json`` placed
    after the subcommand (which the root callback cannot see).
    """
    app_ctx = get_ctx(ctx)
    if _passed_on_commandline(ctx, "output"):
        app_ctx.output = output
    if not app_ctx.is_json and app_ctx.banner:
        app_ctx.stdout_console.print(app_ctx.banner, highlight=False)


def _passed_on_commandline(ctx: typer.Context, param: str) -> bool:
    """True when ``param`` was set by a flag after the subcommand.

    Compare by name, not enum identity: Typer vendors its own click fork whose
    ParameterSource enum is distinct from the installed click package's.
    """
    source = ctx.get_parameter_source(param)
    return source is not None and source.name == "COMMANDLINE"


def resolve_globals(
    ctx: typer.Context,
    output: OutputMode,
    no_cache: bool,
    clear_cache: bool,
    cache_ttl: int,
    timeout: int,
    verbose: bool,
    quiet: bool,
) -> None:
    """Settle every global option for a command, honouring flags placed after the subcommand.

    Each global is declared on both the root callback and the command. The root
    callback's values already sit on ``ctx.obj``; a command-level value overrides
    only when the user actually typed the flag (``COMMANDLINE``). This defers to
    :func:`resolve_output` for the ``--output`` mode and banner handling.
    """
    app_ctx = get_ctx(ctx)
    if _passed_on_commandline(ctx, "no_cache"):
        app_ctx.no_cache = no_cache
    if _passed_on_commandline(ctx, "clear_cache"):
        app_ctx.clear_cache = clear_cache
    if _passed_on_commandline(ctx, "cache_ttl"):
        app_ctx.cache_ttl = cache_ttl
    if _passed_on_commandline(ctx, "timeout"):
        app_ctx.timeout = timeout
    if _passed_on_commandline(ctx, "verbose"):
        app_ctx.verbose = verbose
    if _passed_on_commandline(ctx, "quiet"):
        app_ctx.quiet = quiet
    resolve_output(ctx, output)


def build_summary(
    org_name: str,
    all_repositories: bool,
    repos_scanned: int,
    repos_matched: int,
    gh_client,
    **extra: Any,
) -> dict[str, Any]:
    """Assemble the machine-readable run summary embedded in json output.

    Records what was actually explored — repos scanned/matched, gh API calls, and
    which repos failed — so a consumer without the live progress bar can tell a
    complete empty result from a scan that died partway. ``extra`` carries
    command-specific context (e.g. the libraries requested).
    """
    errored_repos = sorted({e["repo"] for e in gh_client.errors})
    return {
        "org": org_name,
        "all_repositories": all_repositories,
        "repos_scanned": repos_scanned,
        "repos_with_matches": repos_matched,
        "repos_errored": len(errored_repos),
        "errored_repos": errored_repos,
        "gh_api_calls": gh_client.call_count,
        **extra,
    }


def emit_error(ctx: typer.Context, message: str, **fields: Any) -> NoReturn:
    """Report a fatal error, then raise ``typer.Exit(1)``.

    In json mode an ``{"error": ...}`` object is written to stdout so a consumer can
    tell a fatal failure from a clean empty result; in rich mode it prints to the scan
    console. ``fields`` adds context (e.g. ``org=...``).
    """
    app_ctx = get_ctx(ctx)
    if app_ctx.is_json:
        print(orjson.dumps({"error": message, **fields}, option=orjson.OPT_INDENT_2).decode())
    else:
        app_ctx.scan_console.print(f"[red]{message}[/red]")
    raise typer.Exit(code=1)


def emit(
    ctx: typer.Context,
    data: Any,
    render_rich: Callable[[], None],
    summary: dict[str, Any] | None = None,
) -> None:
    """Encode ``data`` according to the selected output mode.

    In json mode, ``data`` is dumped to stdout with no Rich decoration and
    ``render_rich`` is ignored; a ``summary`` (if given) is merged in under a
    ``summary`` key so callers know what was explored. In rich mode, ``render_rich``
    is invoked and the summary is ignored (the live progress bar already shows it).
    """
    if get_ctx(ctx).is_json:
        payload = {"summary": summary, **data} if summary is not None else data
        print(orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode())
    else:
        render_rich()
