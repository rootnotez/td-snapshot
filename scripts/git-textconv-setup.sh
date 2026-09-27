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
if [ ! -f "$SRC_DIR/tocdir/__main__.py" ]; then
    echo "ERROR: tocdir not found at $SRC_DIR/tocdir" >&2
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv not found (see https://docs.astral.sh/uv/)" >&2
    exit 1
fi

# git runs a textconv command via the shell with the target file path
# appended as the final argument, so this string just needs to end at the
# tocdir subcommand name. PYTHONPATH is set to this clone's src/ (an
# absolute path, so it resolves correctly no matter what cwd git invokes
# it from) since `uv run --no-project` does not install the repo itself.
# Relative on purpose: git runs textconv from the top of whichever working
# tree is being diffed (checked 2026-09-27, including from a subdirectory),
# so each worktree uses its own src/tocdir. An absolute path would pin every
# worktree to one checkout and turn `git diff` into an error once that
# checkout is deleted -- the config is shared across worktrees.
TEXTCONV_CMD="PYTHONPATH=src uv run --no-project --quiet python -m tocdir textconv"

git config diff.tocdir.textconv "$TEXTCONV_CMD"
git config diff.tocdir.cachetextconv true

echo "Configured git diff driver 'tocdir' in this repo's .git/config (shared across worktrees, not committed):"
echo "  diff.tocdir.textconv = $TEXTCONV_CMD"
echo "  diff.tocdir.cachetextconv = true"
