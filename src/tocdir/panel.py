"""`.panel` panel-layout reader and writer.

Grammar (from FORMAT.md):

    1                  # format version
    3                  # sub-version
    12                 # body-line count (must equal len(body))
    u 0.424242
    v 0.486486
    rollu 0.0808081
    ...

Three integer header lines then a body of `key value` lines. The third
header integer matches the body length.

Round-trip strategy: keep the three header ints and the body lines as
strings. emit() rejoins. The body-length integer is treated as just
another header value — if a caller mutates the body, they must update
that header themselves (we don't auto-fix; bit-exact is the contract).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Panel:
    header: list[str] = field(default_factory=list)  # first three lines, verbatim
    body: list[str] = field(default_factory=list)    # remaining "key value" lines
    trailing_newline: bool = True

    @classmethod
    def parse(cls, raw: bytes) -> "Panel":
        text = raw.decode("latin-1")
        trailing_newline = text.endswith("\n")
        lines = text.split("\n")
        if trailing_newline:
            lines = lines[:-1]
        header = lines[:3]
        body = lines[3:]
        return cls(header=header, body=body, trailing_newline=trailing_newline)

    def emit(self) -> bytes:
        text = "\n".join(self.header + self.body)
        if self.trailing_newline:
            text += "\n"
        return text.encode("latin-1")

    # ---- accessors ----

    def get(self, key: str) -> Optional[str]:
        for line in self.body:
            k, _, v = line.partition(" ")
            if k == key:
                return v
        return None
