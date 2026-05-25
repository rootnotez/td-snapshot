"""Bit-exact round-trip tests for the toeexpand parser/encoder.

Spec: parse(bytes) → model → emit(model) must produce the exact same bytes,
for every kind we claim to support. Failures here either indicate a parser
bug or surface a deviation that needs to be recorded in
`toeexpand/DEVIATIONS.md`.

Run from the worktree root:
    uv run --no-project pytest tests/test_toeexpand_roundtrip.py -v
or just:
    python -m pytest tests/test_toeexpand_roundtrip.py -v
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "src"))

from toeexpand import build, cparm, n, network, panel, parm, toc  # noqa: E402

CORPUS_ROOTS = [
    REPO / "toeexpand" / "2026-05-18_td_snapshot.tox.dir",
    REPO / "toeexpand" / "2026-05-17__datlab-classified-v1" / "v1" / "classifier.tox.dir",
    REPO / "toeexpand" / "2026-05-17__datlab-classified-v1" / "v1" / "convert_pca.tox.dir",
]


def _toc_paths() -> list[Path]:
    paths: list[Path] = []
    for root in CORPUS_ROOTS:
        if not root.exists():
            continue
        # The .toc sits next to (not inside) the .dir/, so derive its path.
        toc_path = root.with_suffix(root.suffix + ".toc") if root.suffix else None
        # Actually toeexpand produces <name>.tox.dir + <name>.tox.toc; .dir is part of the stem.
        sibling = root.parent / (root.name.removesuffix(".dir") + ".toc")
        if sibling.exists():
            paths.append(sibling)
    return paths


def _build_paths() -> list[Path]:
    paths: list[Path] = []
    for root in CORPUS_ROOTS:
        candidate = root / ".build"
        if candidate.exists():
            paths.append(candidate)
    return paths


def test_toc_roundtrip_corpus():
    found = _toc_paths()
    assert found, "no .toc corpus files found — expected at least one under toeexpand/"
    for p in found:
        raw = p.read_bytes()
        parsed = toc.Toc.parse(raw)
        emitted = parsed.emit()
        assert emitted == raw, f"bit-exact round-trip failed for {p}"


def test_build_roundtrip_corpus():
    found = _build_paths()
    assert found, "no .build corpus files found"
    for p in found:
        raw = p.read_bytes()
        parsed = build.Build.parse(raw)
        emitted = parsed.emit()
        assert emitted == raw, f"bit-exact round-trip failed for {p}"


def test_build_version_accessor():
    found = _build_paths()
    assert found
    parsed = build.Build.parse(found[0].read_bytes())
    assert parsed.version is not None
    assert parsed.build_number is not None


def _n_paths() -> list[Path]:
    paths: list[Path] = []
    for root in CORPUS_ROOTS:
        if not root.exists():
            continue
        paths.extend(root.rglob("*.n"))
    return paths


def test_n_roundtrip_corpus():
    found = _n_paths()
    assert found, "no .n corpus files found"
    failures: list[tuple[Path, bytes, bytes]] = []
    for p in found:
        raw = p.read_bytes()
        parsed = n.N.parse(raw)
        emitted = parsed.emit()
        if emitted != raw:
            failures.append((p, raw, emitted))
    assert not failures, (
        f"{len(failures)}/{len(found)} .n files failed bit-exact round-trip; "
        f"first failure: {failures[0][0]}"
    )


def test_n_family_accessor():
    """Spot-check a known sample so the accessor logic isn't silently empty."""
    sample = REPO / "toeexpand" / "2026-05-18_td_snapshot.tox.dir" / "td_snapshot.n"
    parsed = n.N.parse(sample.read_bytes())
    assert parsed.family == "COMP"
    assert parsed.type == "container"
    assert "viewer" in parsed.flag_tokens()


def _parm_paths() -> list[Path]:
    paths: list[Path] = []
    for root in CORPUS_ROOTS:
        if not root.exists():
            continue
        paths.extend(root.rglob("*.parm"))
    return paths


def test_parm_roundtrip_corpus():
    found = _parm_paths()
    assert found, "no .parm corpus files found"
    failures: list[Path] = []
    for p in found:
        raw = p.read_bytes()
        parsed = parm.Parm.parse(raw)
        emitted = parsed.emit()
        if emitted != raw:
            failures.append(p)
    assert not failures, f"{len(failures)}/{len(found)} .parm files failed bit-exact"


def _suffix_paths(suffix: str) -> list[Path]:
    paths: list[Path] = []
    for root in CORPUS_ROOTS:
        if not root.exists():
            continue
        paths.extend(root.rglob(f"*{suffix}"))
    return paths


def test_panel_roundtrip_corpus():
    found = _suffix_paths(".panel")
    assert found, "no .panel corpus files found"
    failures: list[Path] = []
    for p in found:
        raw = p.read_bytes()
        emitted = panel.Panel.parse(raw).emit()
        if emitted != raw:
            failures.append(p)
    assert not failures, f"{len(failures)}/{len(found)} .panel files failed"


def test_network_roundtrip_corpus():
    found = _suffix_paths(".network")
    if not found:
        return  # not every corpus has .network files
    failures: list[Path] = []
    for p in found:
        raw = p.read_bytes()
        emitted = network.Network.parse(raw).emit()
        if emitted != raw:
            failures.append(p)
    assert not failures, f"{len(failures)}/{len(found)} .network files failed"


def test_network_compinputs_accessor():
    sample = (
        REPO / "toeexpand" / "2026-05-17__datlab-classified-v1" / "v1"
        / "classifier.tox.dir" / "classifier.network"
    )
    if not sample.exists():
        return
    parsed = network.Network.parse(sample.read_bytes())
    inputs = parsed.compinputs()
    assert len(inputs) == 2
    assert inputs[0].op_name == "in_record"
    assert inputs[0].family == "CHOP"


def test_cparm_roundtrip_corpus():
    found = _suffix_paths(".cparm")
    if not found:
        return
    failures: list[Path] = []
    for p in found:
        raw = p.read_bytes()
        emitted = cparm.Cparm.parse(raw).emit()
        if emitted != raw:
            failures.append(p)
    assert not failures, f"{len(failures)}/{len(found)} .cparm files failed"


def test_cparm_pages_accessor():
    sample = (
        REPO / "toeexpand" / "2026-05-17__datlab-classified-v1" / "v1"
        / "classifier.tox.dir" / "classifier.cparm"
    )
    if not sample.exists():
        return
    parsed = cparm.Cparm.parse(sample.read_bytes())
    pages = parsed.pages()
    assert "About" in pages
    assert "Record (in1)" in pages


def test_parm_accessor_smoke():
    """Spot-check a known sample: classifier.parm has mode-decoded fields."""
    sample = (
        REPO / "toeexpand" / "2026-05-17__datlab-classified-v1" / "v1"
        / "classifier.tox.dir" / "classifier.parm"
    )
    parsed = parm.Parm.parse(sample.read_bytes())
    page_markers = [r for r in parsed.rows if r.is_page_marker]
    assert page_markers, "expected at least one ? page marker"

    rows = parsed.parameter_rows()
    assert rows, "expected at least one parameter row"

    # pageindex 67108864 3 → custom-page mode, no expression
    pageindex = parsed.named("pageindex")
    assert pageindex is not None
    assert pageindex.mode == 67108864
    assert pageindex.is_custom_page
    assert not pageindex.has_expression

    # Emb0data 201326673 ... → OP-typed, has expression
    emb0data = parsed.named("Emb0data")
    assert emb0data is not None
    assert emb0data.mode == 201326673
    assert emb0data.is_op_typed
    assert emb0data.has_expression
