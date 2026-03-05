from importlib.metadata import version

from main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"gh-inspector {version('gh-inspector')}" in result.output


def test_version_short_flag():
    result = runner.invoke(app, ["-v"])
    assert result.exit_code == 0
    assert f"gh-inspector {version('gh-inspector')}" in result.output
