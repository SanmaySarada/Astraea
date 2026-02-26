---
phase: 01-foundation
plan: 05
subsystem: io-cli
tags: [xpt-writer, cli, typer, rich, pyreadstat, xpt-v5, terminal-ui]
dependency-graph:
  requires: [01-02, 01-03, 01-04]
  provides: [xpt-v5-writer, cli-profile-command, cli-reference-command, cli-codelist-command]
  affects: [02-01, 02-02, 03-01]
tech-stack:
  added: []
  patterns: [pre-write-validation, round-trip-verification, typer-cli, rich-tables]
key-files:
  created:
    - src/astraea/io/xpt_writer.py
    - src/astraea/cli/app.py
    - src/astraea/cli/display.py
    - src/astraea/cli/__init__.py
    - tests/test_cli/__init__.py
    - tests/test_cli/test_app.py
  modified:
    - src/astraea/io/__init__.py
    - tests/test_io/test_xpt_writer.py
decisions:
  - id: D-0105-01
    description: "XPT writer performs mandatory read-back verification after every write to catch silent pyreadstat corruption"
  - id: D-0105-02
    description: "CLI uses typer.Argument/Option with Rich console for all output formatting"
metrics:
  duration: "~5 minutes (across checkpoint pause)"
  completed: "2026-02-26"
---

# Phase 1 Plan 5: XPT Writer and CLI Summary

**One-liner:** XPT v5 writer with pre-validation and round-trip verification, plus Typer CLI exposing profile/reference/codelist commands with Rich terminal output -- 216 total tests passing.

## What Was Done

### Task 1: XPT v5 Writer with Pre-Write Validation

Created `src/astraea/io/xpt_writer.py` with defense-in-depth against pyreadstat's silent truncation behavior:

| Export | Purpose | Key Detail |
|--------|---------|------------|
| `XPTValidationError` | Custom exception for constraint violations | Lists all errors (not just first) |
| `validate_for_xpt_v5` | Pre-write validation of DataFrame | Checks: var names <= 8 chars, labels <= 40 chars, char values <= 200 bytes, ASCII only, table name valid |
| `write_xpt_v5` | Validated write with round-trip check | Validates -> uppercases -> writes via pyreadstat -> reads back and verifies column names + row count match |

Critical design: The writer refuses to produce output that would be silently corrupted. Every write is followed by a read-back verification that confirms the file on disk matches what was intended. This directly addresses the pyreadstat truncation gotcha documented in PITFALLS.md (m3).

### Task 2: CLI with Profile, Reference, and Codelist Commands

Created `src/astraea/cli/app.py` (Typer app) and `src/astraea/cli/display.py` (Rich formatting):

| Command | Usage | Output |
|---------|-------|--------|
| `astraea profile <folder>` | Profile all SAS files in a directory | Rich table: Dataset, Rows, Columns, Clinical Cols, EDC Cols, Date Cols, Missing% |
| `astraea profile <folder> --detail` | Variable-level detail per dataset | Variable, Label, Type, Format, Missing%, Unique, Top Values |
| `astraea reference <domain>` | Show SDTM-IG domain specification | Domain info + variable table with color-coded core designations (Req/Exp/Perm) |
| `astraea reference <domain> --variable <var>` | Show single variable detail with codelist | Variable metadata including codelist ID and terms |
| `astraea codelist <code>` | Show CT codelist detail | Codelist name, extensible flag, all terms with codes |

The CLI ties together all Phase 1 components: SAS reader (01-02), profiler (01-02), SDTM-IG reference (01-03), CT reference (01-03), displayed through Rich tables.

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

1. **Round-trip verification mandatory (D-0105-01):** Every XPT write is followed by an immediate read-back that asserts column names and row counts match. This catches any silent corruption from pyreadstat at the cost of one extra file read per write -- acceptable for regulatory data integrity.
2. **Rich console output (D-0105-02):** All CLI output goes through Rich Console for consistent formatting. Core designations are color-coded: Required=red, Expected=yellow, Perm=green.

## Verification Results

```
pytest -v                                                    -- 216/216 passed (9.00s)
astraea profile Fakedata/                                    -- Summary table of 36 datasets
astraea reference DM                                         -- 26 variables with core designations
astraea reference DM --variable SEX                          -- SEX variable spec with codelist C66731
astraea codelist C66731                                      -- Sex terms: M, F, U, UNDIFFERENTIATED
XPT round-trip test                                          -- Write/read-back produces identical data
```

All Phase 1 success criteria verified:
1. User runs CLI, points at SAS folder, sees profiling output
2. SDTM-IG domain definitions and CT codelists loaded and queryable
3. Date conversion handles SAS numeric, string formats, and partial dates (01-04)
4. USUBJID generated from components and validated (01-04)
5. Valid XPT file written from DataFrame and passes structural validation

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `1d8aa5e` | XPT v5 writer with pre-write validation and round-trip verification |
| 2 | `3a4255e` | CLI with profile, reference, and codelist commands |

## Phase 1 Completion Summary

This plan completes Phase 1 (Foundation and Data Infrastructure). All 5 plans delivered:

| Plan | What | Tests |
|------|------|-------|
| 01-01 | Pydantic data models + project scaffold | 35 |
| 01-02 | SAS reader + dataset profiler | 42 |
| 01-03 | SDTM-IG + CT reference data (bundled JSON) | 59 |
| 01-04 | Date conversion + USUBJID utilities | 80 |
| 01-05 | XPT writer + CLI | 216 (cumulative) |

Key requirements satisfied: DATA-01 through DATA-07, CLI-01, CLI-04.

## Next Phase Readiness

Phase 2 (eCRF Parsing and Domain Classification) can now use:
- `astraea profile` to inspect any SAS data folder
- `astraea reference` / `astraea codelist` for SDTM-IG and CT lookups
- `write_xpt_v5()` for validated XPT output
- All Phase 1 imports: SAS reader, profiler, reference, dates, USUBJID
