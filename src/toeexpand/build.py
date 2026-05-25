"""`.build` build-stamp reader and writer.

Grammar (from FORMAT.md):
    Plain `key value` lines. Examples:
        version 099
        build 2025.32460
        time Wed May 13 22:49:57 2026
        osname macOS
        osversion 15.7.4

    In TD 088 the trailing `osname`/`osversion` keys are absent (cosmetic
    diff, not parser-breaking).

We preserve key order verbatim. The value side is treated as opaque text
up to the next newline — `time` contains spaces and is not re-tokenized.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Build:
    entries: list[tuple[str, str]]  # ordered (key, value) pairs
    trailing_newline: bool

    @classmethod
    def parse(cls, raw: bytes) -> "Build":
        text = raw.decode("ascii")
        trailing_newline = text.endswith("\n")
        lines = text.split("\n")
        if trailing_newline:
            lines = lines[:-1]

        entries: list[tuple[str, str]] = []
        for line in lines:
            if not line:
                entries.append(("", ""))
                continue
            key, _, value = line.partition(" ")
            entries.append((key, value))
        return cls(entries=entries, trailing_newline=trailing_newline)

    def emit(self) -> bytes:
        lines = [f"{k} {v}" if k else "" for k, v in self.entries]
        text = "\n".join(lines)
        if self.trailing_newline:
            text += "\n"
        return text.encode("ascii")

    def get(self, key: str) -> str | None:
        for k, v in self.entries:
            if k == key:
                return v
        return None

    @property
    def version(self) -> str | None:
        return self.get("version")

    @property
    def build_number(self) -> str | None:
        return self.get("build")


def read_build(path: Path) -> Build:
    return Build.parse(path.read_bytes())


def write_build(path: Path, build: Build) -> None:
    path.write_bytes(build.emit())
