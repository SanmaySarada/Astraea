---
phase: 02-source-parsing
plan: 02
subsystem: parsing
tags: [pymupdf4llm, pdf, ecrf, claude, structured-output, pydantic]

# Dependency graph
requires:
  - phase: 02-01
    provides: ECRFForm/ECRFField Pydantic models, AstraeaLLMClient wrapper
provides:
  - PDF-to-Markdown extraction with page-by-form grouping
  - LLM-based structured eCRF field extraction pipeline
  - JSON cache save/load for extraction results
affects: [02-03 form-dataset-matcher, 02-04 domain-classification, 02-05 cli-commands]

# Tech tracking
tech-stack:
  added: []
  patterns: [two-phase-extraction (deterministic PDF + LLM interpretation), form-header-grouping]

key-files:
  created:
    - src/astraea/parsing/__init__.py
    - src/astraea/parsing/pdf_extractor.py
    - src/astraea/parsing/ecrf_parser.py
    - tests/test_parsing/__init__.py
    - tests/test_parsing/test_pdf_extractor.py
    - tests/test_parsing/test_ecrf_parser.py
  modified: []

key-decisions:
  - "D-0202-01: Escaped curly braces in ECRF_EXTRACTION_PROMPT to avoid str.format() conflicts with JSON examples"
  - "D-0202-02: _MIN_FORM_TEXT_LENGTH=50 chars threshold for skipping trivially short form pages"
  - "D-0202-03: Page separator uses '---' markdown horizontal rule when concatenating multi-page forms"

patterns-established:
  - "Two-phase extraction: deterministic PDF-to-Markdown first, then LLM structured output"
  - "Form grouping via regex on 'Form: <name>' header pattern"
  - "JSON caching of extraction results via Pydantic model_dump_json/model_validate_json"

# Metrics
duration: 5min
completed: 2026-02-26
---

# Phase 2 Plan 2: eCRF PDF Extraction Pipeline Summary

**pymupdf4llm PDF extraction with form grouping and Claude structured output for eCRF field metadata**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-26T21:54:53Z
- **Completed:** 2026-02-26T21:59:58Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- PDF extractor reads eCRF PDF into page-level Markdown, groups pages by form name
- Integration tests confirm real ECRF.pdf produces >100 pages and >10 detected forms
- eCRF parser sends each form to Claude with structured output, returns ECRFForm models
- Cache save/load enables skipping expensive LLM calls on re-runs
- All 28 tests pass (15 PDF extractor + 13 eCRF parser), no API key required for unit tests

## Task Commits

Each task was committed atomically:

1. **Task 1: PDF Extractor** - `e2de846` (feat)
2. **Task 2: eCRF Parser** - `94d1c97` (feat)

## Files Created/Modified
- `src/astraea/parsing/__init__.py` - Module exports for pdf_extractor and ecrf_parser
- `src/astraea/parsing/pdf_extractor.py` - extract_ecrf_pages(), group_pages_by_form(), get_form_names()
- `src/astraea/parsing/ecrf_parser.py` - extract_form_fields(), parse_ecrf(), save/load_extraction()
- `tests/test_parsing/__init__.py` - Test package init
- `tests/test_parsing/test_pdf_extractor.py` - 15 tests (unit + integration with real PDF)
- `tests/test_parsing/test_ecrf_parser.py` - 13 tests (all mocked LLM, no API key)

## Decisions Made
- [D-0202-01] Escaped curly braces in ECRF_EXTRACTION_PROMPT -- the prompt contains JSON examples like `{"Y": "Yes"}` which conflict with Python str.format(). Used double-brace escaping.
- [D-0202-02] Set minimum form text threshold to 50 characters -- trivially short pages (blank, page-break artifacts) are skipped without an LLM call to save cost.
- [D-0202-03] Multi-page form concatenation uses `\n\n---\n\n` separator -- Markdown horizontal rule provides clear visual break for LLM context.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed prompt template curly brace escaping**
- **Found during:** Task 2 (eCRF Parser)
- **Issue:** ECRF_EXTRACTION_PROMPT contained `{"Y": "Yes", "N": "No"}` as a JSON example, which caused KeyError when calling `.format()` on the template string
- **Fix:** Escaped to `{{"Y": "Yes", "N": "No"}}` for Python str.format() compatibility
- **Files modified:** src/astraea/parsing/ecrf_parser.py
- **Verification:** All 28 tests pass
- **Committed in:** 94d1c97 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed unused import and deprecated timezone alias**
- **Found during:** Task 2 (eCRF Parser) - ruff check
- **Issue:** `import json` was unused; `timezone.utc` should use `datetime.UTC` alias per Python 3.12
- **Fix:** Removed unused import, switched to `datetime.UTC`
- **Files modified:** src/astraea/parsing/ecrf_parser.py
- **Verification:** ruff check passes clean
- **Committed in:** 94d1c97 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- PDF extraction and eCRF parsing pipeline is complete and tested
- Ready for 02-03 (Form-Dataset Matcher) which will associate extracted forms with raw SAS datasets
- Integration tests confirm real ECRF.pdf works with the pipeline
- Cache mechanism enables efficient re-runs during development

---
*Phase: 02-source-parsing*
*Completed: 2026-02-26*
