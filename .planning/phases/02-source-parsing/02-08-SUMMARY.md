---
phase: 02-source-parsing
plan: 08
subsystem: parsing
tags: [ecrf, pdf, error-handling, cli, resilience]

# Dependency graph
requires:
  - phase: 02-source-parsing (plans 02, 05)
    provides: ecrf_parser.py and CLI parse-ecrf command
provides:
  - Resilient eCRF parse loop that survives per-form failures
  - Single-pass PDF extraction in CLI (no double extraction)
  - pre_extracted_pages parameter on parse_ecrf()
affects: [03-core-mapping]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "try/except with empty-field placeholder for failed LLM extractions"
    - "Pre-extracted data passthrough to avoid redundant I/O"

key-files:
  created: []
  modified:
    - src/astraea/parsing/ecrf_parser.py
    - src/astraea/cli/app.py
    - tests/test_parsing/test_ecrf_parser.py
    - tests/test_cli/test_parse_ecrf.py

key-decisions:
  - "D-0208-01: Failed forms get empty-field ECRFForm placeholder (not silently dropped)"
  - "D-0208-02: pre_extracted_pages parameter avoids redundant PDF extraction"

patterns-established:
  - "Resilient LLM loop: try/except per-item with loguru warning and placeholder result"

# Metrics
duration: 3min
completed: 2026-02-27
---

# Phase 2 Plan 8: eCRF Parse Resilience and CLI Single Extraction Summary

**Resilient eCRF parse loop with per-form error handling and single-pass PDF extraction in CLI**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T03:33:39Z
- **Completed:** 2026-02-27T03:37:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Single form extraction failure no longer crashes the entire 189-page eCRF pipeline
- Failed forms logged as warnings and included as empty-field placeholders for traceability
- CLI parse-ecrf command extracts PDF exactly once (eliminated redundant extraction)
- All 379 tests passing (15 parser + 9 CLI + existing suite)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add try/except in parse_ecrf loop and refactor for pre-extracted pages** - `49ca616` (feat)
2. **Task 2: Fix double PDF extraction in CLI parse-ecrf command** - `9138298` (fix)

## Files Created/Modified
- `src/astraea/parsing/ecrf_parser.py` - Added try/except around extract_form_fields, added pre_extracted_pages parameter
- `src/astraea/cli/app.py` - Pass pre_extracted_pages to parse_ecrf() to avoid double extraction
- `tests/test_parsing/test_ecrf_parser.py` - Added tests for form failure resilience and pre-extraction bypass
- `tests/test_cli/test_parse_ecrf.py` - Added test verifying single PDF extraction

## Decisions Made
- [D-0208-01] Failed forms produce empty-field ECRFForm placeholders rather than being silently dropped -- ensures the caller knows which forms were attempted and which failed
- [D-0208-02] pre_extracted_pages accepts the same dict-list format returned by extract_ecrf_pages, keeping the interface consistent

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test mock strategy for form failure test**
- **Found during:** Task 1 (writing tests)
- **Issue:** Initial mock approach using client.parse side_effect with content inspection failed because the ECRF_EXTRACTION_PROMPT format made content matching unreliable
- **Fix:** Mocked extract_form_fields directly instead of client.parse for cleaner per-form control
- **Files modified:** tests/test_parsing/test_ecrf_parser.py
- **Verification:** Test correctly validates one form succeeds and one fails
- **Committed in:** 49ca616

**2. [Rule 1 - Bug] Fixed SIM108 lint violation**
- **Found during:** Task 2 (verification)
- **Issue:** ruff flagged if/else block that should be a ternary
- **Fix:** Replaced if/else with ternary operator for pre_extracted_pages check
- **Files modified:** src/astraea/parsing/ecrf_parser.py
- **Committed in:** 9138298

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Minor test approach adjustment and lint fix. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Gap 3 (form failure resilience) and Gap 6 (double extraction) from UAT are now closed
- eCRF parsing pipeline is production-ready for 189-page PDFs with mixed form quality
- Ready for remaining gap closure plans (07, 09-11) or Phase 3

---
*Phase: 02-source-parsing*
*Completed: 2026-02-27*
