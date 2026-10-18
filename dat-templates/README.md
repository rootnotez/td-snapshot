# DAT templates by TouchDesigner build

TouchDesigner fills many DATs with default text when it creates them: the callbacks DAT docked to a Web Server DAT or Script CHOP, the body of an Execute DAT, the shader DATs of a GLSL TOP. A snapshot of a network that holds such a DAT untouched would repeat 1–4 KB of TouchDesigner's text that says nothing about the network.

This directory is a running record of those default texts, one file per TouchDesigner build. `src/core.py` carries a table of their hashes (generated from every file here), and a snapshot shows an untouched DAT as one line:

```
  dat_text: (unchanged webserverDAT callbacks template, 3504 chars)
```

The full text is in this directory, so nothing is lost. A DAT is collapsed only when its text matches a recorded template exactly (after `\r\n` → `\n`). A DAT with even one edited line is shown in full, and so is a template from a build not recorded here. Pass `collapse_dat_templates=False` to `snapshot_patch` to show every body.

Matching is by hash, not by the running build. A DAT saved under an older build still collapses if that build's templates are recorded here, even when the snapshot runs on a newer TouchDesigner.

## Builds recorded

| Build | Captured | OS | Op types | Templates (distinct) | Skipped | Failed | Changes from the previous build |
|---|---|---|---|---|---|---|---|
| 2025.33230 | 2026-10-18 | macOS | 688 | 64 (62) | 165 | 21 | First record |

- **Skipped** types are never created by the capture: hardware/device I/O, network listeners, file writers, window and engine processes (see `SKIP` and `ALLOW` in `capture_td.py`). Their templates, if they have any, are not recorded, so their DATs are always shown in full.
- **Failed** types can't be created from Python on that build (legacy operators such as `svgTOP` or `bandeqCHOP`).
- `glslTOP` and `glslmultiTOP` share two shader templates; the label names both.

## Recording a new build

With the new TouchDesigner running the td-claude-bridge component:

```bash
scripts/capture-dat-templates.sh          # writes dat-templates/<build>.json, then regenerates src/core.py's table
```

It creates and destroys every op type inside `/project1/dat_templates_capture` in batches, and touches nothing else. Then:

1. Add a row to the table above. Fill in **Changes from the previous build** by diffing the two records, e.g. `diff <(jq -r '.templates[] | "\(.op_type) \(.role) \(.sha256)"' A.json) <(jq -r '… B.json')`.
2. Bump `core.py` in `src/versions.txt` (the table changed) and run `./scripts/build.sh`.

`tests/test_dat_templates.py` fails if `src/core.py`'s table doesn't match the records here.

## Files

- `<build>.json`: one record per build.
  - `templates`: one entry per default text: `op_type` (the operator that creates it), `role` (`text` for the DAT's own body, `docked:<name>` for a DAT docked to the operator, `child:<path>` for a DAT inside a COMP), `dat_type`, `sha256`, `chars`, and the full `text`.
  - `skipped`, `failed`: op types with no record, as above.
- `capture_td.py`: runs inside TouchDesigner, driven by `scripts/capture-dat-templates.sh`.
- `scripts/dat_templates.py`: assembles the batches into a record, and regenerates or checks the table in `src/core.py`.

Only Text and Execute-family DATs are recorded. Tables, Info DATs and device or folder listings hold generated, machine-specific content, never a template.
