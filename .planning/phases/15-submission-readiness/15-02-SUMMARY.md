---
phase: 15-submission-readiness
plan: 02
subsystem: submission
tags: [csdrg, ectd, submission-artifacts, fda]
depends_on:
  requires: [15-01]
  provides: [csdrg-content-generation, ectd-assembly]
  affects: [15-03]
tech_stack:
  added: []
  patterns: [jinja2-template-rendering, ectd-directory-convention]
key_files:
  created:
    - src/astraea/submission/ectd.py
    - tests/unit/submission/test_csdrg_content.py
    - tests/unit/submission/test_ectd_structure.py
  modified:
    - src/astraea/submission/csdrg.py
decisions:
  - id: D15-02-01
    decision: "cSDRG Section 2 uses TS parameter codes (TITLE, TPHASE, INDIC, etc.) with [Not specified] fallback"
    rationale: "Standard TS parameters are the canonical source of study metadata"
  - id: D15-02-02
    decision: "cSDRG placed at tabulations/ level, not sdtm/ level, per FDA guidance"
    rationale: "FDA eCTD guidance places reviewer guides at the tabulations level"
  - id: D15-02-03
    decision: "SUPPQUAL justification text includes IG version reference and SUPP{DOMAIN} naming"
    rationale: "Reviewers need to see why each variable was placed in SUPPQUAL"
metrics:
  duration: "~6 min"
  completed: "2026-02-28"
---

# Phase 15 Plan 02: cSDRG Content and eCTD Assembly Summary

**One-liner:** Auto-generated cSDRG Sections 2/6/8 from TS params, validation findings, and SUPPQUAL metadata; eCTD m5/ directory assembly with FDA naming enforcement.

## What Was Done

### Task 1: cSDRG Sections 2, 6, and 8

Enhanced `generate_csdrg()` with three new content generators:

- **Section 2 (Study Description):** `_generate_study_description()` builds a narrative paragraph from TS parameters (TITLE, TPHASE, INDIC, TBLIND, TCNTRL, NARMS, PLANSUB, OBJPRIM). Falls back to placeholder when no TS params provided. Added `ts_params` parameter to `generate_csdrg()`.

- **Section 6 (Known Data Issues):** `_generate_known_data_issues()` groups unresolved ERROR-level validation findings by domain, excluding known false positives. Shows "No unresolved data quality issues" when clean.

- **Section 8 (Non-Standard Variables):** `_build_suppqual_justifications()` generates per-variable justification text for each SUPPQUAL candidate, including source dataset, IG version reference, SUPP{DOMAIN} naming, and data origin (CRF/Derived).

15 tests covering all three sections.

### Task 2: eCTD Directory Structure Assembly

Created `src/astraea/submission/ectd.py` with:

- `assemble_ectd_package()` -- creates `m5/datasets/tabulations/sdtm/` tree, copies XPT files with lowercase renaming, places define.xml in sdtm/ and cSDRG at tabulations/ level
- `validate_xpt_filename()` -- checks FDA naming conventions (lowercase, alphanumeric + underscore, .xpt extension), returns corrected name

15 tests covering directory structure, file copying, renaming, edge cases.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing RuleResult import in csdrg.py**
- **Found during:** Task 1
- **Issue:** `_generate_known_data_issues` used `RuleResult` in type annotation but it was not imported
- **Fix:** Added `RuleResult` to the existing `from astraea.validation.rules.base` import
- **Commit:** 5201274

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D15-02-01 | TS parameter codes for Section 2 | Standard TS params are canonical study metadata source |
| D15-02-02 | cSDRG at tabulations/ level | FDA eCTD guidance placement |
| D15-02-03 | Per-variable SUPPQUAL justification includes IG version | Regulatory reviewers need explicit justification |

## Test Results

- 30 new tests (15 cSDRG content + 15 eCTD structure)
- 1943 total tests passing, 119 skipped
- 1 pre-existing integration test failure (define_xml_integration -- unrelated)
