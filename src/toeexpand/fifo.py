"""`.fifo` FIFO input/event-buffer reader and writer (binary).

Layout (FORMAT.md):

    1\\n             # format version
    <field-count>\\n # ASCII int, redundant with u32[1] in the preamble
    *               # marker byte
    <u32×6>         # preamble: [1, field_count, frame_count, 0, 2, first_field_len]
    <body bytes>    # event rows

`.fifo` is the only DAT-shape kind with two leading ASCII lines before
the `*` marker. Preserve both verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._preamble import Preamble

PREAMBLE_FIELDS = 4


@dataclass
class Fifo:
    version_line: bytes   # e.g. b"1\\n"
    count_line: bytes     # e.g. b"10\\n"
    preamble: Preamble
    body: bytes

    @classmethod
    def parse(cls, raw: bytes) -> "Fifo":
        nl1 = raw.index(b"\n")
        version_line = raw[:nl1 + 1]
        nl2 = raw.index(b"\n", nl1 + 1)
        count_line = raw[nl1 + 1:nl2 + 1]
        preamble = Preamble.parse(raw, nl2 + 1, PREAMBLE_FIELDS)
        body = raw[nl2 + 1 + preamble.byte_size:]
        return cls(version_line=version_line, count_line=count_line, preamble=preamble, body=body)

    def emit(self) -> bytes:
        return self.version_line + self.count_line + self.preamble.emit() + self.body

    @property
    def field_count(self) -> int:
        return self.preamble.fields[1]


def read_fifo(path: Path) -> Fifo:
    return Fifo.parse(path.read_bytes())


def write_fifo(path: Path, f: Fifo) -> None:
    path.write_bytes(f.emit())
