import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import typer
from github_client import GitHubClient
from rich.console import Console
from rich.table import Table
from tqdm import tqdm

console = Console()

MAX_WORKERS = 6

# Requirements file patterns
REQUIREMENTS_PATTERNS = {
    "dev": r"requirements-dev\.txt",
    "all": r"requirements(-dev)?\.txt",
    "default": r"requirements\.txt",
}


def get_requirements_files(gh_client, repo_name, source):
    """Get list of requirements files matching the source pattern."""
    pattern = re.compile(REQUIREMENTS_PATTERNS.get(source, REQUIREMENTS_PATTERNS["default"]))
    files = gh_client.get_repo_tree(repo_name)
    return [f["path"] for f in files if pattern.search(f["path"])]


def process_requirements_file(gh_client, repo_name, file_path, libraries, library_regex):
    """Process a single requirements file and extract library versions."""
    results = defaultdict(list)

    try:
        content = gh_client.get_file_content(repo_name, file_path)
        for line in content.splitlines():
            if match := re.search(library_regex, line):
                lib_name, version = match.group(1), match.group(3)
                # Skip if line contains other tracked libraries (avoid cross-matching)
                if any(other != lib_name and re.search(rf"\b{other}\b", line) for other in libraries):
                    continue
                results[f"{lib_name}$v{version}"].append(f"{repo_name} ({file_path})")
    except Exception as e:
        print(f"Error processing {file_path} in {repo_name}: {e}")

    return results


def process_repo(gh_client, repo, libraries, library_regex, source):
    """Process all requirements files in a repository."""
    repo_name = repo["nameWithOwner"]
    all_results = defaultdict(list)

    try:
        req_files = get_requirements_files(gh_client, repo_name, source)
        for file_path in req_files:
            file_results = process_requirements_file(gh_client, repo_name, file_path, libraries, library_regex)
            for key, values in file_results.items():
                all_results[key].extend(values)
    except Exception as e:
        print(f"Error processing {repo_name}: {e}")

    return all_results


def print_results(library_versions, libraries, output_format):
    """Print results in the specified format using Rich tables."""
    if output_format == "only_repo":
        repos = {repo_file.split()[0] for _, files in library_versions for repo_file in files}

        table = Table(title="Repositories", show_header=True, header_style="bold magenta")
        table.add_column("Repository", style="cyan", no_wrap=False)

        for repo in sorted(repos):
            table.add_row(repo)

        console.print(table)
    else:
        # Group by library name for better organization
        library_data = defaultdict(lambda: defaultdict(list))
        for lib_version, repo_files in library_versions:
            lib_name, version = lib_version.split("$v")
            library_data[lib_name][version].extend(repo_files)

        console.print(f"\n[bold cyan]Version Usage for libraries:[/bold cyan] {', '.join(libraries)}\n")

        for lib_name in sorted(library_data.keys()):
            table = Table(
                title=f"Library: {lib_name}", show_header=True, header_style="bold green", border_style="blue"
            )
            table.add_column("Version", style="yellow", no_wrap=True, width=15)
            table.add_column("Count", justify="center", style="magenta", width=8)
            table.add_column("Repositories (Files)", style="cyan", no_wrap=False)

            sorted_versions = sorted(library_data[lib_name].keys(), reverse=True)
            for idx, version in enumerate(sorted_versions):
                repo_files = library_data[lib_name][version]
                count = len(repo_files)

                # Join all repositories with newlines for compact display
                repos_display = "\n".join(repo_files)

                table.add_row(version, str(count), repos_display)

                # Add separator line between versions (but not after the last one)
                if idx < len(sorted_versions) - 1:
                    table.add_section()

            console.print(table)
            console.print()  # Add spacing between tables


def find_python_library(
    org_name: str = typer.Argument(..., help="GitHub organization name"),
    libraries: list[str] = typer.Argument(..., help="List of libraries to analyze"),
    output_format: str = typer.Option("default", "--format", "-f", help="Output format (default or only_repo)"),
    source: str = typer.Option("default", "--source", "-s", help="Source: default, dev, or all"),
    all_repositories: bool = typer.Option(
        False, "--all-repositories", "-a", help="Check all repos regardless of language"
    ),
):
    """Analyze library usage across repositories of a GitHub organization."""
    gh_client = GitHubClient()

    # Build regex to match library versions
    lib_pattern = "|".join(re.escape(lib) for lib in libraries)
    library_regex = rf"^({lib_pattern})(\[[^\]]*\])?==([0-9]+(?:\.[0-9]+)*)"

    repos = gh_client.get_repos(org_name, all_repositories)
    library_versions = defaultdict(list)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_repo, gh_client, repo, libraries, library_regex, source): repo for repo in repos
        }

        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing repos"):
            for version, repo_files in future.result().items():
                library_versions[version].extend(repo_files)

    print_results(library_versions.items(), libraries, output_format)
