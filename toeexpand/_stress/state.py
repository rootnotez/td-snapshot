"""SQLite layer for the toeexpand stress framework.

Single-writer model: workers return `SampleResult` to the main process,
which is the only thread/process that calls `upsert_sample`. WAL mode
is enabled so the writer doesn't block readers (the report regen path
opens a read-only connection while a run could in principle be live).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    corpus_root   TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    total         INTEGER DEFAULT 0,
    ok            INTEGER DEFAULT 0,
    diff          INTEGER DEFAULT 0,
    parse_failed  INTEGER DEFAULT 0,
    expand_failed INTEGER DEFAULT 0,
    skipped       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS samples (
    source_sha256         TEXT PRIMARY KEY,
    source_path           TEXT NOT NULL,
    status                TEXT NOT NULL,
    td_build              TEXT,
    mismatched_paths_json TEXT,
    first_diff_path       TEXT,
    first_diff_offset     INTEGER,
    len_orig              INTEGER,
    len_ours              INTEGER,
    error_message         TEXT,
    failures_dir          TEXT,
    run_id                INTEGER,
    finished_at           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS samples_status ON samples(status);
CREATE INDEX IF NOT EXISTS samples_run_id ON samples(run_id);
"""


@dataclass
class SampleResult:
    """Everything a worker needs to send back to the main process for one sample."""
    source_sha256: str
    source_path: str                              # corpus-relative
    status: str                                   # ok | diff | parse_failed | expand_failed
    td_build: Optional[str] = None
    mismatched_paths: list[str] = field(default_factory=list)
    first_diff_path: Optional[str] = None
    first_diff_offset: Optional[int] = None
    len_orig: Optional[int] = None
    len_ours: Optional[int] = None
    error_message: Optional[str] = None
    failures_dir: Optional[str] = None            # populated only when status=diff/parse_failed and artifacts were kept


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path, read_only: bool = False) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if read_only:
        # uri-based read-only open
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, isolation_level=None)
    else:
        conn = sqlite3.connect(db_path, isolation_level=None)
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def start_run(conn: sqlite3.Connection, corpus_root: str) -> int:
    cur = conn.execute(
        "INSERT INTO runs (corpus_root, started_at) VALUES (?, ?)",
        (corpus_root, utcnow_iso()),
    )
    return int(cur.lastrowid)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    total: int,
    ok: int,
    diff: int,
    parse_failed: int,
    expand_failed: int,
    skipped: int,
) -> None:
    conn.execute(
        """UPDATE runs SET finished_at=?, total=?, ok=?, diff=?,
                          parse_failed=?, expand_failed=?, skipped=?
           WHERE run_id=?""",
        (utcnow_iso(), total, ok, diff, parse_failed, expand_failed, skipped, run_id),
    )


def upsert_sample(conn: sqlite3.Connection, run_id: int, r: SampleResult) -> None:
    conn.execute(
        """INSERT INTO samples (
              source_sha256, source_path, status, td_build,
              mismatched_paths_json, first_diff_path, first_diff_offset,
              len_orig, len_ours, error_message, failures_dir,
              run_id, finished_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(source_sha256) DO UPDATE SET
              source_path=excluded.source_path,
              status=excluded.status,
              td_build=excluded.td_build,
              mismatched_paths_json=excluded.mismatched_paths_json,
              first_diff_path=excluded.first_diff_path,
              first_diff_offset=excluded.first_diff_offset,
              len_orig=excluded.len_orig,
              len_ours=excluded.len_ours,
              error_message=excluded.error_message,
              failures_dir=excluded.failures_dir,
              run_id=excluded.run_id,
              finished_at=excluded.finished_at
        """,
        (
            r.source_sha256, r.source_path, r.status, r.td_build,
            json.dumps(r.mismatched_paths) if r.mismatched_paths else None,
            r.first_diff_path, r.first_diff_offset,
            r.len_orig, r.len_ours, r.error_message, r.failures_dir,
            run_id, utcnow_iso(),
        ),
    )


def get_known_ok_hashes(conn: sqlite3.Connection) -> set[str]:
    """Hashes already recorded with status=ok; used for incremental skip."""
    return {row["source_sha256"] for row in conn.execute(
        "SELECT source_sha256 FROM samples WHERE status='ok'"
    )}


def iter_samples(conn: sqlite3.Connection, status: Optional[str] = None) -> Iterator[sqlite3.Row]:
    if status is None:
        yield from conn.execute("SELECT * FROM samples ORDER BY finished_at DESC")
    else:
        yield from conn.execute(
            "SELECT * FROM samples WHERE status=? ORDER BY finished_at DESC", (status,)
        )


def latest_run(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    cur = conn.execute("SELECT * FROM runs ORDER BY run_id DESC LIMIT 1")
    return cur.fetchone()


def counts_by_status(conn: sqlite3.Connection) -> dict[str, int]:
    return {row["status"]: row["n"] for row in conn.execute(
        "SELECT status, COUNT(*) AS n FROM samples GROUP BY status"
    )}
