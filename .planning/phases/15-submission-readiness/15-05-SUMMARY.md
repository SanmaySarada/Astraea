---
phase: 15-submission-readiness
plan: 05
subsystem: validation
tags: [fda-business-rules, sdtm-validation, ae-rules, cross-domain]
dependency-graph:
  requires: [04.1-fda-compliance]
  provides: [expanded-fda-business-rules, ae-validation, cross-domain-checks]
  affects: [15-06]
tech-stack:
  added: []
  patterns: [domain-scoped-rules, compiled-regex-validation, iso-8601-pattern]
key-files:
  created:
    - tests/unit/validation/test_expanded_fdab_rules.py
  modified:
    - src/astraea/validation/rules/fda_business.py
    - tests/unit/validation/test_fda_rules.py
decisions:
  - id: D-1505-01
    description: "All 14 new rules implemented in single commit since Task 1 and Task 2 overlap"
    rationale: "The plan's task split (AE+domain in T1, cross-domain in T2) shares the same files and pattern; atomic implementation is cleaner"
metrics:
  duration: ~13 min
  completed: 2026-02-28
---

# Phase 15 Plan 05: Expanded FDA Business Rules Summary

Expanded FDA Business Rules from 7 to 21 rules covering AE CT validation, DM country codes, CM/EX treatment names, cross-domain VISITNUM/DY/DTC checks, LB paired results, and population flag rejection.

## What Was Done

### Task 1+2: All 14 New FDAB Rules (commit 9181e05)

Added 14 new ValidationRule subclasses to `fda_business.py`:

**AE Domain (5 rules):**
- FDAB001: AESER must be Y or N (ERROR)
- FDAB002: AEREL must use causality CT (ERROR)
- FDAB003: AEOUT must use CT C101854 (ERROR)
- FDAB004: AEACN must use action taken CT (ERROR)
- FDAB005: AESTDTC must not be after AEENDTC (WARNING -- partial dates skipped)

**DM Domain (1 rule):**
- FDAB016: COUNTRY must use ISO 3166-1 alpha-3 codes (WARNING)

**CM/EX Domain (2 rules):**
- FDAB025: CMTRT must not be null/blank (ERROR)
- FDAB026: EXTRT must not be null/blank (ERROR)

**Cross-Domain (3 rules):**
- FDAB020: VISITNUM must be numeric (ERROR, any domain)
- FDAB021: --DY must not include Day 0 (ERROR, any DY column)
- FDAB022: --DTC must be ISO 8601 (ERROR, compiled regex)

**LB Paired Results (2 rules):**
- FDAB035: LBORRES/LBORRESU must be paired (WARNING)
- FDAB036: LBSTRESN/LBSTRESU must be paired (WARNING)

**Population Flags (1 rule):**
- FDAB-POP: Population flags must not appear in DM (ERROR)

### Test Coverage
- 46 new tests in `test_expanded_fdab_rules.py`
- Each rule tested: valid data passes, invalid data fires, domain scoping correct
- FDAB005 tested with partial dates (skipped correctly)
- All 2022 tests passing across full suite

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-1505-01 | Combined Task 1 and Task 2 into single implementation | Both tasks modify the same file with the same pattern; no benefit to splitting commits |

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- `pytest tests/unit/validation/test_expanded_fdab_rules.py -v`: 46/46 passed
- `pytest tests/unit/validation/test_fda_rules.py -v`: 40/40 passed
- `ruff check src/astraea/validation/rules/fda_business.py`: All checks passed
- `get_fda_business_rules()` returns 21 rules
- Full suite: 2022 passed, 119 skipped (1 pre-existing integration failure unrelated)

## Success Criteria Verification

- [x] 20+ total FDAB rules (21: 7 original + 14 new)
- [x] AE rules validate AESER, AEREL, AEOUT, AEACN, date ordering
- [x] Cross-domain rules validate VISITNUM, DY, DTC, paired results
- [x] Domain-specific rules validate CMTRT, EXTRT, COUNTRY
- [x] Population flags rejected from DM
- [x] ERROR severity for definitive violations; WARNING for FDAB005, FDAB016, FDAB035, FDAB036
- [x] All existing tests pass
