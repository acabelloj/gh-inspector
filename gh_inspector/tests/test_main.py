import json
from importlib.metadata import version

from main import app
from typer.testing import CliRunner

runner = CliRunner()

VERSION = version("gh-inspector")

MIT_REPOS = [{"nameWithOwner": "org/a", "isPrivate": False, "licenseInfo": {"spdxId": "MIT"}}]


def _stub_client(repos):
    """Build a GitHubClient replacement whose get_repos returns fixed data."""

    class _StubClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_repos(self, *args, **kwargs):
            return repos

        @property
        def call_count(self):
            return 0

    return _StubClient


class TestVersion:
    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert f"gh-inspector {VERSION}" in result.output

    def test_version_short_flag(self):
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert f"gh-inspector {VERSION}" in result.output

    def test_banner_shown_on_command(self, monkeypatch):
        monkeypatch.setattr("commands.find_python_version.GitHubClient", lambda: None)
        result = runner.invoke(app, ["find-python-version", "someorg"])
        assert f"gh-inspector v{VERSION}" in result.output


class TestOutputMode:
    def test_banner_suppressed_in_json_mode(self, monkeypatch):
        monkeypatch.setattr("commands.find_licenses.GitHubClient", _stub_client([]))
        result = runner.invoke(app, ["-o", "json", "find-licenses", "someorg"])
        assert result.exit_code == 0
        assert "gh-inspector v" not in result.stdout

    def test_json_output_is_pure_json(self, monkeypatch):
        monkeypatch.setattr("commands.find_licenses.GitHubClient", _stub_client(MIT_REPOS))
        result = runner.invoke(app, ["-o", "json", "find-licenses", "someorg"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["licenses"] == {"MIT": ["org/a"]}
        # no ANSI escape codes leaked onto stdout
        assert "\x1b[" not in result.stdout

    def test_output_flag_accepted_after_subcommand(self, monkeypatch):
        """--output works both before and after the subcommand."""
        monkeypatch.setattr("commands.find_licenses.GitHubClient", _stub_client(MIT_REPOS))
        before = runner.invoke(app, ["-o", "json", "find-licenses", "someorg"])
        after = runner.invoke(app, ["find-licenses", "someorg", "-o", "json"])
        assert before.exit_code == after.exit_code == 0
        assert json.loads(after.stdout) == json.loads(before.stdout)
        assert "gh-inspector v" not in after.stdout
