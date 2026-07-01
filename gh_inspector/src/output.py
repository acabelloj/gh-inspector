"""Shared output-mode machinery reused by every command.

A single global ``--output`` option selects the encoding (Rich or JSON). Commands
build plain, JSON-serializable data and hand it to :func:`emit`, which either dumps
JSON to stdout or delegates to the command's Rich renderer.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any

import orjson
import typer
from rich.console import Console


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
    # Compare by name, not enum identity: Typer vendors its own click fork whose
    # ParameterSource enum is distinct from the installed click package's.
    source = ctx.get_parameter_source("output")
    if source is not None and source.name == "COMMANDLINE":
        app_ctx.output = output
    if not app_ctx.is_json and app_ctx.banner:
        app_ctx.stdout_console.print(app_ctx.banner, highlight=False)


def emit(ctx: typer.Context, data: Any, render_rich: Callable[[], None]) -> None:
    """Encode ``data`` according to the selected output mode.

    In json mode, ``data`` is dumped to stdout with no Rich decoration and
    ``render_rich`` is ignored. In rich mode, ``render_rich`` is invoked.
    """
    if get_ctx(ctx).is_json:
        print(orjson.dumps(data, option=orjson.OPT_INDENT_2).decode())
    else:
        render_rich()
