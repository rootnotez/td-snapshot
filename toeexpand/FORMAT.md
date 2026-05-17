# toeexpand format notes

`toeexpand` (TouchDesigner CLI tool at `/Applications/TouchDesigner.app/Contents/MacOS/toeexpand`) expands a `.toe`/`.tox` into a git-diffable directory tree plus a sibling `.toc` index file. These notes were derived from:

- `2026-05-13_td_snapshot.tox.dir/` — small, hand-built `.tox`.
- `2026-05-17__datlab-classified-v1/v1/classifier.tox.dir/` — larger `.tox` with custom parameters, COMP inputs, table/script DATs.
- A 12-file sample expanded from `toeexpand/resources/` (TD-Tutorials, TouchDesigner_Shared, SharedTox, TDAudioAnalysis, isf-touchdesigner, FunctionStore_tools, TD-Toxes, etc.) covering both `.tox` and full project `.toe` files.

They may not cover every operator family.

Note: toeexpand accepts only `.toe`/`.tox` input. Pointing it at a `.zip` produces an empty `.toc` and no expansion — unzip first.

## Layout

For an input `td-snapshot.tox`, toeexpand produces:

```
td-snapshot.tox.toc     # flat list of every artifact path
td-snapshot.tox.dir/
  .build                # build metadata
  <root>.n              # node definition
  <root>.parm           # parameter values
  <root>.cparm          # custom-parameter definitions (only on COMPs with custom pars)
  <root>.panel          # panel layout (panel-bearing COMPs only)
  <root>.network        # external connector definitions (COMPs that expose in*/out* connectors)
  <root>.text           # text-DAT body
  <root>.table          # table-DAT body (binary)
  <root>.script         # script-DAT / script-CHOP body
  <root>.chop           # CHOP saved-state body
  <root>.feedback       # Feedback CHOP/TOP body
  <root>.beat           # Beat CHOP body
  <root>.gnode          # geometry COMP transform matrices
  <root>.ts             # time-slicer / track state
  <root>.replicator     # Replicator COMP state
  <root>.oldacbo        # legacy Audio CHOP buffer object
  <root>.lod            # bundled archive of a sub-tree (see below)
  # full .toe roots additionally produce:
  .start                # project startup settings
  .root                 # root viewport state
  .grps                 # group definitions
  .application          # desktop/pane layout
  <root>/               # subdir mirrors COMP children
    <child>.n
    ...
```

The `<root>` name is the top-level COMP name from the .tox (e.g. `td_snapshot`). One file per (node, kind); a node carries whichever subset of `{.n, .parm, .cparm, .panel, .network, .text, .table, .script}` applies to its type and configuration.

## `.toc` — table of contents

```
# 4 0 0 0 1
.build
td_snapshot.n
td_snapshot.parm
td_snapshot.panel
td_snapshot/core.n
...
```

- Line 1: header `# <v0> <v1> <v2> <v3> <v4>`. First field appears to be a format version (4 in this snapshot); remaining fields unknown — likely counters/flags. Present in every toeexpand output.
- Remaining lines: every file in `<basename>.dir/`, relative to the dir, in deterministic order. Acts as a manifest the inverse `toecollapse` tool can read.

## `.build` — build stamp

```
version 099
build 2025.32460
time Wed May 13 22:49:57 2026
osname macOS
osversion 15.7.4
```

Plain `key value` lines. Captures the TD version that produced the export. Sits at the top of the `.dir/`, outside any node subdir.

## `.n` — node definition

```
FAMILY:type
v <vx> <vy> <vzoom>
tile <x> <y> <w> <h>
flags = <tok> <tok> <tok>...
inputs
{
  <slot>\t<source-node-name>
  ...
}
color <r> <g> <b>
view <...12 numbers...>
end
```

