import base64
import json
import subprocess
import threading
import time
from typing import Any

from cache import ResponseCache

_MAX_CONCURRENT_REQUESTS = 8
_MAX_RETRIES = 3
_FALLBACK_RETRY_DELAYS = [15, 60, 120]
_REPO_LIST_TIMEOUT = 120


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


def _repo_from_rest(repo: dict[str, Any]) -> dict[str, Any]:
    """Map a REST repository object to the GraphQL-ish shape callers expect."""
    branch = repo.get("default_branch")
    spdx = (repo.get("license") or {}).get("spdx_id")
    return {
        "nameWithOwner": repo["full_name"],
        "isPrivate": repo.get("private", False),
        "defaultBranchRef": {"name": branch} if branch else None,
        "licenseInfo": {"spdxId": spdx} if spdx else None,
    }


def _command_context(args: list[str]) -> str:
    """Extract a short human-readable label from command args (query strings dropped)."""
    for arg in args:
        path = arg.split("?", 1)[0]  # drop any ?query
        if path.startswith("repos/"):
            parts = path.split("/")
            if len(parts) >= 3:
                return f"{parts[1]}/{parts[2]}"
        # Repo-list endpoints: orgs/<x>/repos, users/<x>/repos, user/repos
        if path == "user/repos":
            return "repo list (self)"
        if path.startswith(("orgs/", "users/")) and path.endswith("/repos"):
            return f"repo list ({path.split('/')[1]})"
        if path == "rate_limit":
            return "rate_limit"
    for arg in reversed(args):
        if not arg.startswith("-") and arg not in ("gh", "api", "list", "repo"):
            return arg.split("?", 1)[0]
    return "unknown"


