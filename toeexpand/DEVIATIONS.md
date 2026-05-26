# toeexpand parser deviations

Places where the parser/encoder in `src/toeexpand/` cannot achieve bit-exact
round-trip, and why. Empty here means we're still bit-exact across the
known corpus. Add an entry the moment a round-trip test fails for reasons
that can't be fixed without giving up exactness.

Format per entry:

```
## <kind> — <one-line summary>

**Sample:** path to a file that fails round-trip
**Build:** version/build from the sibling `.build`
**Reason:** what the source emits that the parser cannot reproduce
**Decision:** preserve verbatim / normalise / flag-and-skip
```

## Resolved

### Text-file encoding — non-ASCII bytes inside `.parm` (and likely other text kinds)

**Sample:** `toeexpand/resources/raytk/examples/tutorial-fields-1-v3-final.toe.dir/project1/raytk/tools/palette/help_section.parm` (byte 0xEF at offset 1666, plus 151 other files in the same corpus).
**Build:** various 099 builds; appears whenever a parameter string contains a UTF-8 multi-byte character (icon glyphs in raytk).
**Resolution:** the parser switched from `decode("ascii")` to `decode("latin-1")`. Latin-1 maps bytes 0x00–0xFF one-to-one to code points U+0000–U+00FF, so any byte sequence is round-trip safe even when the source intent was UTF-8 (the bytes survive identically; we just don't try to interpret them as glyphs).

### `.table` preamble width — FORMAT.md was wrong about 6-u32 universality

**Sample:** `toeexpand/2026-05-17__datlab-classified-v1/v1/classifier.tox.dir/classifier/category_votes_table.table` (19-byte empty table that doesn't even contain 6 u32s).
**Build:** 099 across all observed builds.
**Resolution:** the table-shaped kinds (`.table`, `.renderpick`, `.fifo`, `.data`) use a 4-u32 preamble, not 6. The u32[4]/u32[5] previously documented were actually the first cell's tag + length. Parser now uses kind-specific preamble field counts (6 for `.text`, 4 for everything else table-shaped). FORMAT.md updated.

### `.lod` grammar incompleteness — directory descent / ascend records

**Sample:** `toeexpand/resources/SharedTox/Kantare.toe.dir/local/midi.lod` (record 6 starts with `0x36`, not `0x34`).
**Build:** 099 across all observed builds.
**Resolution:** `.lod` has three record types — `0x34` file, `0x36` directory-descend, `0x35` ascend. Earlier FORMAT.md drafts only described `0x34` because the original survey samples were shallow. Updated grammar verified bit-exact across all 30 `.lod` files in `toeexpand/resources/`.

### `.data` is polymorphic, not a single grammar

**Sample:** `toeexpand/resources/SharedTox/Kantare.toe.dir/project1/Kantare/qrelease.data` (starts with `\x00`, not `*`) plus `MapperTemplate/thumb.data` (starts with ASCII `5`).
**Build:** 099.
**Resolution:** `.data` is a generic binary blob used by different operators for different payloads — TOP icon rasters (ASCII-int header), COMP help text (DAT-cell preamble at offset 0), JSON-style bodies, etc. The parser stores raw bytes and exposes a `signature` accessor that sniffs the first byte (`dat_preamble` / `u32_preamble` / `ascii_int_header` / `brace_block` / `binary_b` / `other_*`). Round-trip is trivially bit-exact since we never re-parse the body.

## Known watch-list (not yet observed as failures)

- **Line endings** — all current samples use LF. If a Windows-exported `.tox`
  shows up with CRLF inside text bodies, that's a deviation candidate.
- **CHOP `.ts` / `.chop` cache state** — the brace-block `data_rle` payloads
  contain RLE-compressed sample buffers. Two TD instances may produce
  different cache state for semantically-identical patches (e.g. last-played
  sample index). Track per-kind whether bit-exact is even meaningful.
- **`.text` body length field** — the u32 `body_length` at preamble offset 23
  must match the actual body byte count. If a Python script gets re-saved
  with a different encoding (UTF-8 vs cp1252), the length changes. Source of
  truth is the file itself, but a re-encoder must keep the length field
  consistent.
- **`.lod` length encoding** — fully decoded as `0x34 | path_len+1 | u32-BE body_len | path\0 | body`. No deviations observed across builds 2017→2023, but if a 088 sample with `.lod` appears it may use the old (untested) layout.
