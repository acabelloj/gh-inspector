# Contributing to gh-inspector

Thank you for your interest in contributing to gh-inspector! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/acabelloj/gh-inspector.git
   cd gh-inspector
   ```

3. Set up your development environment:
   ```bash
   uv venv -p 3.14 --prompt gh-inspector
   source .venv/bin/activate
   uv sync --extra dev
   ```

4. Install pre-commit hooks:
   ```bash
   uv run pre-commit install
   ```

## Development Workflow

1. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and ensure they follow the project's coding standards:
   ```bash
   uv run ruff check --fix .
   uv run ruff format .
   ```

3. Run tests (when available):
   ```bash
   uv run pytest
   ```

4. Commit your changes with a descriptive message:
   ```bash
   git commit -m "Add feature: description of your changes"
   ```

5. Push to your fork and create a Pull Request

## Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Write clear, descriptive commit messages
- Add docstrings to functions and classes
- Keep line length to 120 characters (enforced by Ruff)

## Pull Request Guidelines

- Provide a clear description of the changes
- Link any related issues
- Ensure all tests pass
- Update documentation if needed
- Keep PRs focused on a single feature or fix

## Reporting Issues

When reporting issues, please include:
- A clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, etc.)

## Questions?

Feel free to open an issue for any questions or concerns.

Thank you for contributing! 🎉

