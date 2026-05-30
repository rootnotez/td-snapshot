#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Wide-corpus stress runner for the toeexpand parser.

Pipeline per sample (parallelised across cores):

    raw .tox/.toe
      -> toeexpand (host binary)        -> work/<sha8>/expanded/
      -> Project.from_dir().to_dir()    -> work/<sha8>/reemitted/
      -> sha256 every file pair, diff bytes only on hash mismatch
      -> ok: rm -rf scratch ; diff: move into failures/<sha8>/

State + results land in `tests/_stress/state.db`. Re-runs are
incremental — already-ok hashes are skipped. Failures keep the original
expansion + our re-emission + a copy of the source side-by-side so a
human can byte-diff without re-running toeexpand.

Usage:
    uv run tests/_stress/run.py [corpus] [--workdir DIR]
                                    [--limit N] [--fresh] [--jobs J]
                                    [--timeout SECONDS] [--report]

Override the toeexpand binary path with TOEEXPAND_BIN env var.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import traceback
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

THIS_DIR = Path(__file__).resolve().parent
REPO = THIS_DIR.parent.parent  # tests/_stress/ -> tests/ -> repo root


def _bootstrap_sys_path() -> None:
    """Make `from tocdir import ...` resolve to src/tocdir without install."""
    src = str(REPO / "src")
    if src not in sys.path:
        sys.path.insert(0, src)


_bootstrap_sys_path()

from tocdir import Build, Project, Toc  # noqa: E402

from state import (  # noqa: E402  (sibling module, same dir on sys.path)
    SampleResult,
    connect,
    finish_run,
    get_known_ok_hashes,
    start_run,
    upsert_sample,
)

DEFAULT_TOEEXPAND_BIN = "/Applications/TouchDesigner.app/Contents/MacOS/toeexpand"
ERROR_MSG_MAX = 2000


# ---------------------------------------------------------------------------
# Worker (runs in subprocess)
# ---------------------------------------------------------------------------


@dataclass
class WorkerArgs:
    source_path: str          # absolute
    source_rel: str           # relative to corpus root, for display
    sha_hex: str
    work_root: str            # absolute path to workdir/work
    failures_root: str        # absolute path to workdir/failures
    toeexpand_bin: str
    timeout: int


