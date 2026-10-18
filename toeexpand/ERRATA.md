# TouchDesigner errata

Suspected bugs or unexplained behaviour **on TouchDesigner's side** (the app's
save format, its operator definitions, or the `toeexpand`/`toecollapse`
tools) that this repo has to live with. Distinct from
[`DEVIATIONS.md`](DEVIATIONS.md), which records where *our* `tocdir` parser
diverges from the format.

Each entry is re-checked on every TD update (see the README runbook and
[`tests/toolchain/README.md`](../tests/toolchain/README.md)) and gets a
row in its **History** table per build checked, so we can tell when
Derivative fixes, changes or spreads it. Status values: `open` (unexplained,
still present), `watching` (explained or harmless, still present),
`fixed-in <build>`, `wontfix` (confirmed intentional).

Every finding is tagged with the TD build that produced it.

---

## E1 — `.parm` mode bit `0x1000`: "always written" flag on some parameter groups

**Status:** open · **First seen:** files saved by 2025.33181 (earliest
sample); present at 2025.33230 · **Absent:** every file saved by
≤ 2025.32424 in the 2025.32460-era shipped corpus (0 of ~1.99M mode-bearing
`.parm` rows)

**What it is.** A mode bit that TouchDesigner sets on specific parameter
*definitions*, which makes those parameters get written to `.parm` on every
save, whatever their value. It is a static property of the parameter, not of its
state. The 2025.33230 bridge probe (`tests/toolchain/gen/probe_parm_flags.py`)
shows the bit on every probed parameter in all four variants: default,
changed to a non-default value, changed then set back to the default, and
`par.reset()`. TD's Python API can't see it: the same parameters report
`isDefault=True`, `mode=ParMode.CONSTANT` and `defaultMode=CONSTANT`, and no
Python attribute separates them from ordinary parameters.
Being disabled (`enable=False`) is not the trigger either: a default Geometry
COMP has 97 disabled default-valued pars and only its 5 `instancetex*` pars
are written.

**Where (build 2025.33230, `every_op` fixture, 43 op types)** — two
parameter families, each repeated per slot/prefix:

- *Texture-map sampling blocks* — `<slot>coord`, `…coordattrib`,
  `…coordinterp`, `…samplingmode`, `…extendu`/`v`/`w`, `…filter`,
  `…anisotropy`, `…channelsource`: every 3D COMP's `instancetex*` (geometry,
  actor, blend, bone, bulletsolver, constraint, fbx, force, geotext, gltfin,
  gltfout, handle, light, null, nvidiaflexsolver, nvidiaflowemitter,
  sharedmemin/out, usd, …), Light COMP `projmap*`/`envmap*`, and the map
  slots of the PBR, Phong, Constant and Point Sprite MATs.
- *POP attribute-creation blocks* — `overrideautoattr`, `attrtype`,
  `attrnumcomps`, `attrdefaultval0`–`3` (plus `…t`/`…n`-suffixed and
  `combine…`-prefixed variants) on 26 POPs (accumulate, field, limit,
  linesmooth, lookuptexture, math, noise, normal, normalize, pattern, phaser,
  projection, quantize, random, rerange, skindeform, texturemap, transform,
  trig, twist, …).

It combines with the other bits: Pattern POP `attrnumcomps 4113 1
me.par.vecsize` = `0x1000 | 0x10 | 0x01`.

**Why unknown — possibly unintentional.** The affected groups are exactly the
ones Derivative has been reworking into shared parameter templates: the
sampling block recently spread across MATs, and POPs are under active
development. The same parameters existed before and were written only when
changed (`instancetex*` appears with mode `0` in an older-build file). A flag
left on in a shared template would produce exactly this pattern. It could
also be deliberate, for example pinning values whose defaults vary by
context. Nothing observable from Python distinguishes the two.

**Impact on us.**
- `toeexpand`/`toecollapse` (both 2025.32460 and 2025.33230) pass it through
  byte-identically; `tocdir` round-trips it (mode is an opaque int);
  `has_expression` (`mode & 0x30`) is unaffected.
- `src/core.py` (runs in TD, uses the Python API) is unaffected.
- **A file-based renderer must not treat a `.parm` row as "changed" just
  because it exists.** For a row carrying `0x1000`, compare its value with
  the same op type's row in the committed `every_op` fixture for that save
  build (`tests/toolchain/fixtures/<build>/every_op_<FAMILY>.tox`, all ops at
  defaults) — only a differing value is a real change.
- Adds noise to `.parm` diffs and to census `type_pars` build-to-build
  comparisons (these rows look like "new parameters").

