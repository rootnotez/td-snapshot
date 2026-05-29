"""`.logic` operator-body reader and writer (brace-block grammar).

Fixed per-kind version int: 3 (FORMAT.md). Round-trip is byte-exact
via `_brace_block.BraceBlockBody`; accessors scan the raw bytes on demand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._brace_block import BraceBlockBody


@dataclass
class Logic(BraceBlockBody):
    pass


def read_logic(path: Path) -> Logic:
    return Logic.parse(path.read_bytes())


def write_logic(path: Path, b: Logic) -> None:
    path.write_bytes(b.emit())