- Line 1 — `FAMILY:type`. Family ∈ `COMP|TOP|CHOP|SOP|MAT|DAT|POP`. Type is the operator type id (`container`, `button`, `text`, `out`, `panelexec`, `parexec`, `par`, …).
- `v <x> <y> <zoom>` — only on COMPs; saved network-editor viewport for the COMP's interior.
- `tile <x> <y> <w> <h>` — node tile position and size in the parent network editor.
- `flags = ...` — space-separated tokens, e.g. `picked on current on viewer 1 parlanguage 0`. Token grammar appears to be `<name> <value>` pairs (`viewer 1`, `parlanguage 0`) interleaved with bare `<name> on` flags. Note the literal two spaces after `=`.
- `inputs { ... }` — present only when the node has incoming wires. Body is `<slot-index>\t<source-name>` lines, one per wire. Source name is the sibling node name (not a path) — wires are always intra-network.
- `color <r> <g> <b>` — RGB in 0–1.
- `view <...>` — 12-number editor view state, observed on DATs (text/parexec/panelexec). Layout not fully reverse-engineered.
- `end` — terminator.

Section order in the files observed: family, `v`, `tile`, `flags`, `inputs`, `color`, `view`, `end`.

## `.parm` — parameter values

```
?
pageindex 0 1
label 0 "> Clipboard"
clone 17 "" op.TDTox.op('defaultCOMPs/button')
file 48 "" f'scripts/{me.name}.py'
scaletofit 49 onlyshrink "parent().par[me.curPar.name] or me.curPar.val"
?
```

- `?` lines bracket each parameter page. Only changed-from-default parameters appear between them.
- Each parameter row: `<name> <mode> <value> [<expr>]`
  - `<name>` — parameter internal name.
  - `<mode>` — 32-bit integer bitfield. The width caught us off guard initially: the small `td_snapshot` only exercised the low byte (`0..49`), but `classifier.tox` parameter values use a wider range with bit 26 and bit 27 set.

    **Two-tier structure observed:**
    - High bits — coarse category. Observed: `0x04000000` (bit 26) on most rows; `0x0C000000` (bits 26+27) on rows whose values are operators or contain expressions of a particular kind (e.g. `Emb0data ... op('./stats_table')[...]`). Likely flags like "custom-parameter-page" or "OP-typed value". The small `td_snapshot` had neither set, which is why its modes fit in a byte.
    - Low byte — fine-grained flags. Observed values across both expansions: `0x00, 0x10, 0x11, 0x20, 0x30, 0x31, 0x40, 0x50, 0x51, 0x71, 0xC0` (when high byte is `0x04`) plus extras up to `0x1A3` when wider bits are set. The original small-file modes `0/16/17/32/48/49` are all low-byte-only values, and the same patterns reappear here combined with the high-byte category.

    | mode (decimal) | hex | example | value | expr |
    |---:|:---|:---|:---|:---|
    | 0 | `0x00000000` | `label 0 "> Clipboard"` | real | no |
    | 16 | `0x00000010` | `panels 16 copy_btn parent()` | real | yes |
    | 17 | `0x00000011` | `clone 17 "" op.TDTox.op(...)` | empty | yes |
    | 32 | `0x00000020` | `y 32 200` | real | no |
    | 48 | `0x00000030` | `file 48 "" f'scripts/{me.name}.py'` | empty | yes |
    | 49 | `0x00000031` | `scaletofit 49 onlyshrink "..."` | real | yes |
    | 67108864 | `0x04000000` | `pageindex 67108864 3` | real | no |
    | 67108928 | `0x04000040` | `Searchactive 67108928 on` | real | no |
    | 67109184 | `0x04000140` | `Version 67109184 1.0.1` | real | no |
    | 201326673 | `0x0C000051` | `Emb0data ... "" op('./stats_table')[...]` | empty | yes |
    | 201326912 | `0x0C000140` | `Emb0active 201326912 off` | real | no |

    Open: tease apart what specific TD ParMode each low-byte pattern maps to (CONSTANT/EXPRESSION/EXPORT/BIND × stored-expr/stored-bind/changed-from-default). A targeted fixture with one parameter per mode is the cleanest way to nail this down.
  - `<value>` — literal value token. Strings are double-quoted when needed; numbers, on/off, and bareword tokens (e.g. `onlyshrink`, `multiline`, `cp1252`) are unquoted.
  - `<expr>` — Python expression as written by the user. May be quoted (`"..."`) or unquoted (bare Python, including f-strings). Present only when the mode bit indicates an expression.

