"""`.script` operator-body reader and writer (brace-block grammar).

Fixed per-kind version int: 1 (FORMAT.md). Round-trip is byte-exact
via `_brace_block.BraceBlockBody`; accessors scan the raw bytes on demand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._brace_block import BraceBlockBody


@dataclass
class Script(BraceBlockBody):
    pass


def read_script(path: Path) -> Script:
    return Script.parse(path.read_bytes())


def write_script(path: Path, b: Script) -> None:
    path.write_bytes(b.emit())
