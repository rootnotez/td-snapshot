# toeexpand stress framework

Wide-corpus round-trip validator for the `toeexpand` parser. Walks a
directory of `.tox` / `.toe` files, runs the TouchDesigner `toeexpand`
binary on each, then drives `Project.from_dir().to_dir()` and byte-diffs
the result against the original expansion.

**Latest validated run:** `run-2/` — 1630/1630 OK across builds 2016.5580
→ 2025.31550 (`--timeout 600` to accommodate Luminosity_0_8.toe).
`run-1.md` documents the initial triage that drove the fixes in commits
`5271889` / `b30edfe` / `672cd71` / `f0ad994`.

Failures are kept on disk side-by-side (`orig/`, `ours/`, source copy)
so they can be inspected without re-running `toeexpand`.

## Run

```
uv run tests/_stress/run.py                    # default corpus = toeexpand/resources/
uv run tests/_stress/run.py PATH               # any directory
uv run tests/_stress/run.py PATH --limit 20    # cap for quick checks
uv run tests/_stress/run.py PATH --fresh       # ignore prior ok rows
uv run tests/_stress/run.py --report           # regen report.md only
```

Flags: `--jobs J` (default `min(cpu, 8)`), `--timeout SECONDS`
(per-sample `toeexpand` timeout, default 120), `--toeexpand PATH` or
`TOEEXPAND_BIN` env var (default
`/Applications/TouchDesigner.app/Contents/MacOS/toeexpand`).

Zero third-party deps — `uv run` resolves the interpreter via the script's
PEP 723 header, nothing installs into the host environment.

## Outputs (all gitignored)

```
tests/_stress/
├── state.db          # sqlite — incremental progress + every sample row
├── report.md         # regenerated at end of every run
├── work/             # transient per-sample scratch (cleaned on ok)
└── failures/<sha8>/
    ├── orig/         # toeexpand's expansion
    ├── ours/         # our re-emission via Project.to_dir()
    └── <name>.tox    # copy of the source
```

Re-runs are incremental: hashes already recorded with `status='ok'` are
skipped. `--fresh` forces re-processing.

## Triage workflow

1. Run, inspect `report.md` (by-kind, by-build, top-N samples).
2. Pick a failing sample from `report.md`. Diff its `failures/<sha8>/orig/`
   vs `ours/` with whatever you like (`diff -ru`, `cmp`, `vbindiff`).
3. For each novel signature, record a finding in `toeexpand/DEVIATIONS.md`
   — sample path, TD build (already in the report), byte offset, decision
   (preserve verbatim / normalise / fix parser). See existing entries for
   format. Per the project convention every novel finding records the
   `.build` version that produced it.
4. Fix the parser (or document the deviation), re-run the framework — the
   fixed sample now skips on subsequent runs.

## Failure-mode taxonomy

| status          | meaning                                                            |
|-----------------|--------------------------------------------------------------------|
| `ok`            | every byte matches; scratch cleaned                                |
| `diff`          | round-trip produced different bytes; artifacts in `failures/<sha>/`|
| `parse_failed`  | `Project.from_dir()` threw; traceback in `error_message`           |
| `expand_failed` | `toeexpand` binary returned non-zero or timed out                  |
