import json
from unittest.mock import MagicMock, patch

import pytest
from github_client import GitHubClient


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

    def test_get_repos_python_only(self):
        repos = [{"nameWithOwner": "org/repo", "isPrivate": False}]
        with patch.object(self.client, "run_command", return_value=json.dumps(repos)) as mock_cmd:
            result = self.client.get_repos("org")
            assert result == repos
            assert "--language" in mock_cmd.call_args[0][0]
            assert "Python" in mock_cmd.call_args[0][0]

    def test_get_repos_all(self):
        repos = [{"nameWithOwner": "org/repo", "isPrivate": False}]
        with patch.object(self.client, "run_command", return_value=json.dumps(repos)) as mock_cmd:
            self.client.get_repos("org", all_repositories=True)
            assert "--language" not in mock_cmd.call_args[0][0]

    def test_get_default_branch(self):
        with patch.object(self.client, "run_command", return_value="main"):
            assert self.client.get_default_branch("org/repo") == "main"

    def test_get_default_branch_fallback(self):
        with patch.object(self.client, "run_command", side_effect=Exception("error")):
            assert self.client.get_default_branch("org/repo") == "main"

    def test_get_file_content(self):
        import base64

        encoded = base64.b64encode(b"file content").decode()
        api_response = json.dumps({"content": encoded + "\n"})
        with patch.object(self.client, "run_command", return_value=api_response):
            result = self.client.get_file_content("org/repo", "README.md")
            assert result == "file content"