- The `pageindex` parameter (which page the param editor was last on) is captured here but is suppressed by the snapshot renderer ([src/core.py](../src/core.py)) because it tracks UI state, not user changes.

## `.cparm` — custom parameter *definitions*

Present on COMPs that expose custom parameters (the user-facing UI on `Base`/`Container`/etc.). Separate from `.parm`, which only holds the current *values*.

```
?
pages 4 "Record (in1)" "Search (in2)" "Cache to File" About
772804868 Emb:Emb0label Label 1 1 0 0 1 1 1 2 0 "" "" "Record (in1)" 1
-1374678782 K "K Neighbors" 1 3 1 1 1 100 100 2 0 "" "" "Search (in2)" 2
-1374678769 Selectdisplay Display 1 1 0 0 1 1 1 2 0 "" "" "Search (in2)" 4097 4 neighbors "Neighbors Table" votes "Category Votes" stats "Cache Stats" none None 4
772935937 Recorddur "Record Duration (seconds)" 1 1 0 0 1 1 25 2 0 "" "" "Record (in1)" 10 me.par.Recordtimer.eval()
?
```

- `?` lines bracket the block.
- `pages <count> <name1> <name2> ...` — declares the COMP's custom parameter pages, in order.
- Each subsequent line defines one custom parameter. Observed fields (positional):
  1. **type id** — large signed int (e.g. `772804868`, `-1374678782`). Encodes the par type (Toggle / Int / Float / Str / Menu / Pulse / OP / …). Same id ⇒ same type; the exact decoding of the int is unknown.
  2. **name** — internal name. Multi-component parameters use a `<group>:<name>` form (e.g. `Emb:Emb0label`).
  3. **label** — display label (quoted if it contains spaces).
  4. **size** (typically `1`, sometimes `3` for vector pars like `K`).
  5–11. Numeric range/default/clamp fields: roughly `<min-clamp-flag> <max-clamp-flag> <?> <min> <max> <default> <section>` — exact order not pinned down, but `K`'s `1 3 1 1 1 100 100 2` shows `size=3`, default and limits land where you'd expect for the `K Neighbors` integer parameter.
  12. **`0`** — appears constant in samples.
  13–14. Two empty strings — possibly tooltip / help text slots.
  15. **page name** — which page from the `pages` line this parameter sits on.
  16. **page-internal flags / sort order** — e.g. `1` to `11`, plus `4097` on menu types.
  - Menu parameters add a variable-length suffix: after the flags they emit `<entry-count> <key1> <label1> <key2> <label2> ...` followed by the trailing sort index.
  - Parameters with a bind/eval expression append the expression text at the end of the line (`me.par.Recordtimer.eval()` on `Recorddur`).

  This is the densest part of the format and where most precision loss would happen in a round-trip — leave verbatim unless you've decoded the exact column meanings against a TD-built fixture.

## `.network` — COMP external connectors

Present on COMPs that expose external in/out connectors (have `in_*` / `out_*` operators inside).

```
1
compinputs
{
0 	""
	in_record
	CHOP
1 	""
	in_search
	CHOP
}
end
```

- Line 1: format version (`1`).
- `compinputs { ... }` (and presumably `compoutputs`, not seen yet) blocks list connector slots.
- Each record: `<slot-index>\t"<label>"` then `\t<internal-op-name>` then `\t<family>` (CHOP/TOP/SOP/DAT/MAT/POP).
- Empty `""` label = no explicit user-set label.

## `.script` — Script DAT / Script CHOP / Script SOP body

```
1
{
   rate = 60
   start = 0
   tracklength = 1
   tracks = 1
   {
      name = activeIndex
      data_rle = 0
   }
}
```

- Line 1: version (`1`).
- Body: brace-nested `key = value` records. Used for the serialized internal state of Script-family operators (channels, point attrs, etc.). Pure ASCII, diffs cleanly.

## `.table` — Table DAT body (binary)

