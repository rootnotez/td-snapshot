"""CLI for tocdir operations.

Usage:
    python -m tocdir verify <path-to-.dir-or-.toc>
    python -m tocdir set-text <target.text> <body-source-file>

`verify` checks bit-exact round-trip across a whole tree.

`set-text` replaces a `.text` file's body with the bytes of
`body-source-file`, recomputing the binary length header so the result
stays structurally valid. This is the tocdir-side step `shrink.sh` uses to
inject `src/*.py` into the tree before `toecollapse` repacks it.

Exit codes:
    0  success
    1  one or more round-trip mismatches (verify only)
    2  invalid arguments / missing input
"""

from __future__ import annotations

import sys
from pathlib import Path

from .project import Project
from .text import Text, write_text


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


def _set_text(target: str, source: str) -> int:
    tgt = Path(target)
    body = Path(source).read_bytes()
    t = Text.parse(tgt.read_bytes())
    t.body = body
    t.rebuild_lengths()
    write_text(tgt, t)
    print(f"set-text: {target} <- {source} ({len(body)} bytes)")
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
    if cmd == "set-text":
        if len(argv) != 4:
            print("set-text: expected <target.text> <body-source-file>", file=sys.stderr)
            return 2
        return _set_text(argv[2], argv[3])
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
