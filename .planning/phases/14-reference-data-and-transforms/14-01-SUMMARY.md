---
phase: 14-reference-data-and-transforms
plan: 01
subsystem: reference
tags: [ct-codelists, sdtm-ig, controlled-terminology, reverse-lookup]

# Dependency graph
requires:
  - phase: 13-define-xml-findings
    provides: "Existing codelist and domain infrastructure"
provides:
  - "C66738 codelist with 28 FDA-required TSPARMCD values"
  - "Corrected C66789 variable mapping (LBSPCND)"
  - "Expanded C66742 with 8 additional variable mappings"
  - "VISITNUM/VISIT variables in PE and QS domains"
  - "Collision-safe reverse codelist lookup"
affects: [14-02, 14-03, 14-04, validation, trial-summary, findings-execution]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "dict[str, list[str]] for multi-codelist variable mappings"
    - "loguru warning on codelist collision during single-result lookup"

key-files:
  created:
    - "tests/unit/reference/test_controlled_terms_phase14.py"
  modified:
    - "src/astraea/data/ct/codelists.json"
    - "src/astraea/data/sdtm_ig/domains.json"
    - "src/astraea/reference/controlled_terms.py"
    - "tests/test_reference/test_controlled_terms.py"

key-decisions:
  - "D-14-01-01: C66738 terms use null nci_code (real C-codes require NCI EVS lookup)"
  - "D-14-01-02: Collision-safe lookup stores list[str] not str, returns first with warning"
  - "D-14-01-03: VISIT core designation set to Perm (matching LB pattern) while VISITNUM is Exp"

patterns-established:
  - "get_codelists_for_variable returns list for multi-codelist variables"

# Metrics
duration: 3min
completed: 2026-02-28
---

# Phase 14 Plan 01: Reference Data Fixes Summary

**C66738 TSPARMCD codelist with 28 FDA codes, C66789/C66742 variable mapping fixes, PE/QS VISITNUM additions, collision-safe reverse CT lookup**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-28T19:52:39Z
- **Completed:** 2026-02-28T19:56:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added C66738 (Trial Summary Parameter Code) with 28 FDA-required TSPARMCD values enabling TS domain validation
- Fixed C66789 mapping from LBSPEC to LBSPCND (Specimen Condition vs Specimen Type confusion)
- Expanded C66742 (No Yes Response) with 8 new variable mappings for CE, LB, VS, EG, DV, PE, IE domains
- Added VISITNUM and VISIT variables to PE and QS domains (previously missing, causing validation gaps)
- Made reverse codelist lookup collision-safe with list storage and loguru warning

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix codelists.json** - `edeb747` (feat)
2. **Task 2: Fix domains.json + controlled_terms.py + tests** - `44dce44` (feat)

## Files Created/Modified
- `src/astraea/data/ct/codelists.json` - Added C66738, fixed C66789/C66742 mappings
- `src/astraea/data/sdtm_ig/domains.json` - Added VISITNUM/VISIT to PE and QS
- `src/astraea/reference/controlled_terms.py` - Collision-safe reverse lookup with get_codelists_for_variable
- `tests/unit/reference/test_controlled_terms_phase14.py` - 28 new tests
- `tests/test_reference/test_controlled_terms.py` - Updated codelist count from 29 to 30

## Decisions Made
- C66738 terms use null nci_code since real NCI C-codes would require NCI EVS API lookup
- Reverse lookup uses dict[str, list[str]] internally; get_codelist_for_variable returns first match with loguru warning on collision
- VISIT set to Perm core designation matching LB domain pattern; VISITNUM set to Exp

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated codelist count test**
- **Found during:** Task 2 (test verification)
- **Issue:** test_total_codelist_count expected 29, now 30 after C66738 addition
- **Fix:** Updated assertion from 29 to 30
- **Files modified:** tests/test_reference/test_controlled_terms.py
- **Verification:** All tests pass
- **Committed in:** 44dce44 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary correction for test consistency. No scope creep.

## Issues Encountered
- Pre-existing failure in test_define_xml_integration.py::test_define_xml_multi_domain (ItemDef count mismatch due to value-level ItemDefs). Not related to this plan.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Reference data corrected and ready for Phase 14-02 (transform improvements)
- All 1859 tests passing (119 skipped, 1 pre-existing integration failure excluded)

---
*Phase: 14-reference-data-and-transforms*
*Completed: 2026-02-28*
