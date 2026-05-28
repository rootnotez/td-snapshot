#!/bin/bash
set -e

./scripts/check.sh
./scripts/stamp.sh

{
    cat <<'HEADER'
# td-snapshot.py — BUILT FILE. Do not edit directly.
# Edit src/core.py, then run ./scripts/build.sh to regenerate.
#
# USAGE: Paste into a Text DAT, then RIGHT-CLICK the DAT > Run Script.
# Captures the network containing this DAT (me.parent()) by default.
# To target a different network: snapshot_patch('/project1/some/comp')

HEADER
    cat src/core.py
    echo ""
    cat src/quickpaste_runner.py
} > td-snapshot.py

echo "Built td-snapshot.py"

./scripts/tox-sync.sh
./scripts/hashes.sh
