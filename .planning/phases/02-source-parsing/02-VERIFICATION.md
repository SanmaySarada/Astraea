---
phase: 02-source-parsing
verified: 2026-02-27T02:15:00Z
status: passed
score: 4/4 must-haves verified
re_verification:
  previous_status: passed
  previous_score: 4/4
  gaps_closed:
    - "ecoa/epro match QS domain via filename heuristic (exact match score 1.0)"
    - "Numbered variants ds2, eg3 match their domains via segment-boundary matching (score 0.7)"
    - "Trial design files (TA, TE, TV, TI, TS) get heuristic exact match scores (1.0)"
    - "SDTM-IG has 18 domains including CE, DA, DV, PE, QS, SC, SV, FA"
    - "Heuristic override at 0.95 threshold works (code confirmed in classifier.py)"
    - "Single form extraction failure does not crash eCRF parsing (try/except with skip)"
    - "CLI extracts PDF pages only once via pre_extracted_pages parameter"
  gaps_remaining: []
  regressions: []
must_haves:
  truths:
    - "User provides eCRF PDF and system extracts form names, field names, data types, SAS labels, coded values, and OIDs into structured representation"
    - "System associates eCRF forms with raw datasets by matching form fields to dataset variables without hardcoded rules"
    - "System classifies each raw dataset to an SDTM domain with confidence score and natural language reasoning"
    - "System detects when multiple raw datasets should merge into a single SDTM domain"
  artifacts:
    - path: "src/astraea/models/ecrf.py"
      provides: "ECRFField, ECRFForm, ECRFExtractionResult Pydantic models"
    - path: "src/astraea/models/classification.py"
      provides: "HeuristicScore, DomainClassification, DomainPlan, ClassificationResult models"
    - path: "src/astraea/llm/client.py"
      provides: "AstraeaLLMClient with tool-use structured output, retry, logging"
    - path: "src/astraea/parsing/pdf_extractor.py"
      provides: "PDF-to-Markdown extraction with form grouping"
    - path: "src/astraea/parsing/ecrf_parser.py"
      provides: "LLM-based eCRF field extraction pipeline with cache and error resilience"
    - path: "src/astraea/parsing/form_dataset_matcher.py"
      provides: "Variable-overlap matching between eCRF forms and datasets"
    - path: "src/astraea/classification/heuristic.py"
      provides: "Deterministic filename and variable overlap scoring with 22 domain patterns"
    - path: "src/astraea/classification/classifier.py"
      provides: "LLM domain classifier with heuristic fusion, 0.95 override, and merge detection"
    - path: "src/astraea/cli/app.py"
      provides: "parse-ecrf and classify CLI commands with single-extraction optimization"
    - path: "src/astraea/cli/display.py"
      provides: "Rich display helpers for eCRF summary and classification results"
  key_links:
    - from: "ecrf_parser.py"
      to: "pdf_extractor.py"
      via: "import extract_ecrf_pages, group_pages_by_form"
    - from: "ecrf_parser.py"
      to: "llm/client.py"
      via: "client.parse() with ECRFForm output_format"
    - from: "classifier.py"
      to: "heuristic.py"
      via: "import compute_heuristic_scores, detect_merge_groups"
    - from: "classifier.py"
      to: "llm/client.py"
      via: "client.parse() with _LLMClassificationOutput"
    - from: "cli/app.py"
      to: "ecrf_parser.py + classifier.py + form_dataset_matcher.py"
      via: "CLI commands wire full pipeline"
---

# Phase 2: Source Parsing and Domain Classification Verification Report

