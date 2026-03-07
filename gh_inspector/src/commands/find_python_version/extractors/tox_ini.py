import re

from .category import VersionCategory

FILE_PATTERNS = ["tox.ini"]
CATEGORY = VersionCategory.CI

# basepython = python3.11
_BASEPYTHON_RE = re.compile(r"basepython\s*=\s*python(\d+\.\d+)", re.IGNORECASE)
# envlist shorthand: py310, py311
_ENVLIST_RE = re.compile(r"\bpy(\d)(\d+)\b")


def extract(content: str) -> list[str]:
    results = []
    for line in content.splitlines():
        if m := _BASEPYTHON_RE.search(line):
            results.append(m.group(1))
        else:
            for m in _ENVLIST_RE.finditer(line):
                results.append(f"{m.group(1)}.{m.group(2)}")
    return results
