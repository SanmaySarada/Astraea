---
phase: 08-learning-system
plan: 03
subsystem: learning
tags: [ingestion, metrics, accuracy, sqlite, chromadb, review-pipeline]

# Dependency graph
requires:
  - phase: 08-01
    provides: "Learning data models (MappingExample, CorrectionRecord, StudyMetrics), ExampleStore, LearningVectorStore"
  - phase: 04-human-review-gate
    provides: "DomainReview, ReviewDecision, HumanCorrection, ReviewSession models"
provides:
  - "Ingestion pipeline (review -> learning stores) via ingest_domain_review and ingest_session"
  - "Accuracy metrics computation from review decisions"
  - "Improvement tracking across studies per domain"
affects: [08-04-cli-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deterministic IDs for idempotent ingestion (study_id + domain + variable)"
    - "Dual-store ingestion pattern (SQLite structured + ChromaDB vector simultaneously)"

key-files:
  created:
    - src/astraea/learning/metrics.py
    - src/astraea/learning/ingestion.py
    - tests/unit/learning/test_metrics.py
    - tests/unit/learning/test_ingestion.py
  modified: []

key-decisions:
  - "D-08-03-01: Deterministic example_id as f'{study_id}_{domain}_{sdtm_variable}' for idempotent ingestion"
  - "D-08-03-02: was_corrected flag derived from review decisions (excludes REJECT and ADD types)"
  - "D-08-03-03: ingest_session skips non-COMPLETED domain reviews rather than erroring"

patterns-established:
  - "Dual-store write: every ingested item goes to both SQLite and ChromaDB atomically"
  - "Metrics computation from review decisions, not from correction counts"

# Metrics
duration: 4min
completed: 2026-02-28
---

# Phase 8 Plan 3: Ingestion Pipeline and Accuracy Metrics Summary

**Review-to-learning ingestion pipeline with dual-store writes (SQLite + ChromaDB) and per-domain accuracy tracking with cross-study improvement reports**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-28T06:06:18Z
- **Completed:** 2026-02-28T06:10:18Z
- **Tasks:** 2
- **Files created:** 4

## Accomplishments
- Accuracy metrics computation from DomainReview decisions (approved/corrected/rejected/added counts)
- Cross-study improvement tracking with per-domain accuracy trends
- Ingestion pipeline that extracts mappings and corrections from completed reviews into both stores
- Idempotent ingestion via deterministic IDs -- re-running does not create duplicates

## Task Commits

Each task was committed atomically:

1. **Task 1: Accuracy metrics computation** - `07b711f` (feat)
2. **Task 2: Review-to-learning ingestion pipeline** - `dafe6da` (feat)

## Files Created/Modified
- `src/astraea/learning/metrics.py` - compute_domain_accuracy, compute_improvement_report, format_improvement_summary
- `src/astraea/learning/ingestion.py` - ingest_domain_review, ingest_session with dual-store writes
- `tests/unit/learning/test_metrics.py` - 11 tests for accuracy computation and improvement tracking
- `tests/unit/learning/test_ingestion.py` - 7 tests for ingestion pipeline with real SQLite and ChromaDB

## Decisions Made
- [D-08-03-01] Deterministic example_id as `f"{study_id}_{domain}_{sdtm_variable}"` enables idempotent re-ingestion. CorrectionRecord uses `f"{session_id}_{domain}_{variable}_{type}"`.
- [D-08-03-02] `was_corrected` flag excludes REJECT (variable removed) and ADD (variable added by reviewer) -- only tracks actual corrections to proposed mappings.
- [D-08-03-03] `ingest_session` silently skips non-COMPLETED domain reviews (logs at debug level) rather than erroring, allowing partial session ingestion.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed DomainMappingSpec missing required fields in tests**
- **Found during:** Task 1
- **Issue:** Test helper `_make_spec` was missing `mapping_timestamp` and `model_used` required fields
- **Fix:** Added the two required fields to the test helper
- **Files modified:** tests/unit/learning/test_metrics.py
- **Committed in:** 07b711f

**2. [Rule 1 - Bug] Fixed ruff lint violations in metrics.py and ingestion.py**
- **Found during:** Task 2 verification
- **Issue:** Unused import (DomainReviewStatus in metrics.py), nested if (SIM102), unused variable (F841)
- **Fix:** Removed unused import, combined nested if with `and`, removed unused variable assignment
- **Files modified:** src/astraea/learning/metrics.py, src/astraea/learning/ingestion.py
- **Committed in:** dafe6da

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correctness and lint compliance. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Ingestion pipeline ready for CLI integration (Plan 04)
- Metrics computation provides accuracy tracking for `astraea learning-stats` command
- All 58 learning tests passing (models + stores + retriever + metrics + ingestion)

---
*Phase: 08-learning-system*
*Completed: 2026-02-28*
