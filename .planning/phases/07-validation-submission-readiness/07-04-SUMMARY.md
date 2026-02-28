# Phase 7 Plan 4: Predict-and-Prevent Validation Summary

**One-liner:** Spec-level validation with 7 ASTR-PP rules catching issues before dataset generation, wired into mapping engine

## What Was Built

Predict-and-prevent validation that runs on mapping specifications BEFORE dataset generation, shifting validation left so issues are caught during human review rather than after expensive execution.

### Components

1. **`src/astraea/validation/predict.py`** -- 7 spec-level validation rules:
   - ASTR-PP001 (ERROR): Required variables must have mappings
   - ASTR-PP002 (ERROR): No duplicate variable mappings
   - ASTR-PP003 (WARNING): Referenced codelist codes must exist in CT
   - ASTR-PP004 (ERROR): ASSIGN values must be valid in non-extensible codelists
   - ASTR-PP005 (WARNING): Variable names should exist in SDTM-IG
   - ASTR-PP006 (NOTICE): Origin should be populated for define.xml
   - ASTR-PP007 (NOTICE): Derived variables should have computational_method

2. **`src/astraea/models/mapping.py`** -- Added `predict_prevent_issues: list[dict]` field to `DomainMappingSpec` for storing results without circular imports

3. **`src/astraea/mapping/engine.py`** -- Integrated predict-and-prevent call after spec construction, with ImportError fallback for graceful degradation

### Tests

19 unit tests in `tests/unit/validation/test_predict.py` covering:
- Each rule type independently (positive and negative cases)
- `results_to_issue_dicts` conversion helper
- Integration tests with multiple issue types combined
- Clean spec with minimal issues

## Decisions Made

- Used `list[dict]` for `predict_prevent_issues` field (avoids circular import from models -> validation)
- Predict-and-prevent is informational only -- does NOT block mapping pipeline
- ImportError catch in engine allows mapping to work without validation module installed
- Results stored on spec object for downstream consumers (human review, cSDRG)

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- `pytest tests/unit/validation/test_predict.py -x -q` -- 19 passed
- `pytest tests/unit/mapping/ -x -q` -- 69 passed (no regression)
- `ruff check` -- all modified files pass
- Pre-existing test failures in `test_engine.py` (2 tests assume no default rules, but other 07-XX plans added rules) -- unrelated to this plan

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | b49aac0 | Predict-and-prevent rules + model field + tests |
| 2 | 67d1d59 | Wire predict-and-prevent into mapping engine |

## Duration

~4 minutes (2026-02-28)
