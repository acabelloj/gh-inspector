import fnmatch

from . import pipfile_lock, poetry_lock, requirements, setup_cfg, uv_lock

PARSERS = [requirements, uv_lock, poetry_lock, pipfile_lock, setup_cfg]


def matches_pattern(path: str, pattern: str) -> bool:
    filename = path.split("/")[-1]
    return fnmatch.fnmatch(filename, pattern)
