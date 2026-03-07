#!/usr/bin/env bash
set -euo pipefail

if grep -E 'url = "https?://' uv.lock | grep -Ev 'files\.pythonhosted\.org|pypi\.org'; then
    echo "ERROR: uv.lock contains URLs from a non-public index. Remove private registry configuration and regenerate the lockfile."
    exit 1
fi
