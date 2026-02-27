---
phase: 02-source-parsing
verified: 2026-02-27T01:30:00Z
status: passed
score: 4/4 must-haves verified
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
      provides: "LLM-based eCRF field extraction pipeline with cache"
    - path: "src/astraea/parsing/form_dataset_matcher.py"
      provides: "Variable-overlap matching between eCRF forms and datasets"
    - path: "src/astraea/classification/heuristic.py"
      provides: "Deterministic filename and variable overlap scoring"
    - path: "src/astraea/classification/classifier.py"
      provides: "LLM domain classifier with heuristic fusion and merge detection"
    - path: "src/astraea/cli/app.py"
      provides: "parse-ecrf and classify CLI commands"
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
**Verified:** 2026-02-27T01:30:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User provides eCRF PDF and system extracts form names, field names, data types, SAS labels, coded values, and OIDs into structured representation | VERIFIED | `ECRFField` model has all 7 fields (field_number, field_name, data_type, sas_label, units, coded_values, field_oid). `ecrf_parser.py` sends PDF pages to Claude with structured output, returns `ECRFForm` models. `parse_ecrf()` orchestrates full pipeline. CLI `parse-ecrf` command exposes this end-to-end. SUMMARY reports 39 forms with 356 fields extracted from real ECRF.pdf. |
| 2 | System associates eCRF forms with raw datasets by matching form fields to dataset variables without hardcoded rules | VERIFIED | `form_dataset_matcher.py` implements variable-overlap matching: computes fraction of form field names appearing in dataset clinical variables (case-insensitive, EDC-excluded). No hardcoded form-to-dataset mapping. `match_all_forms()` with configurable threshold (default 0.2). 13 tests cover matching logic. |
| 3 | System classifies each raw dataset to an SDTM domain with confidence score and natural language reasoning | VERIFIED | `classifier.py` implements two-stage classification: heuristic scoring + LLM fusion. `DomainClassification` model includes `confidence` (float 0-1), `reasoning` (str), and `heuristic_scores` (traceability). Heuristic-LLM agreement boosts confidence; disagreement penalizes. CLI `classify` command displays confidence with color coding. |
| 4 | System detects when multiple raw datasets should merge into a single SDTM domain | VERIFIED | `heuristic.py::detect_merge_groups()` uses prefix patterns to find multi-file domains (e.g., lb_biochem + lb_hem -> LB). `classifier.py::classify_all()` cross-references heuristic merge groups with LLM merge_candidates. `DomainPlan` model captures source_datasets list and mapping_pattern. CLI displays merge groups panel. SUMMARY confirms LB merge group (biochem, hem, urin, coagulation) detected. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/astraea/models/ecrf.py` | eCRF Pydantic models | VERIFIED (79 lines) | ECRFField with field_name validation, ECRFForm, ECRFExtractionResult with computed total_fields. Has exports, no stubs. |
| `src/astraea/models/classification.py` | Classification Pydantic models | VERIFIED (97 lines) | HeuristicScore, DomainClassification, DomainPlan (with Literal mapping_pattern), ClassificationResult. Has exports, no stubs. |
| `src/astraea/llm/client.py` | LLM client wrapper | VERIFIED (142 lines) | AstraeaLLMClient with tool-use structured output, tenacity retry (3 attempts, exponential backoff), loguru logging of tokens/latency. No stubs. |
| `src/astraea/parsing/pdf_extractor.py` | PDF extraction | VERIFIED (125 lines) | Uses pymupdf4llm with page_chunks=True. group_pages_by_form() via regex. get_form_names(). No stubs. |
| `src/astraea/parsing/ecrf_parser.py` | eCRF parser | VERIFIED (236 lines) | Full extraction prompt, extract_form_fields() per form, parse_ecrf() orchestrator, save/load cache. No stubs. |
| `src/astraea/parsing/form_dataset_matcher.py` | Form-dataset matcher | VERIFIED (122 lines) | match_form_to_datasets(), match_all_forms(), get_unmatched_datasets/forms(). Variable overlap scoring. No stubs. |
| `src/astraea/classification/heuristic.py` | Heuristic scorer | VERIFIED (282 lines) | 15-domain filename patterns, MERGE_PREFIXES, segment-boundary matching, score_by_variables() against SDTM-IG, detect_merge_groups(). No stubs. |
| `src/astraea/classification/classifier.py` | LLM classifier | VERIFIED (408 lines) | classify_dataset() with heuristic-LLM fusion, classify_all() orchestrator, _determine_mapping_pattern(), save/load cache. No stubs. |
| `src/astraea/cli/app.py` | CLI commands | VERIFIED (478 lines) | parse-ecrf and classify commands with full pipeline wiring, cache support, API key check. No stubs. |
| `src/astraea/cli/display.py` | Rich display helpers | VERIFIED (382 lines) | display_ecrf_summary(), display_ecrf_form_detail(), display_classification() with confidence color-coding and merge groups panel. No stubs. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| ecrf_parser.py | pdf_extractor.py | `from astraea.parsing.pdf_extractor import extract_ecrf_pages, group_pages_by_form` | WIRED | parse_ecrf() calls extract_ecrf_pages() then group_pages_by_form(), uses results for LLM calls |
| ecrf_parser.py | llm/client.py | `client.parse(output_format=ECRFForm)` | WIRED | extract_form_fields() calls client.parse() with model, messages, ECRFForm output_format, temperature=0.2 |
| classifier.py | heuristic.py | `from astraea.classification.heuristic import compute_heuristic_scores, detect_merge_groups` | WIRED | classify_all() calls compute_heuristic_scores() per dataset and detect_merge_groups() for merge detection |
| classifier.py | llm/client.py | `client.parse(output_format=_LLMClassificationOutput)` | WIRED | classify_dataset() calls client.parse() with classification prompt and structured output |
| classifier.py | form_dataset_matcher.py | Indirect via classify CLI | WIRED | CLI classify command calls match_all_forms() then passes form_matches to classify_all() |
| cli/app.py | ecrf_parser + classifier | `from astraea.parsing.ecrf_parser import parse_ecrf` / `from astraea.classification.classifier import classify_all` | WIRED | Full pipeline: profile -> parse eCRF -> match forms -> classify all. Both commands implemented with error handling. |
| models/__init__.py | ecrf.py + classification.py | re-exports | WIRED | All eCRF and classification models re-exported in models/__init__.py |

### Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| ECRF-01: Parse eCRF PDF, extract form-level metadata | SATISFIED | ECRFForm model with form_name, page_numbers; pdf_extractor groups by form header |
| ECRF-02: Extract field-level metadata (names, types, labels, coded values, OIDs) | SATISFIED | ECRFField has all 7 fields; ecrf_parser LLM prompt extracts from field tables |
| ECRF-03: Associate eCRF forms with raw datasets | SATISFIED | form_dataset_matcher.py uses variable overlap, no hardcoded rules |
| ECRF-04: Handle variable eCRF layouts (not hardcoded) | SATISFIED | Regex-based form detection ("Form: <name>"), LLM interprets varying layouts |
| CLSF-01: Classify raw datasets to SDTM domains using eCRF context, variables, data content | SATISFIED | Two-stage: heuristic (filename + variable overlap) + LLM with eCRF form context |
| CLSF-02: Handle all three SDTM domain classes (Interventions, Events, Findings) | SATISFIED | _FINDINGS_DOMAINS set covers LB/VS/EG/PE/QS/SC/FA; filename patterns cover CM/EX (Interventions), AE/CE/MH/DV/DS (Events); _determine_mapping_pattern uses domain class |
| CLSF-03: Detect multi-dataset merges | SATISFIED | detect_merge_groups() with MERGE_PREFIXES for LB/EG/DS/EX/MH; classify_all() cross-refs with LLM merge_candidates; DomainPlan tracks source_datasets |
| CLSF-04: Confidence score and reasoning for each classification | SATISFIED | DomainClassification has confidence (0-1, validated) and reasoning (str); heuristic-LLM fusion adjusts confidence; CLI displays with color coding |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none found) | - | - | - | No TODO, FIXME, placeholder, or stub patterns detected in any Phase 2 source files |

### Human Verification Required

### 1. Real eCRF PDF End-to-End Extraction Quality

**Test:** Run `astraea parse-ecrf ECRF.pdf --detail` and verify extracted field names/types match the actual PDF
**Expected:** Form names match PDF headers; field names are valid SAS variable names; coded values match what the PDF shows
**Why human:** Extraction quality depends on PDF layout; automated tests use mocked LLM responses

### 2. Real Classification Accuracy

**Test:** Run `astraea classify Fakedata/ --ecrf ECRF.pdf` and review domain assignments
**Expected:** ae.sas7bdat -> AE, dm.sas7bdat -> DM, lb_*.sas7bdat -> LB with merge group, etc.
**Why human:** Classification correctness requires domain expertise; automated tests use mocked LLM

### 3. LB Merge Group Completeness

**Test:** Verify the LB merge group includes all lab files (biochem, hem, urin, coagulation)
**Expected:** All lab-related files detected and grouped into LB domain plan
**Why human:** Requires checking against actual Fakedata/ directory contents

### Gaps Summary

No gaps found. All 4 success criteria are structurally verified:

1. eCRF extraction pipeline is complete: PDF -> Markdown -> form grouping -> LLM structured extraction -> ECRFForm models with all required fields (form names, field names, data types, SAS labels, coded values, OIDs).

2. Form-dataset matching uses deterministic variable-overlap scoring with no hardcoded rules. Configurable threshold, EDC columns excluded.

3. Domain classification combines heuristic scoring (15 domains, filename + variable overlap) with LLM reasoning. Every classification includes confidence score (0-1) and natural language reasoning string. Heuristic-LLM fusion adjusts confidence on agreement/disagreement.

4. Merge detection works at both heuristic level (MERGE_PREFIXES for known patterns like lb_*) and LLM level (merge_candidates field). DomainPlan aggregates source datasets and determines mapping pattern (direct/merge/transpose/mixed).

144 tests pass covering all Phase 2 components. All artifacts are substantive (2,351 total lines across 10 files), properly exported, and wired into the CLI.

---

_Verified: 2026-02-27T01:30:00Z_
_Verifier: Claude (gsd-verifier)_
