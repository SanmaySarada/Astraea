---
phase: 05-event-intervention-domains
plan: 02
subsystem: execution
tags: [integration-tests, ae-domain, ds-domain, multi-source-merge, ct-recode]
depends_on:
  requires: ["05-01", "04.1"]
  provides: ["AE integration test", "DS integration test", "LOOKUP_RECODE bug fix"]
  affects: ["05-03", "05-04", "05-05", "05-06", "05-07"]
tech-stack:
  added: []
  patterns: ["multi-source column alignment", "checkbox-to-yn reformat"]
key-files:
  created:
    - tests/integration/execution/test_ae_execution.py
    - tests/integration/execution/test_ds_execution.py
  modified:
    - src/astraea/execution/pattern_handlers.py
decisions:
  - id: "D-05-02-01"
    description: "AE test uses submission_value inputs for LOOKUP_RECODE (already CT-coded source)"
  - id: "D-05-02-02"
    description: "DS test performs column alignment in fixture setup, not in test body"
  - id: "D-05-02-03"
    description: "Fixed preferred_term -> nci_preferred_term attribute name in LOOKUP_RECODE handler"
metrics:
  duration: "~3 min"
  completed: "2026-02-27"
---

# Phase 5 Plan 02: AE and DS Domain Integration Tests Summary

Integration tests proving AE (most complex non-transpose Event domain) and DS (multi-source merge) execute correctly through the DatasetExecutor pipeline. Fixed a pre-existing LOOKUP_RECODE bug that silently broke codelist recoding.

## One-liner

AE domain 14-test suite (checkbox Y/N, MedDRA, 4 CT codelists, dates, --SEQ) + DS domain 9-test suite (dual-source merge with column alignment)

## Completed Tasks

| Task | Name | Commit | Tests |
|------|------|--------|-------|
| 1 | AE domain integration test | e953577 | 14 |
| 2 | DS domain integration test | 4b7a0fa | 9 |

## What Was Built

### AE Domain Integration Test (14 tests)
- Tests 17 SDTM variables across all Event-class mapping patterns
- Checkbox 0/1 -> Y/N conversion via numeric_to_yn REFORMAT (AESDTH, AESLIFE, AESHOSP)
- MedDRA term mapping: AETERM_PT -> AEDECOD, AETERM_SOC -> AEBODSYS via RENAME
- CT codelist recodes: severity (C66769), serious (C66742), action taken (C66767), outcome (C66768)
- Date conversion: DD Mon YYYY -> ISO 8601 via parse_string_date_to_iso
- --SEQ generation with correct per-subject monotonic sequencing
- Column ordering, EDC column filtering, row count preservation

### DS Domain Integration Test (9 tests)
- Multi-source merge: ds (EOT) + ds2 (EOS) via align_multi_source_columns
- Column alignment: DSDECOD2 -> DSDECOD, DSDECOD2_STD -> DSDECOD_STD, DSENDAT2_RAW -> DSSTDAT_RAW
- DSCAT differentiation: DISPOSITION EVENT vs PROTOCOL MILESTONE
- CT codelist recode: disposition event (C66727)
- 6 rows from 2 sources with no NaN from mismatched column names

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed preferred_term -> nci_preferred_term in LOOKUP_RECODE handler**
- **Found during:** Task 1 (investigating why codelist recoding worked in DM test)
- **Issue:** `handle_lookup_recode` in pattern_handlers.py accessed `term.preferred_term` but the CodelistTerm model field is `nci_preferred_term`. Pydantic raises AttributeError, caught by executor's try/except, silently setting the column to None.
- **Impact:** All LOOKUP_RECODE mappings were silently broken. The DM test appeared to pass because `set() <= {"M", "F"}` is vacuously true.
- **Fix:** Changed `term.preferred_term` to `term.nci_preferred_term` on line 138 of pattern_handlers.py
- **Files modified:** src/astraea/execution/pattern_handlers.py
- **Commit:** e953577

## Test Results

- New tests: 23 (14 AE + 9 DS)
- Full suite: 1011 passed, 15 skipped, 0 failed

## Success Criteria Verification

- [x] AE seriousness checkbox 0.0/1.0 values correctly convert to "N"/"Y" via numeric_to_yn REFORMAT
- [x] AE MedDRA terms (AETERM_PT, AETERM_SOC) correctly map to AEDECOD, AEBODSYS
- [x] AE codelist recodes (severity, action taken, outcome) produce valid CT submission values
- [x] DS multi-source merge produces 6 rows (3+3) with no NaN from column misalignment
- [x] DS DSCAT correctly differentiates EOT vs EOS records
- [x] Both domains have --SEQ, correct column order, no EDC column leakage
