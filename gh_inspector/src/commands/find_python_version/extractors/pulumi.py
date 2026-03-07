import re

from .category import VersionCategory

FILE_PATTERNS = ["Pulumi.yaml", "Pulumi.yml", "Pulumi.*.yaml", "Pulumi.*.yml"]
CATEGORY = VersionCategory.RUNTIME

_RE = re.compile(r"python[-_]?version[:\s]+[\"']?(\d+\.\d+(?:\.\d+)?)[\"']?", re.IGNORECASE)


def extract(content: str) -> list[str]:
    return [m.group(1) for line in content.splitlines() if (m := _RE.search(line))]
