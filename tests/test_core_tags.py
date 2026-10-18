"""Tests for the `tags:` line in core.py's render_blocks (no TouchDesigner needed).

Run from the repo root:
    uvx pytest tests/test_core_tags.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import render_blocks  # noqa: E402


def render(**extra):
    n = {"path": "/p", "label": "/p [Container COMP]", "input_slots": [], "outputs": [],
         "pars": [], "refs": [], **extra}
    return render_blocks([n], set(), set(), {}).splitlines()


def tag_lines(lines):
    return [l for l in lines if l.startswith("  tags:")]


def test_absent_or_empty_emits_nothing():
    assert tag_lines(render()) == []
    assert tag_lines(render(tags=[])) == []


def test_tags_are_listed_in_given_order_after_comment():
    lines = render(comment="hi", tags=["a", "b"], flags={"bypass": True})
    assert lines.index("  tags: a, b") == lines.index("  comment: hi") + 1
    assert lines.index("  tags: a, b") < lines.index("  flags: bypass=True")


def test_tricky_characters_are_quoted():
    lines = render(tags=["a,b", "effect", "image filter", "it's"])
    assert tag_lines(lines) == ["  tags: 'a,b', effect, 'image filter', \"it's\""]
