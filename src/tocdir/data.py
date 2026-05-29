"""`.data` generic binary blob reader and writer.

`.data` is the most polymorphic kind in the format. Different operators
use it for different payloads — TOP icon raster (ASCII-int header), COMP
help text (DAT-cell preamble), EXEC DAT body, opfind cache, JSON-ish
blobs, etc. Observed first-byte signatures across the corpus include:

    '5' / '7' / etc. — ASCII version line, e.g. `5\\n150\\n120\\n...` (raster)
    '\\0'           — DAT-cell preamble at offset 0 (text-like body)
    'B'            — alternate binary header
    '{'            — JSON/script-like text

We do **not** attempt to parse a unified schema. The Data class is a
verbatim byte container; emit() returns the bytes as read. Per-subtype
decoding is left to callers that already know the operator family.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Data:
    raw: bytes

    @classmethod
    def parse(cls, raw: bytes) -> "Data":
        return cls(raw=raw)

    def emit(self) -> bytes:
        return self.raw

    @property
    def signature(self) -> str:
        """A short label for the first-byte family. Useful for routing."""
        if not self.raw:
            return "empty"
        b = self.raw[0]
        if b == 0x2A:
            return "dat_preamble"        # '*' — would have DAT-style preamble
        if b == 0x00:
            return "u32_preamble"        # starts with a u32 sentinel (no '*' marker)
        if 0x30 <= b <= 0x39:
            return "ascii_int_header"    # "5\n..." raster-style
        if b == ord("{"):
            return "brace_block"
        if b == ord("B"):
            return "binary_b"
        return f"other_{b:02x}"


def read_data(path: Path) -> Data:
    return Data.parse(path.read_bytes())


def write_data(path: Path, d: Data) -> None:
    path.write_bytes(d.emit())
