#!/bin/bash
set -e

# Expands td-snapshot.tox into the canonical tox/ tree for git diffing.
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

cp td-snapshot.tox "$STAGE"
"$TOEEXPAND" "$STAGE"
rm "$STAGE"
echo "Expanded td-snapshot.tox -> tox/"
