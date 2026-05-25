"""`.cparm` custom-parameter-definitions reader and writer.

Grammar (from FORMAT.md):

    ?
    pages 4 "Record (in1)" "Search (in2)" "Cache to File" About
    772804868 Emb:Emb0label Label 1 1 0 0 1 1 1 2 0 "" "" "Record (in1)" 1
    -1374678782 K "K Neighbors" 1 3 1 1 1 100 100 2 0 "" "" "Search (in2)" 2
    ...
    ?

`?` brackets the block. First content line is the `pages` declaration.
Subsequent lines define one custom parameter per row.

Round-trip strategy: store every line verbatim. Provide accessors for the
type-id, name, and label that scan into each row on demand. Column-by-column
schema (FORMAT.md §.cparm) is intentionally NOT re-parsed at emit time —
the source line is the canonical truth.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CparmRow:
    raw: str

    @property
    def is_page_marker(self) -> bool:
        return self.raw == "?"

    @property
    def is_pages_decl(self) -> bool:
        return self.raw.startswith("pages ")

    @property
    def type_id(self) -> Optional[int]:
        if self.is_page_marker or self.is_pages_decl:
            return None
        parts = self.raw.split(None, 1)
        if not parts:
            return None
        try:
            return int(parts[0])
        except ValueError:
            return None

    @property
    def name(self) -> Optional[str]:
        if self.is_page_marker or self.is_pages_decl:
            return None
        parts = self.raw.split(None, 2)
        return parts[1] if len(parts) >= 2 else None


@dataclass
class Cparm:
    rows: list[CparmRow] = field(default_factory=list)
    trailing_newline: bool = True

    @classmethod
    def parse(cls, raw: bytes) -> "Cparm":
        text = raw.decode("latin-1")
        trailing_newline = text.endswith("\n")
        lines = text.split("\n")
        if trailing_newline:
            lines = lines[:-1]
        rows = [CparmRow(raw=line) for line in lines]
        return cls(rows=rows, trailing_newline=trailing_newline)

    def emit(self) -> bytes:
        text = "\n".join(r.raw for r in self.rows)
        if self.trailing_newline:
            text += "\n"
        return text.encode("latin-1")

    # ---- accessors ----

    def pages(self) -> list[str]:
        """Return the page-name list, parsed from the `pages <count> <names...>` line."""
        for r in self.rows:
            if r.is_pages_decl:
                # `pages 4 "Record (in1)" "Search (in2)" "Cache to File" About`
                # Quoted names contain spaces; bareword names do not.
                rest = r.raw[len("pages "):].split(None, 1)
                if len(rest) < 2:
                    return []
                # Drop the leading count.
                tail = rest[1]
                return _split_quoted_or_bareword(tail)
        return []

    def parameter_rows(self) -> list[CparmRow]:
        return [r for r in self.rows if not r.is_page_marker and not r.is_pages_decl]


def _split_quoted_or_bareword(text: str) -> list[str]:
    """Split a line that mixes "quoted strings" and bareword tokens."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        if text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 1
            out.append(text[i + 1:j])
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace():
                j += 1
            out.append(text[i:j])
            i = j
    return out
