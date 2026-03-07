import re

from .category import VersionCategory

FILE_PATTERNS = [".circleci/config.yml", ".circleci/config.yaml"]
CATEGORY = VersionCategory.CI

# Matches: cimg/python:3.11, circleci/python:3.9, python:3.11-slim
_RE = re.compile(r"(?:cimg/|circleci/)?python:(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)


def extract(content: str) -> list[str]:
    return [m.group(1) for line in content.splitlines() if (m := _RE.search(line))]
