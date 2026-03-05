from collections import defaultdict
from unittest.mock import MagicMock

from commands.find_python_library import get_requirements_files, process_requirements_file


class TestGetRequirementsFiles:
    def setup_method(self):
        self.gh_client = MagicMock()
        self.gh_client.get_repo_tree.return_value = [
            {"path": "requirements.txt"},
            {"path": "requirements-dev.txt"},
            {"path": "src/requirements.txt"},
            {"path": "README.md"},
        ]

    def test_default_source(self):
        files = get_requirements_files(self.gh_client, "org/repo", "default")
        assert files == ["requirements.txt", "src/requirements.txt"]

    def test_dev_source(self):
        files = get_requirements_files(self.gh_client, "org/repo", "dev")
        assert files == ["requirements-dev.txt"]

    def test_all_source(self):
        files = get_requirements_files(self.gh_client, "org/repo", "all")
        assert set(files) == {"requirements.txt", "requirements-dev.txt", "src/requirements.txt"}


class TestProcessRequirementsFile:
    def setup_method(self):
        self.gh_client = MagicMock()

    def test_finds_library_version(self):
        self.gh_client.get_file_content.return_value = "django==4.2.0\nrequests==2.31.0\n"
        library_regex = r"^(django|requests)(\[[^\]]*\])?==([0-9]+(?:\.[0-9]+)*)"

        result = process_requirements_file(
            self.gh_client, "org/repo", "requirements.txt", ["django", "requests"], library_regex
        )

        assert "django$v4.2.0" in result
        assert "requests$v2.31.0" in result

    def test_skips_cross_matches(self):
        self.gh_client.get_file_content.return_value = "django-requests==1.0.0\n"
        library_regex = r"^(django|requests)(\[[^\]]*\])?==([0-9]+(?:\.[0-9]+)*)"

        result = process_requirements_file(
            self.gh_client, "org/repo", "requirements.txt", ["django", "requests"], library_regex
        )

        assert result == defaultdict(list)

    def test_handles_extras(self):
        self.gh_client.get_file_content.return_value = "requests[security]==2.31.0\n"
        library_regex = r"^(requests)(\[[^\]]*\])?==([0-9]+(?:\.[0-9]+)*)"

        result = process_requirements_file(self.gh_client, "org/repo", "requirements.txt", ["requests"], library_regex)

        assert "requests$v2.31.0" in result

    def test_handles_client_error_gracefully(self):
        self.gh_client.get_file_content.side_effect = Exception("network error")
        library_regex = r"^(django)(\[[^\]]*\])?==([0-9]+(?:\.[0-9]+)*)"

        result = process_requirements_file(self.gh_client, "org/repo", "requirements.txt", ["django"], library_regex)

        assert result == defaultdict(list)
