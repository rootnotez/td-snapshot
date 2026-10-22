#!/bin/bash
set -e

command -v shellcheck >/dev/null 2>&1 || { echo "ERROR: shellcheck not found (brew install shellcheck)"; exit 1; }
command -v uv        >/dev/null 2>&1 || { echo "ERROR: uv not found (brew install uv)"; exit 1; }

echo "shellcheck..."
shellcheck scripts/*.sh

echo "py_compile..."
uv run --no-project python -m py_compile src/*.py

# build.sh sets SKIP_TESTS=1 and runs pytest itself after shrink, because some
# tests check the rebuilt td-snapshot.tox (a fresh TD export won't pass them).
if [ -z "${SKIP_TESTS:-}" ]; then
    echo "pytest..."
    # Whole suite: about 10 s, so no need to pick a fast subset.
    uvx pytest -q
fi

# A warning, not a failure: build.sh collapses the .tox with the installed TD,
# whose DAT templates may not be recorded yet.
echo "check-build..."
./scripts/check-build.sh >/dev/null || true

echo "All checks passed."
