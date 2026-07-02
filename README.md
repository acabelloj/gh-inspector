# gh-inspector

[![PyPI version](https://img.shields.io/pypi/v/gh-inspector)](https://pypi.org/project/gh-inspector/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/gh-inspector)](https://pypi.org/project/gh-inspector/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A CLI tool that uses the GitHub CLI (`gh`) to rapidly locate and inspect files in remote GitHub repositories — without cloning them.

## Requirements

- [GitHub CLI (`gh`)](https://cli.github.com/) — authenticated via `gh auth login` or `GH_TOKEN`
- Python 3.10+

## Authentication

`gh-inspector` delegates authentication entirely to the `gh` CLI. The recommended approaches:

```bash
# Persistent login (recommended for local use)
gh auth login

# Token via environment variable
export GH_TOKEN=ghp_yourtoken
```

### 1Password (or any secret manager)

`op run` needs to know which secrets to inject. Use `--env-file` with a `.env` file:

```bash
# 1. Copy the example and fill in your 1Password reference
cp .env.example .env

# 2. Edit .env — the format is op://<vault>/<item>/<field>
# Example:
#   GH_TOKEN=op://Personal/GitHub/token

# 3. Find your exact reference if unsure:
op item list | grep -i github
op item get "GitHub" --fields label=token

# 4. Run with secret injection
op run --env-file=.env -- make e2e
```

## Installation

```bash
pip install gh-inspector
```

Or with `uv`:

```bash
uv tool install gh-inspector
```

## Global options

These apply to every command and may be passed before or after the subcommand.
Each also reads a default from an environment variable; an explicit flag always
wins over the environment variable, which in turn wins over the built-in default.

| Option | Env var | Default | Description |
|---|---|---|---|
| `--output` / `-o` | — | `rich` | Output encoding: `rich` (decorated tables) or `json` (machine-readable). |
| `--no-cache` | `GH_INSPECTOR_NO_CACHE` | `false` | Bypass the on-disk cache: fetch fresh data and leave existing cache entries untouched. |
| `--clear-cache` | `GH_INSPECTOR_CLEAR_CACHE` | `false` | Delete all cached entries before running, then repopulate from this run. |
| `--cache-ttl` | `GH_INSPECTOR_CACHE_TTL` | `3600` | How long (seconds) cached responses stay fresh. |
| `--timeout` | `GH_INSPECTOR_TIMEOUT` | `30` | Per-request timeout (seconds) for `gh` calls. |
| `--verbose` | `GH_INSPECTOR_VERBOSE` | `false` | Log each `gh` command and cache hit/miss. |
| `--quiet` / `-q` | `GH_INSPECTOR_QUIET` | `false` | Suppress the progress bar, totals, and rate-limit logs. Errors still print. |

### JSON output

With `-o json`, stdout is pure JSON: the command's results plus a `summary` block
describing what was explored. Because the live progress bar goes to stderr (and is
hidden by `--quiet` or when there is no terminal), the summary is how an automated
consumer knows a complete empty result from a scan that died partway.

```jsonc
{
  "summary": {
    "org": "python",
    "all_repositories": true,
    "repos_scanned": 120,       // repositories fetched and scanned
    "repos_with_matches": 18,   // repositories that matched (command-specific)
    "repos_errored": 2,         // repositories that failed during the scan
    "errored_repos": ["python/cpython", "python/mypy"],
    "gh_api_calls": 214,
    "libraries_requested": ["requests"]   // present for find-python-library
  },
  "libraries": { /* ... results ... */ }
}
```

Progress, rate-limit notices, and per-repo errors are written to **stderr**, so
`... -o json > results.json` captures only the JSON while diagnostics still reach
your terminal. Rich (non-JSON) output shows the same scan stats live in the
progress bar and the closing totals line.

### Caching

Successful `gh` responses (repo lists, trees, file contents) are cached as JSON
files under `$XDG_CACHE_HOME/gh-inspector/` (falling back to `~/.cache/gh-inspector/`),
so re-running the tool in quick succession skips the downloads. Each entry is keyed
by the exact `gh` command and expires after `--cache-ttl` seconds (1 hour by default).

```bash
# First run downloads everything and populates the cache
gh-inspector find-python-library my-org requests

# A second run within the hour reuses the cache — near-instant, zero API calls
gh-inspector find-python-library my-org requests boto3

# Keep results fresh for longer (e.g. a full day) or expire them sooner
gh-inspector --cache-ttl 86400 find-python-library my-org requests
GH_INSPECTOR_CACHE_TTL=86400 gh-inspector find-python-library my-org requests
```

**Forcing fresh data.** There are two ways, and they differ in what they do to the
stored cache:

| Flag | Reads fresh data | Existing entries | Caches this run |
|---|---|---|---|
| `--no-cache` | yes | left untouched | no |
| `--clear-cache` | yes | **deleted first** | yes |

- `--no-cache` bypasses the cache for one run without touching what is already
  stored — use it for a quick one-off when you suspect data changed but want to
  keep your cache warm for later.
- `--clear-cache` wipes every cached entry first, then runs and repopulates the
  cache — use it when you want a guaranteed clean slate (and to benefit from
  caching on subsequent runs).

If both are given, `--no-cache` wins: it means "leave the stored cache untouched",
so the `--clear-cache` wipe is skipped.

```bash
# One-off fresh read; stored cache is preserved
gh-inspector --no-cache find-python-library my-org requests

# Clean slate: delete all cached entries, then run and re-cache
gh-inspector --clear-cache find-python-library my-org requests
```

### Managing the cache

The `cache` subcommand inspects and manages the cache directly, without running a
scan:

```bash
gh-inspector cache path     # print the cache directory
gh-inspector cache info     # directory + entry count + total size
gh-inspector cache clear    # delete every cached entry, report how many
```

All three honor `-o json` for scripting:

```bash
gh-inspector -o json cache info
# { "path": "…/gh-inspector", "entries": 3406, "bytes": 63771648 }

gh-inspector -o json cache clear
# { "cleared": 3406 }
```

`cache clear` is the standalone equivalent of removing the directory by hand
(`rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/gh-inspector"`); unlike `--clear-cache`, it
does not run a scan afterwards.

### Large organizations

The repository list is fetched with `gh api --paginate`, which pages through the
GitHub API and has **no 1000-repo ceiling** (the `gh repo list` command caps at
1000 regardless of any limit). Organizations with thousands of repositories are
therefore covered in full, not silently truncated at 1000.

Scanning a very large org is inherently slow (one tree lookup plus a file fetch
per matching repo), so the first run against thousands of repos can take several
minutes; the cache makes subsequent runs fast.

## Commands

### `find-python-library`

Scan dependency files across all repositories in a GitHub organization and report which version of a library each repo uses.

```bash
gh-inspector find-python-library <org> <library> [library2 ...]
```

**Examples:**

```bash
# Find Django and requests versions across the org
gh-inspector find-python-library myorg django requests

# Scan only uv.lock files
gh-inspector find-python-library myorg typer --file-types uv.lock

# Scan only dev requirements
gh-inspector find-python-library myorg pytest --file-types requirements-dev.txt

# Scan all requirements txt files (use quotes for globs in shell)
gh-inspector find-python-library myorg django --file-types "requirements*.txt"

# Search all repos, not just Python ones
gh-inspector find-python-library myorg pydantic --all-repositories

# List only repo names (no version breakdown)
gh-inspector find-python-library myorg fastapi --format only_repo
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--format` / `-f` | `default` | Output format: `default` or `only_repo` |
| `--file-types` / `-t` | all | File types to scan (repeatable) |
| `--all-repositories` / `-a` | `false` | Include non-Python repos |

**Supported file types:** `requirements*.txt`, `requirements*.in`, `uv.lock`, `poetry.lock`, `Pipfile.lock`, `setup.cfg`

---

### `find-codeowners`

Scan repositories in a GitHub organization for `CODEOWNERS` files, parse them, and display a tree grouped by owner showing their repos and file patterns.

```bash
gh-inspector find-codeowners <org>
```

**Examples:**

```bash
# Show CODEOWNERS tree for all repos in the org
gh-inspector find-codeowners myorg

# Filter to a specific team
gh-inspector find-codeowners myorg -t @myorg/backend

# Filter to multiple teams
gh-inspector find-codeowners myorg -t @myorg/backend -t @myorg/frontend

# List only repo names that have a CODEOWNERS file
gh-inspector find-codeowners myorg -f only_repo

# Only scan Python repos
gh-inspector find-codeowners myorg --python-only

# Hide repos that don't have a CODEOWNERS file
gh-inspector find-codeowners myorg --skip-missing
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--format` / `-f` | `default` | Output format: `default` (tree by owner) or `only_repo` |
| `--team` / `-t` | all | Filter to specific owner(s) (repeatable) |
| `--python-only` / `-p` | `false` | Only scan Python repos |
| `--skip-missing` | `false` | Hide repos without CODEOWNERS |

**Searched paths:** `.github/CODEOWNERS`, `CODEOWNERS`, `docs/CODEOWNERS` (first found wins)

**Sample output:**

```
CODEOWNERS by Owner
├── @org/backend-team
│   ├── org/repo1 (*.py, /src/)
│   └── org/repo2 (*.go)
├── @org/docs-team
│   └── org/repo1 (docs/)
└── @user
    └── org/repo3 (*)
```

---

### `find-python-version`

Detect which Python version each repository targets, by scanning Dockerfiles, `pyproject.toml`, `.python-version`, GitHub Actions workflows, and more.

```bash
gh-inspector find-python-version <org>
```

**Examples:**

```bash
# Scan all Python repos in the org
gh-inspector find-python-version myorg

# Limit to specific file types
gh-inspector find-python-version myorg --file-types Dockerfile --file-types pyproject.toml

# Include all repos regardless of language
gh-inspector find-python-version myorg --all-repositories
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--file-types` / `-f` | all | File patterns to scan (repeatable) |
| `--all-repositories` / `-a` | `false` | Include non-Python repos |

**Detected file types:** `Dockerfile`, `.python-version`, `pyproject.toml`, `setup.py`, `.github/workflows/*.yml`, `tox.ini`, `Pulumi.prod.yaml`

## Shell Completion

```bash
gh-inspector --install-completion bash   # or zsh, fish
```

Restart your shell after installing.

## Development

```bash
git clone https://github.com/acabelloj/gh-inspector.git
cd gh-inspector
make install   # install deps + pre-commit hooks
```

| Command | Description |
|---------|-------------|
| `make install` | Install deps and set up pre-commit hooks |
| `make lint` | Run ruff linter |
| `make format` | Run ruff formatter |
| `make test` | Run tests |
| `make build` | Build the package |
| `make clean` | Remove build artifacts |

Commits must follow [Conventional Commits](https://www.conventionalcommits.org/) — enforced by pre-commit and required to merge.

## License

MIT — see [LICENSE](LICENSE).
