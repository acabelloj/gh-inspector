"""Snapshot tests for the find-python-library command (json + rich output)."""

from main import app
from typer.testing import CliRunner

runner = CliRunner()

REPOS = [
    {"nameWithOwner": "org/alpha", "isPrivate": False, "defaultBranchRef": {"name": "main"}},
    {"nameWithOwner": "org/beta", "isPrivate": False, "defaultBranchRef": {"name": "main"}},
]

TREES = {
    "org/alpha": [{"path": "requirements.txt"}],
    "org/beta": [{"path": "requirements.txt"}],
}

FILES = {
    ("org/alpha", "requirements.txt"): "requests==2.31.0\ndjango==4.2.0\n",
    ("org/beta", "requirements.txt"): "requests==2.28.0\n",
}


def test_find_python_library_json(monkeypatch, snapshot, fake_client_factory):
    monkeypatch.setattr(
        "commands.find_python_library.GitHubClient", fake_client_factory(repos=REPOS, trees=TREES, files=FILES)
    )
    result = runner.invoke(app, ["-o", "json", "find-python-library", "org", "requests", "-a"])
    assert result.exit_code == 0
    assert result.stdout == snapshot


def test_find_python_library_rich(monkeypatch, snapshot, fake_client_factory):
    monkeypatch.setattr(
        "commands.find_python_library.GitHubClient", fake_client_factory(repos=REPOS, trees=TREES, files=FILES)
    )
    result = runner.invoke(app, ["find-python-library", "org", "requests", "-a"])
    assert result.exit_code == 0
    assert result.stdout == snapshot
