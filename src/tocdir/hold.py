"""`.hold` operator-body reader and writer (brace-block grammar).

Fixed per-kind version int: 1 (FORMAT.md). Round-trip is byte-exact
via `_brace_block.BraceBlockBody`; accessors scan the raw bytes on demand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._brace_block import BraceBlockBody


@dataclass
class Hold(BraceBlockBody):
    pass


def read_hold(path: Path) -> Hold:
    return Hold.parse(path.read_bytes())


def write_hold(path: Path, b: Hold) -> None:
    path.write_bytes(b.emit())
