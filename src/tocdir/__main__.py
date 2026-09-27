"""CLI for tocdir operations.

Usage:
    python -m tocdir verify <path-to-.dir-or-.toc>
    python -m tocdir set-text <target.text> <body-source-file>
    python -m tocdir census <corpus-root> [--json]
    python -m tocdir textconv <file>

`verify` checks bit-exact round-trip across a whole tree.

`set-text` replaces a `.text` file's body with the bytes of
`body-source-file`, recomputing the binary length header so the result
stays structurally valid. This is the tocdir-side step `shrink.sh` uses to
inject `src/*.py` into the tree before `toecollapse` repacks it.

`census` walks every `*.dir/` tree under `<corpus-root>` and reports the
kind-suffix histogram (flagging kinds with no parser), the operator-type
histogram, and per-tree round-trip results. Use it to find format-coverage
gaps across a corpus (e.g. the shipped expansion from build-corpus.sh).

`textconv` writes a human-readable rendering of one tocdir file to stdout,
for use as a git `diff.<driver>.textconv` command (see
`scripts/git-textconv-setup.sh`): `.text` files render as their DAT body,
`.table` files render as one line per row with tab-separated cells. Any
other file, or one that fails to parse, is written through unchanged — a
textconv must never hide a diff by crashing.

Exit codes:
    0  success
    1  one or more round-trip mismatches (verify; census)
    2  invalid arguments / missing input
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .census import census, census_json, render_census
from .project import Project
from .table import Table
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


def _census(root: str, as_json: bool) -> int:
    p = Path(root)
    if not p.is_dir():
        print(f"census: not a directory: {root}", file=sys.stderr)
        return 2
    c = census(p)
    if as_json:
        print(json.dumps(census_json(c), indent=2))
    else:
        print(render_census(c))
    return 1 if c.roundtrip_fail or c.load_errors else 0


def _decode_cell_stream(body: bytes) -> list[bytes] | None:
    """Decode a `.table`-style cell stream: repeated `tag(u32=2) + length(u32)
    + bytes`, no terminator (see FORMAT.md / `_preamble.py`). Returns `None`
    on any structural inconsistency (bad tag, truncated cell, trailing
    bytes) rather than raising, so callers can fall back cleanly."""
    cells: list[bytes] = []
    i = 0
    n = len(body)
    while i < n:
        if i + 8 > n:
            return None
        tag = int.from_bytes(body[i:i + 4], "big")
        length = int.from_bytes(body[i + 4:i + 8], "big")
        i += 8
        if tag != 2 or i + length > n:
            return None
        cells.append(body[i:i + length])
        i += length
    return cells if i == n else None


def _textconv_text(raw: bytes) -> bytes:
    # Reuse the real parser so the rendering tracks the format exactly
    # (including the 19-byte short-form stub, which parses to an empty body).
    return Text.parse(raw).body


def _textconv_table(raw: bytes) -> bytes:
    t = Table.parse(raw)
    # preamble.fields = [sentinel, row_count, col_count, reserved]. NOTE:
    # fields[1] is the ROW count and fields[2] is the COLUMN count —
    # FORMAT.md and the Table.row_count/column_count properties currently
    # have these swapped (being fixed separately on fix/table-rows-cols), so
    # read the raw fields directly here rather than via those properties.
    rows = t.preamble.fields[1]
    cols = t.preamble.fields[2]
    cells = _decode_cell_stream(t.body)
    if cells is None:
        raise ValueError("malformed .table cell stream")
    lines: list[str]
    if cols > 0 and len(cells) == rows * cols:
        lines = [
            "\t".join(c.decode("utf-8", "replace") for c in cells[r * cols:(r + 1) * cols])
            for r in range(rows)
        ]
    else:
        # Cell count disagrees with rows*cols — fall back to one cell per line
        # rather than guessing at a grid shape.
        lines = [c.decode("utf-8", "replace") for c in cells]
    return ("\n".join(lines) + "\n").encode("utf-8") if lines else b""


def _textconv(arg: str) -> int:
    path = Path(arg)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        print(f"textconv: cannot read {arg}: {exc}", file=sys.stderr)
        return 2
    out = raw
    try:
        if path.name.endswith(".text"):
            out = _textconv_text(raw)
        elif path.name.endswith(".table"):
            out = _textconv_table(raw)
    except Exception:  # noqa: BLE001 - a textconv must never hide a diff by crashing
        out = raw
    sys.stdout.buffer.write(out)
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
    if cmd == "census":
        args = argv[2:]
        as_json = "--json" in args
        positional = [a for a in args if a != "--json"]
        if len(positional) != 1:
            print("census: expected <corpus-root> [--json]", file=sys.stderr)
            return 2
        return _census(positional[0], as_json)
    if cmd == "textconv":
        if len(argv) != 3:
            print("textconv: expected <file>", file=sys.stderr)
            return 2
        return _textconv(argv[2])
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
