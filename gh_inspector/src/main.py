"""Main entry point for gh-inspector CLI."""

from importlib.metadata import version

import typer
from cache import cache_app
from commands.find_codeowners import find_codeowners
from commands.find_licenses import find_licenses
from commands.find_python_library import find_python_library
from commands.find_python_version import find_python_version
from output import (
    DEFAULT_CACHE_TTL,
    DEFAULT_TIMEOUT,
    AppContext,
    CacheTtlOption,
    ClearCacheOption,
    NoCacheOption,
    OutputMode,
    OutputOption,
    QuietOption,
    TimeoutOption,
    VerboseOption,
    make_console,
)

__version__ = version("gh-inspector")

# Initialize Typer app
app = typer.Typer(
    name="gh-inspector",
    help="A CLI tool to rapidly locate and inspect files in remote GitHub repositories without cloning.",
)

# Register commands
app.command(name="find-codeowners", no_args_is_help=True)(find_codeowners)
app.command(name="find-licenses", no_args_is_help=True)(find_licenses)
app.command(name="find-python-library", no_args_is_help=True)(find_python_library)
app.command(name="find-python-version", no_args_is_help=True)(find_python_version)
app.add_typer(cache_app, name="cache")


def version_callback(value: bool):
    if value:
        typer.echo(f"gh-inspector {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True, help="Show version and exit."
    ),
    output: OutputOption = OutputMode.RICH,
    no_cache: NoCacheOption = False,
    clear_cache: ClearCacheOption = False,
    cache_ttl: CacheTtlOption = DEFAULT_CACHE_TTL,
    timeout: TimeoutOption = DEFAULT_TIMEOUT,
    verbose: VerboseOption = False,
    quiet: QuietOption = False,
):
    """
    gh-inspector - Inspect GitHub repositories without cloning.

    Run 'gh-inspector COMMAND --help' for more information on a command.
    """
    ctx.obj = AppContext(
        output=output,
        stdout_console=make_console(),
        stderr_console=make_console(stderr=True),
        banner=f"gh-inspector v{__version__}\n",
        no_cache=no_cache,
        clear_cache=clear_cache,
        cache_ttl=cache_ttl,
        timeout=timeout,
        verbose=verbose,
        quiet=quiet,
    )
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


if __name__ == "__main__":
    app()
