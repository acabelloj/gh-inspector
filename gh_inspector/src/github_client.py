import base64
import json
import subprocess
import threading
import time
from typing import Any

_MAX_CONCURRENT_REQUESTS = 8
_MAX_RETRIES = 3
_FALLBACK_RETRY_DELAYS = [15, 60, 120]


def _strip_headers(output: str) -> str:
    """Remove HTTP status line + headers from a --include response, returning the body."""
    sep = "\r\n\r\n" if "\r\n\r\n" in output else "\n\n"
    _, _, body = output.partition(sep)
    return body


def _parse_response_headers(output: str) -> dict[str, str]:
    """Parse HTTP headers from a --include response into a lower-cased dict."""
    sep = "\r\n\r\n" if "\r\n\r\n" in output else "\n\n"
    header_section, _, _ = output.partition(sep)
    headers: dict[str, str] = {}
    for line in header_section.splitlines()[1:]:  # skip the status line
        if ":" in line:
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
    return headers


def _wait_from_headers(headers: dict[str, str]) -> int | None:
    """Return seconds to wait from rate-limit response headers, or None if absent."""
    # Secondary rate limit: Retry-After is an explicit delay in seconds
    if retry_after := headers.get("retry-after"):
        try:
            return int(retry_after) + 2
        except ValueError:
            pass
    # Primary rate limit: X-RateLimit-Reset is a Unix timestamp
    if reset := headers.get("x-ratelimit-reset"):
        try:
            wait = max(0, int(reset) - int(time.time()))
            return wait + 2
        except (ValueError, TypeError):
            pass
    return None


def _command_context(args: list[str]) -> str:
    """Extract a short human-readable label from command args."""
    for arg in args:
        if arg.startswith("repos/"):
            parts = arg.split("/")
            if len(parts) >= 3:
                return f"{parts[1]}/{parts[2]}"
    for arg in reversed(args):
        if not arg.startswith("-") and arg not in ("gh", "api", "list", "repo"):
            return arg
    return "unknown"


class GitHubClient:
    """Client for interacting with GitHub CLI commands."""

    def __init__(self, timeout: int = 30, console=None):
        self.timeout = timeout
        self._semaphore = threading.Semaphore(_MAX_CONCURRENT_REQUESTS)
        self._console = console
        self._call_count = 0
        self._call_count_lock = threading.Lock()

    @property
    def call_count(self) -> int:
        return self._call_count

    def _log_rate_limit(self, wait: int, attempt: int, total: int, context: str, from_gh: bool) -> None:
        if self._console is None:
            return
        source = "GitHub" if from_gh else "fallback"
        self._console.log(
            f"[yellow]⏸ Rate limited[/yellow] [dim]{context}[/dim] — "
            f"waiting {wait}s [{source}] (attempt {attempt}/{total})"
        )

    def _log_resuming(self, context: str) -> None:
        if self._console is not None:
            self._console.log(f"[green]↺ Resuming[/green] [dim]{context}[/dim]")

    def run_command(self, args: list[str], timeout: int = None) -> str:
        timeout = self.timeout if timeout is None else timeout
        context = _command_context(args)

        # Add --include to gh api calls so we can read rate-limit headers on failure
        is_api = len(args) >= 2 and args[0] == "gh" and args[1] == "api"
        effective_args = args + ["--include"] if is_api else args

        for attempt in range(_MAX_RETRIES + 1):
            with self._semaphore:
                try:
                    result = subprocess.run(effective_args, capture_output=True, text=True, timeout=timeout)
                except subprocess.TimeoutExpired as e:
                    raise Exception(f"Command '{' '.join(args)}' timed out after {timeout} seconds") from e
                with self._call_count_lock:
                    self._call_count += 1
                if result.returncode == 0:
                    body = _strip_headers(result.stdout) if is_api else result.stdout
                    return body.strip()
                is_rate_limited = "rate limit" in result.stderr.lower()
                if not is_rate_limited or attempt == _MAX_RETRIES:
                    raise Exception(f"Error executing command '{' '.join(args)}': {result.stderr}")
            # Rate limited — determine wait from response headers
            headers = _parse_response_headers(result.stdout) if is_api else {}
            gh_wait = _wait_from_headers(headers)
            wait = gh_wait or _FALLBACK_RETRY_DELAYS[attempt]
            self._log_rate_limit(wait, attempt + 1, _MAX_RETRIES, context, from_gh=gh_wait is not None)
            time.sleep(wait)
            self._log_resuming(context)
        raise Exception(f"Rate limit exceeded after {_MAX_RETRIES} retries for: {' '.join(args)}")

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
