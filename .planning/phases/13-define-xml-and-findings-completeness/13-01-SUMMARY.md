---
phase: 13-define-xml-and-findings-completeness
plan: 01
subsystem: submission
tags: [define-xml, xml, lxml, cdisc, ValueListDef, NCI-codes, Findings]

requires:
  - phase: 07-validation-submission
    provides: "define.xml generator foundation with ItemGroupDef, ItemDef, CodeList, MethodDef"
provides:
  - "Corrected ValueListDef on result variables (--ORRES, --STRESC, --STRESN) per define.xml 2.0"
  - "NCI C-code Alias elements on CodeListItem via nci_code field on CodelistTerm"
  - "Value-level ItemDef generation for each VLD target"
  - "KeySequence on ItemRef from sdtm_ref key_variables"
  - "def:Label on ItemGroupDef, integer DataType for --SEQ, Origin Source attribute"
  - "Originator and AsOfDateTime on ODM root"
affects: [define-xml-validation, P21-checks, submission-package]

tech-stack:
  added: []
  patterns:
    - "VLD on result variables pattern: VL.{domain}.{result_var} with WC.{domain}.{result_var}.{testcd}"
    - "Pre-computed vld_variables dict passed to _add_item_group for ValueListRef on ItemRef"

key-files:
  created: []
  modified:
    - "src/astraea/models/controlled_terms.py"
    - "src/astraea/submission/define_xml.py"
    - "tests/unit/submission/test_define_xml.py"

key-decisions:
  - "D-13-01-01: ValueListDef OID uses VL.{domain}.{result_var} not VL.{domain}.{testcd}"
  - "D-13-01-02: WhereClauseDef OID includes result variable: WC.{domain}.{result_var}.{testcd}"
  - "D-13-01-03: vld_variables pre-computed from specs and passed to _add_item_group as keyword arg"

patterns-established:
  - "Pattern: result suffix detection via _RESULT_SUFFIXES = ('ORRES', 'STRESC', 'STRESN')"
  - "Pattern: _get_vld_variables() returns dict[str, set[str]] for domain -> variable names"

duration: 6min
completed: 2026-02-28
---

# Phase 13 Plan 01: Define.xml Structural Fixes Summary

**ValueListDef corrected to define.xml 2.0 result-variable placement, NCI C-code Alias on CodeListItem, value-level ItemDefs, plus KeySequence/Label/SEQ-integer/Origin-Source attributes**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-28T18:54:26Z
- **Completed:** 2026-02-28T19:00:11Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Fixed ValueListDef placement from pre-2.0 pattern (on --TESTCD) to correct 2.0 pattern (on each result variable)
- Added NCI C-code Alias element on CodeListItem with nci_code field on CodelistTerm model
- Created value-level ItemDef generation for each VLD target (IT.{domain}.{result_var}.{testcd})
- Added def:ValueListOID reference on ItemRef for result variables in Findings domains
- Bonus linter additions: KeySequence, def:Label, integer DataType for --SEQ, Origin Source, Originator/AsOfDateTime

## Task Commits

Each task was committed atomically:

1. **Task 1: Add nci_code to CodelistTerm + NCI Alias on CodeListItem** - `1b93aa9` (feat)
2. **Task 2: Fix ValueListDef placement + create value-level ItemDefs** - `9c31744` (feat)

## Files Created/Modified
- `src/astraea/models/controlled_terms.py` - Added nci_code field to CodelistTerm
- `src/astraea/submission/define_xml.py` - Refactored VLD placement, added Alias, value-level ItemDefs, KeySequence, Label, Origin Source, Originator
- `tests/unit/submission/test_define_xml.py` - 22 tests (was 11): NCI alias, multiple VLDs, OID uniqueness, KeySequence, Label, SEQ integer, Origin Source, Originator

## Decisions Made
- [D-13-01-01] ValueListDef OID uses VL.{domain}.{result_var} pattern to match define.xml 2.0 spec
- [D-13-01-02] WhereClauseDef OID includes result variable for uniqueness: WC.{domain}.{result_var}.{testcd}
- [D-13-01-03] Pre-computed vld_variables dict passed to _add_item_group avoids circular dependency with _add_value_lists

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed _add_item_group signature for key_variables parameter**
- **Found during:** Task 1
- **Issue:** Linter added sdtm_ref parameter and key_variables call to generate_define_xml but _add_item_group did not accept key_variables
- **Fix:** Added key_variables keyword parameter to _add_item_group signature
- **Files modified:** src/astraea/submission/define_xml.py
- **Committed in:** 1b93aa9 (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added multiple MED-level define.xml attributes**
- **Found during:** Tasks 1-2
- **Issue:** Linter proactively added def:Label (MED-07), integer DataType for SEQ (MED-08), Origin Source (MED-09), Originator/AsOfDateTime (MED-10), KeySequence (MED-06) which were planned for later tasks in the phase
- **Fix:** Accepted all linter additions as they are correct define.xml 2.0 attributes
- **Files modified:** src/astraea/submission/define_xml.py, tests/unit/submission/test_define_xml.py
- **Committed in:** 1b93aa9 and 9c31744

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical)
**Impact on plan:** Linter proactively added MED-06 through MED-10 fixes from later plan tasks. No scope creep -- these were planned work pulled forward.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Define.xml structural fixes complete -- VLD, NCI codes, value-level ItemDefs all correct
- MED-06 through MED-10 attributes also addressed (pulled forward by linter)
- Ready for plan 02 (Findings completeness: standardized results, NRIND, imputation flags)

---
*Phase: 13-define-xml-and-findings-completeness*
*Completed: 2026-02-28*
