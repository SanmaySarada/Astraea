---
phase: 03-core-mapping-engine
plan: 05
subsystem: testing
tags: [integration-test, dm-mapping, llm, claude-api, end-to-end]

# Dependency graph
requires:
  - phase: 03-core-mapping-engine (plans 01-04)
    provides: MappingEngine, context builder, validation, exporters, CLI
provides:
  - Integration test proving end-to-end DM mapping with real data and real LLM
  - Validation fix for ASSIGN pattern confidence scoring
  - 579 tests passing (564 unit + 15 integration)
affects: [04-human-review-gate, 05-event-intervention-domains]

# Tech tracking
tech-stack:
  added: [openpyxl (test dependency for Excel roundtrip)]
  patterns: [module-scoped fixtures for LLM call caching, integration test markers]

key-files:
  created:
    - tests/integration/mapping/__init__.py
    - tests/integration/mapping/test_dm_mapping.py
  modified:
    - src/astraea/mapping/validation.py
    - pyproject.toml

key-decisions:
  - "ASSIGN pattern confidence not penalized for missing codelists (C66734 not bundled, DOMAIN assignment is always correct)"

patterns-established:
  - "Module-scoped LLM fixtures: one real API call per test module, multiple assertions against cached result"
  - "Integration test markers: @pytest.mark.integration + ANTHROPIC_API_KEY skip guard"

# Metrics
duration: ~8min (across two checkpoint-separated sessions)
completed: 2026-02-27
---

# Phase 3 Plan 5: DM Integration Test Summary

**15 integration tests prove end-to-end DM mapping works with real Fakedata and real Claude API -- all Required variables mapped, confidence scores reasonable, exports valid.**

## Performance

- **Duration:** ~8 min (two sessions with human-verify checkpoint)
- **Started:** 2026-02-27
- **Completed:** 2026-02-27
- **Tasks:** 2/2
- **Files modified:** 4

## Accomplishments

- Created 15 integration tests exercising full DM mapping pipeline: profile real SAS data, build context, call Claude, validate proposals, enrich, and export
- All 7 Required DM variables (STUDYID, DOMAIN, USUBJID, SUBJID, SITEID, SEX, COUNTRY) mapped with correct patterns
- Export roundtrip validated: JSON serialization/deserialization and Excel 3-sheet output both verified
- CT codelist references verified: SEX (C66731), ETHNIC (C66790), RACE (C74457)
- Fixed ASSIGN pattern confidence penalty: validation.py was incorrectly penalizing ASSIGN mappings when their codelist (C66734) was not bundled, dropping DOMAIN confidence to 0.40

## Task Commits

Each task was committed atomically:

1. **Task 1: Create DM domain integration test** - `43bc737` (test)
2. **Task 2: Fix ASSIGN pattern confidence penalty** - `05ab5ff` (fix)

## Files Created/Modified

- `tests/integration/mapping/__init__.py` - Package init for integration mapping tests
- `tests/integration/mapping/test_dm_mapping.py` - 15 integration tests for DM domain mapping end-to-end
- `src/astraea/mapping/validation.py` - Fixed: ASSIGN patterns no longer penalized for missing codelists
- `pyproject.toml` - Added openpyxl test dependency

## Decisions Made

- **[D-0305-01] ASSIGN pattern confidence not penalized for missing codelists:** The validation module was capping confidence at 0.40 for any mapping referencing a codelist not in the bundled CT data. ASSIGN patterns (e.g., DOMAIN = "DM") reference C66734 which is not bundled. Since ASSIGN values are hardcoded constants, codelist validation is irrelevant -- the fix skips CT penalty for ASSIGN patterns.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ASSIGN pattern confidence penalty on missing codelists**
- **Found during:** Task 2 (human verification checkpoint)
- **Issue:** DOMAIN variable had confidence 0.40 instead of expected >= 0.85 because validation.py penalized all codelist references equally, including ASSIGN patterns where the codelist (C66734) was not bundled
- **Fix:** Added condition to skip CT-failure confidence penalty when mapping pattern is ASSIGN
- **Files modified:** src/astraea/mapping/validation.py
- **Commit:** 05ab5ff

## Test Results

- 14/15 integration tests passed on first run (before fix)
- 15/15 integration tests pass after ASSIGN confidence fix
- Full suite: 564 unit tests + 15 integration tests = 579 total, all passing

## Phase 3 Completion

This is the final plan (5 of 5) in Phase 3: Core Mapping Engine. The phase delivered:

| Component | Module | Tests |
|-----------|--------|-------|
| Mapping specification models | src/astraea/models/mapping.py | 30 |
| Mapping context assembly | src/astraea/mapping/context.py | 13 |
| System prompt + validation + engine | src/astraea/mapping/prompts.py, validation.py, engine.py | 19 |
| Excel/JSON exporters | src/astraea/mapping/exporters.py | 7 |
| CLI map-domain + display | src/astraea/cli/app.py, display.py | 5 |
| Integration test (DM end-to-end) | tests/integration/mapping/test_dm_mapping.py | 15 |
| **Total Phase 3** | | **89 tests** |

**Combined project test suite: 579 tests passing.**

## Next Phase Readiness

Phase 4 (Human Review Gate) can proceed. The DM mapping engine is proven end-to-end. Key inputs for Phase 4:
- DomainMappingSpec model is stable and tested
- Excel/JSON export provides review artifacts
- CLI map-domain command provides the entry point
- Confidence scoring is calibrated and validated
