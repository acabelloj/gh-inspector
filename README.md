# gh-inspector

A CLI tool using gh to rapidly locate and inspect files in remote GitHub repositories without cloning.

## Prerequisites

- **GitHub CLI (`gh`)**: Install from [cli.github.com](https://cli.github.com/)
- **Python 3.10+**: Required for running the tool
- **uv** (optional): For faster dependency management

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/acabelloj/gh-inspector.git
   cd gh-inspector
   ```

2. **Install dependencies**:
   
   Using `uv` (recommended):
   ```bash
   # Create a virtual environment
   uv venv -p 3.14 --prompt gh-inspector
   
    # Activate the virtual environment
   source .venv/bin/activate
   
   # Sync dependencies
   uv sync
   ```
   
   Or using `pip`:
   ```bash
   # Create a virtual environment
   python -m venv .venv
   source .venv/bin/activate
   
   # Install the package
   pip install -e .
   ```

3. **Authenticate with GitHub CLI** (if not already done):
   ```bash
   gh auth login
   ```

## Shell Completion (Optional)

Enable tab completion for commands and options:

**For Bash**:
```bash
gh-inspector --install-completion bash
# Or with uv:
uv run gh-inspector --install-completion bash
```

**For Zsh**:
```bash
gh-inspector --install-completion zsh
# Or with uv:
uv run gh-inspector --install-completion zsh
```

**For Fish**:
```bash
gh-inspector --install-completion fish
# Or with uv:
uv run gh-inspector --install-completion fish
```

After installation, restart your shell or run:
```bash
source ~/.bashrc  # For Bash
source ~/.zshrc   # For Zsh
```

Now you can use tab completion:
```bash
gh-inspector <TAB>              # Shows available commands
gh-inspector find-python-library <TAB>  # Shows options
```

## Usage

### Running Commands

**Run directly:
```bash
gh-inspector find-python-library <org-name> <library1> [library2]...
```

### Find Python Library Versions

Analyze library usage across repositories in a GitHub organization.

**Examples**:

```bash
# Find Django and requests versions in the 'python' org
gh-inspector find-python-library python django requests

# Find pydantic versions, including all repos (not just Python ones)
gh-inspector find-python-library myorg pydantic --all-repositories

# Show only repository names (no version details)
gh-inspector find-python-library myorg fastapi --format only_repo

# Check dev dependencies
gh-inspector find-python-library myorg pytest --source dev
```

**Options**:
- `--format` / `-f`: Output format (`default` or `only_repo`)
- `--source` / `-s`: Source files to check (`default`, `dev`, or `all`)
- `--all-repositories` / `-a`: Check all repos regardless of primary language

**Supported dependency files**:
- `requirements.txt`

## Development

Install with dev dependencies:

```bash
uv sync --extra dev
```

Run linting and formatting:

```bash
uv run ruff check --fix .
uv run ruff format .
```

Set up pre-commit hooks:

```bash
uv run pre-commit install
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

