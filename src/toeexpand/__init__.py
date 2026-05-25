"""Host-shell parser/encoder for toeexpand-produced `.dir/` + `.toc` trees.

Reads and writes the on-disk format documented in `toeexpand/FORMAT.md`,
independent of a running TouchDesigner process. Goal: bit-exact round-trip
(parse → emit → diff = 0 bytes). Where bit-exact is not achievable, the
deviation is recorded in `toeexpand/DEVIATIONS.md`.

Scope of this package:
    - Read a `<name>.tox.toc` + `<name>.tox.dir/` tree into an in-memory model.
    - Emit the same tree back to disk byte-for-byte.

Out of scope (lives in `src/core.py`, runs inside TouchDesigner):
    - Anything that needs `op()`, `me`, `parent()`, or `td` module access.
"""
