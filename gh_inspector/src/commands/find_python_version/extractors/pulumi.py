import re

from .category import VersionCategory

FILE_PATTERNS = ["Pulumi.yaml", "Pulumi.yml", "Pulumi.*.yaml", "Pulumi.*.yml"]
CATEGORY = VersionCategory.RUNTIME

# "runtime: python3.11" or "runtime: python3.11.5"
_RUNTIME_RE = re.compile(r"^\s*runtime:\s*python(\d+\.\d+(?:\.\d+)?)\s*$", re.IGNORECASE)

# "runtimeVersion: 3.11" or "pythonVersion: 3.11.5" or "python-version: 3.11"
_VERSION_KEY_RE = re.compile(
    r"^\s*(?:runtime[-_]?version|python[-_]?version)\s*:\s*[\"']?(\d+\.\d+(?:\.\d+)?)[\"']?\s*$",
    re.IGNORECASE,
)


def extract(content: str) -> list[str]:
    versions = []
    for line in content.splitlines():
        m = _RUNTIME_RE.match(line) or _VERSION_KEY_RE.match(line)
        if m:
            versions.append(m.group(1))
    return versions