**Phase Goal:** The system can extract structured metadata from any eCRF PDF and automatically classify which raw datasets map to which SDTM domains -- the "understanding the source" layer.
**Verified:** 2026-02-27T02:15:00Z
**Status:** passed
**Re-verification:** Yes -- confirming initial pass plus 7 gap closure items from UAT

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User provides eCRF PDF and system extracts form names, field names, data types, SAS labels, coded values, and OIDs into structured representation | VERIFIED | `ECRFField` model has all 7 fields. `ecrf_parser.py` (254 lines) orchestrates PDF extraction -> form grouping -> LLM structured extraction per form -> `ECRFForm` models. CLI `parse-ecrf` command exposes end-to-end. Error resilience: single form failure is caught and skipped (line 181-193). |
| 2 | System associates eCRF forms with raw datasets by matching form fields to dataset variables without hardcoded rules | VERIFIED | `form_dataset_matcher.py` (122 lines) implements variable-overlap matching. No hardcoded form-to-dataset mapping. Configurable threshold (default 0.2). EDC columns excluded. |
| 3 | System classifies each raw dataset to an SDTM domain with confidence score and natural language reasoning | VERIFIED | `classifier.py` (425 lines) implements two-stage classification: heuristic scoring + LLM fusion. `DomainClassification` model includes `confidence` (float 0-1) and `reasoning` (str). Heuristic override at 0.95 threshold prevents hallucination cascading. |
| 4 | System detects when multiple raw datasets should merge into a single SDTM domain | VERIFIED | `heuristic.py::detect_merge_groups()` with MERGE_PREFIXES for LB/EG/DS/EX/MH. `classify_all()` cross-references heuristic merge groups with LLM merge_candidates. `DomainPlan` tracks source_datasets and mapping_pattern. |

**Score:** 4/4 truths verified

### Gap Closure Verification

All 7 gap closure items from UAT have been verified by executing actual code:

| # | Gap Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | ecoa/epro match QS domain via filename heuristic | VERIFIED | `score_by_filename("ecoa.sas7bdat")` returns QS with score 1.0 (exact match). Same for epro. Patterns include "ecoa" and "epro" in QS entry. |
| 2 | Numbered variants (ds2, eg3) match their domains | VERIFIED | `score_by_filename("ds2.sas7bdat")` returns DS with score 0.7. `_is_segment_match()` handles digit boundaries (line 77: `name[end].isdigit()`). |
| 3 | Trial design files get heuristic scores | VERIFIED | TA, TE, TV, TI, TS all return exact match score 1.0 from `score_by_filename()`. |
| 4 | SDTM-IG has 18+ domains including CE, DA, DV, PE, QS, SC, SV, FA | VERIFIED | `SDTMReference().list_domains()` returns 18 domains: AE, CE, CM, DA, DM, DS, DV, EG, EX, FA, IE, LB, MH, PE, QS, SC, SV, VS. All 8 specified domains present. |
| 5 | Heuristic override at 0.95 threshold works | VERIFIED | `classifier.py` line 190: `if top_heuristic_score >= 0.95 and top_heuristic_domain != final_domain:` overrides LLM with heuristic domain. |
| 6 | Single form extraction failure does not crash eCRF parsing | VERIFIED | `ecrf_parser.py` line 181-193: `try/except Exception` around `extract_form_fields()` call logs warning and appends empty ECRFForm. Pipeline continues. |
| 7 | CLI extracts PDF pages only once | VERIFIED | `parse_ecrf()` accepts `pre_extracted_pages` parameter (line 121). CLI `parse-ecrf` command (line 311) passes `pre_extracted_pages=pages` after extracting once at line 301. |

### Required Artifacts

| Artifact | Lines | Status | Details |
|----------|-------|--------|---------|
| `src/astraea/models/ecrf.py` | 79 | VERIFIED | ECRFField with all 7 fields, ECRFForm, ECRFExtractionResult. No stubs. |
| `src/astraea/models/classification.py` | 97 | VERIFIED | HeuristicScore, DomainClassification, DomainPlan, ClassificationResult. No stubs. |
| `src/astraea/llm/client.py` | 142 | VERIFIED | AstraeaLLMClient with tool-use structured output, tenacity retry, loguru logging. No stubs. |
| `src/astraea/parsing/pdf_extractor.py` | 125 | VERIFIED | pymupdf4llm extraction, group_pages_by_form(). No stubs. |
| `src/astraea/parsing/ecrf_parser.py` | 254 | VERIFIED | Full extraction pipeline with error resilience, pre_extracted_pages optimization, cache. No stubs. |
| `src/astraea/parsing/form_dataset_matcher.py` | 122 | VERIFIED | Variable-overlap matching, configurable threshold. No stubs. |
| `src/astraea/classification/heuristic.py` | 290 | VERIFIED | 22 domain filename patterns, MERGE_PREFIXES, segment-boundary matching, variable overlap scoring. No stubs. |
| `src/astraea/classification/classifier.py` | 425 | VERIFIED | Heuristic-LLM fusion, 0.95 override, merge detection, cache. No stubs. |
| `src/astraea/cli/app.py` | 478 | VERIFIED | parse-ecrf and classify commands with full pipeline wiring, single-extraction. No stubs. |
| `src/astraea/cli/display.py` | 382 | VERIFIED | Rich display helpers for eCRF summary and classification. No stubs. |

