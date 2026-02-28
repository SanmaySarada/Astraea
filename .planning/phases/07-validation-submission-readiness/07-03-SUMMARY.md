---
phase: 07-validation-submission-readiness
plan: 03
subsystem: validation
tags: [cross-domain, fda, trc, consistency, business-rules]
requires: ["07-01"]
provides: ["cross-domain-validation", "fda-business-rules", "trc-prechecks"]
affects: ["07-04", "07-05"]
tech-stack:
  added: []
  patterns: ["cross-domain-validator-pattern", "submission-level-checks"]
key-files:
  created:
    - src/astraea/validation/rules/consistency.py
    - src/astraea/validation/rules/fda_business.py
    - src/astraea/validation/rules/fda_trc.py
    - tests/unit/validation/test_consistency_rules.py
    - tests/unit/validation/test_fda_rules.py
  modified:
    - src/astraea/validation/engine.py
    - tests/unit/validation/test_engine.py
decisions:
  - id: "D-07-03-01"
    decision: "CrossDomainValidator is a standalone class (not ValidationRule subclass) because it needs multi-domain access"
  - id: "D-07-03-02"
    decision: "TRCPreCheck is also standalone -- checks submission-level artifacts (define.xml, file naming), not per-domain data"
  - id: "D-07-03-03"
    decision: "get_consistency_rules() and get_fda_trc_rules() return empty lists since their validators are invoked directly by the engine"
metrics:
  duration: "~6 min"
  completed: "2026-02-28"
---

# Phase 7 Plan 3: Cross-Domain & FDA Validation Rules Summary

Cross-domain consistency validation with 5 rules, 5 FDA Business Rules, and FDA TRC pre-checks for submission readiness.

## What Was Built

### Cross-Domain Consistency Rules (VAL-03)

`CrossDomainValidator` with 5 rules that operate across all generated domains simultaneously:

- **ASTR-C001**: USUBJID consistency -- all USUBJIDs in every domain must exist in DM (P21 equivalent: SD0085, severity: ERROR)
- **ASTR-C002**: STUDYID consistency -- exactly one STUDYID across all domains (severity: ERROR)
- **ASTR-C003**: RFSTDTC vs EXSTDTC consistency -- RFSTDTC should equal earliest EXSTDTC per subject (severity: WARNING)
- **ASTR-C004**: DOMAIN column consistency -- each domain's DOMAIN column must contain only its domain code (severity: ERROR)
- **ASTR-C005**: Study day sign consistency -- positive --DY on/after RFSTDTC, negative before (severity: WARNING)

### FDA Business Rules

5 rules as `ValidationRule` subclasses (auto-registered in engine):

- **FDAB057**: DM.ETHNIC values vs CT codelist C66790 (WARNING)
- **FDAB055**: DM.RACE values vs CT codelist C74457 (WARNING)
- **FDAB039**: Normal range (ORNRLO/ORNRHI) must be numeric when STRESN populated -- Findings domains only (WARNING)
- **FDAB009**: TESTCD/TEST 1:1 relationship -- Findings domains only (ERROR)
- **FDAB030**: STRESU consistency per TESTCD -- Findings domains only (WARNING)

### FDA Technical Rejection Criteria

`TRCPreCheck` class with submission-level checks (all ERROR severity):

- **FDA-TRC-1736**: DM domain must be present
- **FDA-TRC-1734**: TS domain must be present with SSTDTC parameter
- **FDA-TRC-1735**: define.xml must exist in output directory
- **FDA-TRC-STUDYID**: STUDYID consistent across all domains
- **FDA-TRC-FILENAME**: Dataset filenames must be lowercase .xpt

### Engine Updates

- Added `validate_cross_domain()` method to ValidationEngine
- Updated `validate_all()` to run cross-domain checks after per-domain rules
- Updated engine tests to account for auto-registered default rules

## Test Summary

- 20 cross-domain consistency tests
- 31 FDA business + TRC tests
- 165 total validation tests passing (up from 31 in plan 07-01)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated engine tests for default rule loading**
- **Found during:** Verification step
- **Issue:** test_engine.py tests assumed no default rules would be loaded, but plan 07-02 rules now auto-register
- **Fix:** Updated `test_no_rules_initially` -> `test_default_rules_loaded`, made other tests filter by specific rule_id
- **Files modified:** tests/unit/validation/test_engine.py
- **Commit:** 0de1d4f

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-07-03-01 | CrossDomainValidator is standalone, not ValidationRule subclass | Needs `dict[str, DataFrame]` input, not single-domain evaluate() signature |
| D-07-03-02 | TRCPreCheck is standalone | Checks submission artifacts (filesystem paths), not domain data |
| D-07-03-03 | get_*_rules() return empty lists for cross-domain/TRC modules | Their validators are invoked directly by engine methods, not through per-domain rule registry |
