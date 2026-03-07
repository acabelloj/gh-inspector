import base64
import json
import subprocess
import threading
import time
from typing import Any

_MAX_CONCURRENT_REQUESTS = 8
_RATE_LIMIT_RETRY_DELAYS = [10, 30, 60]


class GitHubClient:
    """Client for interacting with GitHub CLI commands."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._semaphore = threading.Semaphore(_MAX_CONCURRENT_REQUESTS)

    def run_command(self, args: list[str], timeout: int = None) -> str:
        timeout = self.timeout if timeout is None else timeout
        for attempt, retry_delay in enumerate([None] + _RATE_LIMIT_RETRY_DELAYS):
            if retry_delay is not None:
                time.sleep(retry_delay)
            with self._semaphore:
                try:
                    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
                except subprocess.TimeoutExpired as e:
                    raise Exception(f"Command '{' '.join(args)}' timed out after {timeout} seconds") from e
                if result.returncode == 0:
                    return result.stdout.strip()
                is_rate_limited = "rate limit" in result.stderr.lower()
                if not is_rate_limited or attempt == len(_RATE_LIMIT_RETRY_DELAYS):
                    raise Exception(f"Error executing command '{' '.join(args)}': {result.stderr}")
        raise Exception(f"Rate limit exceeded after retries for: {' '.join(args)}")

    def get_repos(
        self, org_name: str, all_repositories: bool = False, extra_fields: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Get repositories for an organization.

        Args:
            org_name: GitHub organization name
            all_repositories: If True, get all repos. If False, filter by Python language
            extra_fields: Additional fields to include in the --json query

        Returns:
            List of repository information dictionaries
        """
        fields = "nameWithOwner,isPrivate"
        if extra_fields:
            fields += "," + ",".join(extra_fields)
        args = [
            "gh",
            "repo",
            "list",
            org_name,
            "--limit",
            "1000",
            "--no-archived",
            "--source",
            "--json",
            fields,
        ]
        if not all_repositories:
            args += ["--language", "Python"]
        result = self.run_command(args)
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
            result = self.run_command(["gh", "api", f"repos/{repo_name}", "--jq", ".default_branch"])
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
        result = self.run_command(["gh", "api", f"repos/{repo_name}/git/trees/{branch}?recursive=1"])
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
        result = self.run_command(["gh", "api", f"repos/{repo_name}/contents/{file_path}"])
        content = json.loads(result)["content"]
        return base64.b64decode(content).decode("utf-8")
