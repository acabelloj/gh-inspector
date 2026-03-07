from . import circleci, dockerfile, github_actions, pulumi, pyproject_toml, python_version_file, setup_py, tox_ini
from .category import VersionCategory as VersionCategory

EXTRACTORS = [dockerfile, python_version_file, pulumi, pyproject_toml, setup_py, github_actions, tox_ini, circleci]
