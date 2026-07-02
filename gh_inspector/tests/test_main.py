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
            self.errors = []

        def get_repos(self, *args, **kwargs):
            return repos

        def record_error(self, repo, message):
            self.errors.append({"repo": repo, "error": message})

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
        monkeypatch.setattr("commands.find_python_version.GitHubClient", _stub_client([]))
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


class TestGlobalFlags:
    def _capturing_client(self, captured, repos):
        """Stub whose constructor records the kwargs the command passed."""

        class _Client:
            def __init__(self, *args, **kwargs):
                captured.update(kwargs)
                self.errors = []

            def get_repos(self, *args, **kwargs):
                return repos

            def record_error(self, repo, message):
                self.errors.append({"repo": repo, "error": message})

            @property
            def call_count(self):
                return 0

        return _Client

    def test_global_flags_accepted_before_and_after_subcommand(self, monkeypatch):
        flags = ["--no-cache", "--cache-ttl", "60", "--timeout", "90", "--verbose"]
        for args in (
            [*flags, "find-licenses", "org"],
            ["find-licenses", "org", *flags],
        ):
            captured = {}
            monkeypatch.setattr("commands.find_licenses.GitHubClient", self._capturing_client(captured, MIT_REPOS))
            result = runner.invoke(app, args)
            assert result.exit_code == 0, result.output
            assert captured["timeout"] == 90
            assert captured["verbose"] is True
            assert captured["cache"].enabled is False
            assert captured["cache"].ttl == 60

    def test_env_var_defaults_apply(self, monkeypatch):
        monkeypatch.setenv("GH_INSPECTOR_CACHE_TTL", "120")
        monkeypatch.setenv("GH_INSPECTOR_TIMEOUT", "77")
        captured = {}
        monkeypatch.setattr("commands.find_licenses.GitHubClient", self._capturing_client(captured, MIT_REPOS))
        result = runner.invoke(app, ["find-licenses", "org"])
        assert result.exit_code == 0, result.output
        assert captured["cache"].ttl == 120
        assert captured["timeout"] == 77

    def test_cli_flag_overrides_env_var(self, monkeypatch):
        monkeypatch.setenv("GH_INSPECTOR_TIMEOUT", "77")
        captured = {}
        monkeypatch.setattr("commands.find_licenses.GitHubClient", self._capturing_client(captured, MIT_REPOS))
        result = runner.invoke(app, ["find-licenses", "org", "--timeout", "5"])
        assert result.exit_code == 0, result.output
        assert captured["timeout"] == 5

    def test_clear_cache_wipes_dir_before_run(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        cache_dir = tmp_path / "gh-inspector"
        cache_dir.mkdir(parents=True)
        (cache_dir / "stale.json").write_text("{}")
        monkeypatch.setattr("commands.find_licenses.GitHubClient", _stub_client(MIT_REPOS))
        result = runner.invoke(app, ["--clear-cache", "find-licenses", "org"])
        assert result.exit_code == 0, result.output
        assert list(cache_dir.glob("*.json")) == []

    def test_no_cache_protects_cache_from_clear_cache(self, monkeypatch, tmp_path):
        # --no-cache means "leave the stored cache untouched" and wins over --clear-cache.
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        cache_dir = tmp_path / "gh-inspector"
        cache_dir.mkdir(parents=True)
        (cache_dir / "stale.json").write_text("{}")
        monkeypatch.setattr("commands.find_licenses.GitHubClient", _stub_client(MIT_REPOS))
        result = runner.invoke(app, ["--no-cache", "--clear-cache", "find-licenses", "org"])
        assert result.exit_code == 0, result.output
        assert (cache_dir / "stale.json").exists()  # not wiped

    def test_quiet_suppresses_totals(self, monkeypatch, fake_client_factory):
        # find-python-version always runs scan_repos, which prints the totals line.
        repos = [{"nameWithOwner": "org/a", "isPrivate": False}]
        factory = fake_client_factory(repos=repos, trees={"org/a": []}, files={})
        monkeypatch.setattr("commands.find_python_version.GitHubClient", factory)
        loud = runner.invoke(app, ["find-python-version", "org", "-a"])
        monkeypatch.setattr("commands.find_python_version.GitHubClient", factory)
        quiet = runner.invoke(app, ["find-python-version", "org", "-a", "--quiet"])
        assert loud.exit_code == quiet.exit_code == 0
        assert "Total GitHub API calls" in loud.output
        assert "Total GitHub API calls" not in quiet.output


class TestFatalError:
    def _failing_client(self):
        class _Client:
            def __init__(self, *args, **kwargs):
                self.errors = []

            def get_repos(self, *args, **kwargs):
                raise Exception("gh: Not Found (HTTP 404)")

            def record_error(self, repo, message):
                self.errors.append({"repo": repo, "error": message})

            @property
            def call_count(self):
                return 0

        return _Client

    def test_get_repos_failure_json_is_structured(self, monkeypatch):
        monkeypatch.setattr("commands.find_licenses.GitHubClient", self._failing_client())
        result = runner.invoke(app, ["-o", "json", "find-licenses", "ghost"])
        assert result.exit_code == 1
        data = json.loads(result.stdout)  # pure JSON, not a traceback
        assert data["org"] == "ghost"
        assert "404" in data["error"]
        assert "Traceback" not in result.stdout

    def test_get_repos_failure_rich_prints_error(self, monkeypatch):
        monkeypatch.setattr("commands.find_licenses.GitHubClient", self._failing_client())
        result = runner.invoke(app, ["find-licenses", "ghost"])
        assert result.exit_code == 1
        assert "Failed to list repositories for ghost" in result.output
