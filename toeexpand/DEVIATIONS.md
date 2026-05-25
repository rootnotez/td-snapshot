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
