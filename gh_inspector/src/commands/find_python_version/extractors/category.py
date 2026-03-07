from enum import Enum


class VersionCategory(str, Enum):
    RUNTIME = "runtime"
    MINIMUM = "minimum"
    CI = "ci"
