"""Whole-tree facade over the per-kind parsers.

A `Project` is the in-memory representation of a `<name>.tox.toc` +
`<name>.tox.dir/` pair (or `.toe.toc` + `.toe.dir/`). It walks the `.toc`
in order, parses each entry with the matching kind module, and emits the
tree back byte-identically.

Round-trip contract: for any well-formed input,
    Project.from_dir(d).to_dir(out)
produces a tree where every file (including the sibling `.toc`) equals
the source byte-for-byte.

Kinds without a dedicated parser are held as raw `bytes` — emit still
round-trips them, accessors just aren't available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# toeexpand uses two parallel encodings when sibling node names collide on
# case-insensitive APFS (e.g. `Map` + `map`): the `.toc` lists the duplicate
# with a trailing ` N` (space + digits) suffix, while the on-disk file gets a
# `.N` (dot + digits) suffix. Translate between them so the parser can locate
# the file the `.toc` references.
_TOC_DUP_SUFFIX = re.compile(r" (\d+)$")


def _toc_to_disk(rel: str) -> str:
    return _TOC_DUP_SUFFIX.sub(r".\1", rel)

from . import (
    build as _build,
    chop as _chop,
    cparm as _cparm,
    data as _data,
    fifo as _fifo,
    hold as _hold,
    joystick as _joystick,
    lod as _lod,
    logic as _logic,
    midiin as _midiin,
    mousein as _mousein,
    n as _n,
    network as _network,
    panel as _panel,
    parm as _parm,
    renderpick as _renderpick,
    script as _script,
    table as _table,
    text as _text,
    timestamp as _timestamp,
    toc as _toc,
    ts as _ts,
)

# Suffix-token → (parse(bytes) -> model, model.emit() -> bytes is by convention).
KIND_PARSERS: dict[str, Callable[[bytes], Any]] = {
    "build": _build.Build.parse,
    "n": _n.N.parse,
    "parm": _parm.Parm.parse,
    "cparm": _cparm.Cparm.parse,
    "panel": _panel.Panel.parse,
    "network": _network.Network.parse,
    "text": _text.Text.parse,
    "table": _table.Table.parse,
    "fifo": _fifo.Fifo.parse,
    "renderpick": _renderpick.Renderpick.parse,
    "data": _data.Data.parse,
    "lod": _lod.Lod.parse,
    "timestamp": _timestamp.Timestamp.parse,
    "script": _script.Script.parse,
    "ts": _ts.Ts.parse,
    "chop": _chop.Chop.parse,
    "logic": _logic.Logic.parse,
    "hold": _hold.Hold.parse,
    "midiin": _midiin.Midiin.parse,
    "mousein": _mousein.Mousein.parse,
    "joystick": _joystick.Joystick.parse,
}


def _suffix_key(rel_path: str) -> str:
    """Token used to look up a parser. Handles dotfiles like `.build`."""
    name = rel_path.rsplit("/", 1)[-1]
    stripped = name.lstrip(".")
    if "." not in stripped:
        return stripped
    return stripped.rsplit(".", 1)[-1]


@dataclass
class Project:
    toc: _toc.Toc
    # path-as-listed-in-toc → parsed model OR raw bytes (unknown kinds).
    entries: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dir(cls, dir_path: Path | str) -> "Project":
        """Read a `<name>.tox.dir/` (alongside its `.toc`) into memory.

        `dir_path` is the `.dir/` directory itself; the sibling `.toc` is
        derived by replacing the `.dir` suffix with `.toc`.
        """
        d = Path(dir_path)
        if not d.is_dir():
            raise NotADirectoryError(f"{d} is not a directory")
        if not d.name.endswith(".dir"):
            raise ValueError(f"expected a `.dir/` directory, got {d.name}")

        toc_path = d.parent / (d.name[: -len(".dir")] + ".toc")
        if not toc_path.exists():
            raise FileNotFoundError(f"no sibling .toc for {d} (looked for {toc_path})")

        toc_model = _toc.Toc.parse(toc_path.read_bytes())
        entries: dict[str, Any] = {}
        for rel in toc_model.paths:
            f = d / _toc_to_disk(rel)
            raw = f.read_bytes()
            parser = KIND_PARSERS.get(_suffix_key(rel))
            entries[rel] = parser(raw) if parser is not None else raw
        return cls(toc=toc_model, entries=entries)

    def to_dir(self, dir_path: Path | str) -> None:
        """Write the project back to `<name>.tox.dir/` + sibling `.toc`.

        Creates `dir_path` and any required subdirectories. Overwrites
        existing files. Does not remove pre-existing extra files in the
        target directory — callers wanting a clean write should clear it
        first.
        """
        d = Path(dir_path)
        if not d.name.endswith(".dir"):
            raise ValueError(f"expected a `.dir/` directory, got {d.name}")

        d.mkdir(parents=True, exist_ok=True)
        toc_path = d.parent / (d.name[: -len(".dir")] + ".toc")
        toc_path.write_bytes(self.toc.emit())

        for rel, model in self.entries.items():
            target = d / _toc_to_disk(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = model if isinstance(model, (bytes, bytearray)) else model.emit()
            target.write_bytes(raw)

    def verify(self, dir_path: Path | str) -> list[str]:
        """Compare in-memory emit against on-disk source. Returns mismatched paths.

        Empty list = byte-exact across every entry plus the `.toc`.
        """
        d = Path(dir_path)
        toc_path = d.parent / (d.name[: -len(".dir")] + ".toc")
        mismatches: list[str] = []
        if self.toc.emit() != toc_path.read_bytes():
            mismatches.append(toc_path.name)
        for rel, model in self.entries.items():
            raw = model if isinstance(model, (bytes, bytearray)) else model.emit()
            if raw != (d / _toc_to_disk(rel)).read_bytes():
                mismatches.append(rel)
        return mismatches
