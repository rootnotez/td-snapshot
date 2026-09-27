#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""tcdiff — detect toeexpand/toecollapse behaviour changes across TD builds.

See tests/toolchain/README.md for the full contract (layout, manifest
format, index.jsonl keys). This script implements the CLI documented
there: record / compare / cross / control.

Usage:
    uv run tests/toolchain/tcdiff.py record  [--bin DIR] [--out DIR] [--root DIR]
                                              [--keep-trees DIR] [--jobs N]
                                              [--timeout S] [inputs...]
    uv run tests/toolchain/tcdiff.py compare A_DIR B_DIR [--report FILE]
    uv run tests/toolchain/tcdiff.py cross   --bin DIR --trees DIR --against GOLDEN_DIR [--report FILE]
    uv run tests/toolchain/tcdiff.py control [--bin DIR] [--jobs N] [inputs...]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import common  # noqa: E402  (needs the sys.path insert above)

DEFAULT_TIMEOUT = 120
DEFAULT_JOBS = min(os.cpu_count() or 1, 8)

# Bucket names are part of the README contract — do not rename casually.
BUCKET_ORDER = [
    "identical", "build-only", "content-diff", "fileset-diff",
    "fail-A", "fail-B", "only-A", "only-B",
]
FLAGGED_FIELDS = ("collapse_sha256", "collapse_equals_input", "refixed_point", "expand_rc")


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

@dataclass
class RecordWork:
    id: str
    input_path: str
    bin_dir: str
    trees_out: str
    keep_trees: Optional[str]
    timeout: int


def _default_row(id_: str) -> dict:
    return {
        "id": id_,
        "input_sha256": None,
        "expand_rc": None,
        "expand_ok": False,
        "expand_stdout": "",
        "expand_stderr": "",
        "file_count": 0,
        "tree_sha256": None,
        "collapse_rc": None,
        "collapse_sha256": None,
        "collapse_equals_input": False,
        "refixed_point": False,
        "toolchain_build": None,
    }


def _copy_kept_tree(dest_dir: Path, tree: Path, toc: Path) -> None:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(tree, dest_dir / tree.name)
    shutil.copy2(toc, dest_dir / toc.name)


def _record_one(work: RecordWork) -> dict:
    """Runs in a worker process. Expand -> manifest -> collapse -> re-expand."""
    input_path = Path(work.input_path)
    bin_path = Path(work.bin_dir)
    row = _default_row(work.id)

    try:
        row["input_sha256"] = common.sha256_file(input_path)
    except OSError as e:
        row["expand_stderr"] = f"cannot read input: {e}"
        return row

    try:
        row["toolchain_build"] = common.toolchain_build(bin_path)
    except (OSError, KeyError) as e:
        row["expand_stderr"] = f"cannot resolve toolchain_build: {e}"

    workdir1 = Path(tempfile.mkdtemp(prefix="tcdiff-exp1-"))
    workdir2 = Path(tempfile.mkdtemp(prefix="tcdiff-exp2-"))
    try:
        exp = common.expand(bin_path, input_path, workdir1, timeout=work.timeout)
        row["expand_rc"] = exp.returncode
        row["expand_ok"] = exp.ok
        row["expand_stdout"] = exp.stdout
        row["expand_stderr"] = exp.stderr
        if not exp.ok:
            return row

        manifest = common.tree_manifest(exp.tree)
        row["file_count"] = len(manifest)
        tree_dest = Path(work.trees_out) / f"{work.id}.sha256"
        row["tree_sha256"] = common.write_manifest(tree_dest, manifest)

        if work.keep_trees:
            _copy_kept_tree(Path(work.keep_trees) / work.id, exp.tree, exp.toc)

        coll = common.collapse(bin_path, exp.tree, timeout=work.timeout)
        row["collapse_rc"] = coll.returncode
        if coll.output is not None:
            row["collapse_sha256"] = common.sha256_file(coll.output)
            row["collapse_equals_input"] = row["collapse_sha256"] == row["input_sha256"]

            exp2 = common.expand(bin_path, coll.output, workdir2, timeout=work.timeout)
            if exp2.ok:
                manifest2 = common.tree_manifest(exp2.tree)
                row["refixed_point"] = manifest2 == manifest

        return row
    finally:
        shutil.rmtree(workdir1, ignore_errors=True)
        shutil.rmtree(workdir2, ignore_errors=True)


