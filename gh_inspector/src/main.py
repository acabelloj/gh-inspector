"""Main entry point for gh-inspector CLI."""

from importlib.metadata import version

import typer
from commands.find_python_library import find_python_library
from commands.find_python_version import find_python_version

__version__ = version("gh-inspector")

# Initialize Typer app
app = typer.Typer(
    name="gh-inspector",
    help="A CLI tool to rapidly locate and inspect files in remote GitHub repositories without cloning.",
)

# Register commands
app.command(name="find-python-library")(find_python_library)
app.command(name="find-python-version")(find_python_version)


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
):
    """
    gh-inspector - Inspect GitHub repositories without cloning.

    Run 'gh-inspector COMMAND --help' for more information on a command.
    """
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()
    typer.echo(f"gh-inspector v{__version__}\n")


if __name__ == "__main__":
    app()
