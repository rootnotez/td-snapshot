# tests/toolchain/gen

Fixture generators for the toolchain regression workflow (see
`tests/toolchain/README.md`). These build small, known networks *inside a
live TouchDesigner session* and save them as `.tox` files under
`tests/toolchain/fixtures/<build>/`, so `tcdiff.py record` has real,
documented-provenance input beyond `td-snapshot.tox` and whatever `.toe`/
`.tox` files happen to be lying around.

- `every_op.py` — one operator of every class in TouchDesigner's `families`
  dict, one family per `.tox`. Exercises operator-type coverage.
- `features.py` — one Base COMP exercising the format features
  `td-snapshot`/`tocdir` depend on: parameter modes (CONSTANT, EXPRESSION,
  BIND, EXPORT), custom-parameter styles, wiring shapes, DAT bodies, flags,
  comments/tags, nested/cloned/extended COMPs, an Annotate COMP, op
  storage, a case-collision name probe, and node appearance.

Both are meant to be **read and sent by `run.sh`**, not run directly with a
local Python — they use TouchDesigner-only globals (`op`, `app`, ...) that
only exist inside TD's own interpreter, and `run.sh` prepends the
`OUT_DIR = r'...'` line each one expects.

## Running

1. Start a TouchDesigner session with the bridge component already in it:

   ```bash
   open -a TouchDesigner <path-to>/bridge_dev.toe   # any .toe containing the tdClaudeBridge component
   ```

2. Run a generator:

   ```bash
   tests/toolchain/gen/run.sh every_op
   tests/toolchain/gen/run.sh features
   ```

   Add an explicit output directory to override the default (`tests/toolchain/fixtures/<build>`,
   where `<build>` is asked from the live bridge):

   ```bash
   tests/toolchain/gen/run.sh every_op tests/toolchain/fixtures/2025.99999
   ```

   `TD_BRIDGE` overrides the td-claude-bridge checkout if it isn't a sibling
   of this repo (`../td-claude-bridge`).

Each generator is defensive about its own failures: every operator create
(`every_op.py`) and every named feature (`features.py`) is wrapped in its
own `try`/`except`, recorded into the accompanying `.json` manifest as
applied/failed (+ error string) rather than aborting the run. Check that
JSON after running — a generator printing a clean summary can still have
individually failed entries worth looking at.

## Frozen-fixture rule

Fixtures already committed under `tests/toolchain/fixtures/<build>/` are
**never regenerated in place** — a new TD build gets its own `<build>`
directory (see the layout contract in `tests/toolchain/README.md`), so the
committed set accumulates one generation per build passed through, rather
than silently drifting. `run.sh` enforces this: it refuses to overwrite an
existing `<generator>*.tox` or `<generator>.json` for the resolved
`OUT_DIR` unless `--force` is given. `--force` is for iterating on a
generator *before* it's committed, not for regenerating a committed
fixture — if a generator needs to change after its fixtures are committed,
save the new output to a fresh or scratch directory and reconcile by hand.
