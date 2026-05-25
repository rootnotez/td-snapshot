"""`.network` COMP external-connector reader and writer.

Grammar (from FORMAT.md):

    1
    compinputs
    {
    0 \t""
    \tin_record
    \tCHOP
    1 \t""
    \tin_search
    \tCHOP
    }
    end

Round-trip strategy: keep all lines as a flat list. Accessors decode the
`compinputs` block on demand. emit() rejoins verbatim — tabs and trailing
whitespace within record lines are preserved exactly.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Connector:
    slot: int
    label: str
    op_name: str
    family: str  # CHOP / TOP / SOP / DAT / MAT / POP


@dataclass
class Network:
    lines: list[str] = field(default_factory=list)
    trailing_newline: bool = True

    @classmethod
    def parse(cls, raw: bytes) -> "Network":
        text = raw.decode("latin-1")
        trailing_newline = text.endswith("\n")
        lines = text.split("\n")
        if trailing_newline:
            lines = lines[:-1]
        return cls(lines=lines, trailing_newline=trailing_newline)

    def emit(self) -> bytes:
        text = "\n".join(self.lines)
        if self.trailing_newline:
            text += "\n"
        return text.encode("latin-1")

    # ---- accessors ----

    @property
    def version(self) -> Optional[int]:
        if not self.lines:
            return None
        try:
            return int(self.lines[0])
        except ValueError:
            return None

    def compinputs(self) -> list[Connector]:
        """Parse the compinputs { ... } block into Connector records."""
        return self._parse_block("compinputs")

    def compoutputs(self) -> list[Connector]:
        return self._parse_block("compoutputs")

    def _parse_block(self, label: str) -> list[Connector]:
        try:
            start = self.lines.index(label)
        except ValueError:
            return []
        if start + 1 >= len(self.lines) or self.lines[start + 1].strip() != "{":
            return []
        i = start + 2
        records: list[list[str]] = []
        current: list[str] = []
        while i < len(self.lines) and self.lines[i].strip() != "}":
            line = self.lines[i]
            if line and line[0].isdigit():
                # Starts a new record. First-line shape: `<slot>\t"<label>"`.
                if current:
                    records.append(current)
                current = [line]
            else:
                current.append(line)
            i += 1
        if current:
            records.append(current)

        connectors: list[Connector] = []
        for rec in records:
            if not rec:
                continue
            # Record line 1: `<slot>\t"<label>"`
            head = rec[0]
            slot_str, _, rest = head.partition("\t")
            try:
                slot = int(slot_str.strip())
            except ValueError:
                continue
            quoted_label = rest.strip()
            if quoted_label.startswith('"') and quoted_label.endswith('"'):
                quoted_label = quoted_label[1:-1]
            # Remaining lines hold `\t<op_name>` then `\t<family>`.
            op_name = rec[1].lstrip("\t") if len(rec) > 1 else ""
            family = rec[2].lstrip("\t") if len(rec) > 2 else ""
            connectors.append(Connector(slot=slot, label=quoted_label, op_name=op_name, family=family))
        return connectors
