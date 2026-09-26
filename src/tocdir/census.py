"""Coverage census over many expanded tocdir trees.

Walks a directory full of `<name>.tox.dir/` (+ sibling `.toc`) expansions and
aggregates what the format actually contains, so format-coverage gaps surface
empirically rather than by guesswork:

  - **kind-suffix histogram** — every file-kind suffix seen, flagged parsed
    (a `Project.KIND_PARSERS` entry exists) vs raw (held as bytes → the parser,
    and usually FORMAT.md, does not yet characterise it).
  - **FAMILY:type histogram** — every operator type present, from each `.n`.
  - **round-trip result per tree** — reuse `Project.verify`; mismatches are
    parser bugs or deviations to record in DEVIATIONS.md.
  - **build-version vocabulary** — `.build` `version`/`build` values, to spot
    which TD builds a corpus spans.
  - **`.n` vocabulary** — the section/line keywords and `flags = ` token keys
    seen, so a new keyword or flag in a newer build stands out.
  - **`.parm`/`.cparm` vocabulary** — mode values and "row shape" (field
    count) histograms, so a new mode bit or an extra trailing field shows up
    as a new bucket rather than silently being swallowed by the raw line.
  - **`type_pars`** — per FAMILY:type, the union of parameter names seen
    across every `.parm` instance of that type — diffable across builds to
    spot new parameters on existing operators.
  - **`.toc` header histogram** — the literal header line (or its absence,
    for `.toe`), across trees.

This is read-only analysis built on the existing per-kind parsers; it never
writes to the trees. Runs independent of a TouchDesigner process.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .build import Build
from .cparm import Cparm, _split_quoted_or_bareword as _split_fields
from .n import N
from .parm import Parm
from .project import KIND_PARSERS, Project, _suffix_key

# toeexpand's case-collision disambiguator appends a ` <N>` suffix in the .toc
# (e.g. `image.n 2`); fold it back to the base kind so the histogram counts the
# real kind, not `n 2` / `parm 2`. See FORMAT.md "Case-collision suffix mismatch".
_DUP_SUFFIX = re.compile(r" \d+$")

# A `flags = ` token is a value (not a flag key) when it's a bare on/off or a
# plain (optionally signed) integer — see FORMAT.md "`flags = ...`" for the
# interleaved `<name> <value>` / bare-flag grammar.
_FLAG_VALUE = re.compile(r"^(on|off|-?\d+)$")


def _kind_of(entry_path: str) -> str:
    return _DUP_SUFFIX.sub("", _suffix_key(entry_path))


def _entry_stem_and_dup(entry_path: str, kind: str) -> tuple[str | None, str]:
    """Split `<stem>.<kind>[ <dup>]` into `(stem, dup_suffix)`.

    `dup_suffix` is `""` or `" <N>"` (the case-collision disambiguator — see
    `_DUP_SUFFIX`). Returns `(None, "")` if `entry_path` isn't of kind `kind`
    once the dup suffix is stripped. Used to correlate a `.n` and its sibling
    `.parm`/`.cparm` for the same node (they share stem + dup suffix).
    """
    m = _DUP_SUFFIX.search(entry_path)
    dup = m.group(0) if m else ""
    base = entry_path[: len(entry_path) - len(dup)] if dup else entry_path
    suffix = "." + kind
    if not base.endswith(suffix):
        return None, ""
    return base[: -len(suffix)], dup


def find_trees(root: Path | str) -> list[Path]:
    """Every `*.dir/` under `root` that has a sibling `.toc` (a valid tree)."""
    r = Path(root)
    trees: list[Path] = []
    for d in sorted(r.rglob("*.dir")):
        if not d.is_dir():
            continue
        toc = d.parent / (d.name[: -len(".dir")] + ".toc")
        if toc.exists():
            trees.append(d)
    return trees


@dataclass
class Census:
    tree_count: int = 0
    kind_counts: Counter = field(default_factory=Counter)
    type_counts: Counter = field(default_factory=Counter)
    roundtrip_fail: list[str] = field(default_factory=list)
    load_errors: list[tuple[str, str]] = field(default_factory=list)
    # New-structure detectors (added for the 2025.32460 -> 2025.33230 diff).
    build_versions: Counter = field(default_factory=Counter)
    build_numbers: Counter = field(default_factory=Counter)
    n_line_keywords: Counter = field(default_factory=Counter)
    n_flag_tokens: Counter = field(default_factory=Counter)
    parm_modes: Counter = field(default_factory=Counter)
    parm_row_shapes: Counter = field(default_factory=Counter)
    cparm_row_shapes: Counter = field(default_factory=Counter)
    type_pars: dict = field(default_factory=dict)  # FAMILY:type -> set[str] of par names
    toc_headers: Counter = field(default_factory=Counter)

    def unparsed_kinds(self) -> list[str]:
        """Kind suffixes seen that have no dedicated parser (held as raw bytes)."""
        return sorted(k for k in self.kind_counts if k not in KIND_PARSERS)


def _census_n(model: N, c: Census) -> None:
    for sec in model.sections:
        if sec.label == "<header>":
            continue  # FAMILY:type itself — already tallied in type_counts
        c.n_line_keywords[sec.label] += 1
    for tok in model.flag_tokens():
        if not _FLAG_VALUE.match(tok):
            c.n_flag_tokens[tok] += 1


def _census_build(model: Build, c: Census) -> None:
    v = model.version
    if v is not None:
        c.build_versions[v] += 1
    b = model.build_number
    if b is not None:
        c.build_numbers[b] += 1


def _census_parm(model: Parm, c: Census) -> None:
    for row in model.rows:
        if row.is_page_marker:
            c.parm_row_shapes["page_marker"] += 1
            continue
        mode = row.mode
        if mode is not None:
            c.parm_modes[mode] += 1
        shape = len(_split_fields(row.raw_rest))
        c.parm_row_shapes[str(shape)] += 1


def _census_cparm(model: Cparm, c: Census) -> None:
    for row in model.rows:
        if row.is_page_marker:
            c.cparm_row_shapes["page_marker"] += 1
        elif row.is_pages_decl:
            c.cparm_row_shapes["pages_decl"] += 1
        else:
            c.cparm_row_shapes[str(len(_split_fields(row.raw)))] += 1


def census(root: Path | str) -> Census:
    c = Census()
    for tree in find_trees(root):
        rel = str(tree)
        try:
            project = Project.from_dir(tree)
        except Exception as exc:  # noqa: BLE001 - report, don't abort the sweep
            c.load_errors.append((rel, f"{type(exc).__name__}: {exc}"))
            continue
        c.tree_count += 1

        # Pass 1: map each node's stem+dup suffix -> its FAMILY:type, so the
        # sibling `.parm` pass below can attribute parameter names correctly.
        stem_to_family_type: dict[str, str] = {}
        for entry_path, model in project.entries.items():
            if _kind_of(entry_path) == "n" and isinstance(model, N):
                stem, dup = _entry_stem_and_dup(entry_path, "n")
                if stem is not None and model.family_type:
                    stem_to_family_type[stem + dup] = model.family_type

        for entry_path, model in project.entries.items():
            kind = _kind_of(entry_path)
            c.kind_counts[kind] += 1
            if kind == "n" and isinstance(model, N):
                ft = model.family_type
                if ft:
                    c.type_counts[ft] += 1
                _census_n(model, c)
            elif kind == "build" and isinstance(model, Build):
                _census_build(model, c)
            elif kind == "parm" and isinstance(model, Parm):
                _census_parm(model, c)
                stem, dup = _entry_stem_and_dup(entry_path, "parm")
                if stem is not None:
                    ft = stem_to_family_type.get(stem + dup)
                    if ft:
                        names = {r.name for r in model.parameter_rows() if r.name}
                        c.type_pars.setdefault(ft, set()).update(names)
            elif kind == "cparm" and isinstance(model, Cparm):
                _census_cparm(model, c)

        c.toc_headers[project.toc.header if project.toc.header is not None else "<none>"] += 1

        try:
            if project.verify(tree):
                c.roundtrip_fail.append(rel)
        except Exception as exc:  # noqa: BLE001
            c.load_errors.append((rel, f"verify {type(exc).__name__}: {exc}"))
    return c


def render_census(c: Census) -> str:
    out: list[str] = []
    out.append(f"# tocdir census — {c.tree_count} trees")
    out.append("")

    unparsed = c.unparsed_kinds()
    out.append(f"## kinds ({len(c.kind_counts)} distinct; {len(unparsed)} unparsed)")
    for kind, n in c.kind_counts.most_common():
        mark = "raw " if kind in unparsed else "    "
        out.append(f"  {mark}{n:>7}  {kind}")
    if unparsed:
        out.append("")
        out.append(f"  UNPARSED (no KIND_PARSERS entry): {', '.join(unparsed)}")
    out.append("")

    out.append(f"## operator types ({len(c.type_counts)} distinct)")
    for ft, n in c.type_counts.most_common():
        out.append(f"  {n:>7}  {ft}")
    out.append("")

    out.append(f"## round-trip ({len(c.roundtrip_fail)} trees with mismatches)")
    for rel in c.roundtrip_fail[:50]:
        out.append(f"  FAIL {rel}")
    if len(c.roundtrip_fail) > 50:
        out.append(f"  ... and {len(c.roundtrip_fail) - 50} more")
    if c.load_errors:
        out.append("")
        out.append(f"## load errors ({len(c.load_errors)})")
        for rel, err in c.load_errors[:50]:
            out.append(f"  ERR  {rel}: {err}")
    out.append("")

    out.append(f"## .build ({len(c.build_versions)} version(s), {len(c.build_numbers)} build number(s))")
    for v, n in c.build_versions.most_common():
        out.append(f"  {n:>7}  version {v}")
    for b, n in c.build_numbers.most_common():
        out.append(f"  {n:>7}  build {b}")
    out.append("")

    out.append(
        f"## .n vocabulary ({len(c.n_line_keywords)} line keyword(s), "
        f"{len(c.n_flag_tokens)} flag token(s))"
    )
    for kw, n in c.n_line_keywords.most_common():
        out.append(f"  {n:>7}  keyword {kw}")
    for tok, n in c.n_flag_tokens.most_common():
        out.append(f"  {n:>7}  flag {tok}")
    out.append("")

    out.append(
        f"## .parm vocabulary ({len(c.parm_modes)} mode(s), "
        f"{len(c.parm_row_shapes)} row shape(s))"
    )
    for shape, n in c.parm_row_shapes.most_common():
        out.append(f"  {n:>7}  row_shape={shape}")
    for mode, n in c.parm_modes.most_common(30):
        out.append(f"  {n:>7}  mode={mode} (0x{mode:X})" if mode >= 0 else f"  {n:>7}  mode={mode}")
    if len(c.parm_modes) > 30:
        out.append(f"  ... and {len(c.parm_modes) - 30} more modes")
    out.append("")

    out.append(f"## .cparm row shapes ({len(c.cparm_row_shapes)} distinct)")
    for shape, n in c.cparm_row_shapes.most_common():
        out.append(f"  {n:>7}  row_shape={shape}")
    out.append("")

    out.append(f"## type_pars ({len(c.type_pars)} FAMILY:type entries with a parameter-name set)")
    out.append("")

    out.append(f"## .toc headers ({len(c.toc_headers)} distinct)")
    for hdr, n in c.toc_headers.most_common():
        out.append(f"  {n:>7}  {hdr}")
    return "\n".join(out)


def _sorted_counter(counter: Counter) -> dict:
    """Counter -> dict with keys sorted (numerically if they're ints, else
    lexicographically), so two census JSONs diff cleanly."""
    return {str(k): v for k, v in sorted(counter.items())}


def census_json(c: Census) -> dict:
    return {
        "tree_count": c.tree_count,
        "kinds": dict(sorted(c.kind_counts.items())),
        "unparsed_kinds": c.unparsed_kinds(),
        "operator_types": dict(sorted(c.type_counts.items())),
        "roundtrip_fail": sorted(c.roundtrip_fail),
        "load_errors": [{"tree": t, "error": e} for t, e in sorted(c.load_errors)],
        # New-structure detectors — additive, existing keys above are unchanged.
        "build_versions": _sorted_counter(c.build_versions),
        "build_numbers": _sorted_counter(c.build_numbers),
        "n_vocab": {
            "line_keywords": _sorted_counter(c.n_line_keywords),
            "flag_tokens": _sorted_counter(c.n_flag_tokens),
        },
        "parm_vocab": {
            "modes": _sorted_counter(c.parm_modes),
            "row_shapes": _sorted_counter(c.parm_row_shapes),
        },
        "cparm_vocab": {
            "row_shapes": _sorted_counter(c.cparm_row_shapes),
        },
        "type_pars": {ft: sorted(names) for ft, names in sorted(c.type_pars.items())},
        "toc_headers": _sorted_counter(c.toc_headers),
    }
