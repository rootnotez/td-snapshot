# Toolchain regression workflow

Detects behaviour changes in TouchDesigner's `toeexpand` / `toecollapse`
across TD builds, and pins the capabilities the rest of this repo relies on.

The core idea: what each toolchain produces for a fixed set of inputs is
recorded as **committed sha256 manifests** (`golden/<toolchain-build>/`), so a
future toolchain can be checked against the last known-good one without
having the old binary on hand. The old binary is only needed (via its
archived DMG, see `toeexpand/TOOLCHAINS.md`) to investigate a difference.

## Layout (contract — other tools depend on these paths)

```
tests/toolchain/
  README.md            this file
  common.py            shared helpers: bin resolution, expand/collapse, manifests
  inputs.txt           repo-relative globs = the golden input set
  tcdiff.py            record / compare / cross / control  (PEP 723, no deps)
  test_capabilities.py pytest contract suite
  raw_kinds_allowlist.txt  kind suffixes allowed to stay unparsed (raw)
  gen/                 fixture generators, run inside TD via td-claude-bridge
    every_op.py        one op of every class in `families`
    features.py        format features td-snapshot depends on
  fixtures/<save-build>/<name>.tox   generated fixtures, FROZEN once committed
  golden/<toolchain-build>/
    index.jsonl        one JSON object per input, sorted by id
    trees/<id>.sha256  expansion manifest per input (shasum format)
  runs/                gitignored scratch for ad-hoc (external-corpus) records
```

- **`<save-build>`** — the TD build that *saved* the fixture (its `.build`
  line). Fixtures are never regenerated in place; a new build gets a new dir,
  so the set accumulates files saved by every build we have passed through.
- **`<toolchain-build>`** — the build of the toeexpand/toecollapse that
  *produced* the manifest (`CFBundleVersion` of the app bundle).
- **`<id>`** — input path relative to the record root (the repo root for the
  golden set), POSIX separators. `trees/<id>.sha256` mirrors that path.

## Binary resolution

`TD_TOOLCHAIN_BIN` = a `…/TouchDesigner.app/Contents/MacOS` directory.
Default `/Applications/TouchDesigner.app/Contents/MacOS`. An archived build is
used by mounting its DMG read-only (`scripts/toolchain.sh bin <build>`) — the
binaries must run from inside an app bundle so `@loader_path/../Frameworks`
resolves `libUT` / `libtools` / `libAV` (copies outside a bundle fail in dyld).

## Manifest format

`trees/<id>.sha256` — exactly `shasum -a 256` output, sorted by path:

```
<64-hex>  <name>.toc
<64-hex>  <name>.dir/.build
<64-hex>  <name>.dir/<...>
```

Paths are relative to the directory holding the `.toc` + `.dir`. `.DS_Store`
is excluded. Verify by hand with `shasum -a 256 -c` from that directory.

`index.jsonl` — one object per input, keys:

| key | meaning |
|---|---|
| `id` | input id (see above) |
| `input_sha256` | sha256 of the input file |
| `expand_rc` | toeexpand exit code (1 is normal on success) |
| `expand_ok` | a `.dir/` + `.toc` was produced |
| `expand_stdout` / `expand_stderr` | decoded latin-1, truncated to 2000 chars |
| `file_count` | entries in the tree manifest |
| `tree_sha256` | sha256 of the manifest file text (quick equality) |
| `collapse_rc` | toecollapse exit code |
| `collapse_sha256` | sha256 of the collapsed file, or null |
| `collapse_equals_input` | collapsed bytes == input bytes |
| `refixed_point` | expand(collapse(tree)) manifest == tree manifest |
| `toolchain_build` | CFBundleVersion of the bin used |

## `tcdiff.py` CLI

```
uv run tests/toolchain/tcdiff.py record  [--bin DIR] [--out DIR] [--root DIR] [--keep-trees DIR] [--jobs N] [inputs...]
uv run tests/toolchain/tcdiff.py compare A_DIR B_DIR [--report FILE]
uv run tests/toolchain/tcdiff.py cross   --bin DIR --trees DIR --against GOLDEN_DIR [--report FILE]
uv run tests/toolchain/tcdiff.py control [--bin DIR] [inputs...]
```

- `record` defaults: `--bin` from `TD_TOOLCHAIN_BIN`, `--root` = repo root,
  inputs = `inputs.txt`, `--out` = `golden/<toolchain-build>/`.
- `compare` buckets per id: `identical`, `build-only` (only `.dir/.build`
  differs), `content-diff`, `fileset-diff`, `fail-A`, `fail-B`, `only-A`,
  `only-B`; also reports collapse-sha / round-trip / fixed-point changes.
- `cross` collapses trees recorded by another toolchain (`--keep-trees`) with
  `--bin`, and compares the result to that toolchain's `collapse_sha256`.
- `control` records twice with the same bin into temp dirs and requires
  `compare` to report 100 % identical (determinism + harness sanity).
