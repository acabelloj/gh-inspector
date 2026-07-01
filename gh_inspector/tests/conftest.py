"""Shared fixtures for snapshot tests.

Snapshots must be deterministic across machines, so Rich output is captured at a
fixed console width. In non-TTY mode (as under CliRunner) Rich honours the
``COLUMNS`` env var for width, giving stable rendered tables/trees.
"""

import pytest


@pytest.fixture(autouse=True)
def _fixed_console_width(monkeypatch):
    """Pin terminal width so Rich renders identically everywhere."""
    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.setenv("LINES", "40")


class FakeGitHubClient:
    """Drop-in replacement for GitHubClient driven by in-memory fixture data.

    ``repos`` is the list returned by ``get_repos``. ``trees`` maps repo name to
    its file tree (list of {"path": ...}). ``files`` maps (repo, path) to content.
    """

    def __init__(self, repos=None, trees=None, files=None, console=None):
        self._repos = repos or []
        self._trees = trees or {}
        self._files = files or {}
        self.console = console
        self.call_count = 0

    def get_repos(self, org_name, all_repositories=False, extra_fields=None):
        return self._repos

    def get_default_branch(self, repo_name):
        return "main"

    def get_repo_tree(self, repo_name, branch=None):
        return self._trees.get(repo_name, [])

    def get_file_content(self, repo_name, file_path):
        try:
            return self._files[(repo_name, file_path)]
        except KeyError as e:
            raise Exception(f"404 not found: {repo_name}/{file_path}") from e


@pytest.fixture
def fake_client_factory():
    """Return a callable that builds a GitHubClient-shaped stub from fixture data.

    Use with ``monkeypatch.setattr`` to replace a command's ``GitHubClient``:
    the returned callable forwards the ``console=`` the command passes and yields
    a :class:`FakeGitHubClient` seeded with the given data.
    """

    def make(repos=None, trees=None, files=None):
        def factory(console=None):
            return FakeGitHubClient(repos=repos, trees=trees, files=files, console=console)

        return factory

    return make
