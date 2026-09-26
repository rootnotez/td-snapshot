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


def test_census_build_versions():
    c = census(TOX)
    # tox/td_snapshot.tox.dir/.build records `version 099`.
    assert c.build_versions["099"] > 0
    assert len(c.build_numbers) > 0
    j = census_json(c)
    assert j["build_versions"]["099"] > 0
    assert j["build_numbers"]


def test_census_n_vocab_nonempty():
    c = census(TOX)
    # Every `.n` has a `tile` line and (for COMPs) a `flags = ` line.
    assert c.n_line_keywords["tile"] > 0
    assert c.n_line_keywords["flags"] > 0
    assert len(c.n_flag_tokens) > 0
    j = census_json(c)
    assert j["n_vocab"]["line_keywords"]["tile"] > 0
    assert j["n_vocab"]["flag_tokens"]


def test_census_parm_and_cparm_vocab_nonempty():
    c = census(TOX)
    assert len(c.parm_modes) > 0
    assert len(c.parm_row_shapes) > 0
    j = census_json(c)
    assert j["parm_vocab"]["modes"]
    assert j["parm_vocab"]["row_shapes"]
    # cparm_vocab is present even if the snapshot tree has no .cparm files.
    assert "row_shapes" in j["cparm_vocab"]


def test_census_type_pars_known_operator():
    c = census(TOX)
    assert "DAT:panelexec" in c.type_pars
    # `panelexec1.parm` in the snapshot tree carries these par names.
    assert {"file", "language", "loadonstart"} <= c.type_pars["DAT:panelexec"]
    j = census_json(c)
    assert j["type_pars"]["DAT:panelexec"] == sorted(j["type_pars"]["DAT:panelexec"])
    assert "file" in j["type_pars"]["DAT:panelexec"]


def test_census_toc_headers():
    c = census(TOX)
    # `.tox.toc` always carries the `# 4 0 0 0 1`-shaped header.
    assert any(hdr.startswith("# ") for hdr in c.toc_headers if hdr != "<none>")
    j = census_json(c)
    assert j["toc_headers"]
