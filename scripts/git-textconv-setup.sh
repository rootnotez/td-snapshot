#!/usr/bin/env bash
set -euo pipefail

# One-time per-clone setup for readable `git diff` / `git log -p` on the
# binary `.text`/`.table` files in tox/ (see .gitattributes at the repo
# root). textconv commands live in `.git/config`, which is never
# committed, so every clone (and every worktree, since worktrees share
# the parent repo's .git/config) needs to run this once. Re-run it after
# bumping the toetools pin in scripts/_toetools.sh.
#
# Usage:
#   scripts/git-textconv-setup.sh

# shellcheck source=scripts/_toetools.sh
source "$(dirname "${BASH_SOURCE[0]}")/_toetools.sh"

if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv not found (see https://docs.astral.sh/uv/)" >&2
    exit 1
fi

# git runs a textconv command via the shell with the target file path
# appended as the final argument, so this string just needs to end at the
# textconv subcommand name. uvx caches the pinned toetools build, so this
# doesn't depend on any checkout or on the cwd git runs it from.
TEXTCONV_CMD="uvx --quiet --from $TOETOOLS_SPEC toetools textconv"

git config diff.tocdir.textconv "$TEXTCONV_CMD"
git config diff.tocdir.cachetextconv true

echo "Configured git diff driver 'tocdir' in this repo's .git/config (shared across worktrees, not committed):"
echo "  diff.tocdir.textconv = $TEXTCONV_CMD"
echo "  diff.tocdir.cachetextconv = true"
