"""`.mousein` operator-body reader and writer (brace-block grammar).

Fixed per-kind version int: 1 (FORMAT.md). Round-trip is byte-exact
via `_brace_block.BraceBlockBody`; accessors scan the raw bytes on demand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._brace_block import BraceBlockBody


@dataclass
class Mousein(BraceBlockBody):
    pass


def read_mousein(path: Path) -> Mousein:
    return Mousein.parse(path.read_bytes())


def write_mousein(path: Path, b: Mousein) -> None:
    path.write_bytes(b.emit())
