"""`.timestamp` saved-state epoch reader and writer.

Layout (FORMAT.md): a single ASCII integer followed by a trailing newline,
e.g. `133959789567600364\n`. Likely microseconds-since-Windows-epoch
(used for save-time markers on certain operators).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Timestamp:
    raw: bytes  # full file bytes, including trailing newline

    @classmethod
    def parse(cls, raw: bytes) -> "Timestamp":
        return cls(raw=raw)

    def emit(self) -> bytes:
        return self.raw

    @property
    def value(self) -> int:
        return int(self.raw.decode("ascii").rstrip("\n"))


def read_timestamp(path: Path) -> Timestamp:
    return Timestamp.parse(path.read_bytes())


def write_timestamp(path: Path, t: Timestamp) -> None:
    path.write_bytes(t.emit())
