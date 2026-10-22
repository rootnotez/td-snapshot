#!/bin/bash
set -e

# Record the default DAT texts of the installed TouchDesigner build into
# dat-templates/<build>.json, then regenerate the matching table in src/core.py.
#
# It creates and destroys every operator type (minus the risky ones in
# capture_td.py's SKIP) inside /project1/dat_templates_capture, in batches so
# TD's UI isn't frozen for long. So it runs in an independent bridge session:
# a TouchDesigner instance of its own, started with td-claude-bridge's
# tools/session.sh on a free port (never 9982, the user's own project) and
# quit, without saving, when the script exits.
#
#   scripts/capture-dat-templates.sh [--force] [--port P]
#
#   --force    overwrite an existing dat-templates/<build>.json
#   --port P   start the session on port P instead of the first free one
#
# TD_BRIDGE overrides the td-claude-bridge checkout (default: ../td-claude-bridge),
# TD_APP the TouchDesigner app the session runs (as in session.sh).
# TD_BRIDGE_PORT or TD_PORT set means "use the session already on that port"
# (as td.sh reads them): no session is started or stopped.

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TD_BRIDGE="${TD_BRIDGE:-$REPO/../td-claude-bridge}"
SCRIPT="$REPO/dat-templates/capture_td.py"
BATCH=60
FORCE=0
SESSION_PORT=()
while [ $# -gt 0 ]; do
    case "$1" in
        --force) FORCE=1; shift ;;
        --port) SESSION_PORT=(--port "${2:?--port needs a number}"); shift 2 ;;
        *) echo "usage: scripts/capture-dat-templates.sh [--force] [--port P]" >&2; exit 2 ;;
    esac
done

if [ ! -x "$TD_BRIDGE/td.sh" ] || [ ! -f "$TD_BRIDGE/tools/session.sh" ]; then
    echo "ERROR: no td.sh and tools/session.sh in $TD_BRIDGE (set TD_BRIDGE to override)" >&2
    exit 1
fi

TMP="$(mktemp -d)"
SESSION_DIR=""
cleanup() {
    if [ -n "$SESSION_DIR" ]; then
        bash "$TD_BRIDGE/tools/session.sh" stop "$SESSION_DIR" || true
    fi
    rm -r "$TMP"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

if [ -n "${TD_BRIDGE_PORT:-}${TD_PORT:-}" ]; then
    PORT="${TD_BRIDGE_PORT:-$TD_PORT}"
    echo "Using the bridge session already on port $PORT (TD_BRIDGE_PORT/TD_PORT is set)."
    if [ "$PORT" = 9982 ]; then
        echo "WARNING: 9982 is usually your own open project; the capture creates and destroys ops in its /project1." >&2
    fi
else
    # The session runs the installed app, so an existing record can be
    # refused before TD is started (the probe below checks again).
    BUILD="$(defaults read "${TD_APP:-/Applications/TouchDesigner.app}/Contents/Info" CFBundleVersion 2>/dev/null || true)"
    if [ -n "$BUILD" ] && [ -f "$REPO/dat-templates/$BUILD.json" ] && [ "$FORCE" -eq 0 ]; then
        echo "ERROR: dat-templates/$BUILD.json already exists (re-run with --force to overwrite)" >&2
        exit 1
    fi
    SESSION_DIR="$TMP/session"
    echo "Starting an independent TouchDesigner session..."
    PORT="$(bash "$TD_BRIDGE/tools/session.sh" start "$SESSION_DIR" ${SESSION_PORT[@]+"${SESSION_PORT[@]}"})"
fi
# td.sh prefers TD_BRIDGE_PORT to TD_PORT, so this one reaches every call.
export TD_BRIDGE_PORT="$PORT"

# td.sh exec -q prints only the script's stdout, and on an exception exits 1
# with the bridge's whole reply on stderr.
run_batch() {
    if ! { printf 'START = %d\nEND = %d\n' "$1" "$2"; cat "$SCRIPT"; } \
            | "$TD_BRIDGE/td.sh" exec -q > "$TMP/reply"; then
        echo "ERROR: batch $1-$2 failed (td.sh reported why above)" >&2
        exit 1
    fi
    if ! grep '^@@DATTEMPLATES@@ ' "$TMP/reply"; then
        echo "ERROR: batch $1-$2 printed no @@DATTEMPLATES@@ line:" >&2
        cat "$TMP/reply" >&2
        exit 1
    fi
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
