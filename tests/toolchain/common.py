"""Shared helpers for the toolchain regression workflow (see README.md).

Stdlib only, so it can be imported from PEP 723 scripts and pytest alike.
"""

from __future__ import annotations

import hashlib
import os
import plistlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
INPUTS_FILE = HERE / "inputs.txt"
GOLDEN_ROOT = HERE / "golden"
FIXTURES_ROOT = HERE / "fixtures"

DEFAULT_BIN = Path("/Applications/TouchDesigner.app/Contents/MacOS")
OUTPUT_MAX = 2000
IGNORED_NAMES = {".DS_Store"}


def bin_dir(explicit: Optional[str | Path] = None) -> Path:
    """Resolve the toolchain dir: explicit arg > $TD_TOOLCHAIN_BIN > /Applications."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("TD_TOOLCHAIN_BIN")
    return Path(env) if env else DEFAULT_BIN


def toolchain_build(bin_path: Path) -> str:
    """CFBundleVersion of the app bundle that `bin_path` (…/Contents/MacOS) sits in."""
    plist = bin_path.parent / "Info.plist"
    with plist.open("rb") as f:
        return str(plistlib.load(f)["CFBundleVersion"])


def load_inputs(root: Path = REPO, inputs_file: Path = INPUTS_FILE) -> list[Path]:
    """Expand the globs in inputs.txt (relative to `root`) into sorted, unique files."""
    found: set[Path] = set()
    for line in inputs_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for p in root.glob(line):
            if p.is_file() and p.suffix in (".toe", ".tox"):
                found.add(p.resolve())
    return sorted(found)


def input_id(path: Path, root: Path = REPO) -> str:
    return Path(path).resolve().relative_to(root.resolve()).as_posix()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _decode(b: Optional[bytes]) -> str:
    return (b or b"").decode("latin-1", errors="replace")[:OUTPUT_MAX]


@dataclass
class ExpandResult:
    tree: Optional[Path]      # <workdir>/<name>.dir, or None on failure
    toc: Optional[Path]       # <workdir>/<name>.toc, or None on failure
    returncode: Optional[int]
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.tree is not None and self.toc is not None


@dataclass
class CollapseResult:
    output: Optional[Path]    # <workdir>/<name>, or None on failure
    returncode: Optional[int]
    stdout: str
    stderr: str


def expand(bin_path: Path, src: Path, workdir: Path, timeout: int = 120) -> ExpandResult:
    """Run toeexpand on a *copy* of `src` staged in `workdir`.

    The staged copy is deleted afterwards so that a later `collapse()` (which
    writes `<workdir>/<name>`) can never write through to the original input.
    toeexpand exits 1 even on success; success = `<name>.dir/` + `<name>.toc` exist.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    staged = workdir / src.name
    shutil.copyfile(src, staged)
    try:
        proc = subprocess.run(
            [str(bin_path / "toeexpand"), staged.name],
            cwd=workdir, capture_output=True, timeout=timeout,
        )
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = None, e.stdout, (e.stderr or b"") + f"\ntimeout after {timeout}s".encode()
    finally:
        staged.unlink(missing_ok=True)
    tree = workdir / (src.name + ".dir")
    toc = workdir / (src.name + ".toc")
    return ExpandResult(
        tree=tree if tree.is_dir() else None,
        toc=toc if toc.is_file() else None,
        returncode=rc, stdout=_decode(out), stderr=_decode(err),
    )


def collapse(bin_path: Path, tree: Path, timeout: int = 120) -> CollapseResult:
    """Run toecollapse on `<name>.dir`; it writes `<name>` next to the tree."""
    output = tree.parent / tree.name[: -len(".dir")]
    output.unlink(missing_ok=True)
    try:
        proc = subprocess.run(
            [str(bin_path / "toecollapse"), tree.name],
            cwd=tree.parent, capture_output=True, timeout=timeout,
        )
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = None, e.stdout, (e.stderr or b"") + f"\ntimeout after {timeout}s".encode()
    return CollapseResult(
        output=output if output.is_file() else None,
        returncode=rc, stdout=_decode(out), stderr=_decode(err),
    )


def tree_manifest(tree: Path) -> dict[str, str]:
    """sha256 of the sibling `.toc` and every file under `<name>.dir/`.

    Keys are relative to `tree.parent` (POSIX), e.g. `x.tox.toc`,
    `x.tox.dir/.build`. `.DS_Store` is ignored.
    """
    base = tree.parent
    toc = base / (tree.name[: -len(".dir")] + ".toc")
    files = [toc] if toc.is_file() else []
    files += [p for p in tree.rglob("*") if p.is_file() and p.name not in IGNORED_NAMES]
    return {p.relative_to(base).as_posix(): sha256_file(p) for p in files}


def format_manifest(manifest: dict[str, str]) -> str:
    return "".join(f"{h}  {rel}\n" for rel, h in sorted(manifest.items()))


def parse_manifest(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if line:
            h, rel = line.split("  ", 1)
            out[rel] = h
    return out


def write_manifest(path: Path, manifest: dict[str, str]) -> str:
    """Write the manifest; return sha256 of its text (index.jsonl `tree_sha256`)."""
    text = format_manifest(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return hashlib.sha256(text.encode()).hexdigest()


def read_manifest(path: Path) -> dict[str, str]:
    return parse_manifest(Path(path).read_text())
