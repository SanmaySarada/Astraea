---
phase: 12-validation-severity-fixes
plan: 01
subsystem: validation
tags: [sdtm, fda, validation, severity, controlled-terminology, presence-rules]

# Dependency graph
requires:
  - phase: 07-validation-submission
    provides: Validation engine with FDA business rules and presence rules
provides:
  - FDAB057 severity corrected to ERROR
  - ASTR-F002 severity corrected to ERROR
  - FDAB015Rule for DM.SEX C66731 validation
  - SeqUniquenessRule (ASTR-P005) for --SEQ per USUBJID
  - DMOneRecordPerSubjectRule (ASTR-P006)
affects: [12-validation-severity-fixes remaining plans, autofix classification]

# Tech tracking
tech-stack:
  added: []
  patterns: [domain-prefixed SEQ column detection using domain[:2] prefix]

key-files:
  created: []
  modified:
    - src/astraea/validation/rules/fda_business.py
    - src/astraea/validation/rules/format.py
    - src/astraea/validation/rules/presence.py
    - tests/unit/validation/test_fda_rules.py
    - tests/unit/validation/test_limit_format_rules.py
    - tests/unit/validation/test_presence_rules.py

key-decisions:
  - "FDAB057 (ETHNIC) and ASTR-F002 (ASCII) promoted to ERROR severity -- non-extensible CT violations and non-ASCII data cause FDA findings/data corruption"
  - "FDAB015 validates DM.SEX against C66731 non-extensible codelist with ERROR severity"
  - "SeqUniquenessRule uses domain[:2] prefix for SEQ column name (matches existing FDAB039 pattern)"
  - "DMOneRecordPerSubjectRule counts unique duplicated subjects for affected_count"

patterns-established:
  - "Domain-prefixed variable detection: f\"{domain[:2]}SEQ\" for per-domain column resolution"

# Metrics
duration: 3min
completed: 2026-02-28
---

# Phase 12 Plan 01: Validation Severity Fixes Summary

**2 severity corrections (FDAB057/ASTR-F002 WARNING->ERROR) + 3 new validation rules (DM.SEX C66731, --SEQ uniqueness, DM one-record-per-subject)**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-28T17:53:45Z
- **Completed:** 2026-02-28T17:57:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Fixed FDAB057 (ETHNIC) and ASTR-F002 (ASCII) severity from WARNING to ERROR -- both are real FDA submission issues
- Added FDAB015Rule validating DM.SEX against non-extensible codelist C66731 (M, F, U, UNDIFFERENTIATED)
- Added SeqUniquenessRule (ASTR-P005) checking --SEQ uniqueness per USUBJID with domain-prefixed column detection
- Added DMOneRecordPerSubjectRule (ASTR-P006) enforcing exactly one DM record per subject
- All 235 validation tests passing with 14 new tests added

## Task Commits

Each task was committed atomically:

1. **Task 1: Severity fixes (FDAB057 and ASTR-F002) + DM.SEX rule** - `86169c6` (fix)
2. **Task 2: SEQ uniqueness and DM one-record-per-subject rules** - `ef6a857` (feat)

## Files Created/Modified
- `src/astraea/validation/rules/fda_business.py` - FDAB057 severity fix + new FDAB015Rule for DM.SEX
- `src/astraea/validation/rules/format.py` - ASTR-F002 severity fix WARNING->ERROR
- `src/astraea/validation/rules/presence.py` - SeqUniquenessRule + DMOneRecordPerSubjectRule
- `tests/unit/validation/test_fda_rules.py` - Updated FDAB057 assertion + 5 new FDAB015 tests
- `tests/unit/validation/test_limit_format_rules.py` - Updated ASCII rule severity assertion
- `tests/unit/validation/test_presence_rules.py` - 9 new tests for ASTR-P005 and ASTR-P006

## Decisions Made
- [D-12-01-01] FDAB057 (ETHNIC) promoted to ERROR: C66790 is non-extensible, invalid values are submission errors
- [D-12-01-02] ASTR-F002 (ASCII) promoted to ERROR: non-ASCII characters cause XPT data corruption, not just warnings
- [D-12-01-03] SeqUniquenessRule uses domain[:2] prefix (AE->AESEQ, LB->LBSEQ) matching existing FDAB039 pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 3 new rules registered in factory functions (get_fda_business_rules, get_presence_rules)
- Validation engine will automatically pick up new rules via register_defaults()
- Ready for remaining 12-02 and 12-03 plans

---
*Phase: 12-validation-severity-fixes*
*Completed: 2026-02-28*
