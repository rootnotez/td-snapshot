"""`.lod` bundled-archive reader and writer (binary).

Grammar (decoded via wide-corpus parsing, supersedes the simpler FORMAT.md
v1 grammar which only described file records):

    Record = FileRecord | DescRecord | AscendRecord

    FileRecord    = 0x34 u8(path_len+1) u32_BE(body_len) <path>\\0 <body>
    DescRecord    = 0x36 u8(subtype)    u8(path_len+1)   <path>\\0
    AscendRecord  = 0x35

`.lod` is a depth-first serialisation of a subtree. File records carry
body bytes identical to what the standalone artifact would contain. Desc
records open a subdirectory (push onto a path stack); Ascend records
close it (pop). The `subtype` byte after `0x36` is consistently `0x34`
in all observed bundles — purpose still inferred (possibly "the children
will be 0x34 file records").

The exposed `Record` type collapses these three forms into a sum, with
`kind` ∈ `{"file", "desc", "ascend"}`. Round-trip is byte-exact.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

FILE_FRAMING = 0x34
DESC_FRAMING = 0x36
ASCEND_FRAMING = 0x35

LENGTH_STRUCT = struct.Struct(">I")  # big-endian u32


@dataclass
class LodRecord:
    kind: Literal["file", "desc", "ascend"]
    path: str = ""          # for file + desc; empty for ascend
    body: bytes = b""       # for file only
    subtype: int = 0x34     # the byte after 0x36 in DescRecord; unused for others


@dataclass
class Lod:
    records: list[LodRecord] = field(default_factory=list)

    @classmethod
    def parse(cls, raw: bytes) -> "Lod":
        records: list[LodRecord] = []
        i = 0
        n = len(raw)
        while i < n:
            framing = raw[i]
            if framing == FILE_FRAMING:
                path_len_p1 = raw[i + 1]
                (body_len,) = LENGTH_STRUCT.unpack(raw[i + 2:i + 6])
                path_start = i + 6
                path_end = path_start + path_len_p1 - 1
                path = raw[path_start:path_end].decode("latin-1")
                body_start = path_end + 1  # skip null terminator
                body_end = body_start + body_len
                records.append(LodRecord(kind="file", path=path, body=raw[body_start:body_end]))
                i = body_end
            elif framing == DESC_FRAMING:
                subtype = raw[i + 1]
                path_len_p1 = raw[i + 2]
                path_start = i + 3
                path_end = path_start + path_len_p1 - 1
                path = raw[path_start:path_end].decode("latin-1")
                records.append(LodRecord(kind="desc", path=path, subtype=subtype))
                i = path_end + 1  # skip null terminator
            elif framing == ASCEND_FRAMING:
                records.append(LodRecord(kind="ascend"))
                i += 1
            else:
                raise ValueError(
                    f"unknown .lod framing byte 0x{framing:02x} at offset {i}"
                )
        return cls(records=records)

    def emit(self) -> bytes:
        out = bytearray()
        for rec in self.records:
            if rec.kind == "file":
                path_bytes = rec.path.encode("latin-1")
                out.append(FILE_FRAMING)
                out.append(len(path_bytes) + 1)
                out.extend(LENGTH_STRUCT.pack(len(rec.body)))
                out.extend(path_bytes)
                out.append(0x00)
                out.extend(rec.body)
            elif rec.kind == "desc":
                path_bytes = rec.path.encode("latin-1")
                out.append(DESC_FRAMING)
                out.append(rec.subtype)
                out.append(len(path_bytes) + 1)
                out.extend(path_bytes)
                out.append(0x00)
            elif rec.kind == "ascend":
                out.append(ASCEND_FRAMING)
            else:
                raise ValueError(f"unknown LodRecord kind: {rec.kind}")
        return bytes(out)

    # ---- helpers ----

    def files(self) -> list[tuple[str, bytes]]:
        """Yield (logical_path, body) pairs by walking desc/ascend stack."""
        out: list[tuple[str, bytes]] = []
        stack: list[str] = []
        for rec in self.records:
            if rec.kind == "desc":
                stack.append(rec.path)
            elif rec.kind == "ascend":
                stack.pop()
            elif rec.kind == "file":
                full = "/".join(stack + [rec.path]) if stack else rec.path
                out.append((full, rec.body))
        return out


def read_lod(path: Path) -> Lod:
    return Lod.parse(path.read_bytes())


def write_lod(path: Path, l: Lod) -> None:
    path.write_bytes(l.emit())
