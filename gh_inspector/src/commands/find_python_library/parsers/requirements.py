import re

FILE_PATTERNS = ["requirements*.txt", "requirements*.in"]


def extract(content: str, libraries: list[str]) -> dict[str, str]:
    lib_pattern = "|".join(re.escape(lib) for lib in libraries)
    regex = re.compile(rf"^({lib_pattern})(\[[^\]]*\])?==([0-9]+(?:\.[0-9]+)*)")
    results = {}
    for line in content.splitlines():
        match = regex.match(line)
        if not match:
            continue
        lib_name, version = match.group(1), match.group(3)
        if any(other != lib_name and re.search(rf"\b{re.escape(other)}\b", line) for other in libraries):
            continue
        results[lib_name] = version
    return results
