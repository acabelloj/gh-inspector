import re

FILE_PATTERNS = ["requirements*.txt", "requirements*.in"]


def extract(content: str, libraries: list[str]) -> dict[str, str]:
    lower_libs = {lib.lower(): lib for lib in libraries}
    lib_pattern = "|".join(re.escape(lib) for lib in libraries)
    regex = re.compile(rf"^({lib_pattern})(\[[^\]]*\])?==([0-9]+(?:\.[0-9]+)*)", re.IGNORECASE)
    results = {}
    for line in content.splitlines():
        match = regex.match(line)
        if not match:
            continue
        matched_name = match.group(1)
        lib_name = lower_libs.get(matched_name.lower(), matched_name)
        version = match.group(3)
        if any(other != lib_name and re.search(rf"\b{re.escape(other)}\b", line, re.IGNORECASE) for other in libraries):
            continue
        results[lib_name] = version
    return results
