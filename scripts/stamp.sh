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

for f in src/*.py; do
    stamp_file "$f"
done

{
    echo "td-snapshot — source file checksums"
    echo ""
    for f in src/*.py; do
        name=$(basename "$f")
        version=$(awk -v n="$name" '$1 == n { print $2 }' src/versions.txt)
        hash=$(tail -n +2 "$f" | shasum -a 256 | cut -d' ' -f1)
        printf "%-30s v%-8s %s\n" "${name}:" "$version" "$hash"
    done
} > src/hashes.txt

echo "Generated src/hashes.txt"
rm -f /tmp/td_stamp_body
