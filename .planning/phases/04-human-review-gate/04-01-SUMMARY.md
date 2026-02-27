---
phase: 04-human-review-gate
plan: 01
subsystem: review
tags: [pydantic, sqlite, session-persistence, human-review, corrections]

dependency_graph:
  requires: [03-core-mapping-engine]
  provides: [review-data-models, session-persistence]
  affects: [04-02, 04-03, 08-learning-loop]

tech_stack:
  added: []
  patterns: [sqlite-session-store, structured-correction-capture, pydantic-json-roundtrip]

key_files:
  created:
    - src/astraea/review/__init__.py
    - src/astraea/review/models.py
    - src/astraea/review/session.py
    - tests/unit/review/__init__.py
    - tests/unit/review/test_models.py
    - tests/unit/review/test_session.py
  modified: []

decisions:
  - id: D-0401-01
    description: "CoreDesignation uses REQ/EXP/PERM (not REQUIRED/EXPECTED/PERMISSIBLE)"
  - id: D-0401-02
    description: "SessionStore uses sqlite3.Row factory for dict-like row access"
  - id: D-0401-03
    description: "Domain review decisions serialized as JSON dict in SQLite TEXT column"

metrics:
  duration: "4 minutes"
  completed: "2026-02-27"
---

# Phase 4 Plan 1: Review Data Models + Session Persistence Summary

**One-liner:** Pydantic review models (7 correction types, 4 review statuses) with SQLite-backed session persistence for interrupt/resume review gate.

## What Was Done

### Task 1: Review Data Models
Created `src/astraea/review/models.py` with 8 Pydantic models and 4 StrEnum types:

- **CorrectionType** (7 values): source_change, logic_change, pattern_change, ct_change, confidence_override, reject, add
- **ReviewStatus** (4 values): pending, approved, corrected, skipped
- **DomainReviewStatus** (4 values): pending, in_progress, completed, skipped
- **SessionStatus** (3 values): in_progress, completed, abandoned
- **ReviewDecision**: Per-variable decision with model_validator enforcing corrected_mapping when status is CORRECTED
- **HumanCorrection**: Structured correction record linking original to corrected mapping (Phase 8 training data)
- **DomainReview**: Per-domain review state with original spec, decisions dict, and corrections list
- **ReviewSession**: Top-level session with ordered domain list and current_domain_index for resume

17 tests covering enum completeness, validation enforcement, and JSON round-trip serialization.

### Task 2: SQLite Session Persistence
Created `src/astraea/review/session.py` with `SessionStore` class:

- **3 SQLite tables**: sessions, domain_reviews, corrections
- **create_session()**: Generates uuid4 hex[:12] session_id, persists domain specs as pending reviews
- **save_session()**: Updates session state (status, current_domain_index) and all domain reviews
- **save_domain_review()**: Saves/updates individual domain review with decisions and corrections
- **save_correction()**: Appends correction to corrections table
- **load_session()**: Full session reconstruction from SQLite including nested models
- **list_sessions()**: Session summaries with optional study_id filter
- **close()**: Clean database connection shutdown

13 tests covering CRUD operations, round-trip persistence, filtering, and error handling.

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-0401-01 | CoreDesignation uses REQ/EXP/PERM enum values | Existing enum in models/sdtm.py uses abbreviated names |
| D-0401-02 | sqlite3.Row factory for dict-like row access | Cleaner than positional indexing, aligns with column names |
| D-0401-03 | Decisions/corrections serialized as JSON in TEXT columns | Pydantic model_dump/model_validate handles nested models cleanly |

## Test Results

```
30 passed in 0.14s
ruff: All checks passed!
```

## Next Phase Readiness

Plan 04-02 (review display and reviewer logic) can proceed. It will import:
- `ReviewSession`, `DomainReview`, `ReviewDecision` from `astraea.review.models`
- `SessionStore` from `astraea.review.session`
