import configparser
import re

FILE_PATTERNS = ["setup.cfg"]


def extract(content: str, libraries: list[str]) -> dict[str, str]:
    config = configparser.ConfigParser()
    config.read_string(content)
    lower_libs = {lib.lower(): lib for lib in libraries}
    results = {}
    raw = config.get("options", "install_requires", fallback="")
    lib_pattern = "|".join(re.escape(lib) for lib in libraries)
    regex = re.compile(rf"^({lib_pattern})(\[[^\]]*\])?==([0-9]+(?:\.[0-9]+)*)", re.IGNORECASE)
    for line in raw.splitlines():
        line = line.strip()
        match = regex.match(line)
        if match:
            lib_name = lower_libs.get(match.group(1).lower(), match.group(1))
            results[lib_name] = match.group(3)
    return results
