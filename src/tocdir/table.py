"""`.table` Table-DAT body reader and writer (binary).

Layout (FORMAT.md):

    1\\n             # format version
    *               # marker byte
    <u32×4>         # preamble: [1, row_count, col_count, 0]
    <cell stream>   # cells: tag(0x00000002) + u32 length + utf-8 bytes (no terminator)

The cell stream after the preamble holds `row_count * col_count` cells.
For bit-exact we keep the cell stream as opaque bytes — accessors decode
on demand.

Corrected 2026-09-27 against build 2025.33230: earlier drafts (and this
module) had u32[1]/u32[2] swapped as column_count/row_count. See the
"Important correction" note in FORMAT.md for the evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._preamble import Preamble

# .table uses 4 u32s: [1, row_count, col_count, 0]. The cell stream follows.
PREAMBLE_FIELDS = 4


@dataclass
class Table:
    version_line: bytes
    preamble: Preamble
    body: bytes  # cell stream

    @classmethod
    def parse(cls, raw: bytes) -> "Table":
        nl = raw.index(b"\n")
        version_line = raw[:nl + 1]
        preamble = Preamble.parse(raw, nl + 1, PREAMBLE_FIELDS)
        body = raw[nl + 1 + preamble.byte_size:]
        return cls(version_line=version_line, preamble=preamble, body=body)

    def emit(self) -> bytes:
        return self.version_line + self.preamble.emit() + self.body

    # ---- accessors ----

    @property
    def version(self) -> int:
        return int(self.version_line.decode("ascii").rstrip("\n"))

    @property
    def row_count(self) -> int:
        return self.preamble.fields[1]

    @property
    def column_count(self) -> int:
        return self.preamble.fields[2]


def read_table(path: Path) -> Table:
    return Table.parse(path.read_bytes())


def write_table(path: Path, t: Table) -> None:
    path.write_bytes(t.emit())