class GitHubClient:
    """Client for interacting with GitHub CLI commands."""

    def __init__(
        self,
        timeout: int = 30,
        console=None,
        cache: ResponseCache | None = None,
        verbose: bool = False,
        repo_list_timeout: int = _REPO_LIST_TIMEOUT,
    ):
        self.timeout = timeout
        self.repo_list_timeout = repo_list_timeout
        self._semaphore = threading.Semaphore(_MAX_CONCURRENT_REQUESTS)
        self._console = console
        self._cache = cache
        self._verbose = verbose
        self._call_count = 0
        self._call_count_lock = threading.Lock()
        self._errors: list[dict[str, str]] = []
        self._errors_lock = threading.Lock()

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def errors(self) -> list[dict[str, str]]:
        """Repos that failed during the scan, as ``{"repo": ..., "error": ...}`` dicts."""
        with self._errors_lock:
            return list(self._errors)

    def record_error(self, repo: str, message: str) -> None:
        """Record a per-repo failure for the run summary (thread-safe)."""
        with self._errors_lock:
            self._errors.append({"repo": repo, "error": message})

    @property
    def console(self):
        """Console for progress/error output, routed to stderr in json mode."""
        return self._console

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

    def _log_verbose(self, message: str) -> None:
        if self._verbose and self._console is not None:
            self._console.log(f"[dim]{message}[/dim]")

    def run_command(self, args: list[str], timeout: int = None) -> str:
        timeout = self.timeout if timeout is None else timeout
        context = _command_context(args)

        if self._cache is not None and (hit := self._cache.get(args)) is not None:
            self._log_verbose(f"⚡ cache hit {context}")
            return hit

        # Add --include to gh api calls so we can read rate-limit headers on failure.
        # Skip it for --paginate, where --include would interleave per-page headers
        # into the body and break JSON parsing; those calls fall back to stderr-based
        # rate-limit detection and the fallback delays.
        is_api = len(args) >= 2 and args[0] == "gh" and args[1] == "api"
        include_headers = is_api and "--paginate" not in args
        effective_args = args + ["--include"] if include_headers else args

        for attempt in range(_MAX_RETRIES + 1):
            with self._semaphore:
                self._log_verbose(f"→ {' '.join(args)}")
                try:
                    result = subprocess.run(effective_args, capture_output=True, text=True, timeout=timeout)
                except subprocess.TimeoutExpired as e:
                    raise Exception(f"Command '{' '.join(args)}' timed out after {timeout} seconds") from e
                with self._call_count_lock:
                    self._call_count += 1
                if result.returncode == 0:
                    body = _strip_headers(result.stdout) if include_headers else result.stdout
                    body = body.strip()
                    # Don't cache an empty body: a blank result from a returncode-0 gh call
                    # is almost always a transient glitch, and caching it would replay the
                    # failure (e.g. json.loads("")) for the whole TTL.
                    if self._cache is not None and body:
                        self._cache.set(args, body)
                    return body
                is_rate_limited = "rate limit" in result.stderr.lower()
                if not is_rate_limited or attempt == _MAX_RETRIES:
                    raise Exception(f"Error executing command '{' '.join(args)}': {result.stderr}")
            # Rate limited — determine wait from response headers when available, else
            # (e.g. --paginate calls with no captured headers) probe the rate_limit
            # endpoint for the precise reset before falling back to fixed delays.
            headers = _parse_response_headers(result.stdout) if include_headers else {}
            gh_wait = _wait_from_headers(headers) or self._wait_from_rate_limit_api()
            wait = gh_wait or _FALLBACK_RETRY_DELAYS[attempt]
            self._log_rate_limit(wait, attempt + 1, _MAX_RETRIES, context, from_gh=gh_wait is not None)
            time.sleep(wait)
            self._log_resuming(context)
        raise Exception(f"Rate limit exceeded after {_MAX_RETRIES} retries for: {' '.join(args)}")

    def _wait_from_rate_limit_api(self) -> int | None:
        """Seconds until the core rate limit resets, via ``gh api rate_limit``, or None.

        Used when a rate-limited call carried no headers to read (``--paginate``). The
        ``rate_limit`` endpoint does not itself count against the limit; any failure
        returns None so the caller falls back to fixed delays.
        """
        try:
            reset = subprocess.run(
                ["gh", "api", "rate_limit", "--jq", ".resources.core.reset"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if reset.returncode != 0:
                return None
            return max(0, int(reset.stdout.strip()) - int(time.time())) + 2
        except (subprocess.SubprocessError, ValueError):
            return None

    def get_repos(
        self, org_name: str, all_repositories: bool = False, extra_fields: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Get repositories for an organization or user.

        Paginates the REST API so orgs with more than 1000 repositories are fully
        covered (``gh repo list`` hard-caps at 1000 regardless of ``--limit``).
        Private repos the token can see are included for orgs and for the token's own
        account; another user's private repos are not exposed by the API. Forks and
        archived repos are excluded here (matching the old ``--source --no-archived``),
        as are non-Python repos when ``all_repositories`` is False.

        Args:
            org_name: GitHub organization or user name
            all_repositories: If True, get all repos. If False, filter by Python language
            extra_fields: Accepted for backward compatibility; REST always returns
                the underlying fields, so this is ignored.

        Returns:
            Repository dicts in the shape callers expect: ``nameWithOwner``,
            ``isPrivate``, ``defaultBranchRef.name`` and ``licenseInfo.spdxId``.
        """
        path = self._repos_endpoint(org_name)
        # --slurp wraps each page as its own array (a single reliable JSON value even
        # across many pages); flatten the pages back into one repo list.
        raw = self.run_command(["gh", "api", "--paginate", "--slurp", path], timeout=self.repo_list_timeout)
        repos = []
        for repo in (r for page in json.loads(raw) for r in page):
            if repo.get("archived") or repo.get("fork"):
                continue
            # Empty repos (no commits) report size 0; the tree endpoint 409s on them,
            # so skip rather than scan-then-error. GraphQL's defaultBranchRef was null
            # for these; REST always populates default_branch, so filter on size.
            if repo.get("size") == 0:
                continue
            if not all_repositories and repo.get("language") != "Python":
                continue
            repos.append(_repo_from_rest(repo))
        return repos

    def _repos_endpoint(self, name: str) -> str:
        """Pick the REST repos endpoint for ``name`` (org, the authenticated user, or another user).

        ``orgs/<name>/repos`` and the authenticated-user ``user/repos`` return private
        repos the token can see; ``users/<name>/repos`` (another user) is public-only,
        which is all the API exposes. GitHub logins are case-insensitive, so the
        self-check compares case-folded. Only a genuine 404 means "not an org" — other
        errors (network, auth, rate limit) are re-raised rather than silently mistaking
        a failure for a user and querying the wrong endpoint.
        """
        # The authenticated-user object carries the login; check self first so scanning
        # your own account needs no extra users/<name> probe.
        if self._authenticated_login() == name.lower():
            return "user/repos?per_page=100&affiliation=owner"
        if self._get_account(name).get("type") == "Organization":
            return f"orgs/{name}/repos?per_page=100"
        return f"users/{name}/repos?per_page=100"

    def _authenticated_login(self) -> str | None:
        """Case-folded login of the token's own account, or None if it can't be read."""
        try:
            return self.run_command(["gh", "api", "user", "--jq", ".login"]).lower()
        except Exception:
            return None

    def _get_account(self, name: str) -> dict[str, Any]:
        """Return the ``users/<name>`` account object, treating a 404 as an empty dict."""
        try:
            return json.loads(self.run_command(["gh", "api", f"users/{name}"]))
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                return {}
            raise

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