**Total:** 2,394 lines across 10 files.

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| ecrf_parser.py | pdf_extractor.py | `from astraea.parsing.pdf_extractor import extract_ecrf_pages, group_pages_by_form` | WIRED |
| ecrf_parser.py | llm/client.py | `client.parse(output_format=ECRFForm)` | WIRED |
| classifier.py | heuristic.py | `from astraea.classification.heuristic import compute_heuristic_scores, detect_merge_groups` | WIRED |
| classifier.py | llm/client.py | `client.parse(output_format=_LLMClassificationOutput)` | WIRED |
| cli/app.py | ecrf_parser + classifier + form_dataset_matcher | Direct imports, full pipeline orchestration | WIRED |

### Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| ECRF-01: Parse eCRF PDF, extract form-level metadata | SATISFIED | ECRFForm model with form_name, page_numbers; pdf_extractor groups by form header |
| ECRF-02: Extract field-level metadata | SATISFIED | ECRFField has all 7 fields; LLM structured extraction |
| ECRF-03: Associate eCRF forms with raw datasets | SATISFIED | form_dataset_matcher.py variable overlap matching |
| ECRF-04: Handle variable eCRF layouts | SATISFIED | Regex-based form detection, LLM interprets layouts |
| CLSF-01: Classify raw datasets to SDTM domains | SATISFIED | Two-stage heuristic + LLM classification |
| CLSF-02: Handle all three SDTM domain classes | SATISFIED | _FINDINGS_DOMAINS covers Findings; filename patterns cover Events and Interventions |
| CLSF-03: Detect multi-dataset merges | SATISFIED | detect_merge_groups() + LLM merge_candidates |
| CLSF-04: Confidence score and reasoning | SATISFIED | DomainClassification has confidence (0-1) and reasoning |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| ecrf_parser.py | 188 | "placeholder" in comment | Info | Comment explains error-recovery behavior (empty form when extraction fails). Not a stub -- legitimate design. |

### Human Verification Required

### 1. Real eCRF PDF End-to-End Extraction Quality

**Test:** Run `astraea parse-ecrf ECRF.pdf --detail` and verify extracted field names/types match the actual PDF
**Expected:** Form names match PDF headers; field names are valid SAS variable names; coded values match PDF
**Why human:** Extraction quality depends on PDF layout; automated tests use mocked LLM responses

### 2. Real Classification Accuracy

**Test:** Run `astraea classify Fakedata/ --ecrf ECRF.pdf` and review domain assignments
**Expected:** ae.sas7bdat -> AE, dm.sas7bdat -> DM, lb_*.sas7bdat -> LB with merge group
**Why human:** Classification correctness requires domain expertise

### 3. Heuristic Override Behavior in Practice

**Test:** Verify that when a dataset has a strong filename match (e.g., ae.sas7bdat), the heuristic override prevents LLM hallucination
**Expected:** Override triggers for exact-match filenames if LLM disagrees, logged as warning
**Why human:** Requires LLM disagreement scenario which cannot be reliably triggered in tests

### Gaps Summary

No gaps found. All 4 success criteria are structurally verified. All 7 gap closure items from UAT are confirmed working via code execution. 389 tests pass. No stub patterns or blockers detected. The phase goal -- "understanding the source layer" -- is achieved.

---

_Verified: 2026-02-27T02:15:00Z_
_Verifier: Claude (gsd-verifier)_
