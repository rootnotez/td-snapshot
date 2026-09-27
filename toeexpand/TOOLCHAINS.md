# TD toolchain registry

Registry of TouchDesigner builds whose `toeexpand`/`toecollapse` toolchain
has been validated for this repo (see `tests/toolchain/README.md` for the
regression workflow that produces the hashes and golden sets below, and
`scripts/toolchain-check.sh` for the one-command post-update check).

## Keeping old builds around

DMGs are kept **outside this repo**, in `TD_BUILDS_DIR` (default
`~/rootnotez/touch-designer/td-builds`), named
`TouchDesigner.<build>.arm64.dmg`. Old builds are downloadable from the
Derivative archive: <https://derivative.ca/download/archive>.

Verify a downloaded DMG against the sha256 recorded below before using it:

```
shasum -a 256 "$TD_BUILDS_DIR/TouchDesigner.<build>.arm64.dmg"
```

To use an archived build for a one-off check or comparison, mount it
read-only via `scripts/toolchain.sh` and point `TD_TOOLCHAIN_BIN` at the
mounted bundle's `Contents/MacOS`:

```
TD_TOOLCHAIN_BIN="$(scripts/toolchain.sh bin <build>)"
```

**Why the whole app bundle has to be mounted:** the `toeexpand`/`toecollapse`
binaries are ~60 KB wrapper executables — they load the real implementation
(`libUT.dylib`, `libtools.dylib`, `libAV.dylib`) via `@rpath` from the app
bundle's `Contents/Frameworks/`. A copy of just the two binaries outside the
bundle fails in `dyld` at launch. `scripts/toolchain.sh` mounts the DMG
read-only and non-browsing instead of copying anything out of it.

## Validated builds

| Build | DMG filename | DMG sha256 | Current until | Golden set | Notes |
|---|---|---|---|---|---|
| 2025.32460 | `TouchDesigner.2025.32460.arm64.dmg` | `7447df344d6744c3b4f3292a7563a6cb32d9037240851b6edf5460e7eed9897f` | 2026-09-26 | `tests/toolchain/golden/2025.32460/` | wrapper hashes toeexpand `a7bcf116b7314ca82a75e840b58ceb4586ca7da2b7304a87dd23bb41a455bf35` / toecollapse `6cc392eefdf1ebae8f82c7be6b1edf07a144168c622f8efd43722333b559e61c`; dylibs libUT `4d14031306d12f8a84fc0cf591c6ddff46e0f671cc15ad0a6572229d4e3b8dc2`, libtools `4bbe28258158525e191c1c7c3cc079d8c6b03e5abd10f089c3e0495c4a656acb`, libAV `b8c26c7d2330c514aec7ddd2b404f84ca4943cb363a1542cf061736a56d3d1a1` |
| 2025.33230 | `TouchDesigner.2025.33230.arm64.dmg` | `d53e49b0e7ade48ddfeda6cf7dd7f6baeb249266691692279c2122f4e05c62fd` | current | `tests/toolchain/golden/2025.33230/` | toeexpand `24a699f0d4d01f5b4db81b50ef15d619e6deefd1c8d37b766861a679e3b490a0` / toecollapse `ac5265cf9c4134fa6ce6d9d527604b4bcdbd8ab8345aeac44a9b4d3d53e24611`; libUT `3250b64221f014ad51c4634b01f907570b1c45e39e90de5285ae781a4654dd45`, libtools `c4f775ab68b53073c96ce63e5fef976e8bf1df9e8e27fcc6dc50e74cad5658f7`, libAV `8125b1a2ab52ae51f45132208d36a7d8bbe35b5c126ae24513315dcc9acd7d72`. No toolchain behaviour change vs 2025.32460 across 1,813 inputs — see the delta report `toeexpand/toolchain-deltas/2026-09-26_32460-vs-33230.md`, cross-checked against both golden sets (`tests/toolchain/golden/2025.32460/`, `tests/toolchain/golden/2025.33230/`) |

"Golden set" paths are where the committed expansion manifests for that
toolchain build live, once recorded (`tcdiff record --bin <bin> --out
tests/toolchain/golden/<build>/`) — see the layout contract in
`tests/toolchain/README.md`. A row with no golden set recorded yet just
means the toolchain's hashes are pinned here but `tcdiff record` hasn't been
run and committed for it.
