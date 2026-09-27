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
