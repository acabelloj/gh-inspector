import time

import pytest
from cache import ResponseCache

ARGS = ["gh", "api", "repos/org/repo/contents/uv.lock"]
_NOW = 1_000_000.0


@pytest.fixture(autouse=True)
def _freeze_now(monkeypatch):
    """Freeze the write timestamp so TTL tests are deterministic."""
    monkeypatch.setattr(time, "time", lambda: _NOW)


@pytest.fixture
def cache_home(monkeypatch, tmp_path):
    """Point the cache at an isolated temp dir via XDG_CACHE_HOME."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    return tmp_path


class TestResponseCache:
    def test_set_then_get_round_trip(self, cache_home):
        cache = ResponseCache(enabled=True, ttl=3600)
        cache.set(ARGS, "body")
        assert cache.get(ARGS) == "body"

    def test_miss_when_absent(self, cache_home):
        assert ResponseCache(enabled=True, ttl=3600).get(ARGS) is None

    def test_ttl_expiry(self, cache_home, monkeypatch):
        cache = ResponseCache(enabled=True, ttl=10)
        cache.set(ARGS, "body")
        monkeypatch.setattr(time, "time", lambda: _NOW + 11)
        assert cache.get(ARGS) is None

    def test_within_ttl(self, cache_home, monkeypatch):
        cache = ResponseCache(enabled=True, ttl=10)
        cache.set(ARGS, "body")
        monkeypatch.setattr(time, "time", lambda: _NOW + 5)
        assert cache.get(ARGS) == "body"

    def test_corrupt_file_is_miss_and_removed(self, cache_home):
        cache = ResponseCache(enabled=True, ttl=3600)
        path = cache._path(ARGS)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ not json")
        assert cache.get(ARGS) is None
        assert not path.exists()

    def test_valid_json_wrong_shape_is_miss_and_removed(self, cache_home):
        # Valid JSON but missing the expected keys (e.g. old format) must miss, not crash.
        cache = ResponseCache(enabled=True, ttl=3600)
        path = cache._path(ARGS)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"data": "hi"}')  # no "ts"
        assert cache.get(ARGS) is None
        assert not path.exists()

    def test_disabled_never_reads(self, cache_home):
        ResponseCache(enabled=True, ttl=3600).set(ARGS, "body")
        assert ResponseCache(enabled=False, ttl=3600).get(ARGS) is None

    def test_disabled_set_is_noop(self, cache_home):
        disabled = ResponseCache(enabled=False, ttl=3600)
        disabled.set(ARGS, "body")
        # A subsequent enabled cache must not see anything the disabled one "wrote".
        assert ResponseCache(enabled=True, ttl=3600).get(ARGS) is None

    def test_atomic_write_leaves_no_tmp(self, cache_home):
        cache = ResponseCache(enabled=True, ttl=3600)
        cache.set(ARGS, "body")
        tmps = list(cache_home.glob("gh-inspector/*.tmp"))
        assert tmps == []

    def test_honours_xdg_cache_home(self, cache_home):
        cache = ResponseCache(enabled=True, ttl=3600)
        cache.set(ARGS, "body")
        assert (cache_home / "gh-inspector").is_dir()

    def test_clear_removes_entries(self, cache_home):
        cache = ResponseCache(enabled=True, ttl=3600)
        cache.set(ARGS, "a")
        cache.set(["gh", "api", "repos/org/other"], "b")
        assert cache.clear() == 2
        assert cache.get(ARGS) is None
        assert list((cache_home / "gh-inspector").glob("*.json")) == []

    def test_clear_on_empty_cache_returns_zero(self, cache_home):
        assert ResponseCache(enabled=True, ttl=3600).clear() == 0

    def test_info_counts_entries_and_size(self, cache_home):
        cache = ResponseCache(enabled=True, ttl=3600)
        cache.set(ARGS, "a")
        cache.set(["gh", "api", "repos/org/other"], "bb")
        count, size = cache.info()
        assert count == 2
        assert size > 0

    def test_info_on_missing_dir(self, cache_home):
        count, size = ResponseCache(enabled=True, ttl=3600).info()
        assert (count, size) == (0, 0)

    def test_path_points_at_cache_dir(self, cache_home):
        assert ResponseCache(enabled=True, ttl=3600).path == cache_home / "gh-inspector"
