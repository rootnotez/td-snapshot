#!/bin/bash
set -e

# Record the default DAT texts of the running TouchDesigner build into
# dat-templates/<build>.json, then regenerate the matching table in src/core.py.
#
# Needs a live TD session with the td-claude-bridge component. It creates and
# destroys every operator type (minus the risky ones in capture_td.py's SKIP)
# inside /project1/dat_templates_capture, in batches so TD's UI isn't frozen
# for long. Nothing else in the project is touched.
#
#   scripts/capture-dat-templates.sh [--force]
#
# TD_BRIDGE overrides the td-claude-bridge checkout (default: ../td-claude-bridge).

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TD_BRIDGE="${TD_BRIDGE:-$REPO/../td-claude-bridge}"
SCRIPT="$REPO/dat-templates/capture_td.py"
BATCH=60
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

if [ ! -x "$TD_BRIDGE/td.sh" ]; then
    echo "ERROR: $TD_BRIDGE/td.sh not found or not executable (set TD_BRIDGE to override)" >&2
    exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -r "$TMP"' EXIT

run_batch() {
    local reply
    reply="$( { printf 'START = %d\nEND = %d\n' "$1" "$2"; cat "$SCRIPT"; } | "$TD_BRIDGE/td.sh" exec)"
    if ! grep -q '^status: ok' <<<"$reply"; then
        echo "ERROR: batch $1-$2 failed inside TD:" >&2
        printf '%s\n' "$reply" >&2
        exit 1
    fi
    grep '^@@DATTEMPLATES@@ ' <<<"$reply"
}

# A zero-width batch reports the build and the number of op types.
run_batch 0 0 > "$TMP/probe"
read -r BUILD TYPES < <(sed 's/^@@DATTEMPLATES@@ //' "$TMP/probe" | jq -r '"\(.build) \(.types)"')
OUT="$REPO/dat-templates/$BUILD.json"
if [ -f "$OUT" ] && [ "$FORCE" -eq 0 ]; then
    echo "ERROR: $OUT already exists (re-run with --force to overwrite)" >&2
    exit 1
fi

echo "Capturing $TYPES op types from TD $BUILD..."
for ((start = 0; start < TYPES; start += BATCH)); do
    end=$((start + BATCH))
    [ "$end" -gt "$TYPES" ] && end=$TYPES
    run_batch "$start" "$end" > "$TMP/batch_$(printf '%04d' "$start")"
    echo "  $start-$end"
done

uv run --no-project python "$REPO/scripts/dat_templates.py" assemble "$OUT" "$TMP"/batch_*
uv run --no-project python "$REPO/scripts/dat_templates.py" gen-core
