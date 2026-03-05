# Agent Guidelines

This file documents conventions for AI agents (Claude, Codex, Copilot, etc.) working in this repository.

---

## Do

- **Work in a branch** — never commit directly to `main`. Always use a feature branch and open a PR.
- **Follow Conventional Commits** — every commit and PR title must use the correct prefix (`feat:`, `fix:`, `ci:`, etc.). This drives automated versioning and PyPI releases.
- **Run checks before pushing** — `make lint`, `make test`, and `make lint-commits` should all pass locally before opening a PR.
- **Write tests for new behaviour** — new commands and logic must have corresponding tests in `gh_inspector/tests/`.
- **Mock `GitHubClient` in tests** — never make real `gh` CLI calls in tests.
- **Use `args: list[str]` in subprocess calls** — never use `shell=True` or build commands with f-strings passed to a shell.
- **Pass GitHub context via `env:`** — in GitHub Actions, never interpolate `${{ github.event.* }}` directly into `run:` scripts. Use environment variables to avoid injection.
- **Pin actions to commit SHAs** — when adding a GitHub Actions step, pin to a full SHA and add a version comment (e.g. `# v4`). Verify the SHA matches the tag.
- **Keep PRs focused** — one concern per PR. Easier to review, easier to revert if needed.
- **Restore what you remove** — if rewriting a file, preserve docstrings, comments, and type annotations that were already there.

---

## Don't

- **Don't push directly to `main`** — branch protection enforces this, but don't work around it (e.g. by temporarily disabling protection) except in genuine emergencies, and restore it immediately.
- **Don't use `shell=True`** — it opens shell injection vulnerabilities. Pass a list of arguments to `subprocess.run` instead.
- **Don't add unused dependencies** — every entry in `pyproject.toml` increases the supply chain surface. Only add what is actually imported.
- **Don't use unpinned actions** — floating tags like `@v4` can be silently updated. Always pin to a SHA.
- **Don't add docstrings, comments, or type annotations to code you didn't change** — only touch what the task requires.
- **Don't make the solution more complex than the problem** — prefer simple, flat, readable code. No abstractions for one-off logic.
- **Don't squash commits without checking** — if asked to squash, verify `make lint-commits` passes on the result first.
- **Don't ignore failing tests** — all 31 tests must pass. If a change breaks tests, fix the tests or the code — don't skip or delete them.
- **Don't remove branch protection** without restoring it in the same session.

---

## Project Structure

```
gh_inspector/
  src/
    main.py                  # Typer app entry point, command registration
    github_client.py         # GitHubClient — wraps gh CLI via subprocess
    commands/
      find_python_library.py # find-python-library command
      find_python_version.py # find-python-version command
  tests/
    test_find_python_library.py
    test_find_python_version.py
    test_github_client.py
```

## Adding a New Command

1. Create `gh_inspector/src/commands/<command_name>.py`
2. Define the command function with Typer annotations
3. Register it in `gh_inspector/src/main.py`
4. Add tests in `gh_inspector/tests/test_<command_name>.py`

## Development Setup

```bash
make install        # install deps + pre-commit hooks
make test           # run pytest
make lint           # run ruff
make lint-commits   # verify commits follow Conventional Commits
```

## Release Process

Releases are fully automated via [release-please](https://github.com/googleapis/release-please):
1. Merge a PR to `main` — the **PR title** becomes the commit and drives the version bump
2. release-please opens a release PR (bumps version in `pyproject.toml` + updates `CHANGELOG.md`)
3. Merging the release PR creates a GitHub Release and triggers PyPI publish via OIDC trusted publishing
