import json

import pytest
from cache import ResponseCache, _human_size
from main import app
from typer.testing import CliRunner

runner = CliRunner()


class TestHumanSize:
    def test_units_scale(self):
        assert _human_size(0) == "0 B"
        assert _human_size(512) == "512 B"
        assert _human_size(2048) == "2.0 KB"
        assert _human_size(5 * 1024**2) == "5.0 MB"
        assert _human_size(3 * 1024**3) == "3.0 GB"
        # TB must render (previously dead code returned it as a large GB number)
        assert _human_size(2 * 1024**4) == "2.0 TB"


@pytest.fixture
def cache_home(monkeypatch, tmp_path):
    """Isolate the cache under a temp XDG_CACHE_HOME."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    return tmp_path


def _seed(n: int) -> None:
    cache = ResponseCache(enabled=True, ttl=3600)
    for i in range(n):
        cache.set(["gh", "api", f"repos/org/repo{i}"], f"body-{i}")


class TestCacheClear:
    def test_clear_removes_entries(self, cache_home):
        _seed(3)
        result = runner.invoke(app, ["cache", "clear"])
        assert result.exit_code == 0
        assert "Cleared 3" in result.stdout
        assert ResponseCache().info()[0] == 0

    def test_clear_empty_reports_zero(self, cache_home):
        result = runner.invoke(app, ["cache", "clear"])
        assert result.exit_code == 0
        assert "Cleared 0" in result.stdout

    def test_clear_json(self, cache_home):
        _seed(2)
        result = runner.invoke(app, ["-o", "json", "cache", "clear"])
        assert result.exit_code == 0
        assert json.loads(result.stdout) == {"cleared": 2}
        assert "\x1b[" not in result.stdout


class TestCachePath:
    def test_path_respects_xdg(self, cache_home):
        result = runner.invoke(app, ["cache", "path"])
        assert result.exit_code == 0
        assert str(cache_home / "gh-inspector") in result.stdout

    def test_path_json(self, cache_home):
        result = runner.invoke(app, ["-o", "json", "cache", "path"])
        assert result.exit_code == 0
        assert json.loads(result.stdout) == {"path": str(cache_home / "gh-inspector")}


class TestCacheInfo:
    def test_info_reports_count_and_size(self, cache_home):
        _seed(4)
        result = runner.invoke(app, ["cache", "info"])
        assert result.exit_code == 0
        assert "4" in result.stdout

    def test_info_json(self, cache_home):
        _seed(4)
        result = runner.invoke(app, ["-o", "json", "cache", "info"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["path"] == str(cache_home / "gh-inspector")
        assert data["entries"] == 4
        assert data["bytes"] > 0
        assert "\x1b[" not in result.stdout
