---
status: complete
phase: 02-source-parsing
source: 02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md, 02-04-SUMMARY.md, 02-05-SUMMARY.md
started: 2026-02-27T01:30:00Z
updated: 2026-02-27T01:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. eCRF Data Model Completeness
expected: All 7 eCRF field attributes captured (field_name, data_type, sas_label, units, coded_values, field_oid) with proper validation
result: pass

### 2. Classification Model with SUPPQUAL + Merge Support
expected: DomainClassification includes secondary_domains, merge_candidates, confidence 0-1, and DomainPlan has mapping_pattern Literal
result: pass

### 3. PDF Extraction and Multi-Page Form Grouping
expected: pymupdf4llm extracts 189 pages, groups into 39 forms, handles multi-page forms (e.g., Vital Signs 7 pages)
result: pass

### 4. eCRF LLM Structured Extraction
expected: Each form sent to Claude with Pydantic schema, returns structured ECRFForm with fields; results cacheable to JSON
result: pass

### 5. Heuristic Filename Pattern Coverage
expected: All standard SDTM domains have filename patterns for automatic scoring
result: issue
reported: "Only 15 domains covered. Missing QS (questionnaires -- needed for ecoa/epro files), SC, FA, and trial design domains (TA, TE, TV, TI, TS). 12/36 files (33%) get no filename heuristic match."
severity: major

### 6. Heuristic Numbered Variant Matching
expected: Files like ds2.sas7bdat and eg3.sas7bdat match their base domain (DS, EG) via filename heuristic
result: issue
reported: "Segment boundary matching is too strict -- bare digits after domain code don't count as boundaries. ds2, eg3, llb all get no filename match."
severity: minor

### 7. Variable Overlap Scoring Against SDTM-IG
expected: Variable overlap uses bundled SDTM-IG reference for all relevant domains
result: issue
reported: "SDTM-IG reference bundle only contains 10 domains (AE, CM, DM, DS, EG, EX, IE, LB, MH, VS). Missing CE, DA, DV, PE, QS, SC, SV, FA. Variable overlap scoring impossible for these domains."
severity: major

### 8. Form-Dataset Matcher (Variable Overlap)
expected: Case-insensitive matching, configurable threshold, EDC columns excluded, no hardcoded rules
result: pass

### 9. Heuristic-LLM Fusion Logic
expected: High heuristic + LLM agreement boosts confidence; disagreement penalizes confidence and flags for review
result: issue
reported: "When heuristic >= 0.8 disagrees with LLM, the LLM's domain is still used (only confidence penalized). Per Pitfall C1, heuristic should override LLM on very high-confidence exact matches (>= 0.95) to prevent hallucination cascading."
severity: minor

### 10. CLI parse-ecrf Command
expected: Extracts PDF, shows Rich-formatted table of forms with field counts and page ranges
result: issue
reported: "PDF is extracted TWICE -- once for progress display count, once inside parse_ecrf(). Performance bug, not correctness."
severity: minor

### 11. CLI classify Command
expected: Profiles SAS files, classifies to domains with color-coded confidence, shows merge groups
result: pass

### 12. LLM Client Tool-Use Structured Output
expected: Forced tool_choice guarantees Pydantic-valid JSON; retry on transient errors only; BadRequestError not retried
result: pass

### 13. Parse Error Resilience
expected: If LLM fails on one eCRF form, pipeline continues with remaining forms
result: issue
reported: "No try/except around extract_form_fields in parse_ecrf loop. Single form extraction failure crashes entire pipeline."
severity: major

## Summary

total: 13
passed: 7
issues: 6
pending: 0
skipped: 0

## Gaps

- truth: "All standard SDTM domains have filename patterns for heuristic scoring"
  status: failed
  reason: "Only 15 of ~25 domains covered. Missing QS, SC, FA, TA, TE, TV, TI, TS."
  severity: major
  test: 5
  artifacts:
    - path: "src/astraea/classification/heuristic.py"
      issue: "FILENAME_PATTERNS dict missing domains"
  missing:
    - "Add QS, SC, FA, TA, TE, TV, TI, TS patterns"

- truth: "Variable overlap scoring works for all classifiable domains"
  status: failed
  reason: "SDTM-IG reference bundle only has 10 domains. LLM available_domains list is limited to these 10."
  severity: major
  test: 7
  artifacts:
    - path: "src/astraea/reference/"
      issue: "Bundled JSON missing CE, DA, DV, PE, QS, SC, SV, FA domain specs"
  missing:
    - "Expand SDTM-IG JSON bundle with additional domain specifications"
    - "Update SDTMReference to expose all domains"

- truth: "Single form extraction failure does not crash eCRF parsing pipeline"
  status: failed
  reason: "No error handling around individual form extraction in parse_ecrf loop"
  severity: major
  test: 13
  artifacts:
    - path: "src/astraea/parsing/ecrf_parser.py"
      issue: "Missing try/except in parse_ecrf form iteration loop"
  missing:
    - "Add try/except around extract_form_fields, log warning, continue with remaining forms"

- truth: "Numbered variant files match base domain via heuristic"
  status: failed
  reason: "Segment boundary matching rejects bare digits as boundaries"
  severity: minor
  test: 6
  artifacts:
    - path: "src/astraea/classification/heuristic.py"
      issue: "_is_segment_match too strict"
  missing:
    - "Allow digits as right-boundary characters in segment matching"

- truth: "Heuristic overrides LLM on very high-confidence exact filename matches"
  status: failed
  reason: "LLM domain always used even when heuristic has exact match (1.0)"
  severity: minor
  test: 9
  artifacts:
    - path: "src/astraea/classification/classifier.py"
      issue: "Disagreement handling at lines 186-207"
  missing:
    - "Add override: if heuristic >= 0.95, use heuristic domain regardless of LLM"

- truth: "CLI parse-ecrf extracts PDF once, not twice"
  status: failed
  reason: "Double PDF extraction -- once for count, once in parse_ecrf()"
  severity: minor
  test: 10
  artifacts:
    - path: "src/astraea/cli/app.py"
      issue: "Lines 296-314 extract twice"
  missing:
    - "Pass pre-extracted pages to parse_ecrf or refactor to extract once"
