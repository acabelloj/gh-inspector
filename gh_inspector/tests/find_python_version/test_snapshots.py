"""Snapshot tests for the find-python-version command (json + rich output)."""

from main import app
from typer.testing import CliRunner

runner = CliRunner()

REPOS = [
    {"nameWithOwner": "org/alpha", "isPrivate": False, "defaultBranchRef": {"name": "main"}},
    {"nameWithOwner": "org/beta", "isPrivate": False, "defaultBranchRef": {"name": "main"}},
    {"nameWithOwner": "org/gamma", "isPrivate": False, "defaultBranchRef": {"name": "main"}},
]

TREES = {
    "org/alpha": [{"path": ".python-version"}, {"path": "pyproject.toml"}],
    # org/beta runtime (3.9) is below its declared minimum (>=3.11) -> inconsistent
    "org/beta": [{"path": ".python-version"}, {"path": "pyproject.toml"}],
    "org/gamma": [{"path": "README.md"}],
}

FILES = {
    ("org/alpha", ".python-version"): "3.12\n",
    ("org/alpha", "pyproject.toml"): '[project]\nrequires-python = ">=3.10"\n',
    ("org/beta", ".python-version"): "3.9\n",
    ("org/beta", "pyproject.toml"): '[project]\nrequires-python = ">=3.11"\n',
}


def test_find_python_version_json(monkeypatch, snapshot, fake_client_factory):
    monkeypatch.setattr(
        "commands.find_python_version.GitHubClient", fake_client_factory(repos=REPOS, trees=TREES, files=FILES)
    )
    result = runner.invoke(app, ["-o", "json", "find-python-version", "org", "-a"])
    assert result.exit_code == 0
    assert result.stdout == snapshot


def test_find_python_version_rich(monkeypatch, snapshot, fake_client_factory):
    monkeypatch.setattr(
        "commands.find_python_version.GitHubClient", fake_client_factory(repos=REPOS, trees=TREES, files=FILES)
    )
    result = runner.invoke(app, ["find-python-version", "org", "-a"])
    assert result.exit_code == 0
    assert result.stdout == snapshot
