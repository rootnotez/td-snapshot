"""`.toc` table-of-contents reader and writer.

`.toc` grammar (from FORMAT.md):
    - Optional header line `# <v0> <v1> <v2> <v3> <v4>` on `.tox.toc` files;
      absent on `.toe.toc` files. Confirmed clean .tox/.toe marker across
      builds 2017-2025.
    - Remaining lines: relative paths inside the sibling `.dir/`, one per
      file, in deterministic order.
    - Trailing newline preserved verbatim — some tocs end with `\\n`, some
      don't; we keep what we saw.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Toc:
    header: Optional[str]  # full header line incl. leading "# ", without trailing newline; None if absent
    paths: list[str]       # one entry per artifact, in file order
    trailing_newline: bool # whether the on-disk file ended with a final \n

    @classmethod
    def parse(cls, raw: bytes) -> "Toc":
        text = raw.decode("latin-1")
        trailing_newline = text.endswith("\n")
        lines = text.split("\n")
        if trailing_newline:
            lines = lines[:-1]  # drop the empty tail from the final \n

        header: Optional[str] = None
        if lines and lines[0].startswith("# "):
            header = lines[0]
            paths = lines[1:]
        else:
            paths = lines

        return cls(header=header, paths=paths, trailing_newline=trailing_newline)

    def emit(self) -> bytes:
        lines: list[str] = []
        if self.header is not None:
            lines.append(self.header)
        lines.extend(self.paths)
        text = "\n".join(lines)
        if self.trailing_newline:
            text += "\n"
        return text.encode("latin-1")


def read_toc(path: Path) -> Toc:
    return Toc.parse(path.read_bytes())


def write_toc(path: Path, toc: Toc) -> None:
    path.write_bytes(toc.emit())
