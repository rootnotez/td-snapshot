"""Tests for `python -m tocdir textconv`.

textconv renders a tocdir `.text`/`.table` file as readable text for git's
`diff.<driver>.textconv`. It must never raise or hide a diff — anything it
can't confidently parse is written through unchanged.

Run from the worktree root:
    uv run --no-project pytest tests/test_tocdir_textconv.py -v
"""

import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SRC = REPO / "src"
sys.path.insert(0, str(SRC))

from tocdir.__main__ import _textconv_table, _textconv_text  # noqa: E402

TOX = REPO / "tox" / "td_snapshot.tox.dir"
TABLE_FIXTURE = (
    REPO / "tests" / "baselines" / "toeexpand_kinds" / "table" / "features_2025.33230_tableDemo.table"
)


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tocdir", *args],
        cwd=REPO,
        env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
        capture_output=True,
    )


# ---- .text ----


def test_textconv_text_renders_dat_body():
    core_text = TOX / "td_snapshot" / "core.text"
    assert core_text.exists(), "canonical tox/ expansion missing core.text"
    out = _textconv_text(core_text.read_bytes())
    assert out.startswith(b"# core.py v"), out[:80]
    assert b"\x00" not in out


def test_textconv_text_short_form_stub_has_no_body():
    # 19-byte short-form stub: "2\n" + "*" + 4 u32 sentinels, no body field.
    raw = b"2\n" + b"*" + struct.pack(">4I", 1, 1, 1, 1)
    assert len(raw) == 19
    assert _textconv_text(raw) == b""


def test_textconv_cli_text_matches_direct_call():
    core_text = TOX / "td_snapshot" / "core.text"
    result = _run_cli("textconv", str(core_text))
    assert result.returncode == 0, result.stderr
    assert result.stdout == _textconv_text(core_text.read_bytes())


# ---- .table ----


def test_textconv_table_renders_expected_grid():
    out = _textconv_table(TABLE_FIXTURE.read_bytes())
    rows = out.decode("utf-8").splitlines()
    assert rows == [
        "\t\t",
        "col1\tcol2\tcol3",
        "a1\t\tc1",
        "\tb2\t",
        "a3\tb3\tc3",
    ]


def test_textconv_table_cell_count_mismatch_falls_back_to_one_per_line():
    # 2 rows x 2 cols declared, but only 3 cells present in the stream.
    preamble = struct.pack(">4I", 1, 2, 2, 0)

    def cell(s: bytes) -> bytes:
        return struct.pack(">II", 2, len(s)) + s

    body = cell(b"a") + cell(b"b") + cell(b"c")
    raw = b"1\n" + b"*" + preamble + body
    out = _textconv_table(raw).decode("utf-8").splitlines()
    assert out == ["a", "b", "c"]


def test_textconv_cli_table_matches_direct_call():
    result = _run_cli("textconv", str(TABLE_FIXTURE))
    assert result.returncode == 0, result.stderr
    assert result.stdout == _textconv_table(TABLE_FIXTURE.read_bytes())


# ---- fallback behavior ----


def test_textconv_non_tocdir_file_passthrough(tmp_path):
    p = tmp_path / "plain.txt"
    p.write_text("hello world\n")
    result = _run_cli("textconv", str(p))
    assert result.returncode == 0, result.stderr
    assert result.stdout == b"hello world\n"


def test_textconv_malformed_table_falls_back_to_raw_bytes(tmp_path):
    p = tmp_path / "bad.table"
    raw = b"1\n*garbagebytes"
    p.write_bytes(raw)
    result = _run_cli("textconv", str(p))
    assert result.returncode == 0, result.stderr
    assert result.stdout == raw


def test_textconv_malformed_text_falls_back_to_raw_bytes(tmp_path):
    # Too short to even contain a newline for the version line -> Text.parse
    # raises ValueError; textconv must still emit something rather than crash.
    p = tmp_path / "bad.text"
    raw = b"not-a-valid-text-file"
    p.write_bytes(raw)
    result = _run_cli("textconv", str(p))
    assert result.returncode == 0, result.stderr
    assert result.stdout == raw


def test_textconv_missing_file_reports_error():
    result = _run_cli("textconv", "/nonexistent/path/does-not-exist.text")
    assert result.returncode == 2
    assert b"textconv" in result.stderr
