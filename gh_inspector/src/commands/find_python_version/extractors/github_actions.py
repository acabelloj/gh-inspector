import re

from .category import VersionCategory

FILE_PATTERNS = [".github/workflows/*.yml", ".github/workflows/*.yaml"]
CATEGORY = VersionCategory.CI

# Matrix list: python-version: ["3.10", "3.11", "3.12"]
_MATRIX_RE = re.compile(r"python-version\s*:\s*\[([^\]]+)\]", re.IGNORECASE)
# Single value: python-version: '3.11' or python-version: 3.11
_SINGLE_RE = re.compile(r'python-version[:\s]+["\']?(\d+\.\d+(?:\.\d+)?)["\']?', re.IGNORECASE)


def extract(content: str) -> list[str]:
    results = []
    for line in content.splitlines():
        if m := _MATRIX_RE.search(line):
            results.extend(re.findall(r"(\d+\.\d+(?:\.\d+)?)", m.group(1)))
        elif m := _SINGLE_RE.search(line):
            results.append(m.group(1))
    return results
