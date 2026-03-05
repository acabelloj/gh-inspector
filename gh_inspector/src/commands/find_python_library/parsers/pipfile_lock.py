import json

FILE_PATTERNS = ["Pipfile.lock"]


def extract(content: str, libraries: list[str]) -> dict[str, str]:
    data = json.loads(content)
    lower_libs = {lib.lower(): lib for lib in libraries}
    results = {}
    for section in ("default", "develop"):
        for name, info in data.get(section, {}).items():
            if name.lower() in lower_libs:
                original = lower_libs[name.lower()]
                version_str = info.get("version", "")
                results[original] = version_str.lstrip("=")
    return results
