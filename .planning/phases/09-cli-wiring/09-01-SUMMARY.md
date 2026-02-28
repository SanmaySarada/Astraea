---
phase: 09-cli-wiring
plan: 01
subsystem: cli
tags: [cli, trial-design, ts, ta, te, tv, ti, sv, xpt]
depends_on:
  requires: [06-findings-domains]
  provides: [generate-trial-design CLI command, GAP-1 closure]
  affects: [09-02, 09-03]
tech_stack:
  added: []
  patterns: [lazy-import CLI command, XPT column label dicts]
key_files:
  created:
    - tests/unit/cli/test_trial_design_cli.py
  modified:
    - src/astraea/cli/app.py
    - src/astraea/execution/trial_design.py
    - tests/unit/execution/test_trial_design.py
decisions:
  - id: D-09-01-01
    decision: "TABESSION renamed to TABRSESS (8 chars max for XPT v5 compliance)"
  - id: D-09-01-02
    decision: "SV label 'Description of Unplanned Visit' truncated to 'Desc of Unplanned Visit' for 40-char XPT label limit"
  - id: D-09-01-03
    decision: "TA label 'Planned Order of Element within Arm' truncated to 'Planned Order of Element in Arm' for 40-char XPT label limit"
metrics:
  duration: "~7 minutes"
  completed: 2026-02-28
---

# Phase 9 Plan 1: Trial Design CLI Wiring Summary

**One-liner:** Wired TS/TA/TE/TV/TI/SV trial design builders into `astraea generate-trial-design` CLI command with JSON config input and XPT output, closing GAP-1.

## What Was Done

### Task 1: Add generate-trial-design CLI command
- Added `@app.command(name="generate-trial-design")` to `src/astraea/cli/app.py`
- Reads JSON config with `ts_config` and `trial_design` sections
- Builds all 6 trial design domains: TS, TA, TE, TV, TI, SV
- Writes XPT files with proper SDTM column labels
- Optional `--dm-path` for TS date derivation (SSTDTC from DM RFSTDTC)
- Optional `--data-dir` for SV domain from raw visit metadata
- Prints Rich summary table with domain, row count, output path
- All imports lazy inside function body (consistent with existing commands)
- Updated module docstring to include new command

### Task 2: Add CLI wiring tests
- Created `tests/unit/cli/test_trial_design_cli.py` with 5 tests:
  1. `test_generate_trial_design_basic` -- verifies XPT file generation
  2. `test_generate_trial_design_missing_config` -- error handling
  3. `test_generate_trial_design_ts_validation_warnings` -- SSTDTC warning
  4. `test_generate_trial_design_with_dm_path` -- DM date derivation verified via XPT read-back
  5. `test_generate_trial_design_sv_from_data_dir` -- SV generation with mocked SAS reader

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TABESSION column name exceeds XPT v5 8-char limit**
- **Found during:** Task 1 (XPT write validation failure)
- **Issue:** `TABESSION` (9 chars) in `trial_design.py` builder exceeds XPT v5 max 8-char column name
- **Fix:** Renamed to `TABRSESS` (8 chars) in builder, CLI labels, and existing test
- **Files modified:** `src/astraea/execution/trial_design.py`, `tests/unit/execution/test_trial_design.py`, `src/astraea/cli/app.py`
- **Commit:** ace41ba

**2. [Rule 1 - Bug] XPT label length constraints**
- **Found during:** Task 1 (label definition)
- **Issue:** Several planned labels exceeded 40-char XPT limit
- **Fix:** Truncated "Planned Order of Element within Arm" -> "Planned Order of Element in Arm", "Description of Unplanned Visit" -> "Desc of Unplanned Visit"
- **Files modified:** `src/astraea/cli/app.py`
- **Commit:** 170a546

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-09-01-01 | TABESSION -> TABRSESS | XPT v5 column names max 8 chars; 9-char name caused validation failure |
| D-09-01-02 | Truncated SV label | XPT v5 labels max 40 chars |
| D-09-01-03 | Truncated TA label | XPT v5 labels max 40 chars |

## Test Results

- 5 new tests in `tests/unit/cli/test_trial_design_cli.py`
- 12 existing tests in `tests/unit/execution/test_trial_design.py` still passing
- 668 total unit tests passing (no regressions)

## GAP-1 Status

**CLOSED.** Trial design builders (TS, TA, TE, TV, TI, SV) are now accessible via `astraea generate-trial-design` CLI command.
