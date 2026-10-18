"""Tests for core.py's render_blocks parameter, flag, comment, dat_text and
wire rendering (no TouchDesigner needed).

These enforce the project rule that every changed parameter's value, default,
mode and expression/bind text appears in the output. Node dicts are built by
hand in the shape walk_patch produces (BIND text travels in the 'expr' key).

Run from the repo root:
    uvx pytest tests/test_core_render_pars.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import render_blocks, _fmt_flags, _fmt_dat_text_block, _fmt_comment_block  # noqa: E402


def par(name, current, default, mode="CONSTANT", expr=None):
    return {"name": name, "current": current, "default": default, "mode": mode, "expr": expr}


def node(path, typ, pars=(), **extra):
    n = {"path": path, "label": "{} [{}]".format(path, typ), "input_slots": [], "outputs": [],
         "pars": list(pars), "refs": []}
    n.update(extra)
    return n


def render(*nodes, wires=(), refs=()):
    return render_blocks(list(nodes), set(wires), set(refs), {}).split("\n")


def test_non_default_par_shows_value_and_default():
    out = render(node("/p", "Container COMP"), node("/p/blur1", "Blur TOP", [par("size", 5.0, 1.0)]))
    assert "  size = 5.0 (default 1.0)" in out


def test_string_values_are_quoted():
    out = render(node("/p", "Container COMP", [par("file", "a.png", "")]))
    assert "  file = 'a.png' (default '')" in out


def test_expression_par_shows_mode_and_expression_text():
    out = render(node("/p", "Container COMP", [par("tx", 0.5, 0.0, "EXPRESSION", "absTime.seconds % 1")]))
    assert "  tx = 0.5 (default 0.0, EXPRESSION, expr='absTime.seconds % 1')" in out


def test_export_par_shows_mode_even_when_value_equals_default():
    out = render(node("/p", "Container COMP", [par("tx", 0.0, 0.0, "EXPORT")]))
    assert "  tx = 0.0 (default 0.0, EXPORT)" in out


def test_bind_par_shows_mode_and_bind_text_even_when_value_equals_default():
    out = render(node("/p", "Container COMP", [par("tx", 0.0, 0.0, "BIND", "op('ctl').par.x")]))
    assert "  tx = 0.0 (default 0.0, BIND, expr=\"op('ctl').par.x\")" in out


def test_constant_mode_is_not_spelled_out():
    out = render(node("/p", "Container COMP", [par("tx", 1, 0)]))
    assert not any("CONSTANT" in line for line in out)


def test_flags_line_only_when_present_and_sorted():
    out = render(node("/p", "Container COMP"),
                 node("/p/a", "Noise TOP", flags={"viewer": True, "bypass": True}),
                 node("/p/b", "Noise TOP"))
    assert "  flags: bypass=True, viewer=True" in out
    assert sum(line.startswith("  flags:") for line in out) == 1


def test_fmt_flags_diverged_off_values():
    assert _fmt_flags({"render": False, "display": False}) == "display=False, render=False"


def test_dat_text_block_indented():
    out = render(node("/p", "Container COMP"),
                 node("/p/t", "Text DAT", dat_text={"text": "a\nb", "truncated": False, "full_len": 3}))
    i = out.index("  dat_text:")
    assert out[i + 1:i + 3] == ["    a", "    b"]
    assert not any("truncated" in line for line in out)


def test_dat_text_truncation_suffix():
    lines = _fmt_dat_text_block({"text": "abc", "truncated": True, "full_len": 9999})
    assert lines == ["    abc", "    (truncated, 9999 chars total)"]
    out = render(node("/p/t", "Text DAT", dat_text={"text": "abc", "truncated": True, "full_len": 9999}))
    assert out[-1] == "    (truncated, 9999 chars total)"


def test_single_line_comment():
    assert _fmt_comment_block("hello there") == ["  comment: hello there"]
    out = render(node("/p", "Container COMP", comment="hello there"))
    assert "  comment: hello there" in out


def test_multi_line_comment_block():
    assert _fmt_comment_block("one\ntwo") == ["  comment:", "    one", "    two"]
    out = render(node("/p", "Container COMP", comment="one\ntwo"))
    i = out.index("  comment:")
    assert out[i + 1:i + 3] == ["    one", "    two"]


def test_wires_and_out_index_only_when_nonzero():
    out = render(node("/p", "Container COMP"), node("/p/a", "Noise TOP"), node("/p/b", "Blur TOP"),
                 wires=[("/p/a", "/p/b", 0, 0), ("/p/a", "/p/b", 1, None), ("/p/a", "/p/b", 2, 3)])
    assert "  in[0] <- a" in out
    assert "  in[1] <- a" in out
    assert "  in[2] <- a [out:3]" in out
    assert not any("[out:0]" in line for line in out)


def test_ref_line():
    out = render(node("/p", "Container COMP"), node("/p/a", "Noise TOP"), node("/p/b", "Blur TOP"),
                 refs=[("/p/b", "/p/a", "top")])
    assert "  ref top -> a" in out


def test_block_line_order():
    out = render(node("/p", "Container COMP"),
                 node("/p/a", "Noise TOP"),
                 node("/p/b", "Blur TOP", [par("size", 5, 1)], comment="c", flags={"bypass": True},
                      storage=[("k", "1")], dat_text={"text": "x", "truncated": False, "full_len": 1}),
                 wires=[("/p/a", "/p/b", 0, None)], refs=[("/p/b", "/p/a", "top")])
    i = out.index("b [Blur TOP]")
    assert out[i + 1:i + 8] == ["  comment: c", "  flags: bypass=True", "  storage k = 1",
                                "  size = 5 (default 1)", "  in[0] <- a", "  ref top -> a", "  dat_text:"]
