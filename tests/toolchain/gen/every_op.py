"""tests/toolchain/gen/every_op.py

Creates one operator of EVERY class in TouchDesigner's `families` dict (one
family per key: CHOP, TOP, SOP, DAT, COMP, MAT, POP as of TD 2025.33230),
under a temporary Base COMP at /project1, then saves one .tox per family
plus a JSON manifest recording what was created, what failed, and coverage.

Runs INSIDE TouchDesigner via td-claude-bridge's /exec (see
tests/toolchain/gen/README.md and td-claude-bridge/README.md). It is sent
with a line `OUT_DIR = r'<abs path>'` prepended by
tests/toolchain/gen/run.sh -- this script does not hardcode a path and
fails clearly if OUT_DIR is missing.

Why the containers matter: `.allowCooking = False` is set on the temp
container and on each per-family COMP *before* any child op is created.
This repo's fixtures capture on-disk *state*, not runtime results (see
memory note "toeexpand serializes state, not runtime") -- letting hardware
/device-backed ops (Kinect, serial, audio device, NDI, ...) actually cook
on creation would try to open real devices for no benefit and could hang
or throw. `allowCooking` can only be disabled on COMPs (verified against
OP_Class.md: "Get or set Cooking Flag. Only COMPs can disable this flag."),
and disabling it on a parent COMP cascades to its whole contents.

Every create() is wrapped individually so one bad class (a family gains a
new operator type in a future build, a licence-gated op refuses to
construct, ...) can never abort the run; it is recorded as a failure and
the loop continues.
"""

import json
import os
import platform

try:
    OUT_DIR  # noqa: F821 -- must be injected by the runner, see module docstring
except NameError:
    raise RuntimeError(
        "OUT_DIR is not defined. tests/toolchain/gen/run.sh must prepend "
        "`OUT_DIR = r'<abs path>'` before sending this script to td.sh exec."
    )


def _tdglobal(name):
    """Resolve a name TouchDesigner injects for scripts (op, app, families, ...).

    td-claude-bridge's `/exec` runs the script through
    `exec(compile(source, '<bridge>', 'exec'), {'__name__': '__bridge__'})` --
    a *fresh* globals dict (see td-claude-bridge/README.md, "6. /exec" and
    "The cook model"). Names that are only conveniences of a particular
    DAT's own module namespace (this repo's src/core.py never needed to
    import anything either) would NOT resolve there; only names TD adds to
    the real `builtins` module would. td-claude-bridge/ruff.toml states
    outright that "these scripts run inside TouchDesigner's interpreter,
    which injects the td module's names as builtins", and
    td_bridge_callbacks.py's own `_exec` relies on exactly this (its
    `onHTTPRequest` uses `op`, `app`, `project` with zero imports, and the
    nested fresh-globals `/exec` is documented as running
    `print(project.name)` successfully with no import). `families` is a
    plain `td.families` module-level attribute alongside `app`/`project`/
    `root` (confirmed via td-docs introspect_td.json's "other" group), so it
    is expected to be injected the same way as those. This resolver tries
    the bare name first (covers the builtin case) and falls back to the
    `td` module (covers the case where a given name turns out NOT to be
    builtin-injected) so the script works either way without guessing.
    """
    try:
        return eval(name)
    except NameError:
        import td
        return getattr(td, name)


op = _tdglobal("op")
app = _tdglobal("app")
families = _tdglobal("families")

os.makedirs(OUT_DIR, exist_ok=True)

ROOT_PATH = "/project1"
CONTAINER_NAME = "tc_gen_every_op"
GRID_COLS = 10
GRID_SPACING_X = 200
GRID_SPACING_Y = 160

root = op(ROOT_PATH)
if root is None:
    raise RuntimeError("every_op.py: %s does not exist" % ROOT_PATH)

# Clean up a container left behind by a previous aborted run before we start,
# so re-running this script is idempotent.
stale = root.op(CONTAINER_NAME)
if stale is not None:
    stale.destroy()

container = root.create("baseCOMP", CONTAINER_NAME)
container.allowCooking = False

report = {
    "app_build": getattr(app, "build", None),
    "app_version": getattr(app, "version", None),
    "os": platform.platform(),
    "families": {},
}

try:
    for family in sorted(families.keys()):
        classes = families[family]
        family_comp = container.create("baseCOMP", family)
        # Must be set before any child of this family is created -- see
        # module docstring.
        family_comp.allowCooking = False

        created = []  # list of o.opType strings, one per successfully created op
        failures = []  # list of {"class": <class __name__>, "error": str(e)}

        for i, cls in enumerate(sorted(classes, key=lambda c: c.__name__)):
            class_name = cls.__name__
            try:
                o = family_comp.create(cls, class_name)
                o.nodeX = (i % GRID_COLS) * GRID_SPACING_X
                o.nodeY = -(i // GRID_COLS) * GRID_SPACING_Y
                created.append(o.opType)
            except Exception as e:
                failures.append({"class": class_name, "error": str(e)})

        out_path = os.path.join(OUT_DIR, "every_op_%s.tox" % family)
        try:
            family_comp.save(out_path)
            saved, save_error = True, None
        except Exception as e:
            saved, save_error = False, str(e)

        expected = set(c.__name__ for c in classes)
        accounted_for = set(created) | set(f["class"] for f in failures)
        # Should always be empty: every class in `families[family]` ends up
        # either in `created` or `failures`. A non-empty result means this
        # script's own bookkeeping missed a class, which is worth flagging
        # loudly rather than silently under-reporting coverage.
        coverage_missing = sorted(expected - accounted_for)

        report["families"][family] = {
            "created": sorted(created),
            "failures": failures,
            "saved": saved,
            "save_error": save_error,
            "coverage_missing": coverage_missing,
        }

    manifest_path = os.path.join(OUT_DIR, "every_op.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)

    print("td-snapshot every_op fixture generator")
    print("OUT_DIR: %s" % OUT_DIR)
    total_created = 0
    total_failed = 0
    any_coverage_gap = False
    for family, info in sorted(report["families"].items()):
        n_created = len(info["created"])
        n_failed = len(info["failures"])
        total_created += n_created
        total_failed += n_failed
        bits = []
        if info["coverage_missing"]:
            any_coverage_gap = True
            bits.append("MISSING=%s" % info["coverage_missing"])
        if not info["saved"]:
            bits.append("SAVE FAILED: %s" % info["save_error"])
        suffix = ("  " + " ".join(bits)) if bits else ""
        print(
            "  %-6s created=%-4d failed=%-3d%s"
            % (family, n_created, n_failed, suffix)
        )
    print("total created=%d failed=%d" % (total_created, total_failed))
    if any_coverage_gap:
        print("WARNING: coverage gap detected -- see coverage_missing above")
    print("manifest: %s" % manifest_path)
finally:
    container.destroy()
