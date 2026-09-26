"""tests/toolchain/gen/features.py

Builds `tc_gen_features` (a Base COMP under /project1) exercising the
format features td-snapshot / tocdir depend on: parameter modes,
custom-parameter styles, wiring shapes, DAT bodies, flags, comments/tags,
nested/cloned/extended COMPs, an Annotate COMP, op storage, a
case-collision name probe, and node appearance. Saves `features.tox` +
`features.json` (build info plus per-feature applied/failed+error) to
OUT_DIR.

Runs INSIDE TouchDesigner via td-claude-bridge's /exec (see
tests/toolchain/gen/README.md). `OUT_DIR = r'<abs path>'` is prepended by
tests/toolchain/gen/run.sh; this script fails clearly if it is missing.

Unlike every_op.py, cooking is left ON here (the default) -- these
features are about parameter/flag/DAT *state*, and several of them
(export by channel name, the extension object) only make sense to inspect
once TD has actually resolved them at least once.

Every feature is its own try/except, recorded into report['features'][name]
as {"applied": bool, "error": str|None}. One feature failing (e.g. a guess
about an internal parameter name turning out wrong) never blocks the rest.
`custom_pars_page` additionally records a per-style breakdown under
`styles`, since it is one Base COMP holding ~13 independent parameter
styles and a single style failing (an unverified sub-par suffix, say)
should not hide the other twelve.
"""

import json
import os
import platform
from contextlib import contextmanager

try:
    OUT_DIR  # noqa: F821 -- must be injected by the runner, see module docstring
except NameError:
    raise RuntimeError(
        "OUT_DIR is not defined. tests/toolchain/gen/run.sh must prepend "
        "`OUT_DIR = r'<abs path>'` before sending this script to td.sh exec."
    )


def _tdglobal(name):
    """Resolve a TouchDesigner global that may be a real interpreter builtin
    or only reachable via `import td`. See every_op.py's `_tdglobal` for the
    full rationale (td-claude-bridge's /exec uses a fresh globals dict, so
    this matters). `ParMode` in particular could not be confirmed present in
    td-docs' introspection captures for this build (it shows up only inside
    other members' docstrings, e.g. Par_Class.md's `mode` example), so
    resolving it defensively -- rather than assuming either `ParMode` bare or
    `td.ParMode` -- is the point of this helper.
    """
    try:
        return eval(name)
    except NameError:
        import td
        return getattr(td, name)


op = _tdglobal("op")
app = _tdglobal("app")

os.makedirs(OUT_DIR, exist_ok=True)

ROOT_PATH = "/project1"
CONTAINER_NAME = "tc_gen_features"

root = op(ROOT_PATH)
if root is None:
    raise RuntimeError("features.py: %s does not exist" % ROOT_PATH)

stale = root.op(CONTAINER_NAME)
if stale is not None:
    stale.destroy()

container = root.create("baseCOMP", CONTAINER_NAME)

report = {
    "app_build": getattr(app, "build", None),
    "app_version": getattr(app, "version", None),
    "os": platform.platform(),
    "features": {},
}


@contextmanager
def feature(name):
    """Run one fixture-building feature; record applied/failed+error.

    Yields the report entry dict so a feature (e.g. custom_pars_page) can
    attach extra detail before the block finishes or raises.
    """
    entry = {"applied": False, "error": None}
    report["features"][name] = entry
    try:
        yield entry
        entry["applied"] = True
    except Exception as e:
        entry["applied"] = False
        entry["error"] = str(e)


