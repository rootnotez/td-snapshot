#!/bin/bash
set -e

# tocdir -> .tox (the "shrink" direction).
#
# Patches the .text DAT bodies in tox/td_snapshot.tox.dir/ from src/*.py
# (via `python -m tocdir set-text`, which recomputes each .text length
# header), then runs the toecollapse binary to pack the tree back into
# td-snapshot.tox.
#
# Called automatically by build.sh after stamp.sh has run, so src/*.py
# already carry their version/hash stamp headers when synced.

TOECOLLAPSE=/Applications/TouchDesigner.app/Contents/MacOS/toecollapse
TOX_DIR=tox/td_snapshot.tox.dir

if [ ! -x "$TOECOLLAPSE" ]; then
    echo "ERROR: toecollapse not found at $TOECOLLAPSE (is TouchDesigner installed?)" >&2
    exit 1
fi

if [ ! -d "$TOX_DIR" ]; then
    echo "ERROR: canonical expansion not found at $TOX_DIR" >&2
    echo "  Run ./scripts/grow.sh to create it from td-snapshot.tox" >&2
    exit 1
fi

# Each src/*.py body is injected into its matching .text file in the tree.
SET_TEXT() { PYTHONPATH=src uv run python -m tocdir set-text "$2" "$1"; }
SET_TEXT src/core.py               "$TOX_DIR/td_snapshot/core.text"
SET_TEXT src/tox_runner_copy.py    "$TOX_DIR/td_snapshot/tox_runner_copy.text"
SET_TEXT src/tox_runner_inspect.py "$TOX_DIR/td_snapshot/tox_runner_inspect.text"

"$TOECOLLAPSE" "$TOX_DIR"
mv tox/td_snapshot.tox td-snapshot.tox
echo "Rebuilt td-snapshot.tox"
