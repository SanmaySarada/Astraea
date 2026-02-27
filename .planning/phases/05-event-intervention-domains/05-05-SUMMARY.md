---
phase: 05-event-intervention-domains
plan: 05
subsystem: execution-pipeline
tags: [cross-domain, xpt, usubjid, study-day, epoch, origin, integration-test]
depends_on: ["05-02", "05-03", "05-04"]
provides:
  - Cross-domain USUBJID validation (orphan subject detection)
  - --DY study day derivation via cross-domain RFSTDTC
  - EPOCH assignment from SE domain element ranges
  - Variable origin metadata validation (CRF, Derived, Assigned)
  - XPT file output generation and read-back verification for AE and CM
affects: ["06", "07"]
tech-stack:
  added: []
  patterns:
    - Cross-domain context passing for derived variable computation
    - XPT write + pyreadstat read-back verification
key-files:
  created:
    - tests/integration/execution/test_cross_domain_validation.py
    - tests/integration/execution/test_xpt_output.py
  modified:
    - src/astraea/io/xpt_writer.py
decisions:
  - id: "D-05-05-01"
    description: "Test uses pre-ISO dates in raw data (not string dates requiring conversion) to isolate cross-domain behavior from date parsing"
  - id: "D-05-05-02"
    description: "Fixed xpt_writer bug: table_label -> file_label for pyreadstat.write_xport()"
metrics:
  duration: "~3 min"
  completed: "2026-02-27"
  tests_added: 20
---

# Phase 5 Plan 5: Cross-Domain Validation and XPT Output Summary

Cross-domain USUBJID validation, --DY derivation from RFSTDTC, EPOCH from SE data, variable origin metadata, and XPT file generation -- 20 integration tests proving domains work together.

## What Was Done

### Task 1: Cross-Domain Validation, --DY, EPOCH, and Origin Metadata Tests (12 tests)

Created `tests/integration/execution/test_cross_domain_validation.py` (412 lines) with 4 test classes:

- **TestCrossDomainValidation** (3 tests): Validates `validate_cross_domain_usubjid()` detects orphan subjects not in DM, passes when all subjects match, works across multiple domains simultaneously.
- **TestStudyDayDerivation** (2 tests): Verifies --DY calculation with cross-domain RFSTDTC lookup for 3 subjects (days 15, 18, 43), and graceful handling when no CrossDomainContext is provided.
- **TestEpochDerivation** (2 tests): Confirms EPOCH assignment from SE domain date ranges (all 3 subjects in TREATMENT epoch), and graceful handling when SE data is missing.
- **TestVariableOriginMetadata** (5 tests): Validates origin is populated for ASSIGN (Assigned), DIRECT (CRF), DERIVATION (Derived) patterns, survives execution pipeline, and all mappings have non-None origin.

### Task 2: XPT File Output Tests (8 tests)

Created `tests/integration/execution/test_xpt_output.py` (261 lines):

- **TestXPTOutput** (8 tests): AE and CM domains produce .xpt files via `execute_to_xpt`, files are readable by pyreadstat with correct shapes (3x6), column labels preserved in metadata, table names correct, variable names <= 8 chars, labels <= 40 chars.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed xpt_writer table_label parameter name**

- **Found during:** Task 2
- **Issue:** `write_xpt_v5()` passed `table_label` to `pyreadstat.write_xport()`, but the correct parameter name is `file_label`. This caused `TypeError: write_xport() got an unexpected keyword argument 'table_label'` for any domain with a domain_label set.
- **Fix:** Changed `write_kwargs["table_label"]` to `write_kwargs["file_label"]` in `src/astraea/io/xpt_writer.py`
- **Files modified:** `src/astraea/io/xpt_writer.py`
- **Commit:** 208ffa4

## Commits

| Hash | Description |
|------|-------------|
| fa42f88 | test(05-05): cross-domain validation, --DY, EPOCH, and origin metadata tests |
| 208ffa4 | test(05-05): XPT file output tests for AE and CM domains + xpt_writer bug fix |
| 818c9d9 | style(05-05): fix lint issues in cross-domain and XPT tests |

## Verification

- All 20 new tests pass
- Full suite: 1031 passed, 86 skipped
- Ruff lint: clean (0 errors)
- All success criteria met

## Next Phase Readiness

Phase 5 is now complete (all 7 plans executed). Ready for Phase 6 (Findings domains with transpose logic).
