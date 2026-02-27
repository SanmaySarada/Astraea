---
phase: 03-core-mapping-engine
plan: 03
subsystem: mapping-engine
tags: [llm, mapping, validation, enrichment, sdtm, ct, prompts, pydantic]
depends_on:
  requires: [03-01, 03-02]
  provides: [MappingEngine, validate_and_enrich, check_required_coverage, MAPPING_SYSTEM_PROMPT]
  affects: [03-04, 03-05, 04-human-review]
tech_stack:
  added: []
  patterns: [mock-based-testing, two-phase-mapping, confidence-adjustment]
key_files:
  created:
    - src/astraea/mapping/prompts.py
    - src/astraea/mapping/validation.py
    - src/astraea/mapping/engine.py
    - tests/unit/mapping/test_validation.py
    - tests/unit/mapping/test_engine.py
  modified:
    - src/astraea/mapping/__init__.py
decisions:
  - id: D-0303-01
    summary: System prompt includes TRANSPOSE pattern for forward-compatibility with Phase 6
  - id: D-0303-02
    summary: Confidence adjustments are +0.05 for CT pass on lookup_recode, cap 0.4 for CT failure, cap 0.3 for unknown variables
  - id: D-0303-03
    summary: MappingEngine uses keyword-only args for build_prompt to match context builder API
metrics:
  duration: ~6 minutes
  completed: 2026-02-27
  tests_added: 19
  tests_total: 552
---

# Phase 3 Plan 3: Core Mapping Engine Summary

**One-liner:** MappingEngine orchestrates LLM proposal -> SDTM-IG/CT validation -> confidence adjustment -> DomainMappingSpec construction, tested entirely with mocks (no API calls).

## What Was Built

### Task 1: System Prompt Module (`prompts.py`)
- MAPPING_SYSTEM_PROMPT: Defines SDTM mapping specialist role with all 9 mapping patterns (ASSIGN, DIRECT, RENAME, REFORMAT, SPLIT, COMBINE, DERIVATION, LOOKUP_RECODE, TRANSPOSE)
- TRANSPOSE included for forward-compatibility with Phase 6 Findings domains
- Instructions for confidence scoring, suppqual candidates, _STD column preference
- MAPPING_USER_INSTRUCTIONS: Template appended after context, parameterized by {domain}

### Task 2: Validation/Enrichment Module (`validation.py`)
- `validate_and_enrich()`: Validates each LLM proposal against SDTM-IG domain spec and CT reference
  - Enriches with labels, data_type, core designation from VariableSpec
  - Validates CT codelist existence and term validity for non-extensible codelists
  - Confidence adjustments: +0.05 for CT pass on lookup_recode, cap 0.4 for CT failure, cap 0.3 for unknown variables
- `check_required_coverage()`: Flags Required variables missing from mappings
- 9 tests using real bundled SDTM-IG and CT reference data

### Task 3: MappingEngine Orchestrator (`engine.py`)
- `MappingEngine.map_domain()`: Full orchestration pipeline
  1. Get domain spec from SDTMReference
  2. Build context via MappingContextBuilder
  3. Append user instructions
  4. Call LLM via AstraeaLLMClient.parse() with DomainMappingProposal schema
  5. Validate and enrich proposals
  6. Check required coverage
  7. Build DomainMappingSpec with summary statistics
  8. Log completion summary
- `_build_spec()`: Computes total_variables, required_mapped, expected_mapped, high/medium/low confidence counts, cross_domain_sources, mapping_timestamp
- 10 mock-based tests verify full flow without API calls

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-0303-01 | TRANSPOSE in system prompt for forward-compatibility | Phase 6 Findings domains will need it; defining now ensures consistency |
| D-0303-02 | Confidence adjustment thresholds: +0.05/0.4/0.3 | Per research doc recommendations; calibrated to route attention correctly |
| D-0303-03 | build_prompt uses keyword-only args | Matches existing MappingContextBuilder API from plan 03-02 |

## Deviations from Plan

None -- plan executed exactly as written. Context builder (03-02 dependency) was already in place from a prior execution.

## Test Results

- 9 validation tests: CT validation, confidence adjustments, required coverage
- 10 engine tests: spec construction, enrichment, timestamps, model passthrough, error handling
- 13 context tests (pre-existing): prompt formatting, EDC filtering, output size
- **32 mapping tests total, 552 tests suite-wide, all passing**

## Next Phase Readiness

Plan 03-04 (CLI mapping display) can proceed -- MappingEngine provides the spec it needs to display. Plan 03-05 (integration test) will need real LLM calls.
