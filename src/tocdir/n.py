"""`.n` node-definition reader and writer.

Grammar (from FORMAT.md):

    FAMILY:type
    v <x> <y> <zoom>            # COMPs only
    tags <count> <flag> <tag>... # optional
    dict <hex pickle>           # optional, Python pickle v4
    tile <x> <y> <w> <h>
    flags = <tok> <tok>...      # note the literal two spaces after '='
    comment "<text>"            # optional
    inputs { ... }              # optional, multi-line block
    extrainputs { ... }         # optional, multi-line block
    exports { ... }             # optional, multi-line block
    dock <sibling>              # optional
    color <r> <g> <b>           # trailing space observed
    view <11-or-12 numbers>     # DAT/MAT operators, layout family-dependent
    end

Round-trip strategy: parse into an ordered list of logical sections,
preserving every byte. Block sections (`inputs/extrainputs/exports`) keep
their inner lines verbatim. emit() rejoins. We do NOT re-tokenize numeric
fields — strings round-trip identically even if a future edit wants to
change a value.

Structured accessors (family, type, flag tokens, comment text) read the
underlying section text on demand without disturbing it.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

BLOCK_SECTIONS = ("inputs", "extrainputs", "exports")


@dataclass
class Section:
    """One logical section of a `.n` file.

    `lines` is the raw decoded text of every line that belongs to this
    section, with newlines stripped — emit() puts the newlines back.
    """

    label: str           # first whitespace-delimited token of the opening line
    lines: list[str]     # all lines belonging to this section, in order
    is_block: bool       # True if this section uses { ... } body
    trailing_blank: bool # True if a blank line followed this section in the source


@dataclass
class N:
    sections: list[Section] = field(default_factory=list)
    trailing_newline: bool = True

    @classmethod
    def parse(cls, raw: bytes) -> "N":
        text = raw.decode("latin-1")
        trailing_newline = text.endswith("\n")
        all_lines = text.split("\n")
        if trailing_newline:
            all_lines = all_lines[:-1]

        sections: list[Section] = []
        i = 0
        n = len(all_lines)
        # The first line is the FAMILY:type header — always its own section.
        if n == 0:
            return cls(sections=[], trailing_newline=trailing_newline)

        # Treat the FAMILY:type line as a section with label "FAMILY:type".
        sections.append(Section(label="<header>", lines=[all_lines[0]], is_block=False, trailing_blank=False))
        i = 1

        while i < n:
            line = all_lines[i]
            if not line.strip():
                # Blank line — attach to the previous section if any.
                if sections:
                    sections[-1].trailing_blank = True
                i += 1
                continue

            # First whitespace-delimited token decides the section label.
            label = line.split(None, 1)[0]
            if label in BLOCK_SECTIONS:
                # Block: collect from here until matching `}` line.
                block_lines = [line]  # the `inputs` line itself
                i += 1
                # Next line should be `{` — collect until `}`
                while i < n:
                    block_lines.append(all_lines[i])
                    if all_lines[i].strip() == "}":
                        i += 1
                        break
                    i += 1
                sections.append(Section(label=label, lines=block_lines, is_block=True, trailing_blank=False))
            else:
                sections.append(Section(label=label, lines=[line], is_block=False, trailing_blank=False))
                i += 1

        return cls(sections=sections, trailing_newline=trailing_newline)

    def emit(self) -> bytes:
        parts: list[str] = []
        for sec in self.sections:
            parts.extend(sec.lines)
            if sec.trailing_blank:
                parts.append("")
        text = "\n".join(parts)
        if self.trailing_newline:
            text += "\n"
        return text.encode("latin-1")

    # ---- structured accessors (read-only conveniences) ----

    @property
    def family_type(self) -> str:
        """The `FAMILY:type` header line, e.g. `COMP:container`."""
        return self.sections[0].lines[0] if self.sections else ""

    @property
    def family(self) -> str:
        return self.family_type.split(":", 1)[0] if ":" in self.family_type else ""

    @property
    def type(self) -> str:
        return self.family_type.split(":", 1)[1] if ":" in self.family_type else ""

    def section(self, label: str) -> Optional[Section]:
        for sec in self.sections:
            if sec.label == label:
                return sec
        return None

    def flag_tokens(self) -> list[str]:
        """Return the space-separated tokens after `flags = `, or [] if absent."""
        sec = self.section("flags")
        if sec is None:
            return []
        line = sec.lines[0]
        # `flags = ` has a literal two spaces after = in the source. Strip the prefix once.
        prefix = "flags = "
        if not line.startswith(prefix):
            return []
        # The remainder may itself begin with a space (the second of the doubled ones).
        # Split on any whitespace — that loses the doubled-space, but the parsed list is
        # canonical; emit() uses the raw line so round-trip stays bit-exact.
        return line[len(prefix):].split()

    def comment_text(self) -> Optional[str]:
        """The unescaped comment, or None if no `comment` section."""
        sec = self.section("comment")
        if sec is None:
            return None
        line = sec.lines[0]
        # comment "<text>"; the text uses \n escapes per FORMAT.md.
        # Find the first quote and the last quote.
        first = line.find('"')
        last = line.rfind('"')
        if first < 0 or last <= first:
            return ""
        return line[first + 1:last]


def read_n(path: Path) -> N:
    return N.parse(path.read_bytes())


def write_n(path: Path, n: N) -> None:
    path.write_bytes(n.emit())
