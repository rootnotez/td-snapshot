#!/bin/bash
set -e

command -v shellcheck >/dev/null 2>&1 || { echo "ERROR: shellcheck not found (brew install shellcheck)"; exit 1; }
command -v uv        >/dev/null 2>&1 || { echo "ERROR: uv not found (brew install uv)"; exit 1; }

echo "shellcheck..."
shellcheck scripts/*.sh

echo "py_compile..."
uv run --no-project python -m py_compile src/*.py

echo "All checks passed."
