---
phase: 11-execution-contract
plan: 02
subsystem: execution
tags: [derivation-rules, pattern-handlers, column-resolution, dsl-parser, race-checkbox, date-conversion]

# Dependency graph
requires:
  - phase: 04.1-fda-compliance
    provides: "Pattern handlers, DatasetExecutor, transform registry"
  - phase: 11-execution-contract plan 01
    provides: "Bug fixes for dates, wildcard matching, autofix classification"
provides:
  - "Formal derivation rule vocabulary parser (parse_derivation_rule)"
  - "13-keyword dispatch table (_DERIVATION_DISPATCH)"
  - "10+ handler functions for CONCAT, ISO8601_DATE, RACE_CHECKBOX, etc."
  - "Column name resolution layer (_resolve_column) with EDC alias fallback"
  - "Race checkbox column-to-CT-value extraction"
affects: [11-execution-contract plan 03, 11-execution-contract plan 04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Derivation rule DSL: KEYWORD(arg1, arg2) parsed by regex dispatcher"
    - "Column resolution chain: exact -> custom alias -> EDC alias -> case-insensitive"
    - "Handler source_variable fallback: when no args provided, use mapping.source_variable"

key-files:
  created:
    - tests/unit/execution/test_derivation_parser.py
    - tests/unit/execution/test_derivation_handlers.py
  modified:
    - src/astraea/execution/pattern_handlers.py

key-decisions:
  - "Handler functions take (df, args, mapping, **kwargs) -- args from parser, kwargs from executor"
  - "Bare keywords (no parens) dispatch too, using mapping.source_variable as fallback for column arg"
  - "RACE_CHECKBOX returns CDISC CT upper-case race names, not display names"
  - "Cross-domain date aggregation supported via kwargs['cross_domain_dfs']"
  - "13 keywords in dispatch including 3 aliases (RACE_FROM_CHECKBOXES, LAST_DISPOSITION_DATE, LAST_DISPOSITION_DATE_PER_SUBJECT)"

patterns-established:
  - "Derivation DSL pattern: KEYWORD(arg1, arg2) with dataset prefix stripping"
  - "Handler fallback chain: dispatch table -> legacy special-case -> transform registry -> None with warning"

# Metrics
duration: 9min
completed: 2026-02-28
---

# Phase 11 Plan 02: Derivation Rule Handlers Summary

**Formal derivation rule vocabulary parser with 13-keyword dispatch table covering CONCAT, ISO8601_DATE, RACE_CHECKBOX, MIN/MAX_DATE_PER_SUBJECT, and 7 more handlers -- the core fix for CRIT-02/CRIT-03 all-NULL derived columns**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-28T15:53:47Z
- **Completed:** 2026-02-28T16:02:49Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Implemented derivation rule parser that extracts keyword and args from KEYWORD(arg1, arg2) format with dataset prefix stripping
- Built column resolution helper with 4-level fallback chain (exact, custom alias, EDC alias, case-insensitive)
- Implemented 10 handler functions covering all DM-domain derivation needs plus general-purpose rules
- Updated handle_derivation, handle_reformat, and handle_combine to dispatch through parser before falling back to legacy paths
- All 1629 existing tests continue to pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Derivation rule parser and column resolution helper** - `f573a9b` (feat)
2. **Task 2: Implement all derivation rule handlers and dispatch** - `493aef5` (feat)

## Files Created/Modified
- `src/astraea/execution/pattern_handlers.py` - Added parser, resolver, 10 handler functions, dispatch table, updated 3 pattern handlers
- `tests/unit/execution/test_derivation_parser.py` - 20 tests for parser, column resolver, race extraction
- `tests/unit/execution/test_derivation_handlers.py` - 20 tests for all handler functions and dispatch integration

## Decisions Made
- [D-11-02-01] Handler functions fall back to mapping.source_variable when no args provided (supports bare keyword rules like "numeric_to_yn")
- [D-11-02-02] RACE_CHECKBOX returns CT upper-case race names (e.g., "WHITE", "MULTIPLE") per C74457
- [D-11-02-03] Cross-domain date aggregation uses kwargs["cross_domain_dfs"] dict -- deferred to executor to populate

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed SAS date test values**
- **Found during:** Task 2 (handler tests)
- **Issue:** Plan specified 22738 = 2022-03-30 but actual calculation is 22734 = 2022-03-30
- **Fix:** Corrected test values to use accurate SAS date numbers
- **Files modified:** tests/unit/execution/test_derivation_handlers.py
- **Committed in:** 493aef5

**2. [Rule 1 - Bug] Fixed numeric_to_yn NaN assertion**
- **Found during:** Task 2 (handler tests)
- **Issue:** pandas .map() converts None return to NaN; test asserted `is None`
- **Fix:** Changed assertion to use `pd.isna()`
- **Files modified:** tests/unit/execution/test_derivation_handlers.py
- **Committed in:** 493aef5

---

**Total deviations:** 2 auto-fixed (2 bugs in test expectations)
**Impact on plan:** Minimal -- test value corrections, no scope changes.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Derivation rule handlers are ready for prompt vocabulary constraint (Plan 03)
- Column resolution layer is ready for executor integration (Plan 04)
- All 10 rule keywords are tested and dispatch correctly

---
*Phase: 11-execution-contract*
*Completed: 2026-02-28*
