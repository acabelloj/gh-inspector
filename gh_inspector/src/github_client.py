import base64
import json
import subprocess
from typing import Any


class GitHubClient:
    """Client for interacting with GitHub CLI commands."""

    def __init__(self, timeout: int = 30):
        """
        Initialize the GitHub client.

        Args:
            timeout: Default timeout for commands in seconds
        """
        self.timeout = timeout

    def run_command(self, command: str, timeout: int = None) -> str:
        """
        Execute a GitHub CLI command.

        Args:
            command: The command to execute
            timeout: Optional timeout override for this command

        Returns:
            The command output as a string

        Raises:
            Exception: If the command fails or times out
        """
        timeout = timeout or self.timeout
        try:
            result = subprocess.run(command, capture_output=True, text=True, shell=True, timeout=timeout)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                raise Exception(f"Error executing command '{command}': {result.stderr}")
        except subprocess.TimeoutExpired as e:
            raise Exception(f"Command '{command}' timed out after {timeout} seconds") from e

    def get_repos(self, org_name: str, all_repositories: bool = False) -> list[dict[str, Any]]:
        """
        Get repositories for an organization.

        Args:
            org_name: GitHub organization name
            all_repositories: If True, get all repos. If False, filter by Python language

        Returns:
            List of repository information dictionaries
        """
        filter_by_language = "--language Python" if not all_repositories else ""
        command = f"gh repo list {org_name} --limit 1000 {filter_by_language} --no-archived --source --json nameWithOwner,isPrivate"
        result = self.run_command(command)
        return json.loads(result)

    def get_default_branch(self, repo_name: str) -> str:
        """
        Get the default branch name for a repository.

        Args:
            repo_name: Full repository name (owner/repo)

        Returns:
            The default branch name (e.g., 'main', 'master')
        """
        try:
            command = f"gh api repos/{repo_name} --jq .default_branch"
            result = self.run_command(command)
            return result.strip() or "main"
        except Exception:
            return "main"

    def get_repo_tree(self, repo_name: str, branch: str = None) -> list[dict[str, Any]]:
        """
        Get the file tree of a repository.

        Args:
            repo_name: Full repository name (owner/repo)
            branch: Branch name (default: auto-detect from repository)

        Returns:
            List of file/directory information
        """
        if branch is None:
            branch = self.get_default_branch(repo_name)

        command = f"gh api repos/{repo_name}/git/trees/{branch}?recursive=1"
        result = self.run_command(command)
        return json.loads(result)["tree"]

    def get_file_content(self, repo_name: str, file_path: str) -> str:
        """
        Get the content of a file from a repository.

        Args:
            repo_name: Full repository name (owner/repo)
            file_path: Path to the file in the repository

        Returns:
            Decoded file content as a string
        """
        command = f"gh api repos/{repo_name}/contents/{file_path}"
        result = self.run_command(command)
        content = json.loads(result)["content"]
        return base64.b64decode(content).decode("utf-8")