try:
    # -- Parameter modes on built-in pars -----------------------------------

    with feature("par_mode_constant") as entry:
        # Noise CHOP's `seed` par (Noise_CHOP.md: "Seed `seed` - Any number
        # ... which starts the [random] sequence"); default is non-42, so
        # this is a real, non-default CONSTANT-mode change.
        o = container.create("noiseCHOP", "parModeConstant")
        o.par.seed.val = 42

    with feature("par_mode_expression") as entry:
        # Transform SOP's `tx` (Translate X, part of the `t` ParGroup;
        # Transform_SOP.md). Setting `.expr` also switches the par into
        # EXPRESSION mode (documented on Par_Class.md's `expr` member).
        o = container.create("transformSOP", "parModeExpression")
        o.par.tx.expr = "absTime.seconds"

    with feature("par_mode_bind") as entry:
        # `bindExpr` alone does NOT switch mode (Par_Class.md's `bindExpr`
        # doc has no "will also be placed in ... mode" sentence, unlike
        # `val` and `expr`) -- `mode` is set explicitly afterward.
        ParMode = _tdglobal("ParMode")
        src = container.create("transformSOP", "parModeBindSource")
        tgt = container.create("transformSOP", "parModeBind")
        tgt.par.ty.bindExpr = "op('parModeBindSource').par.ty"
        tgt.par.ty.mode = ParMode.BIND

    with feature("par_mode_export") as entry:
        # EXPORT set up via "Channel Name is Path:Parameter"
        # (CHOP_Export.md), fully scriptable without any drag-and-drop:
        # rename the channel to "<sibling path>:<par name>" using the
        # Common-page rename pars (documented generically on every CHOP,
        # e.g. Lag_CHOP.md's "Rename from `commonrenamefrom`" / "Rename to
        # `commonrenameto`"), point `exportmethod` at `autoname`, and flip
        # the CHOP-level `export` flag (CHOP_Class.md: "Get or set Export
        # Flag"). Export Root defaults to `parent()`, which is `container`
        # for both ops below, so the bare sibling name resolves.
        target = container.create("baseCOMP", "exportTarget")
        page = target.appendCustomPage("Demo")
        page.appendFloat("Value1")
        target.par.Value1.val = 0.0

        src = container.create("constantCHOP", "exportSource")
        src.par.commonrenamefrom.val = "*"
        src.par.commonrenameto.val = "exportTarget:Value1"
        src.par.exportmethod.val = "autoname"
        src.export = True

    # -- Custom parameter pages ----------------------------------------------

    with feature("custom_pars_page") as entry:
        comp = container.create("baseCOMP", "customParsDemo")
        page = comp.appendCustomPage("Demo")
        styles = {}

        def _style(name, fn):
            try:
                fn()
                styles[name] = {"applied": True, "error": None}
            except Exception as e:
                styles[name] = {"applied": False, "error": str(e)}

        def _float_multi():
            # Page.appendFloat(..., size=3): Page_Class.md confirms the
            # `size` kwarg exists but not the resulting sub-par name suffix
            # (assumed digit suffixes 1/2/3, the generic-append convention;
            # unverified against a live session).
            page.appendFloat("FloatMulti", size=3)
            comp.par.FloatMulti1.val = 1.5
            comp.par.FloatMulti2.val = 2.5
            comp.par.FloatMulti3.val = 3.5

        _style("float_multi_size3", _float_multi)

        def _int_par():
            page.appendInt("IntPar")
            comp.par.IntPar.val = 7

        _style("int", _int_par)

        def _toggle():
            page.appendToggle("TogglePar")
            comp.par.TogglePar.val = True

        _style("toggle", _toggle)

        def _menu():
            page.appendMenu("MenuPar")
            comp.par.MenuPar.menuNames = ["optA", "optB", "optC"]
            comp.par.MenuPar.menuLabels = ["Option A", "Option B", "Option C"]
            comp.par.MenuPar.val = "optB"

        _style("menu_names_labels", _menu)

        def _str_par():
            page.appendStr("StrPar")
            comp.par.StrPar.val = "a custom string value"

        _style("str", _str_par)

        def _op_ref():
            page.appendOP("OpRefPar")
            comp.par.OpRefPar.val = container

        _style("op_reference", _op_ref)

        def _pulse():
            page.appendPulse("PulsePar")

        _style("pulse", _pulse)

        def _rgb():
            page.appendRGB("RgbPar")

        _style("rgb", _rgb)

        def _xy():
            page.appendXY("XyPar")

        _style("xy", _xy)

        def _xyz():
            page.appendXYZ("XyzPar")

        _style("xyz", _xyz)

        def _file():
            page.appendFile("FilePar")
            comp.par.FilePar.val = "/tmp/tc_gen_example.txt"

        _style("file", _file)

        def _expr_float():
            page.appendFloat("ExprFloat")
            comp.par.ExprFloat.expr = "absTime.seconds"

        _style("expression_mode", _expr_float)

        def _clamped_int():
            page.appendInt("ClampedInt")
            p = comp.par.ClampedInt
            p.default = 5
            p.min = 0
            p.max = 10
            p.clampMin = True
            p.clampMax = True
            p.val = 7

        _style("non_default_default_min_max_clamp", _clamped_int)

        entry["styles"] = styles
        failed = [k for k, v in styles.items() if not v["applied"]]
        if failed:
            raise RuntimeError("style(s) failed: %s" % failed)

    # -- Wiring ---------------------------------------------------------------

    with feature("wiring_multi_input") as entry:
        merge = container.create("mergeCHOP", "mergeDemo")
        for i in range(3):
            src = container.create("constantCHOP", "mergeIn%d" % (i + 1))
            # Connector_Class.md: connecting via the INPUT connector replaces
            # that specific input, which keeps each of the 3 inputs
            # deterministic regardless of creation order.
            merge.inputConnectors[i].connect(src)

    with feature("wiring_chain") as entry:
        a = container.create("noiseCHOP", "chainA")
        b = container.create("lagCHOP", "chainB")
        c = container.create("nullCHOP", "chainC")
        b.inputConnectors[0].connect(a)
        c.inputConnectors[0].connect(b)

    with feature("wiring_op_ref_pars") as entry:
        # Select CHOP's OP-reference-ish par is `chop` (singular) per
        # Select_CHOP.md -- NOT `chops` as initially guessed from the task
        # description; verified against the wiki before use.
        a = container.op("chainA")
        if a is None:
            a = container.create("noiseCHOP", "chainA")
        sel = container.create("selectCHOP", "selectRefDemo")
        sel.par.chop.val = a.name

        # Composite TOP's list par is `top` (singular) per Composite_TOP.md
        # -- also singular, not `tops`.
        top_a = container.create("constantTOP", "compositeIn1")
        top_b = container.create("constantTOP", "compositeIn2")
        comp_top = container.create("compositeTOP", "compositeRefDemo")
        comp_top.par.top.val = "%s %s" % (top_a.name, top_b.name)

    # -- DATs -------------------------------------------------------------------

    with feature("dat_text") as entry:
        d = container.create("textDAT", "unicodeText")
        d.text = (
            "line one\twith a tab\n"
            "line two: café, naïve, 日本語\n"
            "\tindented third line, tab-led\n"
            "emoji: \U0001f39b️\n"
        )

    with feature("dat_table") as entry:
        d = container.create("tableDAT", "tableDemo")
        d.appendRows(
            [
                ["col1", "col2", "col3"],
                ["a1", "", "c1"],
                ["", "b2", ""],
                ["a3", "b3", "c3"],
            ]
        )

    # -- Flags --------------------------------------------------------------

    with feature("flag_bypass") as entry:
        o = container.create("nullCHOP", "bypassDemo")
        o.bypass = True

    with feature("flag_display_render") as entry:
        geo = container.create("geometryCOMP", "geoFlagsDemo")
        box = geo.create("boxSOP", "flagsSOP")
        box.display = False
        box.render = False

    with feature("flag_viewer") as entry:
        o = container.create("nullTOP", "viewerDemo")
        o.viewer = True

    with feature("flag_lock") as entry:
        # Locked data gets baked into the .tox -- an interesting case for
        # the tocdir format (see project TODO in the main repo CLAUDE.md).
        o = container.create("constantTOP", "lockDemo")
        o.lock = True

    # -- Comment / tags -------------------------------------------------------

    with feature("comment_single") as entry:
        o = container.create("nullCHOP", "commentSingle")
        o.comment = "a single-line comment"

    with feature("comment_multi") as entry:
        o = container.create("nullCHOP", "commentMulti")
        o.comment = "first line\nsecond line\nthird line"

    with feature("tags") as entry:
        o = container.create("nullCHOP", "tagsDemo")
        # OP_Class.md's own example assigns a list even though `tags` is
        # typed as a set: `n.tags = ['effect', 'image filter']`.
        o.tags = ["alpha", "beta"]

    # -- Nested / cloned / extended COMPs ------------------------------------

    with feature("nested_comps") as entry:
        l1 = container.create("baseCOMP", "nestLevel1")
        l2 = l1.create("baseCOMP", "nestLevel2")
        l3 = l2.create("baseCOMP", "nestLevel3")

    with feature("clone_par") as entry:
        # Base_COMP.md: "Clone Master `clone` - Path to a component used as
        # the Master Clone."
        master = container.create("baseCOMP", "cloneMaster")
        master_page = master.appendCustomPage("Demo")
        master_page.appendInt("Val")
        master.par.Val.val = 5

        child = container.create("baseCOMP", "cloneChild")
        child.par.clone.val = master

    with feature("extension") as entry:
        # Base_COMP.md Extensions page: `ext0object` ("A number of class
        # instances that can be attached to the component"), `ext0promote`
        # ("Controls whether ... visible directly at the component level").
        # The Object par's stored value is itself literal Python source that
        # TD evaluates in the COMP's own context (`me` below refers to
        # `extHost` once TD evaluates it, not to anything in this script) --
        # this specific mechanics (is it eval'd as an expression, or just a
        # constant string containing source?) was not independently
        # confirmed against a live session, only against Base_COMP.md's
        # prose description and the common `op(...).module.Cls(me)` idiom
        # seen throughout the wiki.
        ext_dat = container.create("textDAT", "extCode")
        ext_dat.text = (
            "class FeatureExt:\n"
            "    def __init__(self, comp):\n"
            "        self.comp = comp\n"
            "\n"
            "    def Double(self, x):\n"
            "        return x * 2\n"
        )
        host = container.create("baseCOMP", "extHost")
        host.par.ext0object.val = "op('extCode').module.FeatureExt(me)"
        host.par.ext0promote.val = True

    with feature("annotate_comp") as entry:
        container.create("annotateCOMP", "tcAnnotate")

    with feature("op_storage") as entry:
        o = container.create("baseCOMP", "storageDemo")
        o.store("k", {"a": [1, 2, 3]})

    # -- Case-collision probe ------------------------------------------------

    with feature("case_collision_probe") as entry:
        a = container.create("baseCOMP", "caseProbe")
        b = container.create("baseCOMP", "caseprobe")
        entry["names"] = {"first": a.name, "second": b.name}
        if a.name.lower() != b.name.lower():
            # TD renamed the second one away from a case-only variant of the
            # first (e.g. to "caseprobe1") rather than accepting it outright
            # -- still useful to know, but it no longer probes the
            # case-insensitive-filesystem disambiguation toeexpand does.
            raise RuntimeError(
                "expected a case-only-differing pair; got %r and %r"
                % (a.name, b.name)
            )

    # -- Appearance -----------------------------------------------------------

    with feature("color_node_size") as entry:
        o = container.create("nullTOP", "styledDemo")
        o.color = (0.8, 0.2, 0.3)
        o.nodeWidth = 300
        o.nodeHeight = 40

    # -- Save + manifest ------------------------------------------------------

    out_path = os.path.join(OUT_DIR, "features.tox")
    try:
        container.save(out_path)
        report["saved"] = True
        report["save_error"] = None
    except Exception as e:
        report["saved"] = False
        report["save_error"] = str(e)

    manifest_path = os.path.join(OUT_DIR, "features.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)

    print("td-snapshot features fixture generator")
    print("OUT_DIR: %s" % OUT_DIR)
    n_applied = sum(1 for v in report["features"].values() if v["applied"])
    n_failed = len(report["features"]) - n_applied
    for name, info in sorted(report["features"].items()):
        status = "ok" if info["applied"] else "FAILED: %s" % info["error"]
        print("  %-28s %s" % (name, status))
    print("applied=%d failed=%d" % (n_applied, n_failed))
    print("saved=%s" % report["saved"])
    print("manifest: %s" % manifest_path)
finally:
    container.destroy()
