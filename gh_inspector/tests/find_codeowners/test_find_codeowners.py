from unittest.mock import MagicMock

from commands.find_codeowners import (
    _format_patterns,
    _is_owner,
    aggregate_by_owner,
    find_codeowners_file,
    parse_codeowners,
    process_repo,
)


class TestFormatPatterns:
    def test_single_pattern(self):
        assert _format_patterns(["*.py"]) == "*.py"

    def test_at_limit(self):
        patterns = ["*.py", "/src/", "docs/", "/api/", "/lib/"]
        assert _format_patterns(patterns) == "*.py, /src/, docs/, /api/, /lib/"

    def test_over_limit_shows_remainder(self):
        patterns = ["*.py", "/src/", "docs/", "/api/", "/lib/", "/cmd/", "/pkg/"]
        assert _format_patterns(patterns) == "*.py, /src/, docs/, /api/, /lib/ + 2 more"

    def test_many_patterns(self):
        patterns = [f"path{i}/" for i in range(50)]
        result = _format_patterns(patterns)
        assert result.endswith("+ 45 more")

    def test_empty_list(self):
        assert _format_patterns([]) == ""


class TestIsOwner:
    def test_team_handle(self):
        assert _is_owner("@org/backend") is True

    def test_user_handle(self):
        assert _is_owner("@username") is True

    def test_email(self):
        assert _is_owner("user@example.com") is True

    def test_plain_word(self):
        assert _is_owner("Misleading") is False

    def test_word_with_comma(self):
        assert _is_owner("name,") is False

    def test_lowercase_word(self):
        assert _is_owner("the") is False

    def test_path_like(self):
        assert _is_owner("/src/") is False


class TestParseCodeowners:
    def test_basic_entry(self):
        content = "*.py @org/backend"
        assert parse_codeowners(content) == [("*.py", ["@org/backend"])]

    def test_multiple_owners(self):
        content = "/src/ @org/backend @org/platform"
        assert parse_codeowners(content) == [("/src/", ["@org/backend", "@org/platform"])]

    def test_comments_and_blanks_skipped(self):
        content = "# This is a comment\n\n*.py @org/backend\n# Another comment\n"
        assert parse_codeowners(content) == [("*.py", ["@org/backend"])]

    def test_empty_content(self):
        assert parse_codeowners("") == []

    def test_section_headers_skipped(self):
        content = "[Documentation]\ndocs/ @org/docs\n[Backend]\n*.py @org/backend"
        assert parse_codeowners(content) == [
            ("docs/", ["@org/docs"]),
            ("*.py", ["@org/backend"]),
        ]

    def test_pattern_without_owner_skipped(self):
        content = "*.py\n*.go @org/backend"
        assert parse_codeowners(content) == [("*.go", ["@org/backend"])]

    def test_crlf_line_endings(self):
        content = "*.py @org/backend\r\n*.go @org/platform\r\n"
        assert parse_codeowners(content) == [
            ("*.py", ["@org/backend"]),
            ("*.go", ["@org/platform"]),
        ]

    def test_prose_line_without_hash_ignored(self):
        content = (
            "Misleading name, this should actually be change for mocking multiple service verticals\n*.py @org/backend"
        )
        assert parse_codeowners(content) == [("*.py", ["@org/backend"])]

    def test_non_owner_tokens_filtered(self):
        content = "*.py @org/backend some_random_word"
        assert parse_codeowners(content) == [("*.py", ["@org/backend"])]

    def test_email_owner(self):
        content = "docs/ user@example.com"
        assert parse_codeowners(content) == [("docs/", ["user@example.com"])]

    def test_line_with_no_valid_owners_skipped(self):
        content = "the owner should be squad that this to change"
        assert parse_codeowners(content) == []


class TestFindCodeownersFile:
    def _make_client(self, paths: list[str]):
        client = MagicMock()
        client.get_repo_tree.return_value = [{"path": p} for p in paths]
        return client

    def test_finds_in_github_dir(self):
        client = self._make_client([".github/CODEOWNERS", "README.md"])
        assert find_codeowners_file(client, "org/repo") == ".github/CODEOWNERS"

    def test_finds_in_root(self):
        client = self._make_client(["CODEOWNERS", "README.md"])
        assert find_codeowners_file(client, "org/repo") == "CODEOWNERS"

    def test_finds_in_docs(self):
        client = self._make_client(["docs/CODEOWNERS", "README.md"])
        assert find_codeowners_file(client, "org/repo") == "docs/CODEOWNERS"

    def test_prefers_github_over_root(self):
        client = self._make_client([".github/CODEOWNERS", "CODEOWNERS"])
        assert find_codeowners_file(client, "org/repo") == ".github/CODEOWNERS"

    def test_returns_none_when_missing(self):
        client = self._make_client(["README.md", "src/main.py"])
        assert find_codeowners_file(client, "org/repo") is None

    def test_returns_none_on_api_error(self):
        client = MagicMock()
        client.get_repo_tree.side_effect = Exception("API error")
        assert find_codeowners_file(client, "org/repo") is None


class TestAggregateByOwner:
    def test_single_repo(self):
        results = [("org/repo1", [("*.py", ["@org/backend"]), ("docs/", ["@org/docs"])])]
        agg = aggregate_by_owner(results)
        assert agg == {
            "@org/backend": [("org/repo1", ["*.py"])],
            "@org/docs": [("org/repo1", ["docs/"])],
        }

    def test_multiple_repos(self):
        results = [
            ("org/repo1", [("*.py", ["@org/backend"])]),
            ("org/repo2", [("*.go", ["@org/backend"])]),
        ]
        agg = aggregate_by_owner(results)
        assert agg == {
            "@org/backend": [("org/repo1", ["*.py"]), ("org/repo2", ["*.go"])],
        }

    def test_patterns_grouped_per_repo(self):
        results = [
            ("org/repo1", [("*.py", ["@org/backend"]), ("/src/", ["@org/backend"])]),
        ]
        agg = aggregate_by_owner(results)
        assert agg == {
            "@org/backend": [("org/repo1", ["*.py", "/src/"])],
        }

    def test_empty_results(self):
        assert aggregate_by_owner([]) == {}


class TestProcessRepo:
    def test_returns_parsed_result(self):
        client = MagicMock()
        client.get_repo_tree.return_value = [{"path": ".github/CODEOWNERS"}]
        client.get_file_content.return_value = "*.py @org/backend\n"
        repo = {"nameWithOwner": "org/repo1"}
        result = process_repo(client, repo)
        assert result == ("org/repo1", [("*.py", ["@org/backend"])])

    def test_returns_none_when_no_codeowners(self):
        client = MagicMock()
        client.get_repo_tree.return_value = [{"path": "README.md"}]
        repo = {"nameWithOwner": "org/repo1"}
        assert process_repo(client, repo) is None

    def test_handles_api_error(self):
        client = MagicMock()
        client.get_repo_tree.side_effect = Exception("timeout")
        repo = {"nameWithOwner": "org/repo1"}
        assert process_repo(client, repo) is None