def _worker_entry(args: WorkerArgs) -> SampleResult:
    """Process one sample. Imports happen lazily inside the worker process."""
    _bootstrap_sys_path()
    from tocdir import Build, Project, Toc  # noqa: F811

    # Scratch must be unique per invocation so concurrent workers can never
    # contaminate each other's expansion — e.g. two corpus files with the
    # same sha would have collided here when scratch was sha-keyed, racing
    # toeexpand writes inside the same `expanded/` and producing impossible
    # output names like `<name>.2.toe.dir`.
    scratch = Path(tempfile.mkdtemp(prefix=f"{args.sha_hex[:8]}-", dir=args.work_root))
    expanded = scratch / "expanded"
    reemitted = scratch / "reemitted"
    expanded.mkdir(parents=True, exist_ok=True)

    src = Path(args.source_path)

    # ---- 1. Expand
    # toeexpand writes <name>.tox.dir + <name>.tox.toc next to the input.
    # We don't want to pollute the corpus, so symlink the source into the scratch dir.
    staged = expanded / src.name
    try:
        os.symlink(src, staged)
    except OSError:
        shutil.copy2(src, staged)

    try:
        proc = subprocess.run(
            [args.toeexpand_bin, str(staged)],
            cwd=expanded,
            capture_output=True,
            timeout=args.timeout,
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(scratch, ignore_errors=True)
        return SampleResult(
            source_sha256=args.sha_hex,
            source_path=args.source_rel,
            status="expand_failed",
            error_message=f"toeexpand timeout after {args.timeout}s",
        )
    except FileNotFoundError as e:
        shutil.rmtree(scratch, ignore_errors=True)
        return SampleResult(
            source_sha256=args.sha_hex,
            source_path=args.source_rel,
            status="expand_failed",
            error_message=str(e)[:ERROR_MSG_MAX],
        )

    # toeexpand exits non-zero even on success (it prints "expanded into
    # directory ..." to stderr). Use the presence of <name>.dir/ as the
    # actual success signal; fall back to exit code + stderr only if the
    # output is absent.
    dir_candidates = [p for p in expanded.iterdir() if p.is_dir() and p.name.endswith(".dir")]
    if not dir_candidates:
        err = (proc.stderr or proc.stdout or b"").decode("latin-1", errors="replace")[:ERROR_MSG_MAX]
        shutil.rmtree(scratch, ignore_errors=True)
        return SampleResult(
            source_sha256=args.sha_hex,
            source_path=args.source_rel,
            status="expand_failed",
            error_message=f"exit {proc.returncode}, no .dir/ produced: {err}",
        )
    if len(dir_candidates) > 1:
        # Pick the one matching the source stem; if ambiguous, take the first sorted.
        dir_candidates.sort(key=lambda p: 0 if p.name.startswith(src.stem) else 1)
    expanded_dir = dir_candidates[0]

    # Read td_build early so even failure rows can record it.
    td_build: Optional[str] = None
    build_path = expanded_dir / ".build"
    if build_path.exists():
        try:
            td_build = Build.parse(build_path.read_bytes()).build_number
        except Exception:
            td_build = None

    # ---- 2. Parse + re-emit
    reemitted.mkdir(parents=True, exist_ok=True)
    reemitted_dir = reemitted / expanded_dir.name
    try:
        project = Project.from_dir(expanded_dir)
        project.to_dir(reemitted_dir)
    except Exception:
        tb = traceback.format_exc()[:ERROR_MSG_MAX]
        fail_dir = _move_failure(scratch, args.failures_root, args.sha_hex, src)
        return SampleResult(
            source_sha256=args.sha_hex,
            source_path=args.source_rel,
            status="parse_failed",
            td_build=td_build,
            error_message=tb,
            failures_dir=str(fail_dir),
        )

    # ---- 3. Diff (sha256 first, byte-scan only on mismatch)
    toc = project.toc
    toc_filename = expanded_dir.name[: -len(".dir")] + ".toc"
    orig_toc = expanded_dir.parent / toc_filename
    ours_toc = reemitted_dir.parent / toc_filename

    pairs: list[tuple[str, Path, Path]] = [(toc_filename, orig_toc, ours_toc)]
    from toeexpand.project import _toc_to_disk  # local to keep top-level import surface tight
    for rel in toc.paths:
        disk_rel = _toc_to_disk(rel)
        pairs.append((rel, expanded_dir / disk_rel, reemitted_dir / disk_rel))

    mismatched: list[str] = []
    first_diff_path: Optional[str] = None
    first_diff_offset: Optional[int] = None
    first_len_orig: Optional[int] = None
    first_len_ours: Optional[int] = None

    for rel, a, b in pairs:
        ah = _sha256_file(a)
        bh = _sha256_file(b)
        if ah == bh:
            continue
        mismatched.append(rel)
        if first_diff_path is None:
            ab, bb = a.read_bytes(), b.read_bytes()
            first_diff_path = rel
            first_len_orig = len(ab)
            first_len_ours = len(bb)
            first_diff_offset = _first_diff_offset(ab, bb)

    if not mismatched:
        shutil.rmtree(scratch, ignore_errors=True)
        return SampleResult(
            source_sha256=args.sha_hex,
            source_path=args.source_rel,
            status="ok",
            td_build=td_build,
        )

    fail_dir = _move_failure(scratch, args.failures_root, args.sha_hex, src)
    return SampleResult(
        source_sha256=args.sha_hex,
        source_path=args.source_rel,
        status="diff",
        td_build=td_build,
        mismatched_paths=mismatched,
        first_diff_path=first_diff_path,
        first_diff_offset=first_diff_offset,
        len_orig=first_len_orig,
        len_ours=first_len_ours,
        failures_dir=str(fail_dir),
    )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _first_diff_offset(a: bytes, b: bytes) -> int:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n  # one is a prefix of the other


def _move_failure(scratch: Path, failures_root: str, sha_hex: str, source: Path) -> Path:
    fail_dir = Path(failures_root) / sha_hex[:8]
    if fail_dir.exists():
        shutil.rmtree(fail_dir, ignore_errors=True)
    fail_dir.mkdir(parents=True, exist_ok=True)
    expanded = scratch / "expanded"
    reemitted = scratch / "reemitted"
    if expanded.exists():
        shutil.move(str(expanded), str(fail_dir / "orig"))
    if reemitted.exists():
        shutil.move(str(reemitted), str(fail_dir / "ours"))
    try:
        shutil.copy2(source, fail_dir / source.name)
    except OSError:
        pass
    shutil.rmtree(scratch, ignore_errors=True)
    return fail_dir


# ---------------------------------------------------------------------------
# Main process
# ---------------------------------------------------------------------------


def discover_sources(corpus: Path, workdir: Path) -> list[Path]:
    """Find every .tox / .toe under corpus, excluding our own scratch."""
    work = workdir.resolve() / "work"
    failures = workdir.resolve() / "failures"
    out: list[Path] = []
    for p in corpus.rglob("*"):
        if p.suffix not in (".tox", ".toe"):
            continue
        if not p.is_file():
            continue
        rp = p.resolve()
        if work in rp.parents or failures in rp.parents:
            continue
        out.append(p)
    return sorted(out)


def hash_source(path: Path) -> str:
    return _sha256_file(path)


def _resolve_corpus(arg: Optional[str]) -> Path:
    if arg:
        p = Path(arg).resolve()
    else:
        p = (REPO / "toeexpand" / "resources").resolve()
    if not p.exists():
        raise SystemExit(f"corpus not found: {p}")
    return p


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("corpus", nargs="?", help="directory to scan recursively (default: toeexpand/resources/)")
    p.add_argument("--workdir", default=str(THIS_DIR), help="where state.db + work/ + failures/ live (default: this directory)")
    p.add_argument("--limit", type=int, default=None, help="cap on number of samples per run (after skip filter)")
    p.add_argument("--fresh", action="store_true", help="re-process every sample, ignore prior ok rows")
    p.add_argument("--jobs", type=int, default=min(os.cpu_count() or 1, 8), help="worker processes")
    p.add_argument("--timeout", type=int, default=120, help="per-sample toeexpand timeout seconds")
    p.add_argument("--report", action="store_true", help="just regenerate report.md from state.db and exit")
    p.add_argument("--toeexpand", default=os.environ.get("TOEEXPAND_BIN", DEFAULT_TOEEXPAND_BIN), help="path to toeexpand binary")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    db_path = workdir / "state.db"

    if args.report:
        from report import render  # noqa: WPS433 — sibling module
        out = workdir / "report.md"
        out.write_text(render(db_path))
        print(f"wrote {out}")
        return 0

    if not Path(args.toeexpand).exists():
        print(f"toeexpand binary not found: {args.toeexpand}", file=sys.stderr)
        print("(set TOEEXPAND_BIN env var or pass --toeexpand)", file=sys.stderr)
        return 2

    corpus = _resolve_corpus(args.corpus)
    print(f"corpus: {corpus}")
    print(f"workdir: {workdir}")

    sources = discover_sources(corpus, workdir)
    print(f"discovered {len(sources)} .tox/.toe files")

    conn = connect(db_path)
    known_ok: set[str] = set() if args.fresh else get_known_ok_hashes(conn)

    # Hash up front so the skip filter can prune work before the pool spins up.
    # Hashing 1,630 files (~4.6 GB) is ~5s on Apple Silicon; fine to do serially.
    queued: list[WorkerArgs] = []
    skipped = 0
    failures_root = workdir / "failures"
    work_root = workdir / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    failures_root.mkdir(parents=True, exist_ok=True)

    for src in sources:
        sha = hash_source(src)
        if sha in known_ok:
            skipped += 1
            continue
        queued.append(WorkerArgs(
            source_path=str(src),
            source_rel=str(src.relative_to(corpus)),
            sha_hex=sha,
            work_root=str(work_root),
            failures_root=str(failures_root),
            toeexpand_bin=args.toeexpand,
            timeout=args.timeout,
        ))
        if args.limit is not None and len(queued) >= args.limit:
            break

    print(f"queued: {len(queued)}, skipping ok: {skipped}")

    run_id = start_run(conn, str(corpus))
    counts = {"ok": 0, "diff": 0, "parse_failed": 0, "expand_failed": 0}

    def _handle(r: SampleResult) -> None:
        upsert_sample(conn, run_id, r)
        counts[r.status] = counts.get(r.status, 0) + 1
        marker = {"ok": ".", "diff": "D", "parse_failed": "P", "expand_failed": "E"}.get(r.status, "?")
        print(f"  [{marker}] {r.source_path}  build={r.td_build or '?'}"
              + (f"  {r.first_diff_path}@{r.first_diff_offset}" if r.status == "diff" else "")
              + (f"  {r.error_message[:80]}" if r.error_message else ""), flush=True)

    interrupted = False
    original_sigint = signal.getsignal(signal.SIGINT)

    def _on_sigint(signum, frame):
        nonlocal interrupted
        interrupted = True
        print("\n^C received — finishing in-flight samples, then stopping", file=sys.stderr)

    signal.signal(signal.SIGINT, _on_sigint)

    try:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            in_flight: dict[Future, WorkerArgs] = {}
            iterator = iter(queued)
            max_inflight = args.jobs * 4

            # Prime the pool
            for _ in range(min(max_inflight, len(queued))):
                try:
                    wargs = next(iterator)
                except StopIteration:
                    break
                in_flight[pool.submit(_worker_entry, wargs)] = wargs

            while in_flight:
                done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
                for fut in done:
                    wargs = in_flight.pop(fut)
                    try:
                        result = fut.result()
                    except Exception:
                        tb = traceback.format_exc()[:ERROR_MSG_MAX]
                        result = SampleResult(
                            source_sha256=wargs.sha_hex,
                            source_path=wargs.source_rel,
                            status="parse_failed",
                            error_message=f"worker crashed: {tb}",
                        )
                    _handle(result)

                    if interrupted:
                        continue
                    try:
                        nxt = next(iterator)
                    except StopIteration:
                        continue
                    in_flight[pool.submit(_worker_entry, nxt)] = nxt
    finally:
        signal.signal(signal.SIGINT, original_sigint)

    total = sum(counts.values())
    finish_run(
        conn, run_id,
        total=total,
        ok=counts.get("ok", 0),
        diff=counts.get("diff", 0),
        parse_failed=counts.get("parse_failed", 0),
        expand_failed=counts.get("expand_failed", 0),
        skipped=skipped,
    )

    # Always regenerate the report at the end.
    from report import render  # noqa: WPS433
    (workdir / "report.md").write_text(render(db_path))

    print(f"\nrun_id={run_id}  total={total}  "
          f"ok={counts.get('ok', 0)}  diff={counts.get('diff', 0)}  "
          f"parse_failed={counts.get('parse_failed', 0)}  "
          f"expand_failed={counts.get('expand_failed', 0)}  "
          f"skipped={skipped}")
    print(f"report: {workdir / 'report.md'}")
    if counts.get("diff", 0) or counts.get("parse_failed", 0):
        print(f"failures dir: {failures_root}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
