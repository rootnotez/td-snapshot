# toeexpand format notes

`toeexpand` (TouchDesigner CLI tool at `/Applications/TouchDesigner.app/Contents/MacOS/toeexpand`) expands a `.toe`/`.tox` into a git-diffable directory tree plus a sibling `.toc` index file. These notes were derived by inspecting `2026-05-13_td_snapshot.tox.dir/` + `.toc`; they may not cover every operator family.

## Layout

For an input `td-snapshot.tox`, toeexpand produces:

```
td-snapshot.tox.toc     # flat list of every artifact path
td-snapshot.tox.dir/
  .build                # build metadata
  <root>.n              # one .n per node
  <root>.parm           # one .parm per node (if the node has params)
  <root>.panel          # one .panel per node (panel-bearing nodes only)
  <root>.text           # one .text per node (DAT contents only)
  <root>/               # subdir mirrors COMP children
    <child>.n
    ...
```

The `<root>` name is the top-level COMP name from the .tox (e.g. `td_snapshot`). One file per (node, kind); a node may have any subset of `{.n, .parm, .panel, .text}` depending on what it carries.

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
  - `<mode>` — integer bitfield. Observed values across the full td_snapshot expansion (counts in parens):

    | mode | example | value | expr present | notes |
    |------|---------|-------|--------------|-------|
    | 0 (×84) | `label 0 "> Clipboard"` | real | no | plain constant |
    | 16 (×2) | `panels 16 copy_btn parent()` | real | yes | constant value, expression text *also* saved |
    | 17 (×4) | `clone 17 "" op.TDTox.op('defaultCOMPs/button')` | empty `""` | yes | active expression mode |
    | 32 (×1) | `y 32 200` | real | no | constant-shaped but distinct from 0 — observed only on a `y` position parameter; semantics unclear |
    | 48 (×4) | `file 48 "" f'scripts/{me.name}.py'` | empty `""` | yes | another expression-bearing mode |
    | 49 (×32) | `scaletofit 49 onlyshrink "parent()..."` | real | yes | both literal and expression present |

    Working hypothesis for the bit layout (still tentative — needs more fixtures to confirm):
    - low bits select active mode (TD's ParMode: CONSTANT/EXPRESSION/EXPORT/BIND).
    - bit 4 (0x10): expression text is stored on the parameter (whether or not active).
    - bit 5 (0x20): some additional flag — possibly "bind expression stored" or "value differs from operator default in a way that needs explicit serialization". `y 32 200` doesn't carry trailing expression text, which breaks the simple "bit 5 = bind stored" reading.

    No EXPORT-mode (TD bit unknown) or pure-BIND parameters appeared in this snapshot.
  - `<value>` — literal value token. Strings are double-quoted when needed; numbers, on/off, and bareword tokens (e.g. `onlyshrink`, `multiline`, `cp1252`) are unquoted.
  - `<expr>` — Python expression as written by the user. May be quoted (`"..."`) or unquoted (bare Python, including f-strings). Present only when the mode bit indicates an expression.

- The `pageindex` parameter (which page the param editor was last on) is captured here but is suppressed by the snapshot renderer ([src/core.py](../src/core.py)) because it tracks UI state, not user changes.

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

## Notes / open questions

- `.n` `view` line layout (the 12 trailing numbers) is not decoded — leave verbatim when round-tripping.
- `.parm` mode bitfield: only `0/17/32/48/49` observed in this snapshot; export-mode (bit unknown) and bind-with-expression combinations are untested.
- `.panel` `children` value seems to be a count of nested panel descendants, but the relationship to the actual child list (which is implicit via the sibling subdirectory) hasn't been confirmed.
- `.text` binary preamble: needs more samples (DATs of different families — table, CHOP-derived, etc.) to fully decode.
- `radioname`/`lradioname` appear only at the root container — likely state from the active radio-button selection at save time, not structural.

When extending these notes, prefer to add a small fixture under `tests/` rather than guessing — the existing `Sweet16*` fixtures plus the main `td-snapshot.tox` cover only a narrow slice of TD's operator zoo.
