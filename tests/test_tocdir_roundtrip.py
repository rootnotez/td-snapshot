"""Bit-exact round-trip tests for the tocdir parser/encoder.

Spec: parse(bytes) → model → emit(model) must produce the exact same bytes,
for every kind we claim to support. Failures here either indicate a parser
bug or surface a deviation that needs to be recorded in
`toeexpand/DEVIATIONS.md`.

Run from the repo root:
    uvx pytest tests/test_tocdir_roundtrip.py -v
"""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "src"))

from tocdir import (  # noqa: E402
    Project,
    build,
    chop,
    cparm,
    data,
    fifo,
    hold,
    joystick,
    lod,
    logic,
    midiin,
    mousein,
    n,
    network,
    panel,
    parm,
    renderpick,
    script,
    table,
    text,
    timestamp,
    toc,
    ts,
)

CORPUS_ROOTS = [
    REPO / "tox" / "td_snapshot.tox.dir",
]

# Committed baseline fixtures for kinds that aren't represented in the main corpus.
KIND_FIXTURES = REPO / "tests" / "baselines" / "toeexpand_kinds"


def _fixture_paths(kind: str) -> list[Path]:
    """Return all files under tests/baselines/toeexpand_kinds/<kind>/*.<kind>."""
    d = KIND_FIXTURES / kind
    if not d.exists():
        return []
    return sorted(d.glob(f"*.{kind}"))


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
    sample = REPO / "tox" / "td_snapshot.tox.dir" / "td_snapshot.n"
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
    if not sample.exists():
        # TODO: repoint at a committed .parm fixture with custom pages and
        # expressions (tests/toolchain/fixtures/*/features.tox provides both).
        pytest.skip("classifier.parm sample corpus not present")
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


# --- Binary kinds (preamble-based) ---


def _roundtrip_all(paths: list[Path], parse_fn) -> list[Path]:
    failures: list[Path] = []
    for p in paths:
        raw = p.read_bytes()
        if parse_fn(raw).emit() != raw:
            failures.append(p)
    return failures


def test_text_roundtrip_corpus():
    found = _suffix_paths(".text") + _fixture_paths("text")
    assert found
    failures = _roundtrip_all(found, text.Text.parse)
    assert not failures, f"{len(failures)}/{len(found)} .text files failed"


def test_text_body_length_accessor():
    sample = REPO / "tox" / "td_snapshot.tox.dir" / "td_snapshot" / "core.text"
    if not sample.exists():
        return
    parsed = text.Text.parse(sample.read_bytes())
    assert parsed.version == 2
    assert parsed.body_length == len(parsed.body)


def test_table_roundtrip_corpus():
    found = _suffix_paths(".table") + _fixture_paths("table")
    assert found
    failures = _roundtrip_all(found, table.Table.parse)
    assert not failures, f"{len(failures)}/{len(found)} .table files failed"


def test_table_dimensions_accessor():
    # Old corpus-specific test; skip if classifier project not available
    sample = (
        REPO / "toeexpand" / "2026-05-17__datlab-classified-v1" / "v1"
        / "classifier.tox.dir" / "classifier" / "stats_table.table"
    )
    if not sample.exists():
        # Skip visibly: a bare return here reported PASS with nothing checked.
        pytest.skip(f"corpus sample not present: {sample}")
    parsed = table.Table.parse(sample.read_bytes())
    assert parsed.version == 1
    # stats_table is 2 rows x 9 columns: a header row of 9 labels (status,
    # num_samples, ...) and one row of values. Preamble (1, 2, 9, 0). The
    # earlier comment said "2-column x 9-row", read through the swapped
    # accessors; decoded on 2026-09-27 (build 2025.33230 toeexpand).
    assert parsed.preamble.fields == (1, 2, 9, 0)
    assert parsed.row_count == 2
    assert parsed.column_count == 9


def test_table_row_col_order_tabledemo():
    # Pins the preamble row/col order using tests/toolchain/gen/features.py's
    # tableDemo fixture: a new tableDAT (1 empty row) + appendRows of 4 rows
    # x 3 columns = 5 rows x 3 columns, 15 cells total.
    #
    # Verified 2026-09-27 against build 2025.33230: FORMAT.md and this
    # module previously documented u32[1]/u32[2] as column_count/row_count;
    # measurement on this fixture (and several shipped-corpus tables with
    # distinct row/col counts, e.g. an 18-row x 4-col colDefine.table and a
    # 1-row x 8-col currentTracks.table) shows the opposite — u32[1] is
    # row_count, u32[2] is column_count.
    sample = (
        REPO / "tests" / "baselines" / "toeexpand_kinds" / "table"
        / "features_2025.33230_tableDemo.table"
    )
    assert sample.exists(), f"missing fixture: {sample}"
    parsed = table.Table.parse(sample.read_bytes())
    assert parsed.version == 1
    assert parsed.preamble.fields == (1, 5, 3, 0)
    assert parsed.row_count == 5
    assert parsed.column_count == 3

    cells = _decode_table_cells(parsed.body)
    assert len(cells) == parsed.row_count * parsed.column_count == 15
    rows = [cells[i:i + parsed.column_count] for i in range(0, len(cells), parsed.column_count)]
    assert rows == [
        ["", "", ""],
        ["col1", "col2", "col3"],
        ["a1", "", "c1"],
        ["", "b2", ""],
        ["a3", "b3", "c3"],
    ]

    # No trailing NUL terminator per cell: consecutive cell records are
    # tag+length+bytes with the next tag immediately following.
    import struct
    pos = 0
    for cell in cells:
        tag = struct.unpack_from(">I", parsed.body, pos)[0]
        assert tag == 2
        length = struct.unpack_from(">I", parsed.body, pos + 4)[0]
        assert length == len(cell.encode("utf-8"))
        pos += 8 + length
    assert pos == len(parsed.body)


