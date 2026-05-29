"""`.ts` operator-body reader and writer (brace-block grammar).

Fixed per-kind version int: 65538 (FORMAT.md). Round-trip is byte-exact
via `_brace_block.BraceBlockBody`; accessors scan the raw bytes on demand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._brace_block import BraceBlockBody


@dataclass
class Ts(BraceBlockBody):
    pass


def read_ts(path: Path) -> Ts:
    return Ts.parse(path.read_bytes())


def write_ts(path: Path, b: Ts) -> None:
    path.write_bytes(b.emit())