def discover_inputs(paths: list[Path]) -> list[Path]:
    """Positional inputs: files taken as-is, directories searched recursively."""
    found: set[Path] = set()
    for p in paths:
        rp = p.resolve()
        if rp.is_dir():
            for f in rp.rglob("*"):
                if f.is_file() and f.suffix in (".toe", ".tox"):
                    found.add(f)
        elif rp.is_file():
            found.add(rp)
        else:
            raise SystemExit(f"ERROR: input not found: {p}")
    return sorted(found)


def do_record(
    bin_dir: Path, inputs: list[Path], root: Path, out: Path,
    keep_trees: Optional[Path], jobs: int, timeout: int,
) -> dict:
    trees_out = out / "trees"
    trees_out.mkdir(parents=True, exist_ok=True)
    if keep_trees:
        keep_trees.mkdir(parents=True, exist_ok=True)

    works: list[RecordWork] = []
    for p in inputs:
        try:
            id_ = common.input_id(p, root)
        except ValueError:
            raise SystemExit(f"ERROR: input not under root: {p} (root={root})")
        works.append(RecordWork(
            id=id_, input_path=str(p), bin_dir=str(bin_dir),
            trees_out=str(trees_out),
            keep_trees=str(keep_trees) if keep_trees else None,
            timeout=timeout,
        ))

    print(f"recording {len(works)} inputs -> {out}")
    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futs = {pool.submit(_record_one, w): w for w in works}
        for fut in as_completed(futs):
            w = futs[fut]
            try:
                row = fut.result()
            except Exception as e:  # noqa: BLE001 — worker crash must not kill the batch
                row = _default_row(w.id)
                row["expand_stderr"] = f"worker crashed: {e}"
            rows.append(row)
            marker = "." if row.get("expand_ok") else "E"
            print(f"  [{marker}] {row['id']}", flush=True)

    rows.sort(key=lambda r: r["id"])
    index_path = out / "index.jsonl"
    with index_path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    summary = {
        "total": len(rows),
        "expand_ok": sum(1 for r in rows if r.get("expand_ok")),
        "collapse_equals_input": sum(1 for r in rows if r.get("collapse_equals_input")),
        "refixed_point": sum(1 for r in rows if r.get("refixed_point")),
    }
    print(
        f"summary: total={summary['total']} expand_ok={summary['expand_ok']} "
        f"collapse_equals_input={summary['collapse_equals_input']} "
        f"refixed_point={summary['refixed_point']}"
    )
    print(f"wrote {index_path}")
    return summary


def _require_bin(bin_dir: Path) -> None:
    if not (bin_dir / "toeexpand").is_file():
        raise SystemExit(f"ERROR: toeexpand not found in {bin_dir}")


def cmd_record(args: argparse.Namespace) -> int:
    bin_dir = common.bin_dir(args.bin)
    _require_bin(bin_dir)
    root = Path(args.root).resolve() if args.root else common.REPO

    if args.inputs:
        inputs = discover_inputs([Path(p) for p in args.inputs])
    else:
        inputs = common.load_inputs(root=root)
    if not inputs:
        print("no inputs found", file=sys.stderr)
        return 1

    build = common.toolchain_build(bin_dir)
    out = Path(args.out).resolve() if args.out else (common.GOLDEN_ROOT / build)
    keep_trees = Path(args.keep_trees).resolve() if args.keep_trees else None
    jobs = args.jobs or DEFAULT_JOBS

    do_record(bin_dir, inputs, root, out, keep_trees, jobs, args.timeout)
    return 0


# ---------------------------------------------------------------------------
# compare / cross shared helpers
# ---------------------------------------------------------------------------

