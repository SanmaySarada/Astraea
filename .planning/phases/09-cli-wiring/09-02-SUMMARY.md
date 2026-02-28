---
phase: 09-cli-wiring
plan: 02
subsystem: cli
tags: [learning, retriever, chromadb, map-domain, few-shot]
depends_on: []
provides: [learning-retriever-wiring, map-domain-learning-integration]
affects: [mapping-accuracy, learning-feedback-loop]
tech_stack:
  added: []
  patterns: [lazy-import, auto-detect-config-dir, graceful-fallback]
key_files:
  created:
    - tests/unit/cli/test_map_domain_learning.py
  modified:
    - src/astraea/cli/app.py
decisions:
  - id: D-09-02-01
    description: "_try_load_learning_retriever extracted as module-level helper for direct testability (avoids mocking entire map-domain pipeline)"
  - id: D-09-02-02
    description: "Parameter named rich_console (not console) to avoid shadowing module-level console variable"
  - id: D-09-02-03
    description: "Return type is object | None (not LearningRetriever | None) to avoid import-time dependency on chromadb"
metrics:
  duration: ~3 min
  completed: 2026-02-28
---

# Phase 09 Plan 02: Wire LearningRetriever into map-domain Summary

**One-liner:** LearningRetriever auto-loaded from .astraea/learning/ or --learning-db and passed to MappingEngine for few-shot example injection.

## What Was Done

### Task 1: Wire LearningRetriever into map-domain CLI command
- Added `--learning-db` option to `map_domain` command for explicit ChromaDB path
- Added auto-detection of `.astraea/learning/` directory when no explicit path given
- Extracted `_try_load_learning_retriever()` helper function for testability
- Modified `MappingEngine` instantiation to pass `learning_retriever` kwarg
- All learning imports are lazy (inside try/except) -- graceful fallback when chromadb not installed
- **Commit:** `5c370fc`

### Task 2: Add unit tests for learning retriever wiring
- 5 tests covering all scenarios:
  - `test_no_learning_db_returns_none` -- no DB, no auto-detect dir
  - `test_explicit_learning_db_path` -- explicit --learning-db loads correctly
  - `test_auto_detect_astraea_learning_dir` -- .astraea/learning/ auto-detected via monkeypatch cwd
  - `test_import_error_returns_none` -- chromadb ImportError handled gracefully
  - `test_nonexistent_explicit_path_returns_none` -- invalid path returns None
- Tests use `sys.modules` patching to mock lazy imports without requiring chromadb
- **Commit:** `7331399`

## Deviations from Plan

None -- plan executed exactly as written.

## Verification Results

- `ruff check src/astraea/cli/app.py tests/unit/cli/test_map_domain_learning.py` -- zero violations
- `pytest tests/unit/cli/test_map_domain_learning.py -x -q` -- 5 passed
- `pytest tests/unit/ -x -q` -- 658 passed
- `python -c "from astraea.cli.app import app; print('OK')"` -- no import errors

## GAP Closure

**GAP-2 (v1-MILESTONE-AUDIT.md):** Learning retriever now wired into map-domain CLI command. The feedback loop is closed -- past corrections and approved mappings flow into future mapping prompts via ChromaDB similarity search.
