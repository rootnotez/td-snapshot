#!/bin/bash
set -e

# Expand the shipped TouchDesigner .tox corpus into tocdir trees.
#
# TouchDesigner ships ~788 .tox under its Resources/tfs tree, including the
# OPSnippets library (one .tox per operator across all 7 families). Expanding
# all of them gives a near-complete operator corpus for format coverage work,
# WITHOUT authoring anything — it is regenerable from the install, so the
# output lives under the already-gitignored toeexpand/resources/.
#
# For each source <relpath>/<name>.tox we mirror the source-relative path under
# the corpus root and run toeexpand there (it writes <name>.tox.dir/ +
# <name>.tox.toc next to its input). Mirroring avoids the basename collisions
# that occur across the 788 files. The copied .tox is removed after expansion;
# only the inert text tree is kept.
#
# Usage:  scripts/build-corpus.sh [--force]
#   --force   re-expand even when a tree already exists (default: skip existing)
#
# Env overrides:
#   TD_APP     TouchDesigner.app path (default /Applications/TouchDesigner.app)
#   TOEEXPAND  toeexpand binary (default $TD_APP/Contents/MacOS/toeexpand)
#   SRC_ROOT   source directory to scan (default $TD_APP/Contents/Resources/tfs)

TD_APP="${TD_APP:-/Applications/TouchDesigner.app}"
TOEEXPAND="${TOEEXPAND:-$TD_APP/Contents/MacOS/toeexpand}"
SRC_ROOT="${SRC_ROOT:-$TD_APP/Contents/Resources/tfs}"
DEST_ROOT="toeexpand/resources/shipped"

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

if [ ! -x "$TOEEXPAND" ]; then
    echo "ERROR: toeexpand not found at $TOEEXPAND (is TouchDesigner installed?)" >&2
    exit 1
fi
if [ ! -d "$SRC_ROOT" ]; then
    echo "ERROR: source root not found: $SRC_ROOT" >&2
    exit 1
fi

mkdir -p "$DEST_ROOT"

expanded=0
skipped=0
failed=0
build_version=""

while IFS= read -r -d '' src; do
    rel="${src#"$SRC_ROOT"/}"
    dest="$DEST_ROOT/$rel"
    if [ -d "${dest}.dir" ] && [ "$FORCE" -eq 0 ]; then
        skipped=$((skipped + 1))
        continue
    fi
    rm -rf -- "${dest}.dir" "${dest}.toc"
    mkdir -p -- "$(dirname -- "$dest")"
    cp -- "$src" "$dest"
    # toeexpand exits 1 even on a fully successful expansion, so success is
    # judged by whether the .dir tree was produced, not by the exit code.
    # `|| true` keeps set -e from aborting the sweep on that non-zero exit.
    "$TOEEXPAND" "$dest" >/dev/null 2>&1 || true
    if [ -d "${dest}.dir" ]; then
        expanded=$((expanded + 1))
        if [ -z "$build_version" ] && [ -f "${dest}.dir/.build" ]; then
            build_version="$(grep '^build ' "${dest}.dir/.build" | head -1 || true)"
        fi
    else
        failed=$((failed + 1))
        echo "  WARN: could not expand $rel" >&2
    fi
    rm -f -- "$dest"
done < <(find "$SRC_ROOT" -type f -name '*.tox' -print0)

echo "corpus: expanded=$expanded skipped=$skipped failed=$failed -> $DEST_ROOT"
if [ -n "$build_version" ]; then
    echo "install ${build_version}"
fi
