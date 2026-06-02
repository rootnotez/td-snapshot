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

This is read-only analysis built on the existing per-kind parsers; it never
writes to the trees. Runs independent of a TouchDesigner process.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .n import N
from .project import KIND_PARSERS, Project, _suffix_key

# toeexpand's case-collision disambiguator appends a ` <N>` suffix in the .toc
# (e.g. `image.n 2`); fold it back to the base kind so the histogram counts the
# real kind, not `n 2` / `parm 2`. See FORMAT.md "Case-collision suffix mismatch".
_DUP_SUFFIX = re.compile(r" \d+$")


def _kind_of(entry_path: str) -> str:
    return _DUP_SUFFIX.sub("", _suffix_key(entry_path))


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

    def unparsed_kinds(self) -> list[str]:
        """Kind suffixes seen that have no dedicated parser (held as raw bytes)."""
        return sorted(k for k in self.kind_counts if k not in KIND_PARSERS)


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
        for entry_path, model in project.entries.items():
            kind = _kind_of(entry_path)
            c.kind_counts[kind] += 1
            if kind == "n" and isinstance(model, N):
                ft = model.family_type
                if ft:
                    c.type_counts[ft] += 1
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
    return "\n".join(out)


def census_json(c: Census) -> dict:
    return {
        "tree_count": c.tree_count,
        "kinds": dict(c.kind_counts),
        "unparsed_kinds": c.unparsed_kinds(),
        "operator_types": dict(c.type_counts),
        "roundtrip_fail": c.roundtrip_fail,
        "load_errors": [{"tree": t, "error": e} for t, e in c.load_errors],
    }
