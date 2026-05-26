"""`.text` Text-DAT body reader and writer (binary).

Layout (FORMAT.md):

    2\\n             # format version
    *               # marker byte
    <u32×6>         # preamble: [1, 1, 1, 1, 2, body_length]
    <body bytes>    # the actual DAT text (Python source, GLSL, etc)

The first four u32 fields are sentinel `1` values; u32[4] = `2` is the
end-of-sentinels marker; u32[5] is the body length in bytes.

Round-trip strategy: keep `version_line`, `preamble`, and `body` as raw
bytes. emit() concatenates them. Mutating `body` without also updating
the preamble's body_length field will produce a structurally invalid file;
the rebuild_lengths() helper is provided for callers that intentionally
edit the body.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._preamble import Preamble

# .text uses 6 u32s in its preamble: [1, 1, 1, 1, 2, body_length]
PREAMBLE_FIELDS = 6


@dataclass
class Text:
    version_line: bytes  # e.g. b"2\\n"
    preamble: Preamble
    body: bytes

    @classmethod
    def parse(cls, raw: bytes) -> "Text":
        # Version line: digits up to and including the newline.
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
    def body_length(self) -> int:
        return self.preamble.fields[5]

    def rebuild_lengths(self) -> None:
        """Refresh preamble u32[5] to match the actual `body` length.

        Use only when intentionally editing `body` — bit-exact round-trip
        otherwise relies on never re-deriving stored fields.
        """
        f = self.preamble.fields
        self.preamble = Preamble(fields=(f[0], f[1], f[2], f[3], f[4], len(self.body)))


def read_text(path: Path) -> Text:
    return Text.parse(path.read_bytes())


def write_text(path: Path, t: Text) -> None:
    path.write_bytes(t.emit())
