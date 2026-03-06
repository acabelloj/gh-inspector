import json
from io import StringIO
from unittest.mock import patch

from commands.find_licenses import (
    display_license_table,
    display_unlicensed_table,
    extract_license_id,
    group_by_license,
    parse_cargo_toml,
    parse_license_file,
    parse_package_json,
    parse_pyproject_toml,
    parse_setup_cfg,
)
from github_client import GitHubClient
from rich.console import Console


def _make_repo(name: str, license_key: str | None = None) -> dict:
    """Create a repo dict mimicking gh repo list --json output (key, name, nickname)."""
    license_info = {"key": license_key, "name": f"{license_key} License", "nickname": ""} if license_key else None
    return {"nameWithOwner": name, "isPrivate": False, "licenseInfo": license_info}


def _make_repo_spdx(name: str, spdx_id: str) -> dict:
    """Create a repo dict with spdxId (GraphQL-style response)."""
    return {"nameWithOwner": name, "isPrivate": False, "licenseInfo": {"spdxId": spdx_id}}


class TestExtractLicenseId:
    def test_with_key_field(self):
        repo = _make_repo("org/repo1", "mit")
        assert extract_license_id(repo) == "mit"

    def test_spdx_id_preferred_over_key(self):
        repo = {"nameWithOwner": "org/repo1", "licenseInfo": {"spdxId": "MIT", "key": "mit"}}
        assert extract_license_id(repo) == "MIT"

    def test_falls_back_to_key_when_no_spdx(self):
        repo = {"nameWithOwner": "org/repo1", "licenseInfo": {"key": "bsd-3-clause", "name": "BSD 3-Clause"}}
        assert extract_license_id(repo) == "bsd-3-clause"

    def test_with_no_license_info(self):
        repo = {"nameWithOwner": "org/repo1", "licenseInfo": None}
        assert extract_license_id(repo) is None

    def test_with_missing_license_info_key(self):
        repo = {"nameWithOwner": "org/repo1"}
        assert extract_license_id(repo) is None

    def test_with_empty_key(self):
        repo = {"nameWithOwner": "org/repo1", "licenseInfo": {"key": ""}}
        assert extract_license_id(repo) is None

    def test_noassertion_treated_as_missing(self):
        repo = _make_repo_spdx("org/repo1", "NOASSERTION")
        assert extract_license_id(repo) is None

    def test_other_key_is_surfaced(self):
        repo = _make_repo("org/repo1", "other")
        assert extract_license_id(repo) == "other"


class TestParsePyprojectToml:
    def test_string_license_double_quotes(self):
        assert parse_pyproject_toml('license = "MIT"') == "MIT"

    def test_string_license_single_quotes(self):
        assert parse_pyproject_toml("license = 'Apache-2.0'") == "Apache-2.0"

    def test_table_license_with_text(self):
        assert parse_pyproject_toml('license = {text = "BSD-3-Clause"}') == "BSD-3-Clause"

    def test_table_license_with_text_single_quotes(self):
        assert parse_pyproject_toml("license = {text = 'GPL-3.0'}") == "GPL-3.0"

    def test_no_license_field(self):
        assert parse_pyproject_toml("[project]\nname = 'mypackage'\nversion = '1.0'") is None

    def test_license_in_full_pyproject(self):
        assert parse_pyproject_toml("[project]\nname = 'pkg'\nlicense = 'MIT'\nversion = '1.0'") == "MIT"

    def test_license_file_not_matched(self):
        assert parse_pyproject_toml('license = {file = "LICENSE"}') is None

    def test_ignores_license_in_dependency(self):
        assert parse_pyproject_toml('    "pip-licenses==4.0.3",\nlicense = "MIT"') == "MIT"


class TestParseSetupCfg:
    def test_license_under_metadata(self):
        content = "[metadata]\nname = pkg\nlicense = MIT\nversion = 1.0"
        assert parse_setup_cfg(content) == "MIT"

    def test_license_with_spaces(self):
        content = "[metadata]\nname = pkg\nlicense = Apache 2.0"
        assert parse_setup_cfg(content) == "Apache 2.0"

    def test_no_metadata_section(self):
        content = "[options]\ninstall_requires = requests"
        assert parse_setup_cfg(content) is None

    def test_no_license_in_metadata(self):
        content = "[metadata]\nname = pkg\nversion = 1.0"
        assert parse_setup_cfg(content) is None


class TestParsePackageJson:
    def test_license_string(self):
        assert parse_package_json('{"license": "MIT"}') == "MIT"

    def test_no_license_field(self):
        assert parse_package_json('{"name": "pkg"}') is None

    def test_invalid_json(self):
        assert parse_package_json("not json") is None

    def test_license_object_ignored(self):
        assert parse_package_json('{"license": {"type": "MIT"}}') is None

    def test_empty_license(self):
        assert parse_package_json('{"license": ""}') is None


