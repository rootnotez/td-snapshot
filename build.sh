#!/bin/bash
set -e

cat <<'HEADER' > td-snapshot.py
# td-snapshot.py — BUILT FILE. Do not edit directly.
# Edit src/core.py, then run ./build.sh to regenerate.
#
# Quick paste usage: copy this file into a Text DAT. Open Dialogs > Textport
# and DATs, then run:
#   op('/project1/text1').run()
# Replace 'text1' with your DAT name. Captures me.parent() by default.
# To target a different network: snapshot_patch('/some/comp')

HEADER

cat src/core.py >> td-snapshot.py
echo "" >> td-snapshot.py
cat src/quickpaste_runner.py >> td-snapshot.py

echo "Built td-snapshot.py"
