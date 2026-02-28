---
phase: 11-execution-contract
plan: 03
subsystem: execution
tags: [prompt-vocabulary, column-resolution, executor-kwargs, cross-domain, ecrf-aliases]

# Dependency graph
requires:
  - phase: 11-execution-contract plan 02
    provides: "Derivation rule parser, handler dispatch table, column resolution"
provides:
  - "Constrained LLM prompt with 10-keyword derivation rule vocabulary"
  - "Executor-level column alias building and resolution before handler dispatch"
  - "Cross-domain DataFrame passing via handler kwargs"
  - "resolved_source kwarg for handle_direct/rename/reformat/lookup_recode"
affects: [11-execution-contract plan 04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Derivation Rule Vocabulary table in system prompt constrains LLM output"
    - "Executor builds column_aliases and passes through handler_kwargs"
    - "resolved_source kwarg allows handlers to use aliased columns without mutating mapping"

key-files:
  created:
    - tests/unit/mapping/test_prompts_vocabulary.py
    - tests/unit/execution/test_executor_resolution.py
  modified:
    - src/astraea/mapping/prompts.py
    - src/astraea/execution/executor.py
    - src/astraea/execution/pattern_handlers.py

key-decisions:
  - "LLM prompt contains formal vocabulary table with all 10 keywords and examples"
  - "MAPPING_USER_INSTRUCTIONS references vocabulary instead of vague pseudo-code DSL"
  - "Executor builds column_aliases via _build_column_aliases static method"
  - "cross_domain_dfs populated from raw_dfs entries not in spec.source_datasets"
  - "resolved_source passed through kwargs -- mapping object never mutated"

patterns-established:
  - "Prompt-to-handler contract: vocabulary in prompt matches _DERIVATION_DISPATCH keys"
  - "Pre-handler alias resolution: executor resolves before handler sees the mapping"

# Metrics
duration: 5min
completed: 2026-02-28
---

# Phase 11 Plan 03: Prompt Vocabulary and Column Resolution Summary

**Constrained LLM system prompt with formal 10-keyword derivation rule vocabulary, plus executor-level column alias resolution for eCRF -> SAS name mapping (SSUBJID -> Subject, SSITENUM -> SiteNumber)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-28T16:04:43Z
- **Completed:** 2026-02-28T16:10:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added formal Derivation Rule Vocabulary section to MAPPING_SYSTEM_PROMPT with all 10 recognized keywords, usage descriptions, and examples
- Updated MAPPING_USER_INSTRUCTIONS to reference vocabulary instead of vague "pseudo-code DSL"
- Added _build_column_aliases method to DatasetExecutor for eCRF -> SAS name resolution
- Executor now passes column_aliases and cross_domain_dfs through handler kwargs
- Added resolved_source pre-handler resolution in _apply_mapping
- Updated handle_direct, handle_rename, handle_reformat, handle_lookup_recode to use resolved_source
- All 1645 existing tests continue to pass (119 skipped)

## Task Commits

Each task was committed atomically:

1. **Task 1: Constrain LLM prompt with derivation rule vocabulary** - `0e51f63` (feat)
2. **Task 2: Add column name resolution to executor** - `01a8ac7` (feat)

## Files Created/Modified
- `src/astraea/mapping/prompts.py` - Added vocabulary section to system prompt, updated user instructions
- `src/astraea/execution/executor.py` - Added _build_column_aliases, column_aliases/cross_domain_dfs in kwargs, resolved_source in _apply_mapping
- `src/astraea/execution/pattern_handlers.py` - Updated handle_direct, handle_rename, handle_reformat, handle_lookup_recode for resolved_source
- `tests/unit/mapping/test_prompts_vocabulary.py` - 8 tests for vocabulary and instruction content
- `tests/unit/execution/test_executor_resolution.py` - 8 tests for alias building, name resolution, cross-domain passing

## Decisions Made
- [D-11-03-01] Wildcard "*" checked explicitly alongside null in known_false_positives -- null means "match all" preserved
- [D-11-03-02] Executor resolves source_variable through alias map BEFORE handler dispatch -- handlers get resolved_source in kwargs
- [D-11-03-03] cross_domain_dfs populated from raw_dfs keys not in spec.source_datasets -- zero-config for callers

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- LLM prompt now constrains derivation rule output to recognized vocabulary
- Executor resolves eCRF names before handlers run -- SSUBJID -> Subject works end-to-end
- column_aliases and cross_domain_dfs flow through to all pattern handlers
- Ready for Plan 04 (end-to-end integration testing)

---
*Phase: 11-execution-contract*
*Completed: 2026-02-28*
