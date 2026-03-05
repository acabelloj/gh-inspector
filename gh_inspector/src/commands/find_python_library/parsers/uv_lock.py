try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

FILE_PATTERNS = ["uv.lock"]


def extract(content: str, libraries: list[str]) -> dict[str, str]:
    data = tomllib.loads(content)
    lower_libs = {lib.lower(): lib for lib in libraries}
    results = {}
    for package in data.get("package", []):
        name = package.get("name", "")
        if name.lower() in lower_libs:
            original = lower_libs[name.lower()]
            results[original] = package.get("version", "")
    return results