**Re-check on a new build.**
1. `tests/toolchain/gen/run.sh probe_parm_flags` (TD + bridge running) →
   `tests/toolchain/runs/probe_parm_flags-<build>/`; expand the `.tox` and
   list rows with the bit:
   `find <dir>.dir -name '*.parm' -exec awk '$2 ~ /^[0-9]+$/ && int($2/4096)%2==1 {print FILENAME": "$0}' {} +`
2. After regenerating `every_op` for the new build, run the same `find`/`awk`
   over its expansion to see which parameter groups carry the bit (spread,
   shrink, or gone).
3. `scripts/toolchain-check.sh --corpus` → the census diff's
   `.parm_vocab.modes` keys show whether `4096`-family modes appear or
   disappear in shipped files.

**Open questions.** Did 2025.32460 itself already write the bit for these
groups? Run `every_op` in TD 2025.32460 launched from its archived DMG to
find out. Is it intentional? Asking on the Derivative forum with the Geometry
COMP `instancetexfilter` example is the fastest route.

| Build checked | Date | Result |
|---|---|---|
| 2025.33230 | 2026-09-26 | Present on 43 op types (two families above); probe: set in all 4 variants; API blind to it |

---

## E2 — Phong MAT parameter named `texture4coordnterp`

**Status:** watching · **First seen:** 2025.33230 (probe; not checked earlier)

Phong MAT's texture slots 1–3 name their coordinate-interpolation parameter
`texture<N>coordinterp`; slot 4's is `texture4coordnterp` (missing `i`). The
bundled wiki (`Phong_MAT` page) documents the misspelt name. Harmless for the
format, since the name round-trips as stored. But anything that builds parameter
names by pattern (`op.par.texture4coordinterp`, generated docs, a renderer's
per-slot grouping) will miss it.

**Re-check:** the `probe_parm_flags` probe prints
`phong coordinterp names`.

| Build checked | Date | Result |
|---|---|---|
| 2025.33230 | 2026-09-26 | Present: `texture1coordinterp` … `texture3coordinterp`, `texture4coordnterp` |

---

## E3 — `toeexpand <file> <pattern>` writes the `.toc` but no `.dir/`

**Status:** open · **First seen:** 2025.32460 (and 2025.33230)

The usage text advertises a `pattern` argument (`toeexpand untitled.toe
moviein1`). With any pattern, whether or not it matches an op, `toeexpand` writes
the full `.toc` (byte-identical to a plain expand) but never creates `.dir/`,
and still reports success. Pinned in
`tests/toolchain/test_capabilities.py`; we never use the argument.

| Build checked | Date | Result |
|---|---|---|
| 2025.32460 | 2026-09-26 | Present |
| 2025.33230 | 2026-09-26 | Present |

---

## E4 — Case-collision suffix: `.toc` says `name.n 2`, disk has `name.n.2`

**Status:** watching · **First seen:** 2025.32424-saved snippets (Windows-authored);
reproduced on macOS at 2025.33230

