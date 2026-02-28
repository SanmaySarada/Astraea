---
phase: 15-submission-readiness
plan: 01
subsystem: execution-pipeline
tags: [split-pattern, horizontal-merge, findings-metadata, pattern-handlers]
depends_on:
  requires: [phase-06-findings-domains, phase-05-event-intervention]
  provides: [functional-split-handler, horizontal-merge, findings-metadata-passthrough]
  affects: [15-02, 15-03, 15-04]
tech-stack:
  added: []
  patterns: [derivation-rule-dispatch, key-based-merge, metadata-passthrough]
key-files:
  created:
    - tests/unit/execution/test_split_pattern.py
    - tests/unit/execution/test_merge_horizontal.py
    - tests/unit/execution/test_findings_metadata.py
  modified:
    - src/astraea/execution/pattern_handlers.py
    - src/astraea/execution/findings.py
decisions:
  - id: D15-01-01
    decision: "SPLIT handler dispatches on derivation_rule keyword (SUBSTRING/DELIMITER_PART/REGEX_GROUP) with fallback to source column copy"
    rationale: "Consistent with existing DERIVATION handler dispatch pattern; returning None on unrecognized rules caused downstream issues"
  - id: D15-01-02
    decision: "Horizontal merge uses pd.merge outer join on common key columns (USUBJID, VISITNUM, TESTCD)"
    rationale: "Key-based join preserves row relationships; outer join ensures no data loss from either source"
  - id: D15-01-03
    decision: "Metadata pass-through (SPEC/METHOD/FAST) only copies when source and output lengths match"
    rationale: "Length mismatch after executor processing means row alignment is uncertain; safer to skip than misalign"
metrics:
  duration: "~5 minutes"
  completed: "2026-02-28"
  tests_added: 34
  tests_total_after: 1018
---

# Phase 15 Plan 01: Execution Pipeline Gaps Summary

SPLIT pattern handler with SUBSTRING/DELIMITER_PART/REGEX_GROUP derivation rules, key-based horizontal merge for multi-source findings domains, and specimen/method/fasting metadata pass-through.

## What Was Done

### Task 1: SPLIT Pattern Handler (MED-11)

Replaced the stub `handle_split` that returned None for all inputs with a functional implementation supporting three derivation rule keywords:

- **SUBSTRING(col, start, end)**: Extract substring using Python slice notation
- **DELIMITER_PART(col, delimiter, index)**: Split string by delimiter and take Nth part
- **REGEX_GROUP(col, pattern, group_index)**: Extract regex capture group from string

Fallback behavior: unrecognized rules return the source column unchanged (not None), preventing downstream NaN cascades. No source data at all returns None series.

### Task 2: Key-Based Horizontal Merge (MED-12) + Findings Metadata (MED-13)

**Part A**: Added `merge_mode` parameter to `merge_findings_sources()`:
- `"concat"` (default): existing vertical concatenation behavior unchanged
- `"join"`: horizontal outer merge on common key columns (USUBJID, VISITNUM, domain-specific TESTCD)
- Overlapping non-key columns suffixed with source name to avoid collisions
- Falls back to concat if no common keys found

**Part B**: Added `_pass_through_findings_metadata()` for Expected Findings variables:
- `{domain}SPEC` from source columns matching SPEC/SPECIMEN/SAMPLE (case-insensitive)
- `{domain}METHOD` from METHOD/TESTMETHOD
- `{domain}FAST` from FAST/FASTING
- Only creates columns when matching source data exists; does not create empty columns
- Wired into `_derive_findings_variables` with source_df parameter for all three domain executors (LB, EG, VS)

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D15-01-01 | SPLIT dispatches on derivation_rule keyword with source column fallback | Consistent with DERIVATION handler pattern; None returns caused downstream issues |
| D15-01-02 | Horizontal merge uses outer join on common key columns | Preserves row relationships; no data loss |
| D15-01-03 | Metadata pass-through skips on length mismatch | Row alignment uncertain after executor processing |

## Test Results

- 15 new tests for SPLIT pattern (SUBSTRING, DELIMITER_PART, REGEX_GROUP, fallbacks)
- 6 new tests for horizontal merge (join mode, concat unchanged, single source)
- 13 new tests for findings metadata (SPEC, METHOD, FAST pass-through and edge cases)
- 34 total new tests
- 1018 unit tests passing (full regression clean)

## Next Phase Readiness

No blockers. The execution pipeline now handles all mapping patterns with functional implementations. The pre-existing integration test failure in `test_define_xml_multi_domain` is unrelated to this plan.
