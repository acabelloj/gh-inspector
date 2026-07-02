import base64
import json
import time
from unittest.mock import MagicMock, patch

import pytest
from github_client import GitHubClient, _command_context


class TestCommandContext:
    def test_labels_drop_query_and_recognize_endpoints(self):
        assert _command_context(["gh", "api", "repos/org/repo/contents/uv.lock"]) == "org/repo"
        assert _command_context(["gh", "api", "--paginate", "orgs/myorg/repos?per_page=100"]) == "repo list (myorg)"
        assert (
            _command_context(["gh", "api", "--paginate", "users/someone/repos?per_page=100"]) == "repo list (someone)"
        )
        assert (
            _command_context(["gh", "api", "--paginate", "user/repos?per_page=100&affiliation=owner"])
            == "repo list (self)"
        )
        assert _command_context(["gh", "api", "rate_limit", "--jq", ".resources.core.reset"]) == "rate_limit"


class TestGitHubClient:
    def setup_method(self):
        self.client = GitHubClient()

    def test_run_command_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="output\n", stderr="")
            result = self.client.run_command(["echo", "hello"])
            assert result == "output"

    def test_run_command_failure(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
            with pytest.raises(Exception, match="Error executing command"):
                self.client.run_command(["bad", "command"])

    def _paginated(self, *rest_repos, owner_type="Organization", login="someone-else"):
        """Fake run_command covering the endpoint probes + the --slurp repo pages.

        ``gh api users/<name>`` -> account object (drives org-vs-user);
        ``gh api user --jq .login`` -> the authenticated login (drives self-vs-other);
        ``gh api --paginate --slurp ...`` -> one page array of the fixture repos.
        """

        def side_effect(args, timeout=None):
            if "--paginate" in args:
                return json.dumps([list(rest_repos)])
            if args[-1] == ".login":  # gh api user --jq .login
                return login
            return json.dumps({"type": owner_type})  # gh api users/<name>

        return side_effect

    def test_get_repos_python_only_filters_client_side(self):
        rest = [
            {"full_name": "org/py", "private": False, "language": "Python", "archived": False},
            {"full_name": "org/js", "private": False, "language": "JavaScript", "archived": False},
        ]
        with patch.object(self.client, "run_command", side_effect=self._paginated(*rest)):
            result = self.client.get_repos("org")
        assert [r["nameWithOwner"] for r in result] == ["org/py"]

    def test_get_repos_all_includes_non_python(self):
        rest = [
            {"full_name": "org/py", "private": False, "language": "Python", "archived": False},
            {"full_name": "org/js", "private": True, "language": "JavaScript", "archived": False},
        ]
        with patch.object(self.client, "run_command", side_effect=self._paginated(*rest)):
            result = self.client.get_repos("org", all_repositories=True)
        assert {r["nameWithOwner"] for r in result} == {"org/py", "org/js"}

    def test_get_repos_excludes_archived_and_forks(self):
        rest = [
            {"full_name": "org/live", "private": False, "language": "Python", "archived": False, "fork": False},
            {"full_name": "org/dead", "private": False, "language": "Python", "archived": True, "fork": False},
            {"full_name": "org/forked", "private": False, "language": "Python", "archived": False, "fork": True},
        ]
        with patch.object(self.client, "run_command", side_effect=self._paginated(*rest)):
            result = self.client.get_repos("org", all_repositories=True)
        assert [r["nameWithOwner"] for r in result] == ["org/live"]

    def test_get_repos_skips_empty_repos(self):
        # size 0 == no commits; the tree endpoint 409s on these, so they're skipped.
        rest = [
            {"full_name": "org/has-code", "private": False, "language": "Python", "archived": False, "size": 42},
            {"full_name": "org/empty", "private": False, "language": "Python", "archived": False, "size": 0},
        ]
        with patch.object(self.client, "run_command", side_effect=self._paginated(*rest)):
            result = self.client.get_repos("org", all_repositories=True)
        assert [r["nameWithOwner"] for r in result] == ["org/has-code"]

    def test_get_repos_maps_rest_fields(self):
        rest = [
            {
                "full_name": "org/repo",
                "private": True,
                "language": "Python",
                "archived": False,
                "default_branch": "master",
                "license": {"spdx_id": "MIT"},
            }
        ]
        with patch.object(self.client, "run_command", side_effect=self._paginated(*rest)):
            (repo,) = self.client.get_repos("org", all_repositories=True)
        assert repo == {
            "nameWithOwner": "org/repo",
            "isPrivate": True,
            "defaultBranchRef": {"name": "master"},
            "licenseInfo": {"spdxId": "MIT"},
        }

    def _paginate_path(self, mock) -> str:
        """Return the endpoint arg of the --paginate call recorded on ``mock``."""
        call = [c for c in mock.call_args_list if "--paginate" in c[0][0]][0]
        return next(a for a in call[0][0] if "repos" in a)

    def test_get_repos_uses_orgs_endpoint_for_org(self):
        rest = [{"full_name": "org/r", "private": False, "language": "Python", "archived": False}]
        with patch.object(
            self.client, "run_command", side_effect=self._paginated(*rest, owner_type="Organization")
        ) as m:
            self.client.get_repos("org", all_repositories=True)
        assert self._paginate_path(m).startswith("orgs/org/repos")

    def test_get_repos_uses_public_users_endpoint_for_other_user(self):
        rest = [{"full_name": "someone/r", "private": False, "language": "Python", "archived": False}]
        side = self._paginated(*rest, owner_type="User", login="me")
        with patch.object(self.client, "run_command", side_effect=side) as m:
            self.client.get_repos("someone", all_repositories=True)  # not the auth'd user
        assert self._paginate_path(m).startswith("users/someone/repos")

    def test_get_repos_uses_authenticated_endpoint_for_self(self):
        # The authenticated login matches the target -> use /user/repos so PRIVATE repos are included.
        rest = [{"full_name": "me/r", "private": True, "language": "Python", "archived": False}]
        side = self._paginated(*rest, owner_type="User", login="me")
        with patch.object(self.client, "run_command", side_effect=side) as m:
            self.client.get_repos("me", all_repositories=True)
        assert self._paginate_path(m).startswith("user/repos")

    def test_get_repos_self_check_is_case_insensitive(self):
        # GitHub logins are case-insensitive; scanning your own login in a different
        # case must still use /user/repos (else private repos are silently dropped).
        rest = [{"full_name": "Me/r", "private": True, "language": "Python", "archived": False}]
        side = self._paginated(*rest, owner_type="User", login="me")  # auth login is lowercase "me"
        with patch.object(self.client, "run_command", side_effect=side) as m:
            self.client.get_repos("Me", all_repositories=True)  # target differs only by case
        assert self._paginate_path(m).startswith("user/repos")

    def test_get_repos_reraises_non_404_probe_error(self):
        # A transport/auth failure on the account probe must NOT be silently treated as a user.
        def side_effect(args, timeout=None):
            if "--paginate" in args:
                raise AssertionError("must not reach the repo fetch after a probe error")
            raise Exception("Error executing command: dial tcp: network is unreachable")

        with patch.object(self.client, "run_command", side_effect=side_effect):
            with pytest.raises(Exception, match="network is unreachable"):
                self.client.get_repos("whoknows", all_repositories=True)

    def test_get_repos_treats_404_probe_as_user(self):
        # A genuine 404 on users/<name> means "not an org" -> fall through to user endpoints.
        def side_effect(args, timeout=None):
            if "--paginate" in args:
                return json.dumps([[]])
            if args[-1] == ".login":
                return "me"
            raise Exception("gh: Not Found (HTTP 404)")

        with patch.object(self.client, "run_command", side_effect=side_effect) as m:
            self.client.get_repos("ghost", all_repositories=True)
        assert self._paginate_path(m).startswith("users/ghost/repos")

    def test_get_default_branch(self):
        with patch.object(self.client, "run_command", return_value="main"):
            assert self.client.get_default_branch("org/repo") == "main"

    def test_get_default_branch_fallback(self):
        with patch.object(self.client, "run_command", side_effect=Exception("error")):
            assert self.client.get_default_branch("org/repo") == "main"

    def test_get_file_content(self):
        encoded = base64.b64encode(b"file content").decode()
        api_response = json.dumps({"content": encoded + "\n"})
        with patch.object(self.client, "run_command", return_value=api_response):
            result = self.client.get_file_content("org/repo", "README.md")
            assert result == "file content"

    def test_get_repos_uses_repo_list_timeout_on_paginate(self):
        rest = {"full_name": "org/repo", "private": False, "language": "Python", "archived": False}
        client = GitHubClient(repo_list_timeout=99)
        with patch.object(client, "run_command", side_effect=self._paginated(rest)) as m:
            client.get_repos("org", all_repositories=True)
        paginate_call = [c for c in m.call_args_list if "--paginate" in c[0][0]][0]
        assert paginate_call.kwargs["timeout"] == 99


class TestGitHubClientCache:
    def test_hit_skips_subprocess_and_call_count(self):
        cache = MagicMock()
        cache.get.return_value = "cached body"
        client = GitHubClient(cache=cache)
        with patch("subprocess.run") as mock_run:
            result = client.run_command(["gh", "api", "repos/org/repo"])
        assert result == "cached body"
        mock_run.assert_not_called()
        assert client.call_count == 0
        cache.set.assert_not_called()

    def test_miss_falls_through_and_writes(self):
        cache = MagicMock()
        cache.get.return_value = None
        client = GitHubClient(cache=cache)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="fresh\n", stderr="")
            result = client.run_command(["gh", "repo", "list", "org"])
        assert result == "fresh"
        assert client.call_count == 1
        cache.set.assert_called_once_with(["gh", "repo", "list", "org"], "fresh")

    def test_empty_body_is_not_cached(self):
        # A returncode-0 call with blank output is a transient glitch; caching "" would
        # replay the failure (e.g. json.loads("")) for the whole TTL.
        cache = MagicMock()
        cache.get.return_value = None
        client = GitHubClient(cache=cache)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="  \n", stderr="")
            result = client.run_command(["gh", "api", "--paginate", "--slurp", "orgs/o/repos"])
        assert result == ""
        cache.set.assert_not_called()

    def test_errors_are_not_cached(self):
        cache = MagicMock()
        cache.get.return_value = None
        client = GitHubClient(cache=cache)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
            with pytest.raises(Exception, match="Error executing command"):
                client.run_command(["gh", "repo", "list", "org"])
        cache.set.assert_not_called()


