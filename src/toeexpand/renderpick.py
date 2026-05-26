"""`.renderpick` Render-Pick TOP cache reader and writer (binary).

Same wire layout as `.table` — version "1\\n", then `*<u32×6>`, then a cell
stream. The semantics of the u32 fields mirror `.table`'s column/row
counts; this module is a thin alias around the same structure.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._preamble import Preamble

PREAMBLE_FIELDS = 4  # same shape as .table


@dataclass
class Renderpick:
    version_line: bytes
    preamble: Preamble
    body: bytes

    @classmethod
    def parse(cls, raw: bytes) -> "Renderpick":
        nl = raw.index(b"\n")
        version_line = raw[:nl + 1]
        preamble = Preamble.parse(raw, nl + 1, PREAMBLE_FIELDS)
        body = raw[nl + 1 + preamble.byte_size:]
        return cls(version_line=version_line, preamble=preamble, body=body)

    def emit(self) -> bytes:
        return self.version_line + self.preamble.emit() + self.body

    @property
    def version(self) -> int:
        return int(self.version_line.decode("ascii").rstrip("\n"))

    @property
    def column_count(self) -> int:
        return self.preamble.fields[1]

    @property
    def row_count(self) -> int:
        return self.preamble.fields[2]


def read_renderpick(path: Path) -> Renderpick:
    return Renderpick.parse(path.read_bytes())


def write_renderpick(path: Path, r: Renderpick) -> None:
    path.write_bytes(r.emit())
