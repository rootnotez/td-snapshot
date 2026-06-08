"""Smoke tests for the tocdir census walker.

Uses the canonical `tox/td_snapshot.tox.dir` expansion, which is always
present in the repo, so the walker is guarded without needing the full
shipped corpus (that is regenerable via scripts/build-corpus.sh and
gitignored).

Run from the worktree root:
    uv run --no-project pytest tests/test_tocdir_census.py -v
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "src"))

from tocdir.census import census, census_json, find_trees, render_census  # noqa: E402

TOX = REPO / "tox"


def test_find_trees_locates_the_snapshot_tree():
    trees = find_trees(TOX)
    assert any(t.name == "td_snapshot.tox.dir" for t in trees), trees


def test_census_counts_known_kinds_and_types():
    c = census(TOX)
    assert c.tree_count == 1
    # The snapshot tree carries these kinds; all are parsed (none raw).
    assert c.kind_counts["n"] > 0
    assert c.kind_counts["parm"] > 0
    assert c.kind_counts["text"] > 0
    assert c.unparsed_kinds() == []
    # The two Execute-DAT families that drive the Copy/Inspect buttons.
    assert "DAT:panelexec" in c.type_counts
    assert "DAT:parexec" in c.type_counts


def test_census_clean_roundtrip_on_canonical_tree():
    c = census(TOX)
    assert c.roundtrip_fail == []
    assert c.load_errors == []


def test_render_and_json_smoke():
    c = census(TOX)
    assert "tocdir census" in render_census(c)
    j = census_json(c)
    assert j["tree_count"] == 1
    assert "DAT:panelexec" in j["operator_types"]
