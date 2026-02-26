---
phase: 02-source-parsing
plan: 03
subsystem: classification
tags: [heuristic, sdtm, domain-classification, filename-matching, variable-overlap]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "SDTMReference for variable specs, DatasetProfile for profiling output"
  - phase: 02-source-parsing (plan 01)
    provides: "HeuristicScore and classification models"
provides:
  - "score_by_filename() for filename-based domain scoring"
  - "score_by_variables() for SDTM-IG variable overlap scoring"
  - "compute_heuristic_scores() combining both sources"
  - "detect_merge_groups() for multi-file domain detection"
affects: [02-04-llm-classification, 02-05-cli-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Segment-boundary matching for filename patterns (prevents false positives)"
    - "Heuristic scoring as sanity check against LLM classification (Pitfall C1)"

key-files:
  created:
    - src/astraea/classification/__init__.py
    - src/astraea/classification/heuristic.py
    - tests/test_classification/__init__.py
    - tests/test_classification/test_heuristic.py
  modified: []

key-decisions:
  - "D-0203-01: Segment-boundary matching for filename contains-check to prevent false positives (e.g., 'da' in 'unknown_data')"
  - "D-0203-02: UNCLASSIFIED threshold at 0.3 -- scores below this trigger UNCLASSIFIED return"
  - "D-0203-03: Common identifiers (STUDYID, DOMAIN, USUBJID, SUBJID, SITEID) excluded from variable overlap"

patterns-established:
  - "Heuristic-first classification: deterministic scoring runs before any LLM involvement"
  - "Max-score merge: when multiple signal sources exist, take max per domain and combine signals"

# Metrics
duration: 3min
completed: 2026-02-26
---

# Phase 2 Plan 3: Heuristic Domain Scorer Summary

**Deterministic domain classifier using filename patterns (15 domains) and SDTM-IG variable overlap scoring with multi-file merge detection**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-26T21:54:57Z
- **Completed:** 2026-02-26T21:57:51Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments
- Filename heuristic covers all 15 standard SDTM domains with exact (1.0) and prefix/contains (0.7) scoring
- Variable overlap scorer compares clinical variables against SDTM-IG domain specs, excluding common identifiers
- Merge group detection identifies multi-file domains (lb_biochem + lb_hem -> LB)
- UNCLASSIFIED fallback for datasets with no strong heuristic signal (threshold 0.3)
- 29 tests passing without external dependencies

## Task Commits

Each task was committed atomically:

1. **Task 1: Filename and Variable Heuristic Scorers** - `3ae3769` (feat)

## Files Created/Modified
- `src/astraea/classification/__init__.py` - Package exports for heuristic functions
- `src/astraea/classification/heuristic.py` - Core heuristic scoring: filename patterns, variable overlap, merge detection
- `tests/test_classification/__init__.py` - Test package init
- `tests/test_classification/test_heuristic.py` - 29 tests covering all scoring scenarios

## Decisions Made
- [D-0203-01] Segment-boundary matching for filename contains-check: patterns like "da" only match at word boundaries (delimited by _ or -), preventing false positives like "da" matching inside "unknown_data"
- [D-0203-02] UNCLASSIFIED threshold set at 0.3 -- any dataset where no domain scores >= 0.3 returns UNCLASSIFIED
- [D-0203-03] Common identifiers (STUDYID, DOMAIN, USUBJID, SUBJID, SITEID) excluded from variable overlap to avoid every domain scoring high on shared variables

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed false positive filename matching on short patterns**
- **Found during:** Task 1 (initial test run)
- **Issue:** The contains-match logic for filenames matched "da" inside "unknown_data", producing a false positive DA domain match at score 0.7
- **Fix:** Added `_is_segment_match()` helper requiring pattern boundaries (underscore/hyphen or string edge) instead of bare substring matching
- **Files modified:** src/astraea/classification/heuristic.py
- **Verification:** "unknown_data.sas7bdat" now returns empty list, all 29 tests pass
- **Committed in:** 3ae3769 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential for correctness -- prevents noisy false positives in classification.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Heuristic scorer ready for integration with LLM-based classification (plan 02-04)
- Acts as deterministic sanity check against LLM domain proposals
- Merge groups can feed into DomainPlan construction

---
*Phase: 02-source-parsing*
*Completed: 2026-02-26*