def read_index(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rows[row["id"]] = row
    return rows


def diff_manifests(a: dict[str, str], b: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    keys_a, keys_b = set(a), set(b)
    added = sorted(keys_b - keys_a)
    removed = sorted(keys_a - keys_b)
    changed = sorted(k for k in (keys_a & keys_b) if a[k] != b[k])
    return added, removed, changed


def _file_kind(rel_path: str) -> str:
    name = Path(rel_path).name
    if "." in name:
        return name.rsplit(".", 1)[-1]
    return "(none)"


def _tally_kinds(detail: dict, kind_counts: Counter) -> None:
    for p in detail.get("added", []) + detail.get("removed", []) + detail.get("changed", []):
        kind_counts[_file_kind(p)] += 1


def _render_bucket_table(buckets: dict[str, list[str]], order: list[str]) -> list[str]:
    lines = ["| bucket | count |", "|---|---|"]
    for b in order:
        lines.append(f"| {b} | {len(buckets.get(b, []))} |")
    total = sum(len(v) for v in buckets.values())
    lines.append(f"| **total** | **{total}** |")
    return lines


def _render_kind_rollup(kind_counts: Counter) -> list[str]:
    if not kind_counts:
        return []
    lines = ["## Differing files by kind", "", "| kind | count |", "|---|---|"]
    for kind, count in kind_counts.most_common():
        lines.append(f"| {kind} | {count} |")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------

def classify_id(id_: str, row_a: Optional[dict], row_b: Optional[dict], a_dir: Path, b_dir: Path) -> tuple[str, dict]:
    detail: dict = {}
    if row_a is None:
        return "only-B", detail
    if row_b is None:
        return "only-A", detail

    ok_a, ok_b = row_a.get("expand_ok"), row_b.get("expand_ok")
    if not ok_a or not ok_b:
        if not ok_a and not ok_b:
            detail["note"] = "both sides failed to expand"
        return ("fail-A" if not ok_a else "fail-B"), detail

    try:
        manifest_a = common.read_manifest(a_dir / "trees" / f"{id_}.sha256")
        manifest_b = common.read_manifest(b_dir / "trees" / f"{id_}.sha256")
    except OSError as e:
        detail["note"] = f"missing manifest file: {e}"
        return "fail-A", detail

    added, removed, changed = diff_manifests(manifest_a, manifest_b)
    detail["added"], detail["removed"], detail["changed"] = added, removed, changed
    if not added and not removed and not changed:
        return "identical", detail
    if added or removed:
        return "fileset-diff", detail
    if len(changed) == 1 and Path(changed[0]).name == ".build":
        return "build-only", detail
    return "content-diff", detail


def do_compare(a_dir: Path, b_dir: Path) -> tuple[str, int]:
    idx_a = read_index(a_dir / "index.jsonl")
    idx_b = read_index(b_dir / "index.jsonl")
    ids = sorted(set(idx_a) | set(idx_b))

    build_a = next(iter(idx_a.values()), {}).get("toolchain_build", "unknown")
    build_b = next(iter(idx_b.values()), {}).get("toolchain_build", "unknown")

    buckets: dict[str, list[str]] = defaultdict(list)
    details: dict[str, dict] = {}
    metadata_diffs: dict[str, dict] = {}
    kind_counts: Counter = Counter()

    for id_ in ids:
        row_a, row_b = idx_a.get(id_), idx_b.get(id_)
        bucket, detail = classify_id(id_, row_a, row_b, a_dir, b_dir)
        buckets[bucket].append(id_)
        details[id_] = detail
        _tally_kinds(detail, kind_counts)

        if row_a is not None and row_b is not None:
            mdiff = {}
            for field in FLAGGED_FIELDS:
                va, vb = row_a.get(field), row_b.get(field)
                if va != vb:
                    mdiff[field] = (va, vb)
            if mdiff:
                metadata_diffs[id_] = mdiff

    lines = [f"# toolchain compare: {build_a} vs {build_b}", ""]
    lines.append(f"- A: `{a_dir}` (toolchain_build={build_a})")
    lines.append(f"- B: `{b_dir}` (toolchain_build={build_b})")
    lines.append("")
    lines.append("## Bucket counts")
    lines.append("")
    lines += _render_bucket_table(buckets, BUCKET_ORDER)
    lines.append("")

    if metadata_diffs:
        lines.append(f"## Toolchain metadata differences ({len(metadata_diffs)} ids)")
        lines.append("")
        for id_ in sorted(metadata_diffs):
            lines.append(f"- `{id_}`:")
            for field, (va, vb) in metadata_diffs[id_].items():
                lines.append(f"  - {field}: A=`{va}` B=`{vb}`")
        lines.append("")

    non_identical = [(b, i) for b in BUCKET_ORDER for i in sorted(buckets.get(b, [])) if b != "identical"]
    if non_identical:
        lines.append("## Details")
        lines.append("")
        for bucket, id_ in non_identical:
            d = details.get(id_, {})
            lines.append(f"### `{id_}` — {bucket}")
            if d.get("note"):
                lines.append(f"- {d['note']}")
            if d.get("added"):
                lines.append(f"- added: {d['added']}")
            if d.get("removed"):
                lines.append(f"- removed: {d['removed']}")
            if d.get("changed"):
                lines.append(f"- changed: {d['changed']}")
            lines.append("")

    lines += _render_kind_rollup(kind_counts)

    report = "\n".join(lines).rstrip() + "\n"
    ok = not non_identical and not metadata_diffs
    return report, (0 if ok else 1)


def cmd_compare(args: argparse.Namespace) -> int:
    a_dir = Path(args.a_dir).resolve()
    b_dir = Path(args.b_dir).resolve()
    report, rc = do_compare(a_dir, b_dir)
    print(report)
    if args.report:
        Path(args.report).write_text(report)
        print(f"wrote {args.report}", file=sys.stderr)
    return rc


# ---------------------------------------------------------------------------
# cross
# ---------------------------------------------------------------------------

def discover_kept_trees(trees_root: Path) -> dict[str, tuple[Path, Path]]:
    """Find <name>.dir + <name>.toc pairs kept by `record --keep-trees`."""
    result: dict[str, tuple[Path, Path]] = {}
    for d in sorted(trees_root.rglob("*.dir")):
        if not d.is_dir():
            continue
        stem = d.name[: -len(".dir")]
        toc = d.parent / f"{stem}.toc"
        if not toc.is_file():
            continue
        id_ = d.parent.relative_to(trees_root).as_posix()
        result[id_] = (d, toc)
    return result


def do_cross(bin_dir: Path, trees_root: Path, golden_dir: Path) -> tuple[str, int]:
    golden_index = read_index(golden_dir / "index.jsonl")
    build = common.toolchain_build(bin_dir)
    kept = discover_kept_trees(trees_root)

    buckets: dict[str, list[str]] = defaultdict(list)
    details: dict[str, dict] = {}
    kind_counts: Counter = Counter()

    for id_, (tree, toc) in sorted(kept.items()):
        golden_row = golden_index.get(id_)
        if golden_row is None:
            buckets["missing-golden"].append(id_)
            continue

        workdir = Path(tempfile.mkdtemp(prefix="tcdiff-cross-"))
        try:
            tree_copy = workdir / tree.name
            toc_copy = workdir / toc.name
            shutil.copytree(tree, tree_copy)
            shutil.copy2(toc, toc_copy)

            coll = common.collapse(bin_dir, tree_copy)
            if coll.output is None:
                buckets["fail"].append(id_)
                details[id_] = {"note": f"collapse failed rc={coll.returncode}"}
                continue

            collapse_sha = common.sha256_file(coll.output)
            collapse_match = collapse_sha == golden_row.get("collapse_sha256")

            detail: dict = {}
            expand_match = False
            golden_manifest_path = golden_dir / "trees" / f"{id_}.sha256"
            exp = common.expand(bin_dir, coll.output, workdir / "reexpand")
            if exp.ok and golden_manifest_path.is_file():
                manifest = common.tree_manifest(exp.tree)
                golden_manifest = common.read_manifest(golden_manifest_path)
                added, removed, changed = diff_manifests(golden_manifest, manifest)
                detail["added"], detail["removed"], detail["changed"] = added, removed, changed
                expand_match = not (added or removed or changed)
            else:
                detail["note"] = "re-expand failed or golden manifest missing"

            _tally_kinds(detail, kind_counts)

            if collapse_match and expand_match:
                buckets["identical"].append(id_)
            elif not collapse_match and not expand_match:
                buckets["both-mismatch"].append(id_)
                details[id_] = detail
            elif not collapse_match:
                buckets["collapse-diff"].append(id_)
                details[id_] = detail
            else:
                buckets["expand-diff"].append(id_)
                details[id_] = detail
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    order = ["identical", "collapse-diff", "expand-diff", "both-mismatch", "fail", "missing-golden"]
    lines = [f"# toolchain cross: {build} trees against golden {golden_dir}", ""]
    lines.append(f"- bin: `{bin_dir}` (toolchain_build={build})")
    lines.append(f"- trees: `{trees_root}`")
    lines.append(f"- golden: `{golden_dir}`")
    lines.append("")
    lines.append("## Bucket counts")
    lines.append("")
    lines += _render_bucket_table(buckets, order)
    lines.append("")

    non_identical = [(b, i) for b in order for i in sorted(buckets.get(b, [])) if b != "identical"]
    if non_identical:
        lines.append("## Details")
        lines.append("")
        for bucket, id_ in non_identical:
            d = details.get(id_, {})
            lines.append(f"### `{id_}` — {bucket}")
            if d.get("note"):
                lines.append(f"- {d['note']}")
            if d.get("added"):
                lines.append(f"- added: {d['added']}")
            if d.get("removed"):
                lines.append(f"- removed: {d['removed']}")
            if d.get("changed"):
                lines.append(f"- changed: {d['changed']}")
            lines.append("")

    lines += _render_kind_rollup(kind_counts)

    report = "\n".join(lines).rstrip() + "\n"
    ok = not non_identical
    return report, (0 if ok else 1)


def cmd_cross(args: argparse.Namespace) -> int:
    bin_dir = common.bin_dir(args.bin)
    _require_bin(bin_dir)
    trees_root = Path(args.trees).resolve()
    golden_dir = Path(args.against).resolve()
    report, rc = do_cross(bin_dir, trees_root, golden_dir)
    print(report)
    if args.report:
        Path(args.report).write_text(report)
        print(f"wrote {args.report}", file=sys.stderr)
    return rc


# ---------------------------------------------------------------------------
# control
# ---------------------------------------------------------------------------

def cmd_control(args: argparse.Namespace) -> int:
    bin_dir = common.bin_dir(args.bin)
    _require_bin(bin_dir)
    root = common.REPO

    if args.inputs:
        inputs = discover_inputs([Path(p) for p in args.inputs])
    else:
        inputs = common.load_inputs(root=root)
    if not inputs:
        print("no inputs found", file=sys.stderr)
        return 1

    jobs = args.jobs or DEFAULT_JOBS

    with tempfile.TemporaryDirectory(prefix="tcdiff-control-a-") as tmp_a, \
         tempfile.TemporaryDirectory(prefix="tcdiff-control-b-") as tmp_b:
        out_a, out_b = Path(tmp_a), Path(tmp_b)
        print("control: recording pass A...")
        do_record(bin_dir, inputs, root, out_a, None, jobs, DEFAULT_TIMEOUT)
        print("control: recording pass B...")
        do_record(bin_dir, inputs, root, out_b, None, jobs, DEFAULT_TIMEOUT)
        report, rc = do_compare(out_a, out_b)

    print(report)
    if rc == 0:
        print("control: 100% identical (deterministic)")
    else:
        print("control: DIFFERENCES DETECTED — harness or toolchain is non-deterministic", file=sys.stderr)
    return rc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tcdiff",
        description="Detect toeexpand/toecollapse behaviour changes across TD builds.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_record = sub.add_parser("record", help="record expand/collapse manifests for a toolchain")
    p_record.add_argument("inputs", nargs="*", help="files/dirs to record (default: inputs.txt golden set)")
    p_record.add_argument("--bin", help="…/TouchDesigner.app/Contents/MacOS (default: $TD_TOOLCHAIN_BIN or /Applications/...)")
    p_record.add_argument("--out", help="output dir (default: golden/<toolchain-build>/)")
    p_record.add_argument("--root", help="id root (default: repo root)")
    p_record.add_argument("--keep-trees", help="also copy each expansion tree here, keyed by id")
    p_record.add_argument("--jobs", type=int, default=None, help=f"worker processes (default: {DEFAULT_JOBS})")
    p_record.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="per-call timeout seconds")
    p_record.set_defaults(func=cmd_record)

    p_compare = sub.add_parser("compare", help="compare two recorded index dirs")
    p_compare.add_argument("a_dir")
    p_compare.add_argument("b_dir")
    p_compare.add_argument("--report", help="also write the markdown report here")
    p_compare.set_defaults(func=cmd_compare)

    p_cross = sub.add_parser("cross", help="re-collapse/re-expand kept trees with a bin, compare to a golden set")
    p_cross.add_argument("--bin", required=True)
    p_cross.add_argument("--trees", required=True, help="dir from a prior `record --keep-trees`")
    p_cross.add_argument("--against", required=True, help="golden index dir to compare against")
    p_cross.add_argument("--report", help="also write the markdown report here")
    p_cross.set_defaults(func=cmd_cross)

    p_control = sub.add_parser("control", help="record twice with one bin, compare, check determinism")
    p_control.add_argument("inputs", nargs="*")
    p_control.add_argument("--bin")
    p_control.add_argument("--jobs", type=int, default=None)
    p_control.set_defaults(func=cmd_control)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
