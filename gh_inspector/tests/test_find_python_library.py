import json
from collections import defaultdict
from pathlib import Path
from unittest.mock import MagicMock

from commands.find_python_library import get_matching_files, process_file
from commands.find_python_library.parsers import pipfile_lock as pipfile_parser
from commands.find_python_library.parsers import poetry_lock as poetry_parser
from commands.find_python_library.parsers import requirements as req_parser
from commands.find_python_library.parsers import setup_cfg as setup_cfg_parser
from commands.find_python_library.parsers import uv_lock as uv_parser

FIXTURES = Path(__file__).parent / "fixtures"


class TestRequirementsParser:
    def test_finds_library_version(self):
        content = "django==4.2.0\nrequests==2.31.0\n"
        result = req_parser.extract(content, ["django", "requests"])
        assert result == {"django": "4.2.0", "requests": "2.31.0"}

    def test_skips_cross_matches(self):
        content = "django-requests==1.0.0\n"
        result = req_parser.extract(content, ["django", "requests"])
        assert result == {}

    def test_handles_extras(self):
        content = "requests[security]==2.31.0\n"
        result = req_parser.extract(content, ["requests"])
        assert result == {"requests": "2.31.0"}

    def test_requirements_in_pattern(self):
        assert "requirements*.in" in req_parser.FILE_PATTERNS

    def test_with_fixture_file(self):
        content = (FIXTURES / "requirements.txt").read_text()
        result = req_parser.extract(content, ["django", "requests"])
        assert result == {"django": "4.2.0", "requests": "2.31.0"}

    def test_with_requirements_in_fixture(self):
        content = (FIXTURES / "requirements.in").read_text()
        result = req_parser.extract(content, ["django", "requests"])
        assert result == {"django": "4.2.0", "requests": "2.31.0"}


class TestUvLockParser:
    def test_finds_library(self):
        content = """
[[package]]
name = "django"
version = "4.2.0"

[[package]]
name = "requests"
version = "2.31.0"
"""
        result = uv_parser.extract(content, ["django"])
        assert result == {"django": "4.2.0"}

    def test_case_insensitive(self):
        content = '[[package]]\nname = "Django"\nversion = "4.2.0"\n'
        result = uv_parser.extract(content, ["django"])
        assert result == {"django": "4.2.0"}

    def test_with_fixture_file(self):
        content = (FIXTURES / "uv.lock").read_text()
        result = uv_parser.extract(content, ["django", "requests"])
        assert result == {"django": "4.2.0", "requests": "2.31.0"}


class TestPoetryLockParser:
    def test_finds_library(self):
        content = '[[package]]\nname = "requests"\nversion = "2.31.0"\n'
        result = poetry_parser.extract(content, ["requests"])
        assert result == {"requests": "2.31.0"}

    def test_with_fixture_file(self):
        content = (FIXTURES / "poetry.lock").read_text()
        result = poetry_parser.extract(content, ["django", "requests"])
        assert result == {"django": "4.2.0", "requests": "2.31.0"}


class TestPipfileLockParser:
    def test_finds_library_in_default(self):
        data = {"default": {"requests": {"version": "==2.31.0"}}, "develop": {}}
        result = pipfile_parser.extract(json.dumps(data), ["requests"])
        assert result == {"requests": "2.31.0"}

    def test_finds_library_in_develop(self):
        data = {"default": {}, "develop": {"pytest": {"version": "==7.0.0"}}}
        result = pipfile_parser.extract(json.dumps(data), ["pytest"])
        assert result == {"pytest": "7.0.0"}

    def test_with_fixture_file_default_section(self):
        content = (FIXTURES / "Pipfile.lock").read_text()
        result = pipfile_parser.extract(content, ["django", "requests"])
        assert result == {"django": "4.2.0", "requests": "2.31.0"}

    def test_with_fixture_file_develop_section(self):
        content = (FIXTURES / "Pipfile.lock").read_text()
        result = pipfile_parser.extract(content, ["pytest"])
        assert result == {"pytest": "7.4.0"}


class TestSetupCfgParser:
    def test_finds_library(self):
        content = "[options]\ninstall_requires =\n    django==4.2.0\n    requests==2.31.0\n"
        result = setup_cfg_parser.extract(content, ["django"])
        assert result == {"django": "4.2.0"}

    def test_with_fixture_file(self):
        content = (FIXTURES / "setup.cfg").read_text()
        result = setup_cfg_parser.extract(content, ["django", "requests"])
        assert result == {"django": "4.2.0", "requests": "2.31.0"}


class TestGetMatchingFiles:
    def setup_method(self):
        self.gh_client = MagicMock()
        self.gh_client.get_repo_tree.return_value = [
            {"path": "requirements.txt"},
            {"path": "requirements-dev.txt"},
            {"path": "uv.lock"},
            {"path": "poetry.lock"},
            {"path": "Pipfile.lock"},
            {"path": "setup.cfg"},
            {"path": "src/requirements.txt"},
            {"path": "README.md"},
        ]

    def test_returns_all_by_default(self):
        files = get_matching_files(self.gh_client, "org/repo", None)
        paths = [f for f, _ in files]
        assert "requirements.txt" in paths
        assert "uv.lock" in paths
        assert "poetry.lock" in paths
        assert "Pipfile.lock" in paths
        assert "setup.cfg" in paths
        assert "README.md" not in paths

    def test_filters_by_file_type(self):
        files = get_matching_files(self.gh_client, "org/repo", ["uv.lock"])
        paths = [f for f, _ in files]
        assert paths == ["uv.lock"]

    def test_filters_requirements_txt(self):
        files = get_matching_files(self.gh_client, "org/repo", ["requirements.txt"])
        paths = [f for f, _ in files]
        assert "requirements.txt" in paths
        assert "src/requirements.txt" in paths
        assert "requirements-dev.txt" in paths


class TestProcessFile:
    def setup_method(self):
        self.gh_client = MagicMock()

    def test_returns_results(self):
        self.gh_client.get_file_content.return_value = "django==4.2.0\n"
        result = process_file(self.gh_client, "org/repo", "requirements.txt", req_parser, ["django"])
        assert "django$v4.2.0" in result
        assert result["django$v4.2.0"] == ["org/repo (requirements.txt)"]

    def test_handles_error_gracefully(self):
        self.gh_client.get_file_content.side_effect = Exception("network error")
        result = process_file(self.gh_client, "org/repo", "requirements.txt", req_parser, ["django"])
        assert result == defaultdict(list)
