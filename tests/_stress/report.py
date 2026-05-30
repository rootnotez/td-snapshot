"""Markdown report renderer for the stress framework.

Pure read from state.db; safe to call mid-run (WAL mode).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from state import connect, counts_by_status, latest_run

TOP_N = 20


def render(db_path: Path) -> str:
    if not db_path.exists():
        return "# toeexpand stress report\n\n(no state.db yet)\n"

    conn = connect(db_path, read_only=True)
    out: list[str] = []
    out.append("# toeexpand stress report\n")

    # --- Summary
    run = latest_run(conn)
    if run:
        out.append("## Summary\n")
        out.append(f"- Latest run: `{run['run_id']}`")
        out.append(f"- Corpus: `{run['corpus_root']}`")
        out.append(f"- Started:  {run['started_at']}")
        out.append(f"- Finished: {run['finished_at'] or '(in progress)'}")
        out.append("")

    counts = counts_by_status(conn)
    if counts:
        out.append("Sample status counts (cumulative across runs):\n")
        out.append("| status | count |")
        out.append("|---|---:|")
        for s in ("ok", "diff", "parse_failed", "expand_failed"):
            out.append(f"| `{s}` | {counts.get(s, 0)} |")
        out.append("")

    # --- By kind (diff rows only)
    diff_rows = list(conn.execute(
        "SELECT first_diff_path, mismatched_paths_json FROM samples WHERE status='diff'"
    ))
    if diff_rows:
        kind_counter: Counter[str] = Counter()
        for r in diff_rows:
            for rel in _collect_paths(r):
                kind_counter[_suffix_of(rel)] += 1
        out.append("## Diff failures by kind\n")
        out.append("| kind | mismatched files |")
        out.append("|---|---:|")
        for kind, n in kind_counter.most_common():
            out.append(f"| `{kind}` | {n} |")
        out.append("")

    # --- By TD build
    build_rows = list(conn.execute(
        "SELECT td_build, status, COUNT(*) AS n FROM samples GROUP BY td_build, status ORDER BY td_build"
    ))
    if build_rows:
        out.append("## By TD build\n")
        out.append("| build | status | count |")
        out.append("|---|---|---:|")
        for r in build_rows:
            out.append(f"| {r['td_build'] or '(unknown)'} | `{r['status']}` | {r['n']} |")
        out.append("")

    # --- Sample diffs
    diff_samples = list(conn.execute(
        """SELECT source_path, td_build, first_diff_path, first_diff_offset,
                  len_orig, len_ours, failures_dir
           FROM samples WHERE status='diff'
           ORDER BY finished_at DESC LIMIT ?""",
        (TOP_N,),
    ))
    if diff_samples:
        out.append(f"## Diff samples (latest {len(diff_samples)})\n")
        out.append("| source | build | first diff | offset | orig/ours len | failures dir |")
        out.append("|---|---|---|---:|---|---|")
        for r in diff_samples:
            out.append(
                f"| `{r['source_path']}` "
                f"| {r['td_build'] or '?'} "
                f"| `{r['first_diff_path']}` "
                f"| {r['first_diff_offset']} "
                f"| {r['len_orig']} / {r['len_ours']} "
                f"| `{r['failures_dir'] or ''}` |"
            )
        out.append("")

    # --- Parse / expand failures
    for status_name, heading in (("parse_failed", "Parse failures"), ("expand_failed", "Expand failures")):
        rows = list(conn.execute(
            """SELECT source_path, td_build, error_message, failures_dir
               FROM samples WHERE status=?
               ORDER BY finished_at DESC LIMIT ?""",
            (status_name, TOP_N),
        ))
        if not rows:
            continue
        out.append(f"## {heading} (latest {len(rows)})\n")
        for r in rows:
            msg = (r["error_message"] or "").strip().splitlines()
            msg_head = msg[0] if msg else ""
            out.append(f"- `{r['source_path']}` (build {r['td_build'] or '?'}) — {msg_head}")
            if r["failures_dir"]:
                out.append(f"  - artifacts: `{r['failures_dir']}`")
        out.append("")

    return "\n".join(out) + "\n"


def _collect_paths(row) -> list[str]:
    if row["mismatched_paths_json"]:
        try:
            return list(json.loads(row["mismatched_paths_json"]))
        except json.JSONDecodeError:
            pass
    return [row["first_diff_path"]] if row["first_diff_path"] else []


def _suffix_of(rel: str) -> str:
    name = rel.rsplit("/", 1)[-1]
    stripped = name.lstrip(".")
    if "." not in stripped:
        return stripped or "(none)"
    return stripped.rsplit(".", 1)[-1]
