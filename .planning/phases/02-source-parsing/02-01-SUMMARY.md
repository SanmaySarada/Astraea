---
phase: 02-source-parsing
plan: 01
subsystem: models, llm
tags: [pydantic, anthropic, pymupdf4llm, tenacity, structured-output, ecrf, classification]

requires:
  - phase: 01-foundation
    provides: Pydantic model patterns, pyproject.toml, existing models/__init__.py
provides:
  - ECRFField, ECRFForm, ECRFExtractionResult Pydantic models for eCRF metadata
  - HeuristicScore, DomainClassification, DomainPlan, ClassificationResult models
  - AstraeaLLMClient wrapper with structured output, retry, and logging
  - pymupdf4llm, pdfplumber, tenacity as project dependencies
affects: [02-02 (PDF extraction), 02-03 (eCRF parsing), 02-04 (classification), 02-05 (CLI)]

tech-stack:
  added: [pymupdf4llm>=0.3.4, pdfplumber>=0.11, tenacity>=9.0]
  patterns: [Anthropic messages.parse() for structured output, tenacity retry on transient errors]

key-files:
  created:
    - src/astraea/models/ecrf.py
    - src/astraea/models/classification.py
    - src/astraea/llm/__init__.py
    - src/astraea/llm/client.py
    - tests/test_models/test_ecrf.py
    - tests/test_models/test_classification.py
    - tests/test_llm/__init__.py
    - tests/test_llm/test_client.py
  modified:
    - src/astraea/models/__init__.py
    - pyproject.toml

key-decisions:
  - "ECRFField.field_name validated for no-spaces (SAS variable names cannot contain spaces)"
  - "ECRFExtractionResult.total_fields as computed property, not stored field"
  - "DomainClassification includes heuristic_scores list for traceability of two-stage classification"
  - "AstraeaLLMClient.parse() uses keyword-only arguments for safety"

patterns-established:
  - "LLM client: all pipeline LLM calls go through AstraeaLLMClient.parse() with Pydantic output_format"
  - "Retry: tenacity exponential backoff for APITimeout/Connection/RateLimit; no retry on BadRequest"
  - "Logging: every LLM call logged via loguru with model, temperature, token counts, latency"

duration: 3min
completed: 2026-02-26
---

# Phase 2 Plan 1: Data Models and LLM Client Summary

**eCRF + classification Pydantic models with Anthropic structured-output client wrapper using tenacity retry**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-26T21:49:34Z
- **Completed:** 2026-02-26T21:53:05Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- ECRFField, ECRFForm, ECRFExtractionResult models with validation (no-space field names, field_number >= 1)
- HeuristicScore, DomainClassification, DomainPlan, ClassificationResult models with confidence bounds and literal mapping_pattern
- AstraeaLLMClient wrapping Anthropic SDK messages.parse() with Pydantic structured output
- 43 tests passing (35 model tests + 8 LLM client tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: eCRF and Classification Pydantic Models** - `ecc0d71` (feat)
2. **Task 2: LLM Client Wrapper and Dependencies** - `452de84` (feat)

## Files Created/Modified
- `src/astraea/models/ecrf.py` - ECRFField, ECRFForm, ECRFExtractionResult Pydantic models
- `src/astraea/models/classification.py` - HeuristicScore, DomainClassification, DomainPlan, ClassificationResult models
- `src/astraea/models/__init__.py` - Updated exports for new models
- `src/astraea/llm/__init__.py` - LLM module init exporting AstraeaLLMClient
- `src/astraea/llm/client.py` - Anthropic SDK wrapper with structured output, retry, logging
- `tests/test_models/test_ecrf.py` - 14 tests for eCRF models
- `tests/test_models/test_classification.py` - 21 tests for classification models
- `tests/test_llm/__init__.py` - Test module init
- `tests/test_llm/test_client.py` - 8 mocked unit tests for LLM client
- `pyproject.toml` - Added pymupdf4llm, pdfplumber, tenacity dependencies

## Decisions Made
- [D-0201-01] ECRFField.field_name has min_length=1 and no-spaces validator since SAS variable names cannot contain whitespace
- [D-0201-02] ECRFExtractionResult.total_fields is a @property (computed) rather than a stored field, avoiding stale data
- [D-0201-03] DomainClassification includes heuristic_scores list for full traceability of two-stage (heuristic + LLM) classification
- [D-0201-04] AstraeaLLMClient.parse() uses keyword-only args to prevent positional argument errors in LLM calls

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- eCRF and classification data contracts established for all subsequent Phase 2 plans
- LLM client ready for use by PDF extraction (02-02) and eCRF parsing (02-03) plans
- pymupdf4llm installed and verified for PDF-to-Markdown extraction

---
*Phase: 02-source-parsing*
*Completed: 2026-02-26*
