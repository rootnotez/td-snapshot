"""Shared helpers for the DAT-style binary preamble used by `.text`, `.table`,
`.fifo`, `.renderpick`, and `.data`.

Layout summary (corrected after wide-corpus testing — FORMAT.md was wrong
about the preamble width being uniform):

    [optional version line: "<digit>\\n"]
    [optional extra ASCII line: "<count>\\n"]   # .fifo only
    "*"
    <N big-endian u32 fields>
    <body bytes>

The preamble u32 count is **kind-dependent**:

    .text       6 u32s  (4 sentinels + end-marker + body_length)
    .table      4 u32s  (sentinel + col_count + row_count + reserved)
    .renderpick 4 u32s  (mirrors .table)
    .fifo       4 u32s
    .data       4 u32s  (no version line; preamble starts at offset 0)

After the preamble, `.table` / `.renderpick` / `.fifo` / `.data` carry a
cell stream where each cell is: tag `\\x00\\x00\\x00\\x02` + u32 length +
content bytes + `\\x00` terminator. `.text` carries the raw DAT body
directly.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass
class Preamble:
    """The `*<u32×N>` block following any leading version/count lines."""

    fields: tuple[int, ...]

    @classmethod
    def parse(cls, raw: bytes, offset: int, count: int) -> "Preamble":
        if raw[offset:offset + 1] != b"*":
            raise ValueError(f"expected '*' at offset {offset}, got {raw[offset:offset + 1]!r}")
        fmt = ">" + "I" * count
        size = struct.calcsize(fmt)
        fields = struct.unpack(fmt, raw[offset + 1:offset + 1 + size])
        return cls(fields=fields)

    def emit(self) -> bytes:
        fmt = ">" + "I" * len(self.fields)
        return b"*" + struct.pack(fmt, *self.fields)

    @property
    def byte_size(self) -> int:
        return 1 + 4 * len(self.fields)
