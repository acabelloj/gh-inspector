import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import typer
from github_client import GitHubClient
from packaging.version import InvalidVersion
from packaging.version import parse as parse_version
from rich.console import Console
from rich.table import Table
from tqdm import tqdm

console = Console()

MAX_WORKERS = 6

# File patterns to search for Python version declarations
FILE_PATTERNS = [
    "Dockerfile",
    "Pulumi.prod.yaml",
    ".python-version",
    "pyproject.toml",
    "setup.py",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    "tox.ini",
]

# Regex patterns for finding Python versions in different file types
PYTHON_VERSION_RE = re.compile(r"\b(py(?:thon)?[-_]?(\d+\.\d+))\b", re.IGNORECASE)
DOCKER_PYTHON_VERSION_RE = re.compile(r"FROM\s+[\w${}/:.\-]*python[-:v]*[\w.]*[-:](\d+\.\d+\.\d+)", re.IGNORECASE)
PYPROJECT_VERSION_RE = re.compile(r'python\s*=\s*["\'][\^~>=<]*(\d+\.\d+)', re.IGNORECASE)
SETUP_PY_VERSION_RE = re.compile(r'python_requires\s*=\s*["\'][\^~>=<]*(\d+\.\d+)', re.IGNORECASE)
PYTHON_VERSION_FILE_RE = re.compile(r'^(\d+\.\d+(?:\.\d+)?)$')


def matches_pattern(file_path, pattern):
    """Check if a file path matches a given pattern (supports wildcards)."""
    if "*" in pattern:
        regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
        return re.search(regex_pattern, file_path) is not None
    return file_path.endswith(pattern) or file_path == pattern


def get_files(gh_client, repo_name, file_patterns):
    """Get list of files matching the specified patterns from the repository."""
    try:
        tree = gh_client.get_repo_tree(repo_name)
        matched_files = []
        for file in tree:
            file_path = file["path"]
            for pattern in file_patterns:
                if matches_pattern(file_path, pattern):
                    matched_files.append(file_path)
                    break  # Avoid duplicate matches
        return matched_files
    except Exception as e:
        print(f"Error retrieving file list for {repo_name}: {e}")
        return []


def extract_version_from_content(content):
    """Extract Python version from file content by trying all regex patterns."""
    patterns = [
        PYTHON_VERSION_FILE_RE,
        PYPROJECT_VERSION_RE,
        SETUP_PY_VERSION_RE,
        DOCKER_PYTHON_VERSION_RE,
        PYTHON_VERSION_RE,
    ]

    versions = []
    for line in content.splitlines():
        for pattern in patterns:
            if match := pattern.search(line):
                versions.append(match.group(1))
                break
    return versions


def process_repo(gh_client, repo, file_patterns):
    """Process a repository to find Python versions in specified file types."""
    repo_name = repo["nameWithOwner"]
    repo_results = defaultdict(set)
    try:
        files = get_files(gh_client, repo_name, file_patterns)
        for file in files:
            try:
                content = gh_client.get_file_content(repo_name, file)
                versions = extract_version_from_content(content)
                for version in versions:
                    repo_results[version].add(f"{repo_name} ({file})")
            except Exception as e:
                print(f"Error processing file {file} in {repo_name}: {e}")
    except Exception as e:
        print(f"Error processing {repo_name}: {e}")
    return repo_results


def version_key(version):
    """Sort key for Python versions by extracting and parsing the numeric part."""
    if numeric_match := re.search(r"(\d+(?:\.\d+)*)", version):
        try:
            return parse_version(numeric_match.group(1))
        except (InvalidVersion, TypeError):
            pass
    return parse_version("0.0")


def display_summary_table(sorted_versions, python_versions):
    """Display summary table of Python version usage."""
    summary_table = Table(
        title="Summary - Python Version Usage",
        show_header=True,
        header_style="bold magenta",
        border_style="blue"
    )
    summary_table.add_column("Python Version", style="yellow", no_wrap=True, width=20)
    summary_table.add_column("Count", justify="center", style="magenta", width=10)
    summary_table.add_column("Percentage", justify="center", style="green", width=12)
    summary_table.add_column("Progress Bar", style="cyan", width=30)

    total = sum(len(files) for files in python_versions.values())
    for idx, (version, files) in enumerate(sorted_versions):
        count = len(files)
        percentage = (count / total) * 100
        bar_length = int((count / total) * 20)
        progress_bar = "█" * bar_length + "░" * (20 - bar_length)

        summary_table.add_row(version, str(count), f"{percentage:.1f}%", progress_bar)

        if idx < len(sorted_versions) - 1:
            summary_table.add_section()

    console.print(summary_table)
    console.print()


def display_detail_tables(sorted_versions):
    """Display detailed tables for each Python version."""
    for version, repo_files in sorted_versions:
        detail_table = Table(
            title=f"Python Version: {version}",
            show_header=True,
            header_style="bold green",
            border_style="blue"
        )
        detail_table.add_column("Count", justify="center", style="magenta", width=8)
        detail_table.add_column("Repository (File)", style="cyan", no_wrap=False)

        count = len(repo_files)
        repos_display = "\n".join(sorted(repo_files))
        detail_table.add_row(str(count), repos_display)

        console.print(detail_table)
        console.print()


def display_no_version_table(no_version_repos):
    """Display table of repositories with no Python version found."""
    no_version_table = Table(
        title="Repositories with No Python Version Found",
        show_header=True,
        header_style="bold red",
        border_style="red",
    )
    no_version_table.add_column("Repository", style="cyan", no_wrap=False)

    for repo in sorted(no_version_repos):
        no_version_table.add_row(repo)

    console.print(no_version_table)
    console.print()


def find_python_version(
    org_name: str = typer.Argument(..., help="GitHub organization name"),
    file_types: list[str] = typer.Option(
        None,
        "--file-types",
        "-f",
        help="Specific file patterns to search (e.g., 'Dockerfile', 'pyproject.toml'). If not specified, all default patterns are used."
    ),
    all_repositories: bool = typer.Option(
        False, "--all-repositories", "-a", help="Check all repos regardless of language"
    ),
):
    """Analyze Python version usage across repositories of a GitHub organization."""
    gh_client = GitHubClient()
    file_patterns = file_types if file_types else FILE_PATTERNS
    repos = gh_client.get_repos(org_name, all_repositories)
    python_versions = defaultdict(set)
    no_version_repos = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_repo, gh_client, repo, file_patterns): repo for repo in repos}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing Repos"):
            result = future.result()
            if not result:
                no_version_repos.append(futures[future]["nameWithOwner"])
            for version, repo_files in result.items():
                python_versions[version].update(repo_files)

    sorted_versions = sorted(python_versions.items(), key=lambda item: version_key(item[0]), reverse=True)

    console.print("\n[bold cyan]Python Version Identification Dashboard[/bold cyan]\n")

    if sorted_versions:
        display_summary_table(sorted_versions, python_versions)
        display_detail_tables(sorted_versions)
    else:
        console.print("[yellow]No Python versions found in the specified file patterns.[/yellow]\n")

    if no_version_repos:
        display_no_version_table(no_version_repos)


