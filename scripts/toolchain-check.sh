#!/bin/bash
set -euo pipefail

# One-command post-"updated TouchDesigner" check for the toolchain regression
# workflow (see tests/toolchain/README.md and the README.md "After updating
# TouchDesigner" section).
#
# Resolves the currently-installed toeexpand/toecollapse ("NEW"), refreshes
# src/hashes.txt, runs a determinism control (hard gate), records NEW's
# results against the golden input set and compares them to the newest
# previously-committed golden build (and to NEW's own golden set, if one is
# already recorded), then runs the pytest suite against NEW. All of that is
# collected into a final PASS/DIFF/FAIL summary rather than aborting on the
# first non-identical comparison.
#
# Usage: scripts/toolchain-check.sh [--corpus]
#   --corpus   also rebuild the shipped .tox corpus for NEW and census-diff
#              it against a previously-saved census (~5 min; opt-in).

usage() {
    cat >&2 <<'EOF'
Usage: scripts/toolchain-check.sh [--corpus]

  --corpus   also rebuild the shipped .tox corpus for the current
             TouchDesigner build and diff its census against a
             previously-saved one under tests/toolchain/runs/ (slow, ~5 min).
EOF
}

CORPUS=0
for arg in "$@"; do
    case "$arg" in
        --corpus) CORPUS=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $arg" >&2; usage; exit 2 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GOLDEN_DIR="tests/toolchain/golden"
RUNS_DIR="tests/toolchain/runs"
mkdir -p "$RUNS_DIR"

STEP_NAMES=()
STEP_RESULTS=()
STEP_NOTES=()

record_status() {
    STEP_NAMES+=("$1")
    STEP_RESULTS+=("$2")
    STEP_NOTES+=("${3:-}")
}

note() {
    printf '\n=== %s ===\n' "$*"
}

