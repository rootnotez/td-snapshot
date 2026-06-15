#!/bin/bash
set -e

stamp_file() {
    local file="$1"
    local name
    name=$(basename "$file")
    local version
    version=$(awk -v n="$name" '$1 == n { print $2 }' src/versions.txt)
    if [ -z "$version" ]; then
        echo "ERROR: no version entry for $name in src/versions.txt" >&2
        exit 1
    fi

    if head -1 "$file" | grep -q "^# ${name}"; then
        tail -n +2 "$file" > /tmp/td_stamp_body
    else
        cp "$file" /tmp/td_stamp_body
    fi

    local hash
    hash=$(shasum -a 256 /tmp/td_stamp_body | cut -d' ' -f1)
    { echo "# ${name} v${version} | sha256:${hash}"; cat /tmp/td_stamp_body; } > "$file"
    echo "  stamped $file"
}

# core.py carries a VERSION constant surfaced in the snapshot output preamble;
# keep it in sync with the `core.py` entry in src/versions.txt. Run this BEFORE
# stamp_file so the header hash covers the synced VERSION value.
sync_core_version() {
    local file="src/core.py"
    local version
    version=$(awk '$1 == "core.py" { print $2 }' src/versions.txt)
    if [ -z "$version" ]; then
        echo "ERROR: no version entry for core.py in src/versions.txt" >&2
        exit 1
    fi
    if ! grep -q "^VERSION = " "$file"; then
        echo "ERROR: no VERSION line in $file" >&2
        exit 1
    fi
    sed -E "s/^VERSION = .*/VERSION = '${version}'/" "$file" > /tmp/td_core_py
    mv /tmp/td_core_py "$file"
    echo "  synced $file VERSION = ${version}"
}

sync_core_version

for f in src/*.py; do
    stamp_file "$f"
done

rm -f /tmp/td_stamp_body

# The tocdir package is versioned as a whole via __version__ in its
# __init__.py, kept in sync with the `tocdir` entry in src/versions.txt.
stamp_package() {
    local init="src/tocdir/__init__.py"
    local version
    version=$(awk '$1 == "tocdir" { print $2 }' src/versions.txt)
    if [ -z "$version" ]; then
        echo "ERROR: no version entry for tocdir in src/versions.txt" >&2
        exit 1
    fi
    if ! grep -q '^__version__ = ' "$init"; then
        echo "ERROR: no __version__ line in $init" >&2
        exit 1
    fi
    sed -E "s/^__version__ = .*/__version__ = \"${version}\"/" "$init" > /tmp/td_init_py
    mv /tmp/td_init_py "$init"
    echo "  stamped $init __version__ = ${version}"
}

stamp_package