```
00000000: 31 0a 2a 00 00 00 01 00 00 00 02 00 00 00 09 00  1.*.............
00000010: 00 00 00 00 00 00 02 00 00 00 06 73 74 61 74 75  ...........statu
00000020: 73 00 ...                                        s. ...
```

- Line 1: `1\n` (version) — same convention as `.text`/`.script`.
- Line 2: `*` then a binary header (`\x00\x00\x00\x01`, `\x00\x00\x00\x02` = col count?, `\x00\x00\x00\x09` = row count? — needs more samples).
- Each cell: tag `\x00\x00\x00\x02`, then `\x00\x00\x00<LEN>` big-endian length prefix, then `<LEN>` bytes of UTF-8 text, then `\x00` terminator.

Binary, but predictable; cells are still human-readable in a hex dump, and small table changes produce small diffs.

## `.panel` — panel layout

Present only on panel-bearing COMPs (`COMP:container`, `COMP:button`, `COMP:text`, …).

```
1
3
12
u 0.424242
v 0.486486
trueu 0.424242
truev 0.486486
rollu 0.0808081
rollv 0.324324
children 1
screenw 50
screenh 40
screenwm 50
screenhm 40
picked 1
radioname scopy_btn          # root container only
lradioname scopy_btn         # root container only
```

- Lines 1–3: three integers (format version, sub-version, body-line-count). Body-line-count matches the number of key/value lines that follow.
- Body: `key value` per line. Observed keys: `u`/`v` (normalized scroll), `trueu`/`truev`, `rollu`/`rollv`, `children`, `screenw`/`screenh`, `screenwm`/`screenhm`, `picked`, `radioname`/`lradioname` (radio-group bookkeeping on parent containers).

## `.text` — DAT contents

```
2\n
*<padding>\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x1b\xcb#<text bytes>
```

- Line 1: `2` (format version).
- Line 2: starts with `*`, then 18 spaces (padding), then a binary header of five `\x00\x00\x00\x01` 32-bit big-endian ints followed by `\x00\x00\x00\x02` and a 32-bit length (`\x00\x00\x1b\xcb` = 7115 bytes in the sample) before the raw DAT body (`# core.py v1.1.2 …`). The body is whatever string content the DAT held (Python script, glsl, table CSV, etc.); the binary preamble carries DAT metadata (line count? encoding markers? — not fully decoded).
- Files end without a trailing newline marker beyond what the DAT body itself contains.

The binary header makes `.text` files slightly harder to diff than the other artifacts, but the bulk content is plain text and diffs cleanly in practice.

## Project-only files (full `.toe` roots)

These appear in expansions of `.toe` (whole project) but not `.tox` (single COMP):

- **`.start`** — startup settings, key/value lines:
  ```
  cookrate 60
  clock -f 1 -s 1 -o 0 -w 0
  realtime on
  viewers off
  #expectednodes 101 29193
  resetaudioondevicechange off
  ```
- **`.root`** — root-viewport state. Single `v <x> <y> <zoom>` line plus `end`.
- **`.grps`** — group definitions. Minimal in samples (`-2\n0\n`); needs a project with non-trivial node groups to fully decode.
- **`.application`** — desktop/pane/window layout. `desk ...`, `neteditor ...`, `winplacement ...` directives — a flat command script restoring the editor UI state at save time.

## Operator-body files (per node, family-specific saved state)

Several CHOP/COMP families emit a body file alongside `.n`/`.parm`. The first line is always a version int, then family-specific content.

| ext | example body | notes |
|---|---|---|
| `.chop` | `5\n1\n` | Constant/Null/etc CHOP saved channel data. Bare integers in samples; expect richer payloads for non-trivial CHOPs. |
| `.feedback` | `3\n1920\n1080\n1\n1920\n1080\n0\n109\n` | Feedback TOP cache state — version, then resolution/format ints. |
| `.beat` | `1\n` | Beat CHOP — version only in samples. |
| `.gnode` | `1\nUT_DMatrix4 1 0 0 0 0 1 0 ... 1\n` ×3 | Geometry COMP — three 4x4 transform matrices (xform / pre-pivot / post-pivot, probably). |
| `.ts` | `65538\n1\n555\n554\n0\n0\n1\n...{ rate=60 start=555 ... }` | Time-slicer state — header ints then a brace-block (same syntax as `.script`) holding track metadata. |
| `.replicator` | `3\n0\n` | Replicator COMP cache. Trivial in samples. |
| `.oldacbo` | `1\n0\n0\n` | Legacy Audio CHOP buffer-object cache. |

