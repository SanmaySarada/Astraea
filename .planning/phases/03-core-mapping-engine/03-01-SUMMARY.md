---
phase: 03-core-mapping-engine
plan: 01
subsystem: models
tags: [pydantic, mapping, sdtm, enum, json-schema, llm-tool-use]

requires:
  - phase: 01-foundation
    provides: CoreDesignation enum, VariableSpec, DomainSpec models
  - phase: 02-source-parsing
    provides: ECRFField, DomainClassification models (pattern reference)

provides:
  - MappingPattern enum (9 patterns for all transformation types)
  - VariableMappingProposal / DomainMappingProposal (LLM output schema)
  - VariableMapping / DomainMappingSpec (enriched/validated spec)
  - StudyMetadata model (study-level constants)
  - confidence_level_from_score helper function
  - JSON schema generation for Claude tool definitions

affects:
  - 03-02 (DM mapping agent uses these models as output schema)
  - 03-03 (mapping enrichment engine consumes proposals, produces specs)
  - 03-04 (CLI display reads DomainMappingSpec)
  - 03-05 (integration test validates full model flow)

tech-stack:
  added: []
  patterns:
    - "StrEnum for Python 3.12+ (replaces str, Enum pattern)"
    - "Two-tier model: LLM proposal (simple) -> enriched spec (full)"
    - "Confidence scoring: numeric score + categorical level"

key-files:
  created:
    - src/astraea/models/mapping.py
    - tests/test_models/test_mapping.py
  modified:
    - src/astraea/models/__init__.py

key-decisions:
  - "Used StrEnum instead of (str, Enum) to satisfy ruff UP042 lint rule"
  - "Confidence thresholds: HIGH >= 0.85, MEDIUM >= 0.60, LOW < 0.60"
  - "Proposal models have no reference data (labels, core) -- enrichment is separate step"

patterns-established:
  - "Two-tier mapping model: LLM proposes (VariableMappingProposal), enrichment produces (VariableMapping)"
  - "DomainMappingProposal.model_json_schema() generates Claude tool definition"

duration: 3min
completed: 2026-02-27
---

# Phase 3 Plan 1: Mapping Specification Models Summary

**Pydantic models defining the mapping contract between LLM proposal, enrichment engine, and output exporters -- 8 models with 30 tests, JSON schema ready for Claude tool use.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T11:09:10Z
- **Completed:** 2026-02-27T11:12:24Z
- **Tasks:** 2/2
- **Files modified:** 3

## Accomplishments

- Defined 9-value MappingPattern enum covering all SDTM transformation types (assign, direct, rename, reformat, split, combine, derivation, lookup_recode, transpose)
- Created two-tier model architecture: simple LLM output schema (VariableMappingProposal) and enriched validated spec (VariableMapping) with SDTM-IG reference data
- JSON schema generation verified for Claude tool definitions -- DomainMappingProposal.model_json_schema() produces valid schema with enum values
- 30 unit tests covering enums, validation, confidence scoring, JSON round-trips, and schema generation

## Task Commits

1. **Task 1: Create mapping spec Pydantic models** - `9911b4b` (feat)
2. **Task 2: Unit tests for mapping models** - `587e460` (test)

## Files Created/Modified

- `src/astraea/models/mapping.py` - All 8 mapping specification models (MappingPattern, ConfidenceLevel, VariableMappingProposal, DomainMappingProposal, VariableMapping, DomainMappingSpec, StudyMetadata, confidence_level_from_score)
- `tests/test_models/test_mapping.py` - 30 unit tests covering all models, enums, validation, JSON round-trip, and schema generation
- `src/astraea/models/__init__.py` - Updated exports to include all new mapping models

## Decisions Made

1. **StrEnum over (str, Enum):** Used Python 3.12 `StrEnum` instead of the `(str, Enum)` pattern used in earlier models. Satisfies ruff UP042 lint rule. Functionally identical but cleaner.
2. **Confidence thresholds:** HIGH >= 0.85, MEDIUM >= 0.60, LOW < 0.60. These align with the plan specification and provide a reasonable distribution for human review prioritization.
3. **Two-tier model separation:** LLM proposals intentionally omit reference data fields (sdtm_label, core, codelist_name). Enrichment is a separate deterministic step that adds these from SDTM-IG lookup, keeping the LLM output schema minimal.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] StrEnum migration for lint compliance**
- **Found during:** Task 1 verification
- **Issue:** ruff UP042 flags `(str, Enum)` pattern as deprecated in Python 3.12+
- **Fix:** Used `StrEnum` from `enum` module instead
- **Files modified:** `src/astraea/models/mapping.py`
- **Commit:** `9911b4b`

**2. [Rule 3 - Blocking] Test directory path adjustment**
- **Found during:** Task 2
- **Issue:** Plan specified `tests/unit/models/test_mapping.py` but project uses `tests/test_models/` structure
- **Fix:** Created test at `tests/test_models/test_mapping.py` to match existing project structure
- **Files modified:** `tests/test_models/test_mapping.py`
- **Commit:** `587e460`

**3. [Rule 1 - Bug] Import sorting in test file**
- **Found during:** Task 2 verification
- **Issue:** ruff I001 flagged import block as unsorted
- **Fix:** Ran `ruff check --fix` to auto-sort imports
- **Files modified:** `tests/test_models/test_mapping.py`
- **Commit:** `587e460`
