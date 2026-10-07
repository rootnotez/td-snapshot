"""Tests for core.py's storage summaries (`storage key = value` lines).

Pure functions, so no TouchDesigner is needed: the TD types they special-case
(OPs, tdu.Dependency) are stood in for by small classes with the same shape.

Run from the repo root:
    uvx pytest tests/test_core_storage.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import core  # noqa: E402
from core import _storage_summary as summary  # noqa: E402


class Dependency:
    def __init__(self, val):
        self.val = val


class FakeOP:
    OPType = "baseCOMP"

    def __init__(self, path):
        self.path = path


class Opaque:
    pass


def test_scalars():
    assert summary("abc") == "'abc'"
    assert summary(3) == "3"
    assert summary(None) == "None"


def test_td_built_by_stamp():
    stamp = {"script": "td/build.py", "git": "abc1234", "path": "/project1/geo",
             "fingerprint": "46baab5cc4b1", "children": {"gen1": "x", "gen2": "y"}}
    assert summary(stamp) == ("{children: {2 items}, fingerprint: '46baab5cc4b1', "
                              "git: 'abc1234', path: '/project1/geo', script: 'td/build.py'}")


def test_dependency_and_op_values():
    assert summary(Dependency(Dependency(5))) == "5"
    assert summary(FakeOP("/project1/timer1")) == "op('/project1/timer1')"
    assert summary({"d": Dependency([1, 2])}) == "{d: [2 items]}"


def test_sequences():
    assert summary([1, 2]) == "[1, 2]"
    assert summary({3, 1, 2}) == "[1, 2, 3]"
    assert summary([1, [2]]) == "[2 items]"
    assert summary({"one": {"k": 1}}) == "{one: {1 item}}"


def test_addresses_removed():
    assert " at 0x" not in summary(Opaque())
    assert summary(Opaque()) == summary(Opaque())


def test_long_values_cut():
    item = summary("x" * 500)
    assert item.endswith("…") and len(item) == core.STORAGE_ITEM_MAX + 1
    line = summary({"k%03d" % i: i for i in range(200)})
    assert line.endswith("chars)") and line.startswith("{k000: 0, k001: 1")
