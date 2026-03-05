from commands.find_python_version import extract_version_from_content, matches_pattern, version_key


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


class TestExtractVersionFromContent:
    def test_python_version_file(self):
        assert extract_version_from_content("3.11.4") == ["3.11.4"]

    def test_pyproject_toml(self):
        content = 'python = "^3.11"'
        assert extract_version_from_content(content) == ["3.11"]

    def test_setup_py(self):
        content = 'python_requires = ">=3.10"'
        assert extract_version_from_content(content) == ["3.10"]

    def test_dockerfile(self):
        content = "FROM python:3.12.0-slim"
        assert extract_version_from_content(content) == ["3.12.0"]

    def test_github_actions_workflow(self):
        content = "python-version: '3.11'"
        assert extract_version_from_content(content) == ["3.11"]

    def test_github_actions_workflow_double_quotes(self):
        content = 'python-version: "3.11"'
        assert extract_version_from_content(content) == ["3.11"]

    def test_github_actions_workflow_multiple(self):
        content = "python-version: '3.10'\npython-version: '3.11'"
        assert extract_version_from_content(content) == ["3.10", "3.11"]

    def test_no_version(self):
        assert extract_version_from_content("no version here") == []


class TestVersionKey:
    def test_sorts_correctly(self):
        versions = ["3.9", "3.11", "3.10"]
        sorted_versions = sorted(versions, key=version_key, reverse=True)
        assert sorted_versions == ["3.11", "3.10", "3.9"]

    def test_handles_prefixed_version(self):
        key = version_key("py3.11")
        assert key == version_key("3.11")

    def test_handles_invalid_version(self):
        key = version_key("unknown")
        assert key == version_key("0.0")
