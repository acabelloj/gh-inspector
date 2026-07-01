"""Snapshot tests for the find-codeowners command (json + rich output)."""

from main import app
from typer.testing import CliRunner

runner = CliRunner()

REPOS = [
    {"nameWithOwner": "org/alpha", "isPrivate": False, "defaultBranchRef": {"name": "main"}},
    {"nameWithOwner": "org/beta", "isPrivate": False, "defaultBranchRef": {"name": "main"}},
    {"nameWithOwner": "org/gamma", "isPrivate": False, "defaultBranchRef": {"name": "main"}},
]

TREES = {
    "org/alpha": [{"path": ".github/CODEOWNERS"}],
    "org/beta": [{"path": "CODEOWNERS"}],
    "org/gamma": [{"path": "README.md"}],
}

FILES = {
    ("org/alpha", ".github/CODEOWNERS"): "*       @org/platform\n/src/   @org/backend\n",
    ("org/beta", "CODEOWNERS"): "*.py    @org/backend\n",
}


def test_find_codeowners_json(monkeypatch, snapshot, fake_client_factory):
    monkeypatch.setattr(
        "commands.find_codeowners.GitHubClient", fake_client_factory(repos=REPOS, trees=TREES, files=FILES)
    )
    result = runner.invoke(app, ["-o", "json", "find-codeowners", "org"])
    assert result.exit_code == 0
    assert result.stdout == snapshot


def test_find_codeowners_rich(monkeypatch, snapshot, fake_client_factory):
    monkeypatch.setattr(
        "commands.find_codeowners.GitHubClient", fake_client_factory(repos=REPOS, trees=TREES, files=FILES)
    )
    result = runner.invoke(app, ["find-codeowners", "org"])
    assert result.exit_code == 0
    assert result.stdout == snapshot
