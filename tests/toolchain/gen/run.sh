#!/bin/bash
# Host-side runner for the tests/toolchain/gen fixture generators.
#
#   tests/toolchain/gen/run.sh <every_op|features> [OUT_DIR] [--force]
#
# Sends the matching generator script (every_op.py / features.py) to a live
# TouchDesigner session through td-claude-bridge's /exec, with
# `OUT_DIR = r'<abs path>'` prepended so the generator knows where to save
# its .tox/.json output. See tests/toolchain/gen/README.md and
# td-claude-bridge/README.md for how /exec works and how to start a session.
#
# Default OUT_DIR is tests/toolchain/fixtures/<build>, where <build> is
# asked from the live bridge (`app.build`, e.g. "2025.33230") so fixtures
# land under the directory named for the TD build that saved them, per the
# layout contract in tests/toolchain/README.md. Fixtures are frozen once
# committed: this script refuses to overwrite existing <generator>*.tox /
# <generator>.json files for that build unless --force is given.
#
# TD_BRIDGE overrides the td-claude-bridge checkout
# (default: /Users/arid/rootnotez/touch-designer/td-claude-bridge).
set -euo pipefail

usage() {
  echo "usage: $0 <every_op|features> [OUT_DIR] [--force]" >&2
  exit 2
}

[ "$#" -ge 1 ] || usage
GEN="$1"
shift

case "$GEN" in
  every_op|features) ;;
  *) echo "unknown generator: $GEN (expected 'every_op' or 'features')" >&2; exit 2 ;;
esac

FORCE=0
OUT_DIR_ARG=""
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    -*) echo "unknown option: $arg" >&2; usage ;;
    *) OUT_DIR_ARG="$arg" ;;
  esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
TD_BRIDGE="${TD_BRIDGE:-/Users/arid/rootnotez/touch-designer/td-claude-bridge}"

if [ ! -x "$TD_BRIDGE/td.sh" ]; then
  echo "ERROR: $TD_BRIDGE/td.sh not found or not executable (set TD_BRIDGE to override)" >&2
  exit 1
fi

SCRIPT="$HERE/$GEN.py"
if [ ! -f "$SCRIPT" ]; then
  echo "ERROR: generator script not found: $SCRIPT" >&2
  exit 1
fi

# td-claude-bridge's /exec wraps whatever the script printed as:
#   status: ok|exception
#   --- stdout ---
#   <captured stdout>
#   --- stderr ---        (only present if anything was written to stderr)
#   <captured stderr / traceback>
# (see td-claude-bridge/td_bridge_callbacks.py's `_exec`). This pulls out
# just the stdout section, e.g. to read back a single printed value.
bridge_stdout() {
  awk '
    /^--- stdout ---$/ { grab = 1; next }
    /^--- stderr ---$/ { grab = 0 }
    grab { print }
  '
}

bridge_ok() {
  grep -q '^status: ok'
}

# `app.build` (e.g. "2025.33230") identifies the TD build that will save
# the fixtures -- resolved defensively since it wasn't confirmed whether
# `app` is a real interpreter builtin inside /exec's fresh globals dict, or
# only reachable via `import td` (see every_op.py's `_tdglobal` docstring
# for the full reasoning); this mirrors that same fallback.
query_build() {
  local query reply
  query=$'try:\n    _b = app.build\nexcept NameError:\n    import td\n    _b = td.app.build\nprint(_b)\n'
  reply="$(printf '%s' "$query" | "$TD_BRIDGE/td.sh" exec)"
  if ! printf '%s' "$reply" | bridge_ok; then
    echo "ERROR: failed to query the TD build from the bridge:" >&2
    printf '%s\n' "$reply" >&2
    exit 1
  fi
  printf '%s' "$reply" | bridge_stdout | tr -d '[:space:]'
}

if [ -n "$OUT_DIR_ARG" ]; then
  OUT_DIR="$OUT_DIR_ARG"
else
  echo "Querying TD build from the bridge ($TD_BRIDGE)..." >&2
  BUILD="$(query_build)"
  if [ -z "$BUILD" ]; then
    echo "ERROR: got an empty build string from the bridge" >&2
    exit 1
  fi
  OUT_DIR="$REPO/tests/toolchain/fixtures/$BUILD"
fi

echo "generator: $GEN" >&2
echo "OUT_DIR:   $OUT_DIR" >&2

if [ "$FORCE" -eq 0 ] && [ -d "$OUT_DIR" ]; then
  existing="$(find "$OUT_DIR" -maxdepth 1 -type f \( -name "${GEN}*.tox" -o -name "${GEN}.json" \) 2>/dev/null || true)"
  if [ -n "$existing" ]; then
    echo "ERROR: fixture files for '$GEN' already exist in $OUT_DIR:" >&2
    printf '%s\n' "$existing" >&2
    echo "Fixtures are frozen once committed -- re-run with --force to overwrite." >&2
    exit 1
  fi
fi

mkdir -p "$OUT_DIR"

payload="$(printf "OUT_DIR = r'%s'\n" "$OUT_DIR"; cat "$SCRIPT")"

echo "Running $GEN.py inside TouchDesigner..." >&2
reply="$(printf '%s' "$payload" | "$TD_BRIDGE/td.sh" exec)"
printf '%s\n' "$reply"

bridge_ok <<<"$reply"