class TestParseCargoToml:
    def test_license_field(self):
        content = '[package]\nname = "mycrate"\nlicense = "MIT OR Apache-2.0"'
        assert parse_cargo_toml(content) == "MIT OR Apache-2.0"

    def test_no_license(self):
        content = '[package]\nname = "mycrate"\nversion = "0.1.0"'
        assert parse_cargo_toml(content) is None


class TestParseLicenseFile:
    def test_first_line(self):
        assert parse_license_file("MIT License\n\nCopyright 2024") == "MIT License"

    def test_custom_license(self):
        assert parse_license_file("TravelPerk License\n\nAll rights reserved.") == "TravelPerk License"

    def test_skips_blank_lines(self):
        assert parse_license_file("\n\n  Apache License\nVersion 2.0") == "Apache License"

    def test_empty_content(self):
        assert parse_license_file("") is None

    def test_only_whitespace(self):
        assert parse_license_file("  \n  \n") is None


class TestGroupByLicense:
    def test_basic_grouping(self):
        repos = [_make_repo("org/a", "mit"), _make_repo("org/b", "mit"), _make_repo("org/c", "apache-2.0")]
        grouped, unlicensed = group_by_license(repos)
        assert grouped == {"mit": ["org/a", "org/b"], "apache-2.0": ["org/c"]}
        assert unlicensed == []

    def test_exclude_filter(self):
        repos = [_make_repo("org/a", "mit"), _make_repo("org/b", "apache-2.0"), _make_repo("org/c", "gpl-3.0")]
        grouped, _ = group_by_license(repos, exclude=["mit", "apache-2.0"])
        assert grouped == {"gpl-3.0": ["org/c"]}

    def test_case_insensitive_exclude(self):
        repos = [_make_repo("org/a", "mit"), _make_repo("org/b", "apache-2.0")]
        grouped, _ = group_by_license(repos, exclude=["MIT", "Apache-2.0"])
        assert grouped == {}

    def test_unlicensed_repos(self):
        repos = [_make_repo("org/a", "mit"), _make_repo("org/b")]
        grouped, unlicensed = group_by_license(repos)
        assert grouped == {"mit": ["org/a"]}
        assert unlicensed == ["org/b"]

    def test_skip_missing(self):
        repos = [_make_repo("org/a", "mit"), _make_repo("org/b")]
        grouped, unlicensed = group_by_license(repos, skip_missing=True)
        assert grouped == {"mit": ["org/a"]}
        assert unlicensed == []

    def test_empty_repos(self):
        grouped, unlicensed = group_by_license([])
        assert grouped == {}
        assert unlicensed == []

    def test_resolved_license_overrides_api(self):
        repo = _make_repo("org/a", "other")
        repo["_resolved_license"] = "MIT"
        grouped, unlicensed = group_by_license([repo])
        assert grouped == {"MIT": ["org/a"]}
        assert unlicensed == []

    def test_resolved_license_for_unlicensed_repo(self):
        repo = _make_repo("org/a")
        repo["_resolved_license"] = "Apache-2.0"
        grouped, unlicensed = group_by_license([repo])
        assert grouped == {"Apache-2.0": ["org/a"]}
        assert unlicensed == []


class TestDisplayLicenseTable:
    def test_no_crash_and_contains_license(self):
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False)
        with patch("commands.find_licenses.console", test_console):
            display_license_table({"MIT": ["org/repo1", "org/repo2"]})
        output = buf.getvalue()
        assert "MIT" in output
        assert "org/repo1" in output

    def test_empty_grouped(self):
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False)
        with patch("commands.find_licenses.console", test_console):
            display_license_table({})


class TestDisplayUnlicensedTable:
    def test_no_crash_and_contains_repo(self):
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False)
        with patch("commands.find_licenses.console", test_console):
            display_unlicensed_table(["org/repo1"])
        output = buf.getvalue()
        assert "org/repo1" in output


class TestGetReposExtraFields:
    def setup_method(self):
        self.client = GitHubClient()

    def test_extra_fields_appended(self):
        repos = [{"nameWithOwner": "org/repo", "isPrivate": False, "licenseInfo": None}]
        with patch.object(self.client, "run_command", return_value=json.dumps(repos)) as mock_cmd:
            self.client.get_repos("org", all_repositories=True, extra_fields=["licenseInfo"])
            args = mock_cmd.call_args[0][0]
            json_idx = args.index("--json")
            assert "licenseInfo" in args[json_idx + 1]

    def test_no_extra_fields_unchanged(self):
        repos = [{"nameWithOwner": "org/repo", "isPrivate": False}]
        with patch.object(self.client, "run_command", return_value=json.dumps(repos)) as mock_cmd:
            self.client.get_repos("org", all_repositories=True)
            args = mock_cmd.call_args[0][0]
            json_idx = args.index("--json")
            assert args[json_idx + 1] == "nameWithOwner,isPrivate"
