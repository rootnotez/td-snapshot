"""`.chop` operator-body reader and writer (brace-block grammar).

Fixed per-kind version int: 5 (FORMAT.md). Round-trip is byte-exact
via `_brace_block.BraceBlockBody`; accessors scan the raw bytes on demand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._brace_block import BraceBlockBody


@dataclass
class Chop(BraceBlockBody):
    pass


def read_chop(path: Path) -> Chop:
    return Chop.parse(path.read_bytes())


def write_chop(path: Path, b: Chop) -> None:
    path.write_bytes(b.emit())
