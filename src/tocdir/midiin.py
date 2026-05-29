"""`.midiin` operator-body reader and writer (brace-block grammar).

Fixed per-kind version int: 3 (FORMAT.md). Round-trip is byte-exact
via `_brace_block.BraceBlockBody`; accessors scan the raw bytes on demand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._brace_block import BraceBlockBody


@dataclass
class Midiin(BraceBlockBody):
    pass


def read_midiin(path: Path) -> Midiin:
    return Midiin.parse(path.read_bytes())


def write_midiin(path: Path, b: Midiin) -> None:
    path.write_bytes(b.emit())
