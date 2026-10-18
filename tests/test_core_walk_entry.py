"""walk_patch must not require the ambient `me` when a root is passed (#19).

Run: uvx pytest tests/test_core_walk_entry.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import core  # noqa: E402


class FakeOp:
    OPType = "baseCOMP"
    label = "Base"
    family = "COMP"

    def __init__(self, path, parent=None):
        self.path = path
        self._parent = parent

    def pars(self):
        return []

    def parent(self):
        return self._parent

    def findChildren(self, **kw):
        return []


def test_root_given_without_me(monkeypatch):
    root = FakeOp("/r")
    monkeypatch.setattr(core, "op", lambda p: root, raising=False)
    monkeypatch.delattr(core, "me", raising=False)
    nodes, _, _, by_path = core.walk_patch("/r")
    assert list(by_path) == ["/r"]


def test_no_root_no_me_raises(monkeypatch):
    monkeypatch.delattr(core, "me", raising=False)
    with pytest.raises(ValueError, match="pass a root"):
        core.walk_patch()


def test_me_still_excluded(monkeypatch):
    root = FakeOp("/r")
    comp = FakeOp("/r/snap", root)
    dat = FakeOp("/r/snap/dat", comp)
    root.findChildren = lambda **kw: [comp, dat]
    comp.findChildren = lambda **kw: [dat]
    monkeypatch.setattr(core, "op", lambda p: root, raising=False)
    monkeypatch.setattr(core, "me", dat, raising=False)
    _, _, _, by_path = core.walk_patch("/r")
    assert list(by_path) == ["/r"]
