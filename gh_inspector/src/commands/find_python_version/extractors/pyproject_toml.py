import re

from .category import VersionCategory

FILE_PATTERNS = ["pyproject.toml"]
CATEGORY = VersionCategory.MINIMUM

# PEP 517/518: requires-python = ">=3.10"
_REQUIRES_PYTHON_RE = re.compile(r'requires-python\s*=\s*["\']([^"\']+)["\']')
# Poetry: python = "^3.11"
_POETRY_PYTHON_RE = re.compile(r'(?<![a-z_-])python\s*=\s*["\']([^"\']+)["\']')


def extract(content: str) -> list[str]:
    results = []
    for line in content.splitlines():
        if m := _REQUIRES_PYTHON_RE.search(line):
            results.append(m.group(1))
        elif m := _POETRY_PYTHON_RE.search(line):
            results.append(m.group(1))
    return results