Two ops whose names differ only by case get disambiguated inconsistently: the
`.toc` entry uses a ` N` suffix while the on-disk file uses `.N`. `tocdir`
maps between them (`project._toc_to_disk`). Details in
[FORMAT.md — Case-collision suffix mismatch](FORMAT.md#case-collision-suffix-mismatch-toeexpand-bug);
pinned by `test_case_collision_suffix_disambiguation` against the
`features` fixture.

| Build checked | Date | Result |
|---|---|---|
| 2025.33230 | 2026-09-26 | Present (`caseprobe.n 2` ↔ `caseprobe.n.2`) |

---

## E5 — `toecollapse` usually does not reproduce a TD save byte-for-byte

**Status:** watching (explained 2026-10-18, harmless) · **First seen:**
2025.32460; explained at 2025.33230 ·
**Research:** [#35](https://github.com/rootnotez/td-snapshot/issues/35)

**What we observed (1,025 files, 2025.33230 toolchain):** expanding a
`.toe`/`.tox` with `toeexpand` and collapsing it with `toecollapse` gives
a file that expands to the identical tree, but usually not the same bytes.

| Corpus | Byte-identical after round trip |
|---|---|
| `CurriculumExamples` ([2026-09-26 delta report](toolchain-deltas/2026-09-26_32460-vs-33230.md), Question A) | 0 / 199 |
| Golden set, excluding `td-snapshot.tox` | 0 / 13 |
| `td-snapshot.tox` (written by `toecollapse`: `scripts/build.sh` → `scripts/shrink.sh`) | 1 / 1 |
| `Keyframer.toe`, external project (Windows original + macOS re-save) | 0 / 2 |
| Shipped `tfs` in the 2025.33230 app bundle (2026-10-13 sweep) | 8 / 804 |
| Fresh TD saves in a throwaway project (2026-10-14) | 1 / 6 (`empty.tox`) |
| Fresh TD saves, 2026-10-18 (incl. a flat COMP with custom pars) | 2 / 8 (`empty`, `flatpars`) |

**Cause (2026-10-18, 2025.33230).** Both writers use the same compression
and the same cipher. They lay out the archive *inside* differently:
`toecollapse` stores every entry under its full path, while TD's save
stores basenames grouped under directory records. The two layouts are the
same exactly when the tree has no subdirectories, which is why a flat COMP
round-trips and a COMP with children never does. The container format
itself is in [FORMAT.md, "Binary container"](FORMAT.md#binary-container--the-toe--tox-file).

The evidence is the unpacked length the header carries in clear (the
payload is encrypted, so we compare sizes and ciphertext blocks, never
plaintext):

- **`toecollapse` writes `17 + Σ (len(path) + 7 + size)`** over the `.toc`
  entries, with `path` as the `.toc` spells it. Exact on every file tested:
  synthetic trees, the 13 goldens, 4 `.toe`, the shipped files, and
  multi-chunk files when summed over chunks.
- **TD writes `17 + Σ (len(basename) + 7 + size) + Σ (len(dir leaf) + 5)`**,
  the second sum taken over every directory the walk enters in `.toc` order
  (each directory is entered once). Exact, with residual 0, on the 9
  goldens and 9 fresh saves that are `.tox`, including 3-level nesting
  (`deep`) and `every_op_COMP.tox` (41 directories, 544 bytes).
- **ECB block comparison confirms it.** The cipher is ECB, so equal
  plaintext blocks at equal offsets give equal ciphertext. 631 of the 796
  differing shipped files share no 8-byte block with their rebuild, and the
  first differing byte is in block 0 or 1 for 774 of them. The plaintext
  differs from the start: this is not the same content reordered and not a
  trailer or padding difference.
- **Same compressor.** Swapping a Text DAT body changes the packed size of
  `toecollapse` output by what `zlib.compress(body, 6)` predicts, and
  incompressible bodies show up as stored blocks of about 16 KB. TD's save
  of a flat tree comes out byte-identical, so it uses the same settings.
- **The writers' sizes differ in both directions**: e.g. `ops` +8 bytes,
  `big` −8. Packed sizes move in 8-byte cipher blocks, and TD's shorter
  plaintext usually, but not always, compresses smaller.

**Item 1: is the save time the only other difference? Yes.** For 6 nested
COMPs (`ops`, `code`, `big`, `one`, `deep`, `rnd`), TD's save of the
original and TD's save of the `toecollapse` rebuild, after `loadTox`, made
in the same second, are byte-identical (6/6). Trap: `loadTox` makes the
loaded COMP current, which writes `current on` into its `.n` `flags` line.
The original has to be made current in its own parent
(`orig.current = True`) before the comparison holds. `c.current = False`
on the loaded copy does not clear it. The 2026-10-14 re-saves that
"differed in 248–1,301 bytes" had different `.build` times.

**Item 2: when do the writers agree?** When the archive layout is the same:

- **The tree is flat**: no `.toc` entry contains `/`. That covers TD's fresh
  `empty.tox` and `flatpars.tox` (a Container COMP with custom
  parameters, a 1.2 KB string parameter, storage and a comment, but no
  children), and the shipped `midi`, `dialog_bookmarks`,
  `dialog_importfile`, `dialog_winplacement` and `keymanager` `.tox` (2–5
  entries each; their contents sit in a top-level `.lod`).
- **The file was already in the full-path layout.** The shipped
  `Config/System/ui.tox` (20,245 nested entries, 4 chunks) and both
  `Samples/Setup/*/NewProject.toe` are nested, yet their unpacked lengths
  equal the `toecollapse` formula exactly. Derivative wrote them with
  `toecollapse` or an equivalent tool. `NewProject.toe`'s `.build` time is
  exactly `12:00:00`.

Build, platform, operator kinds, entry count and file size don't predict
agreement. `dialog_bookmarks` (2021.38420) agrees, and three other dialogs
from the same build don't.

**Item 3: what differs between the encodings?** Only the archive layout,
above. The compression level (zlib 6), the cipher (ECB with 8-byte blocks),
the 16-byte trailer and the chunking rule are shared. `toecollapse`
follows the `.toc` order and doesn't sort (reversing a `.toc` changes the
bytes). The header "u16" in earlier notes is the top half of the unpacked
length (u32). `Keyframer.toe`'s `0x0008`/`0x0009` meant TD's plaintext was
`0x0008xxxx` bytes and `toecollapse`'s `0x0009xxxx`.

**Item 4: does `toeexpand` drop anything?** For `.tox` saved by
2025.33230: nothing we can detect. Every byte of TD's plaintext is
accounted for by the expanded files and the directory records (residual 0
on 18 files), and TD's re-save of the rebuilt file is byte-identical.
For `.toe`, two residuals remain:

- **Empty directory records for clone COMPs** (`watching`). In a `.toe`, TD
  doesn't store the children of some clone COMPs. The Sweet16 projects'
  `docsHelper` (`clone` = `op.TDResources.op('docsHelper')`), `annotate52`
  / `annotate58` and `annotate_networkLabel` (`op.TDAnnotate.op(...)`) are
  examples. It still writes an empty directory record for each, costing
  `len(name) + 5` (16 + 15 + 25 = 56 bytes, the full Sweet16 excess).
  `toeexpand` has no way to represent an empty directory, so the record
  is lost. It only carries a name that the COMP's own `.n` already
  records, and TD rebuilds the clone internals on load (`.start` lists
  `#expectednodes 135` against 43 stored `.n` files). A `.tox` save of the
  same COMP stores the internals in full and has no residual.
- **A constant 9 bytes in every `.toe`** (`open`,
  [#43](https://github.com/rootnotez/td-snapshot/issues/43)). TD's `.toe` plaintext is
  9 bytes larger than the model in all 6 `.toe` checked: 2025.32460
  `BlankProject` and `SwitchMultiOutput`, the Sweet16 pair after removing
  the 56, and two fresh 2025.33230 saves (a bare session, and one with a
  nested COMP). `toecollapse`'s `.toe` output has no such 9 bytes. It is
  the same size as one more directory record with a 4-character name, or an
  entry with a 2-character name and an empty body. What it holds is
  unknown. The `.toe` `.toc` also lacks the `# 4 0 0 0 1` header line
  that `.tox` tocs have (FORMAT.md, `.toc`), which may be related.

**Impact on us.** Byte equality of a `.toe`/`.tox` against its rebuild
still isn't a usable check for TD-saved nested files. Compare expanded
trees instead (`tocdir verify`, or expand → `diff -r`). Two new uses:

- **Which writer wrote a file** can be read offline. Compare the summed
  header unpacked lengths with `17 + Σ (len(path) + 7 + size)` over its
  expansion: equal means a full-path (`toecollapse`-style) file, smaller
  means a TD save. This applies to nested trees only, since flat trees
  agree under both formulas.
- **Rebuilding through TD gives TD's bytes back.** `toecollapse` → `loadTox`
  → `save()` reproduces TD's own save exactly, given the same `.build`
  time and the `current` flag.

**Caveat on re-saving a `.toe`.** Opening a `.toe` in TD and saving it also
writes runtime state: window and panel sizes (`w`/`h` in `.parm`,
`screenw`/`screenh` in `.panel`), expression-driven values, timeline `.ts`
state, `.start`'s `#expectednodes`. The item 1 result is for `.tox`
through `loadTox`; for `.toe` it is untested.

**Reproduce.**

- **Container probes.** Build a tree by hand: `.build`, a root `r.n`, and
  one Text DAT `r/t.{n,parm,text}` copied from `tox/`, plus a
  `# 4 0 0 0 1` `.toc`. Swap the body with
  `python -m tocdir set-text r/t.text BODY`, then run `toecollapse`.
  Vary the body length and compressibility, flip single bytes, and diff
  the outputs block by block (8-byte blocks from offset 14).
- **Size models.** Walk the chunk chain and sum `unpacked_len`, then
  compare with the two formulas over the file's own expansion:

  ```python
  collapse = 17 + sum(len(p.encode()) + 7 + size(p) for p in toc)
  td = 17 + sum(len(basename(p).encode()) + 7 + size(p) for p in toc) \
          + sum(len(leaf.encode()) + 5 for leaf in dirs_entered_in_toc_order)
  ```
- **Item 1 (TD side).** In a throwaway TD session, `c.save()` each probe
  COMP. Then, in one exec: `loadTox` the `toecollapse` rebuild,
  `orig.current = True`, save both, and check that the `.build` times
  match. Compare with `cmp`.

| Build checked | Date | Result |
|---|---|---|
| 2025.33230 | 2026-10-13 | 0/214 non-`tfs` files (excluding `toecollapse`-written `td-snapshot.tox`) and 796/804 shipped `tfs` files differ from their rebuild; 8 shipped files identical (writer unknown); collapse deterministic |
| 2025.33230 | 2026-10-14 | Fresh TD saves: 1/6 identical after round trip (`empty.tox`); TD save deterministic apart from save time; TD re-save of `toecollapse` output returns to TD's original size |
| 2025.33230 | 2026-10-18 | Explained: archive layout (full paths vs per-directory basenames); both size models exact; flat trees and full-path-layout files agree (8/8 shipped explained); same-second TD re-save of rebuild byte-identical 6/6; `.toe` residuals: clone-COMP empty dirs (explained), constant +9 (open) |
