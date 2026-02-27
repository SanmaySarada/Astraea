---
status: complete
phase: 02-source-parsing
source: 02-06-SUMMARY.md, 02-07-SUMMARY.md, 02-08-SUMMARY.md
started: 2026-02-27T04:00:00Z
updated: 2026-02-27T04:10:00Z
---

## Current Test

[testing complete]

## Tests

### 1. QS/SC/FA Domain Filename Matching
expected: Files like ecoa.sas7bdat and epro.sas7bdat match QS domain. sc.sas7bdat matches SC. fa.sas7bdat matches FA. All via filename heuristic with score 1.0.
result: pass
verified: score_by_filename('ecoa.sas7bdat') -> QS 1.0, 'epro.sas7bdat' -> QS 1.0, 'sc.sas7bdat' -> SC 1.0, 'fa.sas7bdat' -> FA 1.0

### 2. Trial Design Domain Filename Matching
expected: ta.sas7bdat, te.sas7bdat, tv.sas7bdat, ti.sas7bdat, ts.sas7bdat all match their respective SDTM domains with score 1.0.
result: pass
verified: All 5 trial design files return exact match score 1.0 for TA, TE, TV, TI, TS respectively

### 3. Numbered Variant File Matching
expected: ds2.sas7bdat matches DS domain, eg3.sas7bdat matches EG, ae2.sas7bdat matches AE. Digits after domain code treated as valid boundaries.
result: pass
verified: ds2->DS 0.7, eg3->EG 0.7, ae2->AE 0.7, cm1->CM 0.7 via contains-match with digit boundary fix

### 4. SDTM-IG 18-Domain Coverage
expected: SDTMReference().list_domains() returns 18+ domains including CE, DA, DV, PE, QS, SC, SV, FA.
result: pass
verified: Returns exactly 18 domains: ['AE','CE','CM','DA','DM','DS','DV','EG','EX','FA','IE','LB','MH','PE','QS','SC','SV','VS'] -- all 8 new domains present

### 5. Heuristic Override at 0.95 Threshold
expected: When heuristic score >= 0.95 and LLM disagrees, heuristic domain is used. Prevents hallucination cascading.
result: pass
verified: classifier.py line 189 checks `top_heuristic_score >= 0.95` and overrides LLM with heuristic domain + logs "Heuristic override"

### 6. eCRF Parse Error Resilience
expected: Single form extraction failure does not crash entire pipeline. Failed forms logged as warnings, remaining forms continue.
result: pass
verified: ecrf_parser.py lines 172/180 wrap extract_form_fields in try/except; failed forms produce empty-field ECRFForm placeholders

### 7. CLI Single PDF Extraction
expected: CLI parse-ecrf command extracts PDF only once. pre_extracted_pages parameter passes already-extracted pages to parse_ecrf().
result: pass
verified: app.py line 301 extracts once into `pages`, line 311 passes `pre_extracted_pages=pages` to parse_ecrf() -- no second extraction

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
