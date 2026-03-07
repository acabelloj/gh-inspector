import re

from .category import VersionCategory

FILE_PATTERNS = [".python-version"]
CATEGORY = VersionCategory.RUNTIME

_RE = re.compile(r"^(\d+\.\d+(?:\.\d+)?)$")


def extract(content: str) -> list[str]:
    return [m.group(1) for line in content.splitlines() if (m := _RE.match(line.strip()))]
