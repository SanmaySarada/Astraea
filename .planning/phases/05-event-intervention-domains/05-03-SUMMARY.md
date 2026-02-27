---
phase: 05-event-intervention-domains
plan: 03
subsystem: execution-integration-tests
tags: [cm, ex, integration-test, interventions, partial-dates, row-filtering, multi-source]
depends_on:
  requires: ["05-01"]
  provides: ["CM domain execution test", "EX domain execution test with filtering and merge"]
  affects: ["05-05", "05-06", "05-07"]
tech_stack:
  added: []
  patterns: ["pre-execution row filtering", "multi-source DataFrame merge", "Interventions-class domain testing"]
key_files:
  created:
    - tests/integration/execution/test_cm_execution.py
    - tests/integration/execution/test_ex_execution.py
  modified:
    - tests/unit/execution/test_pattern_handlers.py
decisions:
  - id: "D-05-03-01"
    description: "CM test uses synthetic partial dates: 'un UNK 2020' -> '2020', 'un Jun 2019' -> '2019-06'"
  - id: "D-05-03-02"
    description: "EX test applies filter_rows before passing to executor (pre-execution filtering pattern)"
  - id: "D-05-03-03"
    description: "Fixed pre-existing mock bug: preferred_term -> nci_preferred_term in test_pattern_handlers"
metrics:
  duration: "~3 min"
  completed: "2026-02-27"
---

# Phase 5 Plan 3: CM and EX Domain Integration Tests Summary

CM and EX Interventions-class domain integration tests with partial date handling, CT codelist recodes, row filtering, and multi-source merge.

## Tasks Completed

### Task 1: CM domain integration test
Created `tests/integration/execution/test_cm_execution.py` with 10 tests:
- `test_output_has_correct_columns` -- 12 mapped variables present
- `test_five_rows_preserved` -- all 5 source rows in output
- `test_cmtrt_direct_copy` -- CMTRT values match raw source
- `test_partial_date_year_only` -- "un UNK 2020" produces "2020"
- `test_partial_date_year_month` -- "un Jun 2019" produces "2019-06"
- `test_full_date_converted` -- "15 Jan 2022" produces "2022-01-15"
- `test_route_recoded` -- CMROUTE via C66729 (ORAL -> ORAL)
- `test_frequency_recoded` -- CMDOSFRQ via C71113 (BID, QD, PRN)
- `test_cmseq_generated` -- CMSEQ sequential per USUBJID
- `test_no_edc_columns` -- projectid and raw source columns excluded

### Task 2: EX domain integration test with row filtering and multi-source
Created `tests/integration/execution/test_ex_execution.py` with 9 tests:
- `test_output_has_correct_columns` -- 11 mapped variables present
- `test_non_administered_filtered_out` -- EXYN=N row excluded (5 rows, not 6)
- `test_extrt_direct_copy` -- all EXTRT values are "C1-INH"
- `test_multi_source_merged` -- both main study (Jan 2022) and OLE (Jul 2022) dates present
- `test_dosage_form_recoded` -- EXDOSFRM via C66726 (INJECTION)
- `test_route_recoded` -- EXROUTE via C66729 (INTRAVENOUS)
- `test_dates_converted` -- EXSTDTC in ISO 8601 YYYY-MM-DD format
- `test_exseq_generated` -- EXSEQ sequential per USUBJID
- `test_no_exyn_column_in_output` -- EXYN_STD and projectid excluded

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mock attribute name in test_pattern_handlers**
- **Found during:** Verification (full test suite)
- **Issue:** `test_lookup_recode_with_codelist` mock used `preferred_term` but actual `CodelistTerm` model uses `nci_preferred_term`, causing the test to fail
- **Fix:** Changed mock attribute from `preferred_term` to `nci_preferred_term`
- **Files modified:** tests/unit/execution/test_pattern_handlers.py
- **Commit:** included in metadata commit

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-05-03-01 | CM test uses synthetic partial dates | Validates parse_string_date_to_iso handles "un UNK YYYY" and "un Mon YYYY" |
| D-05-03-02 | EX test applies filter_rows before executor | Demonstrates pre-execution filtering pattern for domain-specific row exclusion |
| D-05-03-03 | Fixed mock bug: preferred_term -> nci_preferred_term | Pre-existing test failure caused by model field name mismatch |

## Verification Results

- CM tests: 10/10 passing
- EX tests: 9/9 passing
- Full suite: 1011 passed, 15 skipped, 0 failed
- Lint: all checks passed

## Success Criteria Verification

- [x] CM partial dates: "un UNK 2020" produces "2020", "un Jun 2019" produces "2019-06"
- [x] CM codelist recodes work for route (C66729), frequency (C71113), unit (C71620)
- [x] EX EXYN=N row excluded (5 rows, not 6)
- [x] EX multi-source merge combines main + OLE data
- [x] Both domains have --SEQ, correct column order, no EDC leakage