print_summary() {
    note "Summary"
    local i
    for i in "${!STEP_NAMES[@]}"; do
        if [ -n "${STEP_NOTES[$i]}" ]; then
            printf '%-32s %-8s %s\n' "${STEP_NAMES[$i]}" "${STEP_RESULTS[$i]}" "${STEP_NOTES[$i]}"
        else
            printf '%-32s %-8s\n' "${STEP_NAMES[$i]}" "${STEP_RESULTS[$i]}"
        fi
    done
    echo ""
    if [ "$COMPARE_DIFF" -eq 1 ]; then
        cat <<EOF
Compare step(s) showed differences against a golden set. Next steps:
  1. Mount the previous build and cross-check:
       PREV_BIN="\$(scripts/toolchain.sh bin $PREV_BUILD_FOR_MSG)"
       uv run tests/toolchain/tcdiff.py cross --bin "\$NEW_BIN" \\
           --trees <trees-from-a-prior--keep-trees-record> --against $GOLDEN_DIR/$PREV_BUILD_FOR_MSG
  2. Run an external-corpus A/B: \`tcdiff record --root <corpus>\` with both
     the previous and NEW toolchains, then \`tcdiff compare\` the two.
  3. Regenerate fixtures for the new build:
       tests/toolchain/gen/run.sh every_op
       tests/toolchain/gen/run.sh features
     (needs a live TouchDesigner session with the td-claude-bridge component;
     see tests/toolchain/gen/README.md.)
  4. Record goldens for both toolchains once fixtures are settled:
       uv run tests/toolchain/tcdiff.py record --bin "\$NEW_BIN" --out $GOLDEN_DIR/$NEW_BUILD
  5. Tag any new findings in toeexpand/FORMAT.md / toeexpand/DEVIATIONS.md
     with the $NEW_BUILD build number, and write a delta note under
     toeexpand/toolchain-deltas/.
See tests/toolchain/README.md for the full contract.
EOF
    else
        echo "No compare step showed a difference against a golden set."
    fi
    # Errata (suspected TD-side bugs) are re-checked on every build, diff or not.
    if ! grep -q "| $NEW_BUILD |" toeexpand/ERRATA.md 2>/dev/null; then
        echo ""
        echo "toeexpand/ERRATA.md has no History row for $NEW_BUILD yet: re-check each"
        echo "entry (e.g. tests/toolchain/gen/run.sh probe_parm_flags) and record the result."
    fi
    if [ "$OTHER_FAIL" -eq 1 ]; then
        echo "One or more non-compare steps (pytest / corpus build / census) failed above — see their output."
    fi
}

COMPARE_DIFF=0
OTHER_FAIL=0
PREV_BUILD_FOR_MSG=""

# ---------------------------------------------------------------------------
# a. Resolve NEW bin + build
# ---------------------------------------------------------------------------
note "a. Resolve current toolchain"
NEW_BIN="$(scripts/toolchain.sh bin current)"
NEW_INFO_PLIST="$(dirname "$NEW_BIN")/Info.plist"
NEW_BUILD="$(plutil -extract CFBundleVersion raw -o - "$NEW_INFO_PLIST")"
echo "NEW bin:   $NEW_BIN"
echo "NEW build: $NEW_BUILD"
record_status "a. resolve-new" "PASS" "build=$NEW_BUILD"

# ---------------------------------------------------------------------------
# b. Find the newest committed golden set other than NEW's own build
# ---------------------------------------------------------------------------
note "b. Find previous committed golden set"
PREV_BUILD=""
COMMITTED_BUILDS="$(git ls-files "$GOLDEN_DIR" | awk -F/ 'NF>4 {print $4}' | sort -u -V || true)"
while IFS= read -r b; do
    [ -z "$b" ] && continue
    [ "$b" = "$NEW_BUILD" ] && continue
    PREV_BUILD="$b"
done <<< "$COMMITTED_BUILDS"

if [ -n "$PREV_BUILD" ]; then
    echo "previous golden build: $PREV_BUILD ($GOLDEN_DIR/$PREV_BUILD)"
    record_status "b. find-previous" "PASS" "prev=$PREV_BUILD"
    PREV_BUILD_FOR_MSG="$PREV_BUILD"
else
    echo "no previous committed golden set found under $GOLDEN_DIR/ (only NEW's own build, or none at all) — continuing without it"
    record_status "b. find-previous" "NONE" "no prior golden committed"
fi

# ---------------------------------------------------------------------------
# c. Refresh src/hashes.txt
# ---------------------------------------------------------------------------
note "c. Refresh src/hashes.txt"
./scripts/hashes.sh
git --no-pager diff --stat -- src/hashes.txt || true
record_status "c. hashes.sh" "PASS"

# ---------------------------------------------------------------------------
# d. Determinism control (hard gate — abort on failure)
# ---------------------------------------------------------------------------
note "d. Determinism control (tcdiff control)"
if TD_TOOLCHAIN_BIN="$NEW_BIN" uv run tests/toolchain/tcdiff.py control --bin "$NEW_BIN"; then
    record_status "d. control" "PASS"
else
    record_status "d. control" "FAIL"
    echo "FATAL: tcdiff control failed — toolchain or harness is non-deterministic." >&2
    print_summary
    exit 1
fi

# ---------------------------------------------------------------------------
# e. Record NEW against the golden input set, compare to previous + own
# ---------------------------------------------------------------------------
note "e. Record + compare (tcdiff record / compare)"
CHECK_OUT="$RUNS_DIR/check-$NEW_BUILD"
rm -rf "$CHECK_OUT"
uv run tests/toolchain/tcdiff.py record --bin "$NEW_BIN" --out "$CHECK_OUT"
record_status "e. record-new" "PASS" "out=$CHECK_OUT"

if [ -n "$PREV_BUILD" ]; then
    PREV_REPORT="$RUNS_DIR/check-$NEW_BUILD.md"
    set +e
    uv run tests/toolchain/tcdiff.py compare "$GOLDEN_DIR/$PREV_BUILD" "$CHECK_OUT" --report "$PREV_REPORT"
    PREV_RC=$?
    set -e
    if [ "$PREV_RC" -eq 0 ]; then
        record_status "e. compare-vs-prev" "PASS" "$PREV_BUILD -> identical"
    else
        record_status "e. compare-vs-prev" "DIFF" "$PREV_BUILD vs $NEW_BUILD, report=$PREV_REPORT"
        COMPARE_DIFF=1
    fi
else
    record_status "e. compare-vs-prev" "SKIP" "no previous golden"
fi

OWN_GOLDEN="$GOLDEN_DIR/$NEW_BUILD"
if [ -d "$OWN_GOLDEN" ]; then
    OWN_REPORT="$RUNS_DIR/check-$NEW_BUILD-vs-own-golden.md"
    set +e
    uv run tests/toolchain/tcdiff.py compare "$OWN_GOLDEN" "$CHECK_OUT" --report "$OWN_REPORT"
    OWN_RC=$?
    set -e
    if [ "$OWN_RC" -eq 0 ]; then
        record_status "e. compare-vs-own" "PASS" "identical to recorded $NEW_BUILD golden"
    else
        record_status "e. compare-vs-own" "DIFF" "differs from recorded $NEW_BUILD golden, report=$OWN_REPORT"
        COMPARE_DIFF=1
    fi
else
    record_status "e. compare-vs-own" "SKIP" "no golden/$NEW_BUILD recorded yet"
fi

# ---------------------------------------------------------------------------
# f. pytest against NEW
# ---------------------------------------------------------------------------
note "f. pytest (tests/) against NEW"
set +e
TD_TOOLCHAIN_BIN="$NEW_BIN" uv run --no-project --with pytest pytest tests -q
PYTEST_RC=$?
set -e
if [ "$PYTEST_RC" -eq 0 ]; then
    record_status "f. pytest" "PASS"
else
    record_status "f. pytest" "FAIL" "pytest exit=$PYTEST_RC"
    OTHER_FAIL=1
fi

# ---------------------------------------------------------------------------
# g. Optional: shipped-corpus rebuild + census diff
# ---------------------------------------------------------------------------
if [ "$CORPUS" -eq 1 ]; then
    note "g. Corpus rebuild + census diff (--corpus)"
    CORPUS_DEST="toeexpand/resources/shipped-$NEW_BUILD"
    if DEST_ROOT="$CORPUS_DEST" ./scripts/build-corpus.sh; then
        record_status "g. corpus-build" "PASS" "dest=$CORPUS_DEST"
    else
        record_status "g. corpus-build" "FAIL"
        OTHER_FAIL=1
    fi

    CENSUS_JSON="$RUNS_DIR/census-shipped-$NEW_BUILD.json"
    set +e
    PYTHONPATH=src uv run --no-project python -m tocdir census "$CORPUS_DEST" --json > "$CENSUS_JSON"
    CENSUS_RC=$?
    set -e
    if [ "$CENSUS_RC" -eq 0 ]; then
        record_status "g. census" "PASS" "out=$CENSUS_JSON"
    else
        record_status "g. census" "DIFF" "roundtrip_fail/load_errors nonzero, out=$CENSUS_JSON"
        COMPARE_DIFF=1
    fi

    if ! command -v jq >/dev/null 2>&1; then
        echo "jq not found — skipping census diff against the previous build"
    elif [ -z "$PREV_BUILD" ]; then
        echo "no previous golden build known — skipping census diff"
    else
        PREV_CENSUS_JSON="$RUNS_DIR/census-shipped-$PREV_BUILD.json"
        if [ -f "$PREV_CENSUS_JSON" ]; then
            echo "--- census diff: $PREV_BUILD -> $NEW_BUILD ---"
            for expr in '.kinds | keys' '.operator_types | keys' '.unparsed_kinds' \
                        '.toc_headers' '.build_versions' '.n_vocab' \
                        '.parm_vocab.modes | keys' '.cparm_vocab.row_shapes | keys'; do
                echo "## jq '$expr'"
                diff <(jq "$expr" "$PREV_CENSUS_JSON") <(jq "$expr" "$CENSUS_JSON") \
                    && echo "  (no difference)" || true
            done
        else
            echo "no census JSON found for previous build at $PREV_CENSUS_JSON — skipping census diff"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# h. Final summary
# ---------------------------------------------------------------------------
print_summary
