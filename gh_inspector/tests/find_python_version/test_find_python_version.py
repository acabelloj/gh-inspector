from commands.find_python_version import (
    _find_project_roots,
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

    def test_pulumi_runtime_inline(self):
        # "runtime: python3.11" — version embedded in runtime value
        content = "runtime: python3.11"
        assert extract_versions_for_file("infra/Pulumi.yaml", content) == [("3.11", VersionCategory.RUNTIME)]

    def test_pulumi_runtime_patch(self):
        content = "runtime: python3.11.5"
        assert extract_versions_for_file("Pulumi.yaml", content) == [("3.11.5", VersionCategory.RUNTIME)]

    def test_pulumi_runtime_version_key(self):
        # Newer Pulumi format with separate runtimeVersion key
        content = "runtime: python\nruntimeVersion: 3.11"
        result = extract_versions_for_file("Pulumi.yaml", content)
        assert ("3.11", VersionCategory.RUNTIME) in result

    def test_pulumi_python_version_key(self):
        content = "python-version: 3.12.1"
        assert extract_versions_for_file("Pulumi.yaml", content) == [("3.12.1", VersionCategory.RUNTIME)]

    def test_pulumi_stack_file_nested(self):
        # Stack file in infra/envs/ should still be detected
        content = "runtime: python3.11"
        assert extract_versions_for_file("infra/envs/Pulumi.prod.yaml", content) == [("3.11", VersionCategory.RUNTIME)]

    def test_pulumi_no_version(self):
        content = "runtime: nodejs\nname: my-stack"
        assert extract_versions_for_file("Pulumi.yaml", content) == []

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


class TestFindProjectRoots:
    def _tree(self, paths):
        return [{"path": p} for p in paths]

    def test_root_pyproject(self):
        assert _find_project_roots(self._tree(["pyproject.toml", "src/main.py"])) == {""}

    def test_subproject(self):
        assert _find_project_roots(self._tree(["apps/app1/pyproject.toml"])) == {"apps/app1"}

    def test_multiple_subprojects(self):
        roots = _find_project_roots(self._tree(["apps/app1/pyproject.toml", "libs/lib1/setup.py"]))
        assert roots == {"apps/app1", "libs/lib1"}

    def test_no_markers(self):
        assert _find_project_roots(self._tree(["Dockerfile", ".github/workflows/ci.yml"])) == set()

    def test_setup_py_and_cfg(self):
        roots = _find_project_roots(self._tree(["svc/setup.py", "svc/setup.cfg"]))
        assert roots == {"svc"}

    def test_pulumi_base_file(self):
        assert _find_project_roots(self._tree(["infra/Pulumi.yaml"])) == {"infra"}

    def test_pulumi_nested(self):
        roots = _find_project_roots(self._tree(["infra/env/Pulumi.yaml", "infra/env/Pulumi.prod.yml"]))
        assert roots == {"infra/env"}

    def test_pulumi_multiple_envs(self):
        roots = _find_project_roots(self._tree(["infra/dev/Pulumi.yaml", "infra/prod/Pulumi.yaml"]))
        assert roots == {"infra/dev", "infra/prod"}

    def test_pulumi_stack_only(self):
        # Directory with only a stack file (no base Pulumi.yaml) is still a project root
        roots = _find_project_roots(self._tree(["infra/env/Pulumi.prod.yml", "infra/env/.python-version"]))
        assert roots == {"infra/env"}

    def test_pulumi_stack_variants(self):
        roots = _find_project_roots(self._tree(["infra/Pulumi.staging.yaml", "infra/Pulumi.prod.yml"]))
        assert roots == {"infra"}


class TestProjectKey:
    def test_root_file(self):
        assert _project_key("pyproject.toml", {""}) == ""

    def test_github_actions(self):
        assert _project_key(".github/workflows/ci.yml", {""}) == ""

    def test_circleci(self):
        assert _project_key(".circleci/config.yml", {""}) == ""

    def test_subproject(self):
        assert _project_key("service-a/pyproject.toml", {"service-a"}) == "service-a"

    def test_nested_subproject(self):
        assert _project_key("service-a/backend/Dockerfile", {"service-a"}) == "service-a"

    def test_root_dockerfile(self):
        assert _project_key("Dockerfile", {""}) == ""

    def test_deep_monorepo(self):
        roots = {"apps/app1", "apps/app2", "libs/lib1"}
        assert _project_key("apps/app1/.python-version", roots) == "apps/app1"
        assert _project_key("apps/app2/Dockerfile", roots) == "apps/app2"
        assert _project_key("libs/lib1/pyproject.toml", roots) == "libs/lib1"

    def test_no_roots_falls_back_to_first_dir(self):
        assert _project_key("apps/app1/Dockerfile", set()) == "apps"

    def test_deepest_root_wins(self):
        # if both "apps" and "apps/app1" are roots, "apps/app1" wins for a file inside it
        roots = {"apps", "apps/app1"}
        assert _project_key("apps/app1/Dockerfile", roots) == "apps/app1"


class TestVersionKey:
    def test_sorts_correctly(self):
        versions = ["3.9", "3.11", "3.10"]
        assert sorted(versions, key=version_key, reverse=True) == ["3.11", "3.10", "3.9"]

    def test_handles_specifier(self):
        key = version_key(">=3.11")
        assert key == version_key("3.11")

    def test_handles_invalid_version(self):
        assert version_key("unknown") == version_key("0.0")
