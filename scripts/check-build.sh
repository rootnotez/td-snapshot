#!/bin/bash
set -euo pipefail

# Run after updating TouchDesigner (README: "After updating TouchDesigner").
# Reads the installed app's build and says what this repo still needs for it:
# a dat-templates/<build>.json record. Before the toetools split this warning
# lived in scripts/toolchain-check.sh, which moved to toetools without it.
#
#   scripts/check-build.sh
#
# TD_APP overrides the app (default /Applications/TouchDesigner.app).
# Exit status: 0 the build is recorded, 1 it is not, 2 no app to read.

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TD_APP="${TD_APP:-/Applications/TouchDesigner.app}"

if ! BUILD="$(defaults read "$TD_APP/Contents/Info" CFBundleVersion 2>/dev/null)" || [ -z "$BUILD" ]; then
    echo "check-build: can't read CFBundleVersion from $TD_APP (set TD_APP)" >&2
    exit 2
fi

echo "Installed TouchDesigner build: $BUILD"
if [ -f "$REPO/dat-templates/$BUILD.json" ]; then
    echo "dat-templates/$BUILD.json is recorded."
    exit 0
fi
cat >&2 <<MSG
WARNING: no dat-templates/$BUILD.json record for the installed build.
Untouched default DATs created in $BUILD are shown in full, not collapsed. To record it:
  1. scripts/capture-dat-templates.sh   (see dat-templates/README.md)
  2. Add the build's row to the table in dat-templates/README.md.
  3. Bump core.py in src/versions.txt and run ./scripts/build.sh.
MSG
exit 1
