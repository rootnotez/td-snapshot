#!/bin/bash
set -e

cat <<'HEADER' > td-snapshot.py
# td-snapshot.py — BUILT FILE. Do not edit directly.
# Edit src/core.py, then run ./build.sh to regenerate.
#
# USAGE: Paste into a Text DAT, then RIGHT-CLICK the DAT > Run Script.
# Captures the network containing this DAT (me.parent()) by default.
# To target a different network: snapshot_patch('/project1/some/comp')

HEADER

cat src/core.py >> td-snapshot.py
echo "" >> td-snapshot.py
cat src/quickpaste_runner.py >> td-snapshot.py

echo "Built td-snapshot.py"
