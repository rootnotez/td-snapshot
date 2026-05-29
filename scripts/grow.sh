#!/bin/bash
set -e

# .tox -> tocdir (the "grow" direction).
#
# Runs the toeexpand binary to expand td-snapshot.tox into the canonical
# tox/ tree for git diffing.
#
# Run this after exporting a fresh td-snapshot.tox from TouchDesigner.
# The updated files in tox/ will show what changed in the GUI via git diff.
#
# toeexpand names its output after the input file, so we stage the tox
# under the canonical name in tox/ before expanding.

TOEEXPAND=/Applications/TouchDesigner.app/Contents/MacOS/toeexpand
STAGE=tox/td_snapshot.tox

if [ ! -x "$TOEEXPAND" ]; then
    echo "ERROR: toeexpand not found at $TOEEXPAND (is TouchDesigner installed?)" >&2
    exit 1
fi

if [ ! -f td-snapshot.tox ]; then
    echo "ERROR: td-snapshot.tox not found in working directory" >&2
    exit 1
fi

# toeexpand refuses to overwrite an existing expansion. Confirm with the
# user before deleting any prior .dir/.toc so a fresh expand can run.
TARGETS=()
[ -d "${STAGE}.dir" ] && TARGETS+=("${STAGE}.dir")
[ -f "${STAGE}.toc" ] && TARGETS+=("${STAGE}.toc")

if [ ${#TARGETS[@]} -gt 0 ]; then
    echo "grow.sh will DELETE the following before re-expanding td-snapshot.tox:"
    for t in "${TARGETS[@]}"; do echo "  $t"; done
    if ! git diff --quiet -- "${TARGETS[@]}" 2>/dev/null \
       || ! git diff --cached --quiet -- "${TARGETS[@]}" 2>/dev/null; then
        echo "  WARNING: these have uncommitted changes."
    fi
    read -rp "Proceed? [y/N] " reply
    case "$reply" in
        [yY]|[yY][eE][sS]) ;;
        *) echo "Aborted." >&2; exit 1 ;;
    esac
    for t in "${TARGETS[@]}"; do rm -rf -- "$t"; done
fi

cp td-snapshot.tox "$STAGE"
"$TOEEXPAND" "$STAGE"
rm "$STAGE"
echo "Expanded td-snapshot.tox -> tox/"
