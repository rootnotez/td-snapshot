"""Tests for core.py's render_blocks naming (no TouchDesigner needed).

Operators are named by their path relative to the root (the first block);
the root and anything outside it keep absolute paths; an op() in an
expression that resolved to nothing is shown as <unresolved X>.

Run from the repo root:
    uvx pytest tests/test_core_render.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import render_blocks  # noqa: E402


def node(path, typ, pars=()):
    return {"path": path, "label": "{} [{}]".format(path, typ), "input_slots": [], "outputs": [],
            "pars": list(pars), "refs": []}


def render(extra=()):
    nodes = [node("/project1", "Container COMP"),
             node("/project1/noise1", "Noise TOP"),
             *extra,
             node("/project1/geo/blur1", "Blur TOP",
                  [{"name": "size", "current": 5.0, "default": 1.0, "mode": "CONSTANT", "expr": None}])]
    wires = {("/project1/noise1", "/project1/geo/blur1", 0, None),
             ("/project1/noise1", "/project1/geo/blur1", 1, 2)}
    refs = {("/project1/geo/blur1", "/project1", "top"),
            ("/project1/geo/blur1", "/local/time", "chop"),
            ("/project1/geo/blur1", "text/stroke", "dat"),
            ("/project1/noise1", "/project1/geo/blur1", "top")}
    return render_blocks(nodes, wires, refs, {}).split("\n")


def test_names_are_root_relative():
    out = render()
    assert "/project1 [Container COMP]" in out
    assert "noise1 [Noise TOP]" in out
    assert "geo/blur1 [Blur TOP]" in out
    assert "  in[0] <- noise1" in out
    assert "  in[1] <- noise1 [out:2]" in out
    assert "  ref top -> geo/blur1" in out


def test_root_outside_and_unresolved_targets():
    out = render()
    assert "  ref top -> /project1" in out
    assert "  ref chop -> /local/time" in out
    assert "  ref dat -> <unresolved text/stroke>" in out
    assert not any(line.startswith("n") and " = " in line for line in out), "no positional ids"


def test_adding_an_operator_changes_only_its_own_block():
    before, after = render(), render([node("/project1/lfo1", "LFO CHOP")])
    added = [line for line in after if line not in before]
    assert added == ["lfo1 [LFO CHOP]", ""] or added == ["lfo1 [LFO CHOP]"]
    assert [line for line in before if line not in after] == []
