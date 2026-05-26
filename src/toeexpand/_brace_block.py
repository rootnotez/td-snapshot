"""Shared base for operator-body files that use the brace-block grammar.

The recurring shape (FORMAT.md):

    <version-int>\\n
    <0 or more header-int lines>\\n
    {
       rate = N
       start = N
       tracklength = N
       tracks = N
       {
          name = X
          data_rle = ...
       }
       ...
    }

Per-kind format versions are fixed (`.logic=3`, `.hold=1`, `.ts=65538`,
`.midiin=3`, `.mousein=1`, `.joystick=1`, `.script=1`, `.chop=5`). The
number and meaning of the header ints between the version line and the
opening `{` varies by kind. Some files (`.chop` with trivial state)
omit the brace block entirely.

`BraceBlockBody` stores the file as raw bytes plus a parsed boundary:
where the version line ends, where the brace block begins (or -1 if
none). Round-trip is byte-exact because we hold the original bytes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BraceBlockBody:
    raw: bytes

    @classmethod
    def parse(cls, raw: bytes) -> "BraceBlockBody":
        return cls(raw=raw)

    def emit(self) -> bytes:
        return self.raw

    # ---- structured accessors ----

    @property
    def version(self) -> int | None:
        nl = self.raw.find(b"\n")
        if nl < 0:
            return None
        try:
            return int(self.raw[:nl].decode("ascii"))
        except ValueError:
            return None

    @property
    def has_brace_block(self) -> bool:
        return self.raw.find(b"{") >= 0

    def header_lines(self) -> list[bytes]:
        """Lines between the version line and the `{` (or EOF). Raw bytes, no newline."""
        brace = self.raw.find(b"{")
        head_end = brace if brace >= 0 else len(self.raw)
        first_nl = self.raw.find(b"\n")
        if first_nl < 0 or first_nl >= head_end:
            return []
        body = self.raw[first_nl + 1:head_end]
        return [line for line in body.split(b"\n") if line]

    def brace_text(self) -> bytes | None:
        """The `{...}` block including the braces, or None if absent."""
        start = self.raw.find(b"{")
        if start < 0:
            return None
        return self.raw[start:]
