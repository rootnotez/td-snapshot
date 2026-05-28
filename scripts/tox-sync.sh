#!/bin/bash
set -e

# Patches the .text DAT bodies in tox/td_snapshot.tox.dir/ from src/*.py,
# then collapses the tree back to td-snapshot.tox.
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
    echo "  Run ./scripts/tox-expand.sh to create it from td-snapshot.tox" >&2
    exit 1
fi

uv run python - <<'PYEOF'
import sys
from pathlib import Path
sys.path.insert(0, "src")
from toeexpand.text import Text, write_text

SYNCS = [
    ("src/core.py",               "tox/td_snapshot.tox.dir/td_snapshot/core.text"),
    ("src/tox_runner_copy.py",    "tox/td_snapshot.tox.dir/td_snapshot/tox_runner_copy.text"),
    ("src/tox_runner_inspect.py", "tox/td_snapshot.tox.dir/td_snapshot/tox_runner_inspect.text"),
]

for src_path, dst_path in SYNCS:
    body = Path(src_path).read_bytes()
    t = Text.parse(Path(dst_path).read_bytes())
    t.body = body
    t.rebuild_lengths()
    write_text(Path(dst_path), t)
    print(f"  synced {src_path} -> {dst_path}")
PYEOF

"$TOECOLLAPSE" "$TOX_DIR"
mv tox/td_snapshot.tox td-snapshot.tox
echo "Rebuilt td-snapshot.tox"
