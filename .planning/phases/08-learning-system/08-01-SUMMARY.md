---
phase: 08-learning-system
plan: 01
subsystem: learning
tags: [chromadb, sqlite, pydantic, vector-search, few-shot]

# Dependency graph
requires:
  - phase: 04-human-review-gate
    provides: CorrectionType enum, HumanCorrection model, SessionStore SQLite pattern
  - phase: 03-core-mapping-engine
    provides: VariableMapping model, MappingPattern enum
provides:
  - MappingExample, CorrectionRecord, StudyMetrics Pydantic models
  - ExampleStore (SQLite-backed structured storage for examples, corrections, metrics)
  - LearningVectorStore (ChromaDB semantic similarity search with domain filtering)
  - mapping_to_embedding_text helper for natural language embedding
affects: [08-02 retriever integration, 08-03 metrics and ingestion, 08-04 DSPy optimization]

# Tech tracking
tech-stack:
  added: [chromadb>=1.5.1]
  patterns: [SQLite example/correction storage with domain filtering, ChromaDB two-collection layout with metadata filtering, natural language embedding text for SDTM mappings]

key-files:
  created:
    - src/astraea/learning/__init__.py
    - src/astraea/learning/models.py
    - src/astraea/learning/example_store.py
    - src/astraea/learning/vector_store.py
    - tests/unit/learning/__init__.py
    - tests/unit/learning/test_models.py
    - tests/unit/learning/test_example_store.py
    - tests/unit/learning/test_vector_store.py
  modified:
    - pyproject.toml

key-decisions:
  - "ChromaDB metadata stores booleans as str ('true'/'false') per ChromaDB type constraints"
  - "Two ChromaDB collections (approved_mappings, corrections) kept separate for weighted retrieval"
  - "ExampleStore follows SessionStore SQLite pattern (Row factory, parent mkdir, INSERT OR REPLACE)"
  - "mapping_to_embedding_text uses natural language sentences, not JSON, for MiniLM-L6-v2 compatibility"

patterns-established:
  - "Learning store pattern: SQLite for structured queries + ChromaDB for semantic search"
  - "Invalidation flag on corrections for poisoning protection"
  - "Upsert pattern for both SQLite (INSERT OR REPLACE) and ChromaDB (upsert)"

# Metrics
duration: 5min
completed: 2026-02-28
---

# Phase 8 Plan 1: Learning System Data Models and Storage Summary

**SQLite + ChromaDB dual storage for mapping examples and corrections with domain-filtered semantic retrieval**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-28T05:59:05Z
- **Completed:** 2026-02-28T06:04:06Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Three Pydantic models (MappingExample, CorrectionRecord, StudyMetrics) with defaults, validation, and JSON round-trip
- SQLite-backed ExampleStore with save/retrieve/filter/invalidate for examples, corrections, and metrics
- ChromaDB LearningVectorStore with two collections, domain metadata filtering, and graceful empty handling
- 27 unit tests passing covering all CRUD operations, filtering, invalidation, and edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Pydantic models for learning system data** - `8f95677` (feat)
2. **Task 2: SQLite example store and ChromaDB vector store** - `af8d906` (feat)

## Files Created/Modified
- `src/astraea/learning/__init__.py` - Package init
- `src/astraea/learning/models.py` - MappingExample, CorrectionRecord, StudyMetrics, mapping_to_embedding_text
- `src/astraea/learning/example_store.py` - SQLite-backed ExampleStore with domain filtering and invalidation
- `src/astraea/learning/vector_store.py` - ChromaDB LearningVectorStore with semantic similarity search
- `tests/unit/learning/test_models.py` - 11 tests for Pydantic models
- `tests/unit/learning/test_example_store.py` - 10 tests for ExampleStore
- `tests/unit/learning/test_vector_store.py` - 6 tests for LearningVectorStore
- `pyproject.toml` - Added chromadb>=1.5.1 dependency

## Decisions Made
- [D-08-01-01] ChromaDB metadata stores booleans as lowercase strings ('true'/'false') because ChromaDB metadata values must be str, int, float, or bool
- [D-08-01-02] Two separate ChromaDB collections (approved_mappings, corrections) for differential weighting during retrieval
- [D-08-01-03] ExampleStore uses INSERT OR REPLACE for idempotent upserts (same pattern as SessionStore)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed chromadb dependency**
- **Found during:** Task 2 (ChromaDB vector store)
- **Issue:** chromadb not installed in virtual environment
- **Fix:** pip install chromadb and added to pyproject.toml dependencies
- **Files modified:** pyproject.toml (committed with Task 1)
- **Verification:** import chromadb succeeds, all vector store tests pass

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required dependency installation. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Learning data models and storage ready for retriever integration (08-02)
- ExampleStore and LearningVectorStore can be injected into MappingEngine
- 27 tests provide regression safety for future development

---
*Phase: 08-learning-system*
*Completed: 2026-02-28*
