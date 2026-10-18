"""Tests for the dat-templates/ record and core.py's matching (no TouchDesigner needed).

Run from the repo root:
    uvx pytest tests/test_dat_templates.py -v
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import core  # noqa: E402
import dat_templates  # noqa: E402

RECORDS = sorted((REPO / "dat-templates").glob("*.json"))


def test_records_exist():
    assert RECORDS, "no dat-templates/<build>.json record"


def test_hash_matches_between_capture_and_core():
    text = 'def onStart():\r\n\treturn\r\n'
    assert core._dat_template_hash(text) == dat_templates.text_hash(text)[:16]
    assert core._dat_template_hash(text) == core._dat_template_hash(text.replace('\r\n', '\n'))


def test_core_table_is_current():
    assert dat_templates._current_block(core_src()).group(0) == dat_templates.core_block(), \
        "run: uv run --no-project python scripts/dat_templates.py gen-core"


@pytest.mark.parametrize("record", RECORDS, ids=lambda p: p.stem)
def test_every_recorded_template_is_matched(record):
    for t in json.loads(record.read_text())["templates"]:
        label = core._DAT_TEMPLATES.get(core._dat_template_hash(t["text"]))
        assert label is not None, (t["op_type"], t["role"])
        assert dat_templates.label(t["op_type"], t["role"]) in label.split(" or ")


def test_edited_template_is_not_matched():
    record = json.loads(RECORDS[-1].read_text())
    text = next(t["text"] for t in record["templates"] if t["op_type"] == "executeDAT")
    assert core._dat_template_hash(text + "\n# edited") not in core._DAT_TEMPLATES


def test_template_renders_as_one_line():
    nodes = [{"path": "/p", "label": "/p [Execute DAT]", "input_slots": [], "outputs": [],
              "pars": [], "refs": [], "dat_text": {"template": "executeDAT", "full_len": 940}}]
    out = core.render_blocks(nodes, set(), set(), {"/p": None}).splitlines()
    assert out[-1] == "  dat_text: (unchanged executeDAT template, 940 chars)"


def core_src():
    return (REPO / "src" / "core.py").read_text()
