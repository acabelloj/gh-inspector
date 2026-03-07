from commands.find_python_version import (
    _project_key,
    check_consistency,
    extract_versions_for_file,
    matches_pattern,
    version_key,
)
from commands.find_python_version.extractors import VersionCategory


class TestMatchesPattern:
    def test_exact_match(self):
        assert matches_pattern("Dockerfile", "Dockerfile")

    def test_ends_with_match(self):
        assert matches_pattern(".github/workflows/ci.yml", ".github/workflows/ci.yml")

    def test_wildcard_match(self):
        assert matches_pattern(".github/workflows/ci.yml", ".github/workflows/*.yml")

    def test_wildcard_no_match(self):
        assert not matches_pattern(".github/workflows/ci.yaml", ".github/workflows/*.yml")

    def test_no_match(self):
        assert not matches_pattern("setup.cfg", "Dockerfile")

    def test_endswith(self):
        assert matches_pattern("path/to/pyproject.toml", "pyproject.toml")


class TestExtractVersionsForFile:
    def test_dockerfile(self):
        content = "FROM python:3.12.0-slim"
        assert extract_versions_for_file("Dockerfile", content) == [("3.12.0", VersionCategory.RUNTIME)]

    def test_dockerfile_no_match(self):
        assert extract_versions_for_file("Dockerfile", "FROM ubuntu:22.04") == []

    def test_python_version_file(self):
        assert extract_versions_for_file(".python-version", "3.11.4\n") == [("3.11.4", VersionCategory.RUNTIME)]

    def test_pyproject_requires_python(self):
        content = 'requires-python = ">=3.10"'
        assert extract_versions_for_file("pyproject.toml", content) == [(">=3.10", VersionCategory.MINIMUM)]

    def test_pyproject_poetry(self):
        content = 'python = "^3.11"'
        assert extract_versions_for_file("pyproject.toml", content) == [("^3.11", VersionCategory.MINIMUM)]

    def test_setup_py(self):
        content = 'python_requires = ">=3.10"'
        assert extract_versions_for_file("setup.py", content) == [(">=3.10", VersionCategory.MINIMUM)]

    def test_github_actions_single_quotes(self):
        content = "python-version: '3.11'"
        assert extract_versions_for_file(".github/workflows/ci.yml", content) == [("3.11", VersionCategory.CI)]

    def test_github_actions_double_quotes(self):
        content = 'python-version: "3.11"'
        assert extract_versions_for_file(".github/workflows/ci.yml", content) == [("3.11", VersionCategory.CI)]

    def test_github_actions_matrix(self):
        content = 'python-version: ["3.10", "3.11", "3.12"]'
        result = extract_versions_for_file(".github/workflows/ci.yml", content)
        assert result == [
            ("3.10", VersionCategory.CI),
            ("3.11", VersionCategory.CI),
            ("3.12", VersionCategory.CI),
        ]

    def test_github_actions_multiple_steps(self):
        content = "python-version: '3.10'\npython-version: '3.11'"
        result = extract_versions_for_file(".github/workflows/ci.yml", content)
        assert result == [("3.10", VersionCategory.CI), ("3.11", VersionCategory.CI)]

    def test_tox_envlist(self):
        content = "envlist = py310,py311,py312"
        result = extract_versions_for_file("tox.ini", content)
        assert ("3.10", VersionCategory.CI) in result
        assert ("3.11", VersionCategory.CI) in result
        assert ("3.12", VersionCategory.CI) in result

    def test_tox_basepython(self):
        content = "basepython = python3.11"
        assert extract_versions_for_file("tox.ini", content) == [("3.11", VersionCategory.CI)]

    def test_circleci_cimg(self):
        content = "      - image: cimg/python:3.11.1"
        assert extract_versions_for_file(".circleci/config.yml", content) == [("3.11.1", VersionCategory.CI)]

    def test_circleci_legacy(self):
        content = "      - image: circleci/python:3.9"
        assert extract_versions_for_file(".circleci/config.yml", content) == [("3.9", VersionCategory.CI)]

    def test_circleci_docker_hub(self):
        content = "      - image: python:3.12-slim"
        assert extract_versions_for_file(".circleci/config.yml", content) == [("3.12", VersionCategory.CI)]

    def test_unknown_file(self):
        assert extract_versions_for_file("some_other_file.txt", "python = '3.11'") == []

    def test_no_version(self):
        assert extract_versions_for_file("pyproject.toml", "no version here") == []


class TestCheckConsistency:
    def test_consistent(self):
        assert check_consistency({"3.12": set()}, {">=3.10": set()}) == []

    def test_runtime_below_minimum(self):
        issues = check_consistency({"3.9": set()}, {">=3.10": set()})
        assert len(issues) == 1
        assert "3.9" in issues[0]

    def test_no_runtime(self):
        assert check_consistency({}, {">=3.10": set()}) == []

    def test_no_minimum(self):
        assert check_consistency({"3.12": set()}, {}) == []

    def test_poetry_specifier(self):
        assert check_consistency({"3.11": set()}, {"^3.11": set()}) == []

    def test_poetry_specifier_below(self):
        issues = check_consistency({"3.10": set()}, {"^3.11": set()})
        assert len(issues) == 1


class TestProjectKey:
    def test_root_file(self):
        assert _project_key("pyproject.toml") == ""

    def test_github_actions(self):
        assert _project_key(".github/workflows/ci.yml") == ""

    def test_circleci(self):
        assert _project_key(".circleci/config.yml") == ""

    def test_subproject(self):
        assert _project_key("service-a/pyproject.toml") == "service-a"

    def test_nested_subproject(self):
        assert _project_key("service-a/backend/Dockerfile") == "service-a"

    def test_root_dockerfile(self):
        assert _project_key("Dockerfile") == ""


class TestVersionKey:
    def test_sorts_correctly(self):
        versions = ["3.9", "3.11", "3.10"]
        assert sorted(versions, key=version_key, reverse=True) == ["3.11", "3.10", "3.9"]

    def test_handles_specifier(self):
        key = version_key(">=3.11")
        assert key == version_key("3.11")

    def test_handles_invalid_version(self):
        assert version_key("unknown") == version_key("0.0")
