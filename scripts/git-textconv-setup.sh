#!/usr/bin/env bash
set -euo pipefail

# One-time per-clone setup for readable `git diff` / `git log -p` on
# tocdir's binary `.text`/`.table` files (see .gitattributes at the repo
# root). textconv commands live in `.git/config`, which is never
# committed, so every clone (and every worktree, since worktrees share
# the parent repo's .git/config) needs to run this once.
#
# Usage:
#   scripts/git-textconv-setup.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$REPO_ROOT/src"

if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv not found (see https://docs.astral.sh/uv/)" >&2
    exit 1
fi

# git runs a textconv command via the shell with the target file path
# appended as the final argument, so this string just needs to end at the
# tocdir subcommand name. PYTHONPATH is set to this clone's src/ (an
# absolute path, so it resolves correctly no matter what cwd git invokes
# it from) since `uv run --no-project` does not install the repo itself.
TEXTCONV_CMD="PYTHONPATH=\"$SRC_DIR\" uv run --no-project python -m tocdir textconv"

git config diff.tocdir.textconv "$TEXTCONV_CMD"
git config diff.tocdir.cachetextconv true

echo "Configured git diff driver 'tocdir' in this repo's .git/config (shared across worktrees, not committed):"
echo "  diff.tocdir.textconv = $TEXTCONV_CMD"
echo "  diff.tocdir.cachetextconv = true"
