import re

from .category import VersionCategory

FILE_PATTERNS = ["Dockerfile"]
CATEGORY = VersionCategory.RUNTIME

_RE = re.compile(r"FROM\s+[\w${}/:.\-]*python[-:v]*[\w.]*[-:](\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)


def extract(content: str) -> list[str]:
    return [m.group(1) for line in content.splitlines() if (m := _RE.search(line))]
