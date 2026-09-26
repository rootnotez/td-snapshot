"""Pins the toeexpand/toecollapse toolchain capabilities and quirks this repo
depends on (see README.md for the layout/manifest contract this suite lives
next to). A future TouchDesigner update that changes any of the behaviour
pinned here should fail this suite loudly, rather than silently break
scripts/shrink.sh, scripts/grow.sh, or the tocdir parser.

Run against the default toolchain (from TD_TOOLCHAIN_BIN, else
/Applications/TouchDesigner.app/Contents/MacOS):

    uv run --no-project --with pytest pytest tests/toolchain -q

Run against another installed/mounted build:

    TD_TOOLCHAIN_BIN=/path/to/TouchDesigner.app/Contents/MacOS \\
        uv run --no-project --with pytest pytest tests/toolchain -q

The whole module is skipped (not failed) when no toeexpand binary is found at
the resolved bin dir, so this suite is a no-op on a machine without
TouchDesigner installed.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src"))

import common as c  # noqa: E402

from tocdir.census import census  # noqa: E402
from tocdir.project import Project  # noqa: E402

BIN = c.bin_dir()
if not (BIN / "toeexpand").exists():
    pytest.skip(f"toeexpand not found at {BIN} (set TD_TOOLCHAIN_BIN)", allow_module_level=True)

INPUTS = c.load_inputs()
INPUT_IDS = [c.input_id(p) for p in INPUTS]
TOE_INPUTS = [p for p in INPUTS if p.suffix == ".toe"]
TOE_INPUT_IDS = [c.input_id(p) for p in TOE_INPUTS]

RAW_KINDS_ALLOWLIST = HERE / "raw_kinds_allowlist.txt"


def _load_allowlist() -> set[str]:
    kinds: set[str] = set()
    for line in RAW_KINDS_ALLOWLIST.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            kinds.add(line)
    return kinds


# --------------------------------------------------------------------------
# Session-scoped expansion cache: every golden input is expanded exactly
# once per pytest session, however many tests below need its tree.
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def expand_root(tmp_path_factory):
    return tmp_path_factory.mktemp("golden-expand")


@pytest.fixture(scope="session")
def expand_cache(expand_root):
    cache: dict[str, c.ExpandResult] = {}
    for path in INPUTS:
        iid = c.input_id(path)
        wd = expand_root / iid.replace("/", "__")
        er = c.expand(c.bin_dir(), path, wd, timeout=300)
        assert er.ok, f"expand failed for {iid}: rc={er.returncode} stderr={er.stderr!r}"
        cache[iid] = er
    return cache


@pytest.fixture(scope="session")
def collapse_cache(expand_cache):
    """toecollapse of each cached tree, computed once and reused."""
    cache: dict[str, c.CollapseResult] = {}
    for iid, er in expand_cache.items():
        cache[iid] = c.collapse(c.bin_dir(), er.tree, timeout=300)
    return cache


# --------------------------------------------------------------------------
# 1. expand basics + the exit-code quirk.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", INPUTS, ids=INPUT_IDS)
def test_expand_produces_dir_and_toc_and_exits_1(path, expand_cache):
    """toeexpand's own usage/behaviour: it exits 1 even on a fully successful
    expansion (confirmed in toeexpand/FORMAT.md and common.py's docstring).
    Success must be judged by `<name>.dir/` + `<name>.toc` existing, not by
    the exit code.
    """
    er = expand_cache[c.input_id(path)]
    assert er.returncode == 1
    assert er.tree is not None and er.tree.is_dir()
    assert er.toc is not None and er.toc.is_file()


# --------------------------------------------------------------------------
# 2. tocdir parses every expansion and re-emits it bit-exact.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", INPUTS, ids=INPUT_IDS)
def test_tocdir_roundtrips_expansion_bit_exact(path, expand_cache):
    er = expand_cache[c.input_id(path)]
    project = Project.from_dir(er.tree)
    mismatches = project.verify(er.tree)
    assert mismatches == [], f"tocdir round-trip mismatches: {mismatches[:10]}"


# --------------------------------------------------------------------------
# 3. toecollapse exits 0 and expand(collapse(tree)) is a fixed point.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", INPUTS, ids=INPUT_IDS)
def test_collapse_exits_0_and_reaches_a_fixed_point(path, expand_cache, collapse_cache, tmp_path):
    iid = c.input_id(path)
    er = expand_cache[iid]
    cr = collapse_cache[iid]

    assert cr.returncode == 0
    assert cr.output is not None and cr.output.is_file()

    manifest_before = c.tree_manifest(er.tree)

    er2 = c.expand(c.bin_dir(), cr.output, tmp_path / "refixed", timeout=300)
    assert er2.ok
    manifest_after = c.tree_manifest(er2.tree)

    assert manifest_before == manifest_after


# --------------------------------------------------------------------------
# 4. collapse(expand(x)) byte-exact for td-snapshot.tox; NOT for the repo's
#    .toe inputs (the build pipeline only depends on the .tox case).
# --------------------------------------------------------------------------


def test_collapse_equals_input_byte_exact_for_tox(expand_cache, collapse_cache):
    path = REPO / "td-snapshot.tox"
    iid = c.input_id(path)
    cr = collapse_cache[iid]
    assert cr.output.read_bytes() == path.read_bytes()


@pytest.mark.parametrize("path", TOE_INPUTS, ids=TOE_INPUT_IDS)
def test_collapse_does_not_equal_input_for_toe(path, collapse_cache):
    """Observed on both TD 2025.33230 and 2025.32460: unlike td-snapshot.tox,
    every .toe input in the golden set collapses to bytes that differ from
    the original (always slightly *larger*; first 16 bytes already diverge
    a few bytes past the shared `10\\x00\\x00` magic). The round-trip is still
    a *tree fixed point* (test 3 above) — expand(collapse(x)) reproduces the
    same tree — it is only the raw collapsed *file* that differs from the
    originally-saved .toe.

    This is pinned as a known-true divergence, not a bug to fix: the build
    pipeline (scripts/shrink.sh) only ever collapses into a .tox, never a
    .toe, so byte-exactness is only required for the .tox case (see the test
    above).
    """
    iid = c.input_id(path)
    cr = collapse_cache[iid]
    assert cr.returncode == 0
    assert cr.output is not None
    assert cr.output.read_bytes() != path.read_bytes()


# --------------------------------------------------------------------------
# 5. The shrink path: tocdir set-text -> toecollapse -> toeexpand round-trip.
# --------------------------------------------------------------------------


def test_shrink_set_text_path(tmp_path):
    """Exercise the same sequence scripts/shrink.sh uses to inject src/*.py
    into the canonical tox/ tree, on a throwaway copy.

    Arg order for `python -m tocdir set-text` is <target .text> <source
    file> (src/tocdir/__main__.py's `_set_text`); scripts/shrink.sh's local
    SET_TEXT() shell function is called as `SET_TEXT <source> <target>` and
    swaps them itself (`set-text "$2" "$1"`) to match.
    """
    src_tree = REPO / "tox" / "td_snapshot.tox.dir"
    src_toc = REPO / "tox" / "td_snapshot.tox.toc"
    assert src_tree.is_dir() and src_toc.is_file()

    work_tree = tmp_path / "td_snapshot.tox.dir"
    shutil.copytree(src_tree, work_tree)
    shutil.copy(src_toc, tmp_path / "td_snapshot.tox.toc")

    target_text = work_tree / "td_snapshot" / "core.text"
    assert target_text.is_file()

    new_body = b'# shrink-path-probe\nprint("hello-from-test-capabilities")\n'
    source_file = tmp_path / "new_core_body.py"
    source_file.write_bytes(new_body)

    proc = subprocess.run(
        [sys.executable, "-m", "tocdir", "set-text", str(target_text), str(source_file)],
        cwd=REPO,
        env={**os.environ, "PYTHONPATH": str(REPO / "src")},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    # set-text rewrites the binary length-header preamble around the body,
    # so the body is a suffix/substring, not the whole file.
    assert new_body in target_text.read_bytes()

    cr = c.collapse(c.bin_dir(), work_tree, timeout=120)
    assert cr.returncode == 0
    assert cr.output is not None and cr.output.is_file()

    er2 = c.expand(c.bin_dir(), cr.output, tmp_path / "reexpanded", timeout=120)
    assert er2.ok

    reexpanded_text = er2.tree / "td_snapshot" / "core.text"
    assert reexpanded_text.is_file()
    assert new_body in reexpanded_text.read_bytes()

    project = Project.from_dir(er2.tree)
    assert project.verify(er2.tree) == []


# --------------------------------------------------------------------------
# 6. `toeexpand -b <file>` build-info shape, and the `pattern` argument.
# --------------------------------------------------------------------------


def test_build_info_flag_shape(tmp_path):
    """`toeexpand -b <file>` prints the file's *own saved-build* metadata —
    the same five key/value lines stored in the expansion's `.build` entry
    (confirmed by diff against `tox/td_snapshot.tox.dir/.build`) — not the
    toolchain binary's own build. So this reports whatever TD build last
    *saved* the file, which is why it does not necessarily match
    common.toolchain_build() (the CFBundleVersion of the toolchain running
    it): td-snapshot.tox was last saved by TD 2025.32460, and both the
    2025.33230 and 2025.32460 toeexpand binaries report that same value for
    it.
    """
    path = REPO / "td-snapshot.tox"
    staged = tmp_path / path.name
    shutil.copy(path, staged)

    proc = subprocess.run(
        [str(BIN / "toeexpand"), "-b", staged.name],
        cwd=tmp_path,
        capture_output=True,
        timeout=60,
    )
    assert proc.returncode == 1
    assert proc.stderr == b""

    text = proc.stdout.decode("latin-1")
    lines = [line for line in text.splitlines() if line]
    keys = [line.split(" ", 1)[0] for line in lines]
    assert keys == ["version", "build", "time", "osname", "osversion"]

    # Matches the .build entry already sitting in the canonical tree.
    canonical_build = (REPO / "tox" / "td_snapshot.tox.dir" / ".build").read_text()
    assert text.strip() == canonical_build.strip()


def test_pattern_argument_suppresses_directory_write(tmp_path, expand_cache):
    """`toeexpand file pattern` — usage text: "Example: toeexpand
    untitled.toe moviein1". Observed on both TD 2025.33230 and 2025.32460:
    passing a second positional argument does NOT selectively expand just
    the matching operator. Instead the `.toc` is written out in full
    (byte-identical to a plain expand's `.toc`) but the `.dir/` tree is
    never created at all — regardless of whether the pattern names a real
    operator (`core`) or garbage. stdout/rc still claim the ordinary
    success shape (rc=1, "expanded into directory ... and listed in file
    ..."). This looks like a dead/broken code path in toeexpand, not a
    documented filtering feature — pinned so a future build that actually
    implements filtering (or removes the argument) is caught.
    """
    path = REPO / "td-snapshot.tox"
    staged = tmp_path / path.name
    shutil.copy(path, staged)

    proc = subprocess.run(
        [str(BIN / "toeexpand"), staged.name, "core"],
        cwd=tmp_path,
        capture_output=True,
        timeout=60,
    )
    assert proc.returncode == 1

    toc = tmp_path / (path.name + ".toc")
    tree = tmp_path / (path.name + ".dir")
    assert toc.is_file()
    assert not tree.exists()

    full_er = expand_cache[c.input_id(path)]
    assert toc.read_bytes() == full_er.toc.read_bytes()


# --------------------------------------------------------------------------
# 7. Re-expanding into a directory where `<name>.dir` already exists.
# --------------------------------------------------------------------------


def test_reexpand_refuses_existing_directory(expand_cache):
    """scripts/grow.sh's comments say toeexpand refuses to overwrite an
    existing expansion; pin the exact observed shape: rc=0 (unlike the rc=1
    "success" quirk above) and a "already exists" warning on stderr, with
    the pre-existing tree left untouched.
    """
    path = REPO / "td-snapshot.tox"
    er = expand_cache[c.input_id(path)]
    workdir = er.tree.parent

    before = c.tree_manifest(er.tree)

    staged = workdir / path.name
    shutil.copy(path, staged)
    try:
        proc = subprocess.run(
            [str(BIN / "toeexpand"), staged.name],
            cwd=workdir,
            capture_output=True,
            timeout=60,
        )
    finally:
        staged.unlink(missing_ok=True)

    assert proc.returncode == 0
    assert b"already exists" in proc.stderr

    after = c.tree_manifest(er.tree)
    assert before == after


# --------------------------------------------------------------------------
# 8. Case-collision ` N` suffix (FORMAT.md "Case-collision suffix
#    mismatch"). Fixture generated later; skip gracefully until then.
# --------------------------------------------------------------------------


def test_case_collision_suffix_disambiguation(tmp_path):
    fixtures = sorted(HERE.glob("fixtures/*/features.tox"))
    if not fixtures:
        pytest.skip("no tests/toolchain/fixtures/*/features.tox yet (generated later)")

    fixture = fixtures[0]
    staged = tmp_path / fixture.name
    shutil.copy(fixture, staged)

    er = c.expand(c.bin_dir(), staged, tmp_path, timeout=120)
    assert er.ok

    toc_text = er.toc.read_text()
    dup_lines = [line for line in toc_text.splitlines() if re.search(r" \d+$", line)]
    assert dup_lines, "expected a case-collision ` N` .toc entry (caseProbe/caseprobe)"

    for line in dup_lines:
        base, n = line.rsplit(" ", 1)
        disk_name = f"{base}.{n}"
        assert (er.tree / disk_name).is_file(), (
            f"expected on-disk file {disk_name!r} for .toc entry {line!r} "
            "(FORMAT.md: .toc uses ` N`, disk uses `.N`)"
        )


# --------------------------------------------------------------------------
# 9. Raw-kind allowlist: every unparsed kind the golden inputs actually
#    produce must be a documented, deliberate entry in raw_kinds_allowlist.
# --------------------------------------------------------------------------


def test_unparsed_kinds_within_allowlist(expand_root, expand_cache):
    allowlist = _load_allowlist()
    result = census(expand_root)
    assert result.tree_count == len(expand_cache)
    assert result.load_errors == []

    unexpected = set(result.unparsed_kinds()) - allowlist
    assert not unexpected, (
        f"unparsed kind(s) not in {RAW_KINDS_ALLOWLIST.name}: {sorted(unexpected)} "
        "— new file kind (document in toeexpand/FORMAT.md + add a tocdir "
        "parser, or add to the allowlist deliberately)"
    )
