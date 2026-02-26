---
phase: 02-source-parsing
plan: 04
subsystem: classification
tags: [ecrf, domain-classification, heuristic-fusion, llm, pydantic]

# Dependency graph
requires:
  - phase: 02-source-parsing (02-02)
    provides: "PDF extractor and eCRF parser with LLM-based field extraction"
  - phase: 02-source-parsing (02-03)
    provides: "Heuristic domain scorer with filename and variable overlap scoring"
provides:
  - "Form-to-dataset matcher by variable name overlap"
  - "LLM domain classifier with heuristic fusion and confidence scoring"
  - "Merge detection and DomainPlan creation"
  - "Classification save/load caching"
affects: [02-05-cli-commands, 03-dm-domain-mapping]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Heuristic-LLM fusion: heuristic scores as LLM context + sanity check"
    - "Confidence adjustment: agreement boosts, disagreement penalizes"
    - "Mapping pattern detection: direct/merge/transpose/mixed"

key-files:
  created:
    - src/astraea/parsing/form_dataset_matcher.py
    - src/astraea/classification/classifier.py
    - tests/test_parsing/test_form_dataset_matcher.py
    - tests/test_classification/test_classifier.py
  modified: []

key-decisions:
  - "D-0204-01: Form-dataset matching uses field_name overlap ratio (form fields / clinical vars)"
  - "D-0204-02: Heuristic-LLM disagreement with heuristic >= 0.8 reduces confidence by min * 0.7"
  - "D-0204-03: Findings domains (LB, VS, EG, PE, QS, SC, FA) auto-detect transpose pattern"

patterns-established:
  - "Mock-based LLM testing: all classifier tests use MagicMock for AstraeaLLMClient"
  - "Internal Pydantic models for LLM output: _LLMClassificationOutput not exported"

# Metrics
duration: 4min
completed: 2026-02-26
---

# Phase 2 Plan 4: Form-Dataset Matcher and LLM Domain Classifier Summary

**eCRF form-to-dataset matcher by variable overlap + LLM domain classifier fusing heuristic scores with Claude structured output for confident domain assignment**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-26T22:01:31Z
- **Completed:** 2026-02-26T22:05:22Z
- **Tasks:** 2
- **Files created:** 4

## Accomplishments
- Form-to-dataset matcher associates eCRF forms with raw datasets by variable name overlap (case-insensitive, EDC-excluded)
- LLM classifier fuses heuristic scores with Claude reasoning -- agreement boosts confidence, disagreement reduces it
- Merge detection combines heuristic filename patterns with LLM merge_candidates
- DomainPlan objects determine mapping pattern (direct/merge/transpose/mixed) based on source count and domain class
- 27 new tests (13 matcher + 14 classifier), all passing without API key

## Task Commits

Each task was committed atomically:

1. **Task 1: Form-to-Dataset Matcher** - `4fc176b` (feat)
2. **Task 2: LLM Domain Classifier with Heuristic Fusion** - `3b977c5` (feat)

## Files Created/Modified
- `src/astraea/parsing/form_dataset_matcher.py` - Variable overlap matching between eCRF forms and dataset profiles
- `src/astraea/classification/classifier.py` - LLM domain classification with heuristic fusion, confidence scoring, merge detection
- `tests/test_parsing/test_form_dataset_matcher.py` - 13 tests for form-dataset matching
- `tests/test_classification/test_classifier.py` - 14 tests for classifier (mocked LLM)

## Decisions Made
- [D-0204-01] Form-dataset matching uses overlap ratio of form field names over clinical variable names (uppercase, EDC-excluded)
- [D-0204-02] Heuristic-LLM disagreement (heuristic >= 0.8, LLM different domain) applies min(heuristic, llm_confidence) * 0.7 penalty
- [D-0204-03] Findings domains hardcoded set (LB, VS, EG, PE, QS, SC, FA) plus SDTMReference.get_domain_class() fallback for transpose pattern detection

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed unused json import and line length in classifier.py**
- **Found during:** Task 2 (verification)
- **Issue:** ruff flagged unused `json` import and line > 100 chars
- **Fix:** Removed unused import, split long f-string
- **Files modified:** src/astraea/classification/classifier.py
- **Verification:** `ruff check` passes clean

---

**Total deviations:** 1 auto-fixed (1 bug/lint)
**Impact on plan:** Trivial lint fix. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Form-dataset matcher and LLM classifier ready for CLI integration (Plan 05)
- classify_all() is the main entry point for the classification pipeline
- All 56 classification tests pass (29 heuristic + 27 new)

---
*Phase: 02-source-parsing*
*Completed: 2026-02-26*
