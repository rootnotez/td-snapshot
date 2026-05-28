"""`.renderpick` Render-Pick TOP cache reader and writer.

Two on-disk forms share this extension:

1. **Binary table form.** `1\\n*<u32×4>` + cell stream — same wire layout
   as `.table`.
2. **Brace-block form** (TD 2025.30280+). `1\\n{` + brace-grammar body
   describing rate/start/tracks etc. Stored as opaque bytes via the
   shared `BraceBlockBody` helper.

Discriminator is the byte at offset `nl+1`: `*` → binary, `{` →
brace-block. Both forms keep `version_line` for ergonomics; only one of
`preamble`+`body` and `brace` is populated.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ._brace_block import BraceBlockBody
from ._preamble import Preamble

PREAMBLE_FIELDS = 4  # same shape as .table


@dataclass
class Renderpick:
    version_line: bytes
    preamble: Optional[Preamble] = None
    body: Optional[bytes] = None
    brace: Optional[BraceBlockBody] = None

    @classmethod
    def parse(cls, raw: bytes) -> "Renderpick":
        nl = raw.index(b"\n")
        version_line = raw[:nl + 1]
        marker = raw[nl + 1:nl + 2]
        if marker == b"{":
            return cls(version_line=version_line, brace=BraceBlockBody.parse(raw[nl + 1:]))
        preamble = Preamble.parse(raw, nl + 1, PREAMBLE_FIELDS)
        body = raw[nl + 1 + preamble.byte_size:]
        return cls(version_line=version_line, preamble=preamble, body=body)

    def emit(self) -> bytes:
        if self.brace is not None:
            return self.version_line + self.brace.emit()
        assert self.preamble is not None and self.body is not None
        return self.version_line + self.preamble.emit() + self.body

    @property
    def version(self) -> int:
        return int(self.version_line.decode("ascii").rstrip("\n"))

    @property
    def column_count(self) -> Optional[int]:
        return self.preamble.fields[1] if self.preamble is not None else None

    @property
    def row_count(self) -> Optional[int]:
        return self.preamble.fields[2] if self.preamble is not None else None


def read_renderpick(path: Path) -> Renderpick:
    return Renderpick.parse(path.read_bytes())


def write_renderpick(path: Path, r: Renderpick) -> None:
    path.write_bytes(r.emit())
