---
phase: 14-reference-data-and-transforms
plan: 02
subsystem: transforms
tags: [iso-8601, timezone, date-imputation, partial-dates, datetime-passthrough]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "Date conversion utilities and validation rules"
provides:
  - "ISO 8601 timezone offset support in validation"
  - "ISO datetime passthrough in parse_string_date_to_iso"
  - "HH:MM:SS seconds parsing for DD Mon YYYY format"
  - "impute_partial_date function with first/last/mid methods"
  - "impute_partial_date_with_flag combining imputation with DTF/TMF flags"
affects: [execution, validation, findings-domains]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Partial date imputation with calendar-aware last-day calculation"

key-files:
  created:
    - tests/unit/transforms/test_dates_phase14.py
    - tests/unit/transforms/test_imputation_phase14.py
  modified:
    - src/astraea/transforms/dates.py
    - src/astraea/validation/rules/format.py
    - src/astraea/transforms/imputation.py

key-decisions:
  - "D-14-02-01: ISO datetime passthrough check placed before YYYY-MM-DD check to match more specific pattern first"
  - "D-14-02-02: impute_partial_date returns date-only for YYYY/YYYY-MM inputs (no time appended unless time is partially present)"
  - "D-14-02-03: Timezone group placed inside T-group in validation regex so date-only strings cannot have timezone"

patterns-established:
  - "Partial date imputation: parse pattern, fill missing components based on method"

# Metrics
duration: 3min
completed: 2026-02-28
---

# Phase 14 Plan 02: Date/Time Fixes Summary

**ISO 8601 timezone validation, datetime passthrough, HH:MM:SS parsing, and partial date imputation with first/last/mid methods**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-28T19:52:10Z
- **Completed:** 2026-02-28T19:54:51Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- ISO 8601 validation regex now accepts timezone offsets (Z, +HH:MM, -HH:MM) only when time component present
- parse_string_date_to_iso passes through ISO datetime strings unchanged (avoids re-parsing already-valid data)
- DD Mon YYYY format now supports optional seconds (HH:MM:SS)
- impute_partial_date fills missing date/time components with configurable methods (first/last/mid)
- Leap-year-aware last-day calculation via calendar.monthrange

## Task Commits

Each task was committed atomically:

1. **Task 1: ISO 8601 timezone + datetime passthrough + HH:MM:SS** - `e6b8c57` (feat)
2. **Task 2: Date imputation functions** - `03b6f4f` (feat)

## Files Created/Modified
- `src/astraea/transforms/dates.py` - Added _PATTERN_ISO_DATETIME, HH:MM:SS support, ISO datetime passthrough
- `src/astraea/validation/rules/format.py` - Updated _ISO_8601_PATTERN with timezone offset support
- `src/astraea/transforms/imputation.py` - Added impute_partial_date and impute_partial_date_with_flag functions
- `tests/unit/transforms/test_dates_phase14.py` - 25 tests for date/time fixes
- `tests/unit/transforms/test_imputation_phase14.py` - 24 tests for imputation functions

## Decisions Made
- [D-14-02-01] ISO datetime passthrough check placed before YYYY-MM-DD check so the more specific pattern (with T and time) matches first
- [D-14-02-02] impute_partial_date returns date-only for YYYY and YYYY-MM inputs -- time is not appended unless a partial time component is already present (e.g., "2022-03-30T14")
- [D-14-02-03] Timezone group placed inside T-group in validation regex so "2022-03-30Z" (date with timezone but no time) correctly fails validation

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Date handling now complete for timezone-aware clinical data
- Imputation functions ready for use in execution pipeline when partial dates need filling
- 49 new tests added (25 + 24), all passing with no regressions in existing 74 transform tests

---
*Phase: 14-reference-data-and-transforms*
*Completed: 2026-02-28*
