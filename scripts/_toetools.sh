# shellcheck shell=bash
# Sourced by scripts that need toetools (the tocdir parser, split out to
# rootnotez/toetools on 2026-10-18). Pinned to a release tag; override with
# TOETOOLS_SPEC, e.g. a local checkout while changing both repos:
#   TOETOOLS_SPEC=git+file://$HOME/rootnotez/touch-designer/toetools ./scripts/build.sh
TOETOOLS_SPEC="${TOETOOLS_SPEC:-git+https://github.com/rootnotez/toetools@v0.6.0}"

toetools() { uvx --quiet --from "$TOETOOLS_SPEC" toetools "$@"; }
