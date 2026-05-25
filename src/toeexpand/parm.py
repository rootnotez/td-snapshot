"""`.parm` parameter-values reader and writer.

Grammar (from FORMAT.md):

    ?
    pageindex 0 1
    label 0 "> Clipboard"
    clone 17 "" op.TDTox.op('defaultCOMPs/button')
    file 48 "" f'scripts/{me.name}.py'
    scaletofit 49 onlyshrink "parent().par[me.curPar.name] or me.curPar.val"
    ?

`?` lines bracket each parameter page; only non-default parameters appear
between them. A row is `<name> <mode> <value> [<expr>]` where:
    - mode is a signed 32-bit int (bit-field, see FORMAT.md mode rules).
    - value may be a quoted string, a number, a bareword (on/off, etc.) or
      an empty quoted "".
    - expr is optional Python source, sometimes quoted, sometimes bare.

Round-trip strategy: each row keeps the raw line text. Accessors split
on whitespace at read time for the leading `name`/`mode` tokens, but the
value/expr remainder is exposed as raw_rest — we do NOT re-quote or
re-tokenize, because the canonical source of truth is the source line.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Row:
    """One parameter line OR a `?` page-marker line, preserving raw bytes."""

    raw: str  # exact line text, no trailing newline

    @property
    def is_page_marker(self) -> bool:
        return self.raw == "?"

    @property
    def name(self) -> Optional[str]:
        if self.is_page_marker:
            return None
        parts = self.raw.split(None, 2)
        return parts[0] if parts else None

    @property
    def mode(self) -> Optional[int]:
        if self.is_page_marker:
            return None
        parts = self.raw.split(None, 2)
        if len(parts) < 2:
            return None
        try:
            return int(parts[1])
        except ValueError:
            return None

    @property
    def raw_rest(self) -> str:
        """Everything after `<name> <mode> ` — the value + optional expr.

        Returns empty string for page markers or malformed lines.
        """
        if self.is_page_marker:
            return ""
        parts = self.raw.split(None, 2)
        return parts[2] if len(parts) >= 3 else ""

    @property
    def has_expression(self) -> bool:
        """True when the mode bitfield indicates a trailing expression.

        See FORMAT.md: `(mode & 0x30) != 0` carries an expression.
        """
        m = self.mode
        return m is not None and (m & 0x30) != 0

    @property
    def is_custom_page(self) -> bool:
        """True when the parameter sits on a custom-parameter page (bit 26 set)."""
        m = self.mode
        return m is not None and (m & 0x04000000) != 0

    @property
    def is_op_typed(self) -> bool:
        """True when the value resolves to an operator reference (bits 26+27 set)."""
        m = self.mode
        return m is not None and (m & 0x0C000000) == 0x0C000000


@dataclass
class Parm:
    rows: list[Row] = field(default_factory=list)
    trailing_newline: bool = True

    @classmethod
    def parse(cls, raw: bytes) -> "Parm":
        text = raw.decode("latin-1")
        trailing_newline = text.endswith("\n")
        lines = text.split("\n")
        if trailing_newline:
            lines = lines[:-1]
        rows = [Row(raw=line) for line in lines]
        return cls(rows=rows, trailing_newline=trailing_newline)

    def emit(self) -> bytes:
        text = "\n".join(r.raw for r in self.rows)
        if self.trailing_newline:
            text += "\n"
        return text.encode("latin-1")

    # ---- structured accessors ----

    def named(self, name: str) -> Optional[Row]:
        for r in self.rows:
            if r.name == name:
                return r
        return None

    def parameter_rows(self) -> list[Row]:
        """Just the parameter rows, skipping `?` page markers."""
        return [r for r in self.rows if not r.is_page_marker]


def read_parm(path: Path) -> Parm:
    return Parm.parse(path.read_bytes())


def write_parm(path: Path, parm: Parm) -> None:
    path.write_bytes(parm.emit())
