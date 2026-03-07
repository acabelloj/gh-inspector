import re

from .category import VersionCategory

FILE_PATTERNS = ["setup.py", "setup.cfg"]
CATEGORY = VersionCategory.MINIMUM

_RE = re.compile(r'python_requires\s*=\s*["\']([^"\']+)["\']')


def extract(content: str) -> list[str]:
    return [m.group(1) for line in content.splitlines() if (m := _RE.search(line))]
