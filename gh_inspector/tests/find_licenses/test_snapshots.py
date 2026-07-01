"""Snapshot tests for the find-licenses command (json + rich output)."""

from main import app
from typer.testing import CliRunner

runner = CliRunner()

REPOS = [
    {"nameWithOwner": "org/alpha", "isPrivate": False, "licenseInfo": {"spdxId": "MIT"}},
    {"nameWithOwner": "org/beta", "isPrivate": False, "licenseInfo": {"spdxId": "Apache-2.0"}},
    {"nameWithOwner": "org/gamma", "isPrivate": False, "licenseInfo": {"spdxId": "MIT"}},
    {"nameWithOwner": "org/delta", "isPrivate": False, "licenseInfo": None},
]

FILES = {
    ("org/delta", "pyproject.toml"): '[project]\nlicense = "BSD-3-Clause"\n',
}


def test_find_licenses_json(monkeypatch, snapshot, fake_client_factory):
    monkeypatch.setattr("commands.find_licenses.GitHubClient", fake_client_factory(repos=REPOS, files=FILES))
    result = runner.invoke(app, ["-o", "json", "find-licenses", "org"])
    assert result.exit_code == 0
    assert result.stdout == snapshot


def test_find_licenses_rich(monkeypatch, snapshot, fake_client_factory):
    monkeypatch.setattr("commands.find_licenses.GitHubClient", fake_client_factory(repos=REPOS, files=FILES))
    result = runner.invoke(app, ["find-licenses", "org"])
    assert result.exit_code == 0
    assert result.stdout == snapshot
