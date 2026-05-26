"""CLI for ad-hoc toeexpand-tree verification.

Usage:
    python -m toeexpand verify <path-to-.dir-or-.toc>

Exit codes:
    0  every file in the tree round-tripped byte-for-byte
    1  one or more mismatches (paths printed to stderr)
    2  invalid arguments / missing input
"""

from __future__ import annotations

import sys
from pathlib import Path

from .project import Project


def _resolve_dir(arg: str) -> Path:
    p = Path(arg)
    if p.is_dir() and p.name.endswith(".dir"):
        return p
    if p.is_file() and p.name.endswith(".toc"):
        sibling = p.parent / (p.name[: -len(".toc")] + ".dir")
        if sibling.is_dir():
            return sibling
        raise FileNotFoundError(f"no sibling .dir/ for {p}")
    raise ValueError(f"expected a .dir/ directory or a .toc file, got {p}")


def _verify(arg: str) -> int:
    d = _resolve_dir(arg)
    project = Project.from_dir(d)
    mismatches = project.verify(d)
    if mismatches:
        print(f"{len(mismatches)} mismatched files under {d}:", file=sys.stderr)
        for m in mismatches:
            print(f"  {m}", file=sys.stderr)
        return 1
    print(f"ok: {len(project.entries)} entries round-trip byte-exact ({d})")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help"}:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "verify":
        if len(argv) != 3:
            print("verify: expected exactly one path argument", file=sys.stderr)
            return 2
        return _verify(argv[2])
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