All of these were emitted at least once across the 12-file sample; none have been fully decoded.

## `.lod` — bundled archive

Found inside full-`.toe` expansions, typically under `local/` (TD's project-local component scratch area). A `.lod` is a single binary file that packs an entire sub-COMP's worth of expanded artifacts inline rather than spilling them into a sibling subdirectory.

Hex layout (from `local/midi.lod`):

```
04 20 20 20 59 .build\nversion 099\nbuild 2022.24200\n...
04 09 20 20 20 59 device.n\nDAT:table\ntile 50 -130 644 126\n...
04 20 20 20 5C device.parm\n?\ndefaultreadencoding 0 cp1252\n...
04 20 20 20 5F device.table\n1\n*<padding>...
...
```

Structure (working model):
- Each record begins with a `\x04` framing byte.
- Next 4 bytes encode an entry length (interpreted as a big-endian or padded int — first byte `\x20` ≈ space looks like padding; the trailing byte is the actual length, e.g. `0x59`, `0x5C`, `0x5F`).
- Then the artifact path inside the bundle (e.g. `.build`, `device.n`, `device.parm`).
- Then the artifact body (same bytes the corresponding standalone file would contain).
- Records concatenate until end of file.

A `.lod` essentially is a flat key/value store mirroring what would otherwise be a directory + table-of-contents. Roundtripping requires understanding the length encoding precisely — needs more sampling before doing so.

## Notes / open questions

- `.n` `view` line layout (the 12 trailing numbers) is not decoded — leave verbatim when round-tripping.
- `.parm` mode bitfield: many additional low-byte values appear in third-party toxes (`2, 18, 34, 64, 66, 80, 96, 113, 192, 512, 515, 547`, …). Notable: `113` = `64|32|16|1`, seen with bind-to-parent expressions like `me.parent().par.File`; `512` (bit 9) seen on pulse parameters bound to a same-named parent par; `64` (bit 6 alone) seen on a lot of custom-parameter value writes (`Feedbackgamma 64 0.9`). Map each observed low-byte pattern to TD's actual ParMode (CONSTANT/EXPRESSION/EXPORT/BIND × stored-expr/bind/value flags). The two high bits (`0x04000000`, `0x08000000`) presumably encode "is custom parameter" / "is OP-typed value" but haven't been confirmed.
- `.lod` length encoding: needs more samples and a careful hex inspection to nail down whether the per-record length is 1-byte, 2-byte, or 4-byte big-endian with the padding interpretation above.
- Operator-body files (`.chop`, `.feedback`, `.beat`, `.gnode`, `.ts`, `.replicator`, `.oldacbo`) — only minimal samples decoded. A targeted sweep with non-trivial CHOPs (loaded buffers, recorded channels) would expose richer payloads.
- `.cparm` column layout: the seven numeric fields in positions 5–11 (clamp flags, defaults, min/max, "section") are inferred, not proven. Build a fixture with one custom par per type to lock the schema down.
- `.cparm` type-id integers: the encoding of the leading signed int (e.g. `772804868`, `-1374678782`, `772935937`) is unknown. Same id always means same par type; might be a packed FourCC or a TD-internal hash.
- `.panel` `children` value seems to be a count of nested panel descendants, but the relationship to the actual child list (which is implicit via the sibling subdirectory) hasn't been confirmed.
- `.text` and `.table` binary preambles share the `1\n*<padding><u32...>` shape — looks like a common DAT framing header. Decoding the full preamble would let us round-trip cleanly.
- `radioname`/`lradioname` appear only at the root container — likely state from the active radio-button selection at save time, not structural.

When extending these notes, prefer to add a small fixture under `tests/` rather than guessing — current sources cover only two `.tox`es' worth of the operator zoo.
