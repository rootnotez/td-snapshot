#!/bin/bash
set -e

# Generates src/hashes.txt: source-file checksums, the built td-snapshot.tox
# checksum, and the toeexpand toolchain that collapsed it.
#
# Run by build.sh AFTER shrink.sh, so the recorded td-snapshot.tox hash
# matches the binary just rebuilt — not the previous build's. Reads the
# already-stamped src/*.py bodies (stamp.sh runs earlier in build.sh).

TD_APP=/Applications/TouchDesigner.app
TOEEXPAND_BIN="$TD_APP/Contents/MacOS/toeexpand"
TOECOLLAPSE_BIN="$TD_APP/Contents/MacOS/toecollapse"
TD_PLIST="$TD_APP/Contents/Info.plist"

td_build="unknown"
if [ -f "$TD_PLIST" ]; then
    td_build=$(/usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "$TD_PLIST" 2>/dev/null || echo "unknown")
fi

{
    echo "td-snapshot — source file checksums"
    echo ""
    for f in src/*.py; do
        name=$(basename "$f")
        version=$(awk -v n="$name" '$1 == n { print $2 }' src/versions.txt)
        hash=$(tail -n +2 "$f" | shasum -a 256 | cut -d' ' -f1)
        printf "%-30s v%-8s %s\n" "${name}:" "$version" "$hash"
    done
    echo ""
    echo "td-snapshot — tocdir package"
    echo ""
    pkg_version=$(awk '$1 == "tocdir" { print $2 }' src/versions.txt)
    pkg_hash=$(find src/tocdir -name '*.py' | sort | xargs shasum -a 256 | shasum -a 256 | cut -d' ' -f1)
    printf "%-30s v%-8s %s\n" "tocdir:" "$pkg_version" "$pkg_hash"
    echo ""
    echo "td-snapshot — binary artifact checksum"
    echo ""
    if [ -f td-snapshot.tox ]; then
        tox_hash=$(shasum -a 256 td-snapshot.tox | cut -d' ' -f1)
        printf "%-30s %s\n" "td-snapshot.tox:" "$tox_hash"
    else
        printf "%-30s %s\n" "td-snapshot.tox:" "(not found)"
    fi
    echo ""
    echo "td-snapshot — toeexpand toolchain (TouchDesigner ${td_build})"
    echo ""
    for bin in "$TOEEXPAND_BIN" "$TOECOLLAPSE_BIN"; do
        bin_name=$(basename "$bin")
        if [ -x "$bin" ]; then
            bin_hash=$(shasum -a 256 "$bin" | cut -d' ' -f1)
            printf "%-30s %s\n" "${bin_name}:" "$bin_hash"
        else
            printf "%-30s %s\n" "${bin_name}:" "(not found)"
        fi
    done
} > src/hashes.txt

echo "Generated src/hashes.txt"
