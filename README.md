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

## Commands

### `find-python-library`

Scan requirements files across all repositories in a GitHub organization and report which version of a library each repo uses.

```bash
gh-inspector find-python-library <org> <library> [library2 ...]
```

**Examples:**

```bash
# Find Django and requests versions across the org
gh-inspector find-python-library myorg django requests

# Include dev requirements
gh-inspector find-python-library myorg pytest --source dev

# Search all repos, not just Python ones
gh-inspector find-python-library myorg pydantic --all-repositories

# List only repo names (no version breakdown)
gh-inspector find-python-library myorg fastapi --format only_repo
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--format` / `-f` | `default` | Output format: `default` or `only_repo` |
| `--source` / `-s` | `default` | Requirements source: `default`, `dev`, or `all` |
| `--all-repositories` / `-a` | `false` | Include non-Python repos |

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

---

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