class TestRateLimitBackoff:
    def test_paginate_rate_limit_uses_rate_limit_api_for_wait(self):
        # A --paginate call carries no headers; the backoff must consult gh api rate_limit
        # (rather than only the fixed fallback) to get the precise reset.
        client = GitHubClient()
        reset_at = int(time.time()) + 7
        rl = MagicMock(returncode=0, stdout=f"{reset_at}\n")
        rate_limited = MagicMock(returncode=1, stdout="", stderr="API rate limit exceeded")
        ok = MagicMock(returncode=0, stdout="[[]]\n", stderr="")
        slept = []
        with (
            patch("subprocess.run", side_effect=[rate_limited, rl, ok]) as mock_run,
            patch("time.sleep", side_effect=slept.append),
        ):
            client.run_command(["gh", "api", "--paginate", "--slurp", "orgs/o/repos"])
        # rate_limit endpoint was queried, and we slept ~7s (from the reset), not the 15s fallback.
        assert any("rate_limit" in c[0][0] for c in mock_run.call_args_list)
        assert slept and 5 <= slept[0] <= 12

    def test_rate_limit_api_failure_falls_back_to_fixed_delay(self):
        client = GitHubClient()
        rate_limited = MagicMock(returncode=1, stdout="", stderr="API rate limit exceeded")
        rl_fail = MagicMock(returncode=1, stdout="", stderr="boom")
        ok = MagicMock(returncode=0, stdout="[[]]\n", stderr="")
        slept = []
        with (
            patch("subprocess.run", side_effect=[rate_limited, rl_fail, ok]),
            patch("time.sleep", side_effect=slept.append),
        ):
            client.run_command(["gh", "api", "--paginate", "--slurp", "orgs/o/repos"])
        assert slept and slept[0] == 15  # _FALLBACK_RETRY_DELAYS[0]
