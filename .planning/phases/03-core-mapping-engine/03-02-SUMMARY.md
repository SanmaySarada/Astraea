---
phase: 03-core-mapping-engine
plan: 02
subsystem: mapping
tags: [context-assembly, llm-prompt, sdtm, ct-filtering, edc-filtering]

requires:
  - phase: 01-foundation
    provides: SDTMReference, CTReference, DomainSpec, VariableSpec models
  - phase: 02-source-parsing
    provides: DatasetProfile, ECRFForm models
  - plan: 03-01
    provides: StudyMetadata, mapping models

provides:
  - MappingContextBuilder class for assembling focused LLM prompts
  - _get_relevant_codelists helper for CT filtering
  - _format_variable_profile helper for compact variable summaries

affects:
  - 03-03 (DM mapping agent uses context builder to prepare LLM input)
  - 03-04 (mapping enrichment may reuse context components)
  - 03-05 (integration test exercises context builder end-to-end)

tech-stack:
  added: []
  patterns:
    - "Keyword-only build_prompt() API for clarity"
    - "EDC column filtering at context assembly time (not LLM time)"
    - "Domain-scoped CT inclusion (only referenced codelists)"

key-files:
  created:
    - src/astraea/mapping/__init__.py
    - src/astraea/mapping/context.py
    - tests/unit/__init__.py
    - tests/unit/mapping/test_context.py
  modified: []

key-decisions:
  - "build_prompt uses keyword-only arguments for all domain-specific parameters"
  - "EDC columns filtered by checking is_edc_column on VariableProfile"
  - "CT codelists limited to those with codelist_code on domain VariableSpecs"
  - "Cross-domain profiles show only clinical variable summaries (name + label)"
  - "Large codelists (>20 terms) show first 20 with total count"

patterns-established:
  - "Context builder as separate module from LLM agent (separation of concerns)"
  - "Markdown-formatted sections with ## headers for LLM consumption"

duration: 3min
completed: 2026-02-27
---

# Phase 3 Plan 2: Mapping Context Assembly Summary

**Context builder that assembles focused, EDC-filtered LLM prompts from domain specs, source profiles, eCRF forms, and relevant CT codelists -- 13 tests, output under 20KB for DM domain.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T11:14:12Z
- **Completed:** 2026-02-27T11:17:09Z
- **Tasks:** 2/2
- **Files created:** 4

## Accomplishments

- Created MappingContextBuilder with build_prompt() producing markdown-formatted context with 6 sections: domain spec, source data, eCRF forms, controlled terminology, cross-domain sources, study metadata
- EDC system columns are filtered at context assembly time -- only clinical variables reach the LLM
- CT codelist filtering includes only codelists referenced by the target domain's VariableSpecs
- Cross-domain source summaries show clinical variable names and labels without full profiles
- 13 unit tests using real SDTMReference and CTReference from bundled data

## Task Commits

1. **Task 1: Create mapping context builder** - `b5e3639` (feat)
2. **Task 2: Unit tests for context builder** - `dd7418c` (test)

## Files Created/Modified

- `src/astraea/mapping/__init__.py` - Mapping package init
- `src/astraea/mapping/context.py` - MappingContextBuilder class with 6 formatting helpers
- `tests/unit/__init__.py` - Unit test package init for pytest discovery
- `tests/unit/mapping/test_context.py` - 13 tests covering all context builder features

## Decisions Made

1. **Keyword-only build_prompt:** All parameters except self are keyword-only to prevent argument ordering mistakes when calling with many parameters.
2. **EDC filtering at context level:** Filtering happens during context assembly, not in the LLM prompt instructions. The LLM never sees EDC columns.
3. **Codelist term limit:** Codelists with more than 20 terms show only the first 20 with a total count to keep context focused.
4. **Cross-domain summary:** Cross-domain profiles show only variable name and label (not full profiles with statistics) to minimize context size.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Line length violation in eCRF formatting**
- **Found during:** Task 1 verification
- **Issue:** ruff E501 flagged a 101-character line in the eCRF field formatting
- **Fix:** Split f-string across multiple lines
- **Files modified:** `src/astraea/mapping/context.py`
- **Commit:** `b5e3639`

**2. [Rule 3 - Blocking] Missing tests/unit/__init__.py**
- **Found during:** Task 2
- **Issue:** `tests/unit/` directory existed but lacked `__init__.py` needed for pytest discovery
- **Fix:** Created empty `__init__.py`
- **Files modified:** `tests/unit/__init__.py`
- **Commit:** `dd7418c`

## Test Suite Status

- **New tests:** 13
- **Total suite:** 533 passing
