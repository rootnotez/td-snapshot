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

# .text normally uses 6 u32s in its preamble: [1, 1, 1, 1, 2, body_length].
# TD 2025.30280+ also emits a 4-u32 short form for stub/uninitialized Text
# DATs (file is exactly 19 bytes: `2\n*` + 4 u32s, no body). Detected at
# parse-time by remaining-byte count.
PREAMBLE_FIELDS = 6
PREAMBLE_FIELDS_SHORT = 4


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
        # Bytes available after the `*` marker. Pick 4 u32s when the file
        # is too short for the standard 6-u32 preamble.
        remaining = len(raw) - (nl + 1) - 1
        fields = PREAMBLE_FIELDS if remaining >= 4 * PREAMBLE_FIELDS else PREAMBLE_FIELDS_SHORT
        preamble = Preamble.parse(raw, nl + 1, fields)
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
        # 6-field form stores body length at u32[5]; 4-field stub has no body.
        return self.preamble.fields[5] if len(self.preamble.fields) == PREAMBLE_FIELDS else 0

    def rebuild_lengths(self) -> None:
        """Refresh preamble u32[5] to match the actual `body` length.

        Use only when intentionally editing `body` — bit-exact round-trip
        otherwise relies on never re-deriving stored fields. No-op for the
        4-field short form (stub Text DATs have no body length field).
        """
        f = self.preamble.fields
        if len(f) != PREAMBLE_FIELDS:
            return
        self.preamble = Preamble(fields=(f[0], f[1], f[2], f[3], f[4], len(self.body)))


def read_text(path: Path) -> Text:
    return Text.parse(path.read_bytes())


def write_text(path: Path, t: Text) -> None:
    path.write_bytes(t.emit())
