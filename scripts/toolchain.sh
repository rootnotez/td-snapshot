#!/bin/bash
set -e

# Resolves a TouchDesigner toolchain's Contents/MacOS directory for the
# tests/toolchain regression workflow (see tests/toolchain/README.md).
#
#   scripts/toolchain.sh bin current      -> /Applications/TouchDesigner.app/Contents/MacOS
#   scripts/toolchain.sh bin <build>       -> mounts (or reuses) the build's DMG, prints its MacOS dir
#   scripts/toolchain.sh detach <build>    -> detaches that build's DMG
#   scripts/toolchain.sh list              -> DMGs in TD_BUILDS_DIR and their mount state
#
# Never installs anything or copies the app out of the DMG; archived builds
# run in place from a read-only, non-browsing mount.
#
# Usage:
#   TD_TOOLCHAIN_BIN=$(scripts/toolchain.sh bin 2025.32460)

usage() {
    cat >&2 <<'EOF'
Usage:
  scripts/toolchain.sh bin <build|current>
  scripts/toolchain.sh detach <build>
  scripts/toolchain.sh list

Env:
  TD_BUILDS_DIR   directory holding TouchDesigner.<build>.arm64.dmg files
                  (default: $HOME/rootnotez/touch-designer/td-builds)
EOF
}

builds_dir() {
    echo "${TD_BUILDS_DIR:-$HOME/rootnotez/touch-designer/td-builds}"
}

dmg_path_for_build() {
    local build="$1"
    local dir
    dir="$(builds_dir)"
    echo "${dir}/TouchDesigner.${build}.arm64.dmg"
}

# Prints the mount-point (volume root) of a dmg if it is already attached
# anywhere, else prints nothing.
mounted_root_for_dmg() {
    local dmg="$1"
    hdiutil info -plist | plutil -convert json -o - - | \
        jq -r --arg img "$dmg" '
            .images[]? | select(.["image-path"] == $img) |
            (."system-entities"[]? | .["mount-point"] // empty)
        ' | head -1
}

build_from_dmg_name() {
    local dmg="$1"
    local base
    base="$(basename "$dmg")"
    base="${base#TouchDesigner.}"
    base="${base%.arm64.dmg}"
    echo "$base"
}

cmd_bin() {
    local target="${1:-}"
    if [ -z "$target" ]; then
        echo "ERROR: bin requires <build|current>" >&2
        usage
        exit 2
    fi

    if [ "$target" = "current" ]; then
        local app="/Applications/TouchDesigner.app"
        if [ ! -d "$app" ]; then
            echo "ERROR: $app not found" >&2
            exit 1
        fi
        echo "$app/Contents/MacOS"
        return 0
    fi

    local build="$target"
    local dmg
    dmg="$(dmg_path_for_build "$build")"
    if [ ! -f "$dmg" ]; then
        echo "ERROR: DMG not found: $dmg" >&2
        exit 1
    fi

    local root
    root="$(mounted_root_for_dmg "$dmg")"
    if [ -z "$root" ]; then
        local mountpoint="${TMPDIR:-/tmp}/td-${build}"
        mkdir -p "$(dirname "$mountpoint")"
        echo "mounting $dmg at $mountpoint ..." >&2
        hdiutil attach -readonly -nobrowse -mountpoint "$mountpoint" "$dmg" >&2
        root="$mountpoint"
    else
        echo "reusing existing mount: $root" >&2
    fi

    local app="$root/TouchDesigner.app"
    if [ ! -d "$app" ]; then
        echo "ERROR: TouchDesigner.app not found under $root" >&2
        exit 1
    fi

    local actual
    actual="$(plutil -extract CFBundleVersion raw -o - "$app/Contents/Info.plist" 2>/dev/null || true)"
    if [ "$actual" != "$build" ]; then
        echo "ERROR: mounted app reports CFBundleVersion=$actual, expected $build" >&2
        exit 1
    fi

    echo "$app/Contents/MacOS"
}

cmd_detach() {
    local build="${1:-}"
    if [ -z "$build" ]; then
        echo "ERROR: detach requires <build>" >&2
        exit 2
    fi

    local dmg
    dmg="$(dmg_path_for_build "$build")"
    local root
    root="$(mounted_root_for_dmg "$dmg")"
    if [ -z "$root" ]; then
        echo "not mounted: $dmg" >&2
        return 0
    fi

    echo "detaching $root ..." >&2
    hdiutil detach "$root" >&2
}

cmd_list() {
    local dir
    dir="$(builds_dir)"
    if [ ! -d "$dir" ]; then
        echo "no such directory: $dir" >&2
        exit 1
    fi

    local dmg build root
    for dmg in "$dir"/TouchDesigner.*.arm64.dmg; do
        [ -e "$dmg" ] || continue
        build="$(build_from_dmg_name "$dmg")"
        root="$(mounted_root_for_dmg "$dmg")"
        if [ -n "$root" ]; then
            printf '%s  mounted at %s\n' "$build" "$root"
        else
            printf '%s  not mounted\n' "$build"
        fi
    done
}

main() {
    local sub="${1:-}"
    case "$sub" in
        bin)
            shift
            cmd_bin "$@"
            ;;
        detach)
            shift
            cmd_detach "$@"
            ;;
        list)
            shift
            cmd_list "$@"
            ;;
        *)
            usage
            exit 2
            ;;
    esac
}

main "$@"
