# Contributing to gh-inspector

First off — thank you! Whether you're fixing a typo, reporting a bug, or building a new feature, every contribution makes this project better.

This guide will get you from zero to opening a PR as smoothly as possible.

## Before you start

If you're planning something big, open an issue first so we can discuss it. It avoids the frustration of building something that doesn't fit the project direction. For small fixes, just go ahead.

## Setting up

1. Fork the repo on GitHub, then clone your fork:
   ```bash
   git clone https://github.com/<your-username>/gh-inspector.git
   cd gh-inspector
   ```

2. One command sets everything up:
   ```bash
   make install
   ```
   This installs dependencies and configures the pre-commit hooks (including commit message validation).

3. Make sure you're authenticated with the GitHub CLI:
   ```bash
   gh auth login
   ```

## Making changes

1. Create a branch with a descriptive name:
   ```bash
   git checkout -b feat/scan-pyproject-toml
   ```

2. Make your changes. Run tests and linting as you go:
   ```bash
   make test
   make lint
   ```

3. Commit your work. We use [Conventional Commits](https://www.conventionalcommits.org/) — the pre-commit hook will guide you if something's off:
   ```
   feat: add pyproject.toml scanning
   fix: handle missing requirements file gracefully
   docs: add example for --source flag
   ```

4. Before pushing, verify all your commits are valid:
   ```bash
   make lint-commits
   ```

5. Push and open a PR:
   ```bash
   git push origin feat/scan-pyproject-toml
   gh pr create
   ```

## Opening a PR

### The PR title is what triggers releases

This project uses squash merges, so your **PR title becomes the single commit on `main`**. That commit is what release-please reads to decide whether to cut a new release and what version to bump.

In practice: if your PR title is `feat: add pyproject.toml scanning`, merging it will automatically open a release PR that bumps the minor version and publishes to PyPI. If it's `fix: handle missing file`, it bumps the patch version. If it's `docs: update readme`, no release is triggered.

So the PR title matters — individual commit messages in your branch do not affect releases.

A few other things that help get PRs merged quickly:

- Keep PRs focused. One thing per PR is easier to review and faster to merge.
- Add tests for new behaviour.
- Don't worry about being perfect — we can iterate in the review.

## Commit types

Not sure which prefix to use? Here's a quick reference:

| Prefix | Use for | Release? |
|--------|---------|----------|
| `feat:` | New feature | minor bump |
| `fix:` | Bug fix | patch bump |
| `docs:` | Documentation | no |
| `test:` | Tests only | no |
| `chore:` | Maintenance, deps | no |
| `ci:` | CI/CD changes | no |
| `refactor:` | Restructure without behaviour change | no |
| `feat!:` | Breaking change | major bump |

## Reporting bugs

Found something broken? Open an issue and include:
- What you were trying to do
- What happened instead
- Your environment (OS, Python version, `gh` version)

The more context, the faster we can help.

## Questions?

Open an issue or start a discussion — no question is too small.
