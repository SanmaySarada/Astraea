---
phase: 12-validation-severity-fixes
verified: 2026-02-28T18:05:09Z
status: passed
score: 9/9 must-haves verified
---

# Phase 12: Validation Severity Fixes Verification Report

**Phase Goal:** Add missing validation rules and fix severity misclassifications so the validation engine catches real FDA submission issues and doesn't cry wolf on false positives.
**Verified:** 2026-02-28T18:05:09Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | FDAB057 (ETHNIC) fires as ERROR, not WARNING | VERIFIED | `src/astraea/validation/rules/fda_business.py` line 36: `severity: RuleSeverity = RuleSeverity.ERROR` on FDAB057Rule |
| 2 | ASTR-F002 (ASCII) fires as ERROR, not WARNING | VERIFIED | `src/astraea/validation/rules/format.py` line 104: `severity: RuleSeverity = RuleSeverity.ERROR` on ASCIIRule |
| 3 | DM.SEX validated against C66731 non-extensible codelist | VERIFIED | `FDAB015Rule` class (lines 392-461) looks up `ct_ref.lookup_codelist("C66731")`, checks SEX values against valid terms, fires ERROR for invalid values |
| 4 | --SEQ uniqueness enforced per USUBJID within each domain | VERIFIED | `SeqUniquenessRule` (lines 225-282) uses `domain[:2]` prefix for SEQ col, groups by USUBJID, checks for duplicates, p21_equivalent="SD0007" |
| 5 | DM validated to have exactly one record per USUBJID | VERIFIED | `DMOneRecordPerSubjectRule` (lines 285-333) checks domain=="DM", detects duplicate USUBJIDs via `duplicated(keep=False)` |
| 6 | FDA_REQUIRED_PARAMS contains 26+ TS parameter codes | VERIFIED | Runtime check confirms 26 entries including PLANSUB, RANDOM, SEXPOP, TBLIND, TCNTRL, OBJPRIM, etc. |
| 7 | TRC checks verify SDTMVER, STYPE, TITLE (beyond just SSTDTC) | VERIFIED | `_TRC_REQUIRED_TS_PARAMS` frozenset contains all 4 params; `_check_ts_present()` loops over all 4 with per-param rule_ids |
| 8 | TRCPreCheck integrated into validate_all() | VERIFIED | `engine.py` lines 253-260: lazy import of TRCPreCheck, invoked when both `output_dir` and `study_id` provided, backward compatible |
| 9 | All existing tests pass + new tests for each rule/fix | VERIFIED | 1685 passed, 119 skipped, 0 failures across full test suite |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/astraea/validation/rules/fda_business.py` | FDAB057 severity=ERROR, FDAB015Rule for DM.SEX | VERIFIED | 474 lines, FDAB057 severity=ERROR (line 36), FDAB015Rule class (lines 392-461), registered in get_fda_business_rules() (line 469) |
| `src/astraea/validation/rules/format.py` | ASTR-F002 severity=ERROR | VERIFIED | 199 lines, ASCIIRule severity=ERROR (line 104) |
| `src/astraea/validation/rules/presence.py` | SeqUniquenessRule + DMOneRecordPerSubjectRule | VERIFIED | 346 lines, SeqUniquenessRule ASTR-P005 (line 225), DMOneRecordPerSubjectRule ASTR-P006 (line 285), both registered in get_presence_rules() (lines 341-345) |
| `src/astraea/execution/trial_summary.py` | FDA_REQUIRED_PARAMS with 26+ entries | VERIFIED | 275 lines, frozenset with 26 entries (lines 26-57), documented source |
| `src/astraea/validation/rules/fda_trc.py` | _TRC_REQUIRED_TS_PARAMS with 4 params, loop-based checking | VERIFIED | 240 lines, frozenset with SSTDTC/SDTMVER/STYPE/TITLE (line 19), _check_ts_present loops over all 4 (lines 122-149) |
| `src/astraea/validation/engine.py` | validate_all() with optional output_dir/study_id for TRC | VERIFIED | 291 lines, keyword-only params (lines 220-221), lazy TRCPreCheck import (line 255), backward compatible |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| fda_business.py | get_fda_business_rules() | FDAB015Rule() in return list | WIRED | Line 469: `FDAB015Rule()` included in factory function |
| presence.py | get_presence_rules() | SeqUniquenessRule() + DMOneRecordPerSubjectRule() | WIRED | Lines 343-344: both rules in factory return list |
| engine.py | fda_trc.py | TRCPreCheck instantiation in validate_all() | WIRED | Lines 255-260: lazy import + TRCPreCheck().check_all() invocation |
| engine.py | register_defaults() | All rule modules imported | WIRED | Lines 64-132: presence, format, fda_business all imported and registered |

### Requirements Coverage

| Requirement ID | Description | Status |
|----------------|-------------|--------|
| HIGH-07 | DM.SEX codelist validation (C66731) | SATISFIED |
| HIGH-08 | --SEQ uniqueness check (SD0007) | SATISFIED |
| HIGH-09 | FDAB057 (ETHNIC) severity corrected to ERROR | SATISFIED |
| HIGH-06 | FDA-mandatory TS parameters expanded to 26+ | SATISFIED |
| HIGH-16 | TRC checks expanded to SDTMVER, STYPE, TITLE | SATISFIED |
| MED-01 | ASTR-F002 (ASCII) severity corrected to ERROR | SATISFIED |
| MED-04 | TRCPreCheck integrated into validate_all() | SATISFIED |
| MED-05 | DM one-record-per-subject validation | SATISFIED |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | - | - | - | No anti-patterns detected |

No TODO, FIXME, placeholder, or stub patterns found in any modified files.

### Human Verification Required

None. All changes are deterministic validation rules verifiable through automated tests. No visual, real-time, or external service components.

### Gaps Summary

No gaps found. All 9 success criteria from the ROADMAP are verified in the actual codebase:

1. FDAB057 and ASTR-F002 severity both corrected from WARNING to ERROR
2. Three new rules (FDAB015, ASTR-P005, ASTR-P006) implemented with substantive logic, not stubs
3. All three new rules registered in their factory functions and picked up by the engine
4. FDA_REQUIRED_PARAMS expanded to exactly 26 entries with documented source
5. TRC checks expanded from 1 param (SSTDTC) to 4 params with per-param rule_ids
6. TRCPreCheck integrated into validate_all() with backward-compatible keyword-only params
7. Full test suite passes: 1685 passed, 119 skipped, 0 failures

---

_Verified: 2026-02-28T18:05:09Z_
_Verifier: Claude (gsd-verifier)_