def _decode_table_cells(body: bytes) -> list:
    import struct
    cells = []
    pos = 0
    while pos < len(body):
        tag = struct.unpack_from(">I", body, pos)[0]
        assert tag == 2
        length = struct.unpack_from(">I", body, pos + 4)[0]
        pos += 8
        cells.append(body[pos:pos + length].decode("utf-8"))
        pos += length
    return cells


def test_fifo_roundtrip_fixtures():
    found = _suffix_paths(".fifo") + _fixture_paths("fifo")
    if not found:
        return
    failures = _roundtrip_all(found, fifo.Fifo.parse)
    assert not failures, f"{len(failures)}/{len(found)} .fifo files failed"


def test_renderpick_roundtrip_fixtures():
    found = _suffix_paths(".renderpick") + _fixture_paths("renderpick")
    if not found:
        return
    failures = _roundtrip_all(found, renderpick.Renderpick.parse)
    assert not failures, f"{len(failures)}/{len(found)} .renderpick files failed"


def test_data_roundtrip_fixtures():
    found = _suffix_paths(".data") + _fixture_paths("data")
    if not found:
        return
    failures = _roundtrip_all(found, data.Data.parse)
    assert not failures, f"{len(failures)}/{len(found)} .data files failed"


def test_lod_roundtrip_fixtures():
    found = _suffix_paths(".lod") + _fixture_paths("lod")
    if not found:
        return
    failures = _roundtrip_all(found, lod.Lod.parse)
    assert not failures, f"{len(failures)}/{len(found)} .lod files failed"


def test_lod_files_accessor():
    sample = KIND_FIXTURES / "lod" / "midi.lod"
    if not sample.exists():
        return
    parsed = lod.Lod.parse(sample.read_bytes())
    files = parsed.files()
    paths = [p for p, _ in files]
    assert ".build" in paths
    # midi.lod has nested template/ and template/mapmaster1/ subdirs.
    assert any(p.startswith("template/") for p in paths)


def test_timestamp_roundtrip_fixtures():
    found = _fixture_paths("timestamp")
    if not found:
        return
    failures = _roundtrip_all(found, timestamp.Timestamp.parse)
    assert not failures


# --- Brace-block CHOP-style kinds ---


def test_script_roundtrip_corpus():
    found = _suffix_paths(".script") + _fixture_paths("script")
    if not found:
        return
    failures = _roundtrip_all(found, script.Script.parse)
    assert not failures, f"{len(failures)}/{len(found)} .script files failed"


def test_ts_roundtrip_fixtures():
    found = _suffix_paths(".ts") + _fixture_paths("ts")
    if not found:
        return
    failures = _roundtrip_all(found, ts.Ts.parse)
    assert not failures


def test_chop_roundtrip_fixtures():
    found = _suffix_paths(".chop") + _fixture_paths("chop")
    if not found:
        return
    failures = _roundtrip_all(found, chop.Chop.parse)
    assert not failures


def test_logic_roundtrip_fixtures():
    found = _fixture_paths("logic")
    if not found:
        return
    failures = _roundtrip_all(found, logic.Logic.parse)
    assert not failures


def test_hold_roundtrip_fixtures():
    found = _fixture_paths("hold")
    if not found:
        return
    failures = _roundtrip_all(found, hold.Hold.parse)
    assert not failures


def test_midiin_roundtrip_fixtures():
    found = _fixture_paths("midiin")
    if not found:
        return
    failures = _roundtrip_all(found, midiin.Midiin.parse)
    assert not failures


def test_mousein_roundtrip_fixtures():
    found = _fixture_paths("mousein")
    if not found:
        return
    failures = _roundtrip_all(found, mousein.Mousein.parse)
    assert not failures


def test_joystick_roundtrip_fixtures():
    found = _fixture_paths("joystick")
    if not found:
        return
    failures = _roundtrip_all(found, joystick.Joystick.parse)
    assert not failures


# --- Whole-tree Project facade ---


def test_project_roundtrip_corpus(tmp_path):
    roots = [r for r in CORPUS_ROOTS if r.exists()]
    assert roots, "no tracked-corpus .dir/ trees found"
    for root in roots:
        project = Project.from_dir(root)

        # In-memory verify: every entry's emit() equals the source bytes.
        mismatches = project.verify(root)
        assert not mismatches, f"{root.name}: in-memory verify failed: {mismatches[:5]}"

        # Round-trip through disk: write to a fresh location, diff every file.
        out_dir = tmp_path / root.name
        project.to_dir(out_dir)
        for rel in project.toc.paths:
            src = (root / rel).read_bytes()
            dst = (out_dir / rel).read_bytes()
            assert src == dst, f"{root.name}: {rel} differs after to_dir()"
        src_toc = (root.parent / (root.name[:-len(".dir")] + ".toc")).read_bytes()
        dst_toc = (out_dir.parent / (out_dir.name[:-len(".dir")] + ".toc")).read_bytes()
        assert src_toc == dst_toc, f"{root.name}: .toc differs after to_dir()"


def test_project_entries_match_toc_order():
    root = REPO / "tox" / "td_snapshot.tox.dir"
    if not root.exists():
        return
    project = Project.from_dir(root)
    assert list(project.entries.keys()) == project.toc.paths
