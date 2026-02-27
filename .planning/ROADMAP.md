# Roadmap

**Project:** Astraea-SDTM
**Created:** 2026-02-26
**Phases:** 8

## Overview

This roadmap derives 8 phases from the 66 v1 requirements, following the natural dependency chain of an SDTM mapping pipeline: build data infrastructure first, then source parsing, then prove the mapping engine on a single domain (DM), add human review, expand to all domains (split into Events/Interventions and Findings to separate simple mappings from hard transpose logic), layer in full validation, and finally add the learning system once correction data exists. The split between Phase 5 (Events/Interventions) and Phase 6 (Findings) reflects a real technical boundary: Events and Interventions domains are mostly direct/rename/recode mappings, while Findings domains require horizontal-to-vertical transpose -- the hardest transformation in the entire system.

## Phases

### Phase 1: Foundation and Data Infrastructure

**Goal:** The system can read any study's raw SAS data, access all CDISC reference standards, and produce valid XPT output files -- the deterministic data plumbing that every agent depends on.
**Depends on:** Nothing (first phase)
**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, CLI-01, CLI-04

**Success Criteria:**
1. User can run the CLI, point it at a folder of SAS files, and see profiling output (variable names, types, labels, row counts, value distributions) printed to terminal
2. User can see SDTM-IG domain definitions and NCI CT codelists loaded and queryable (e.g., "show me all required variables for DM domain")
3. System converts a variety of date formats (SAS numeric, DD/MM/YYYY, partial dates) to ISO 8601 correctly, including partial date imputation per SDTM-IG rules
4. System generates USUBJID from STUDYID + SITEID + SUBJID and validates consistency
5. System writes a valid .xpt file from a pandas DataFrame that passes structural validation

**Plans:** 5 plans

Plans:
- [ ] 01-01-PLAN.md -- Project setup, dependencies, and Pydantic data models
- [ ] 01-02-PLAN.md -- SAS file reader and dataset profiler
- [ ] 01-03-PLAN.md -- CDISC SDTM-IG and NCI CT bundled reference data
- [ ] 01-04-PLAN.md -- ISO 8601 date conversion and USUBJID utilities
- [ ] 01-05-PLAN.md -- XPT writer and CLI integration

---

### Phase 2: Source Parsing and Domain Classification

**Goal:** The system can extract structured metadata from any eCRF PDF and automatically classify which raw datasets map to which SDTM domains -- the "understanding the source" layer.
**Depends on:** Phase 1 (needs SAS profiling and SDTM reference data)
**Requirements:** ECRF-01, ECRF-02, ECRF-03, ECRF-04, CLSF-01, CLSF-02, CLSF-03, CLSF-04

**Success Criteria:**
1. User provides an eCRF PDF and the system extracts form names, field names, data types, SAS labels, coded values, and OIDs into a structured representation
2. System associates eCRF forms with raw datasets (matching form fields to dataset variables) without hardcoded rules
3. System classifies each raw dataset to an SDTM domain with a confidence score and natural language reasoning
4. System correctly detects when multiple raw datasets should merge into a single SDTM domain (e.g., multiple lab files into LB)

**Plans:** 8 plans (5 core + 3 gap closure)

Plans:
- [ ] 02-01-PLAN.md -- Pydantic models (eCRF + classification) and LLM client wrapper
- [ ] 02-02-PLAN.md -- PDF extraction and eCRF parser (pymupdf4llm + Claude structured output)
- [ ] 02-03-PLAN.md -- Heuristic domain scorer (deterministic filename + variable matching)
- [ ] 02-04-PLAN.md -- Form-dataset matcher and LLM domain classifier with heuristic fusion
- [ ] 02-05-PLAN.md -- CLI commands (parse-ecrf, classify) and integration verification
- [ ] 02-06-PLAN.md -- Gap closure: expand filename patterns + numbered variant matching
- [ ] 02-07-PLAN.md -- Gap closure: expand SDTM-IG reference bundle + heuristic override
- [ ] 02-08-PLAN.md -- Gap closure: eCRF error handling + CLI double extraction fix

---

### Phase 3: Core Mapping Engine (Demographics)

**Goal:** The system can take a classified domain, propose complete variable-level mappings using all mapping patterns, and output a mapping specification document -- proven end-to-end on the DM domain as the reference implementation.
**Depends on:** Phase 2 (needs parsed eCRF and domain classification)
**Requirements:** MAP-01, MAP-02, MAP-03, MAP-04, MAP-05, MAP-06, MAP-07, MAP-08, MAP-09, MAP-10, MAP-11, MAP-12, DOM-01, SPEC-01, SPEC-02, SPEC-03, SPEC-04

**Success Criteria:**
1. System produces a complete DM domain mapping specification (Excel workbook and JSON) with every SDTM variable traced to its source, derivation algorithm, and controlled terminology
2. Every mapping decision includes a confidence score (HIGH/MEDIUM/LOW) and a natural language explanation of why this source maps to this target
3. System handles all 9 mapping patterns correctly on DM: direct copy, rename, reformat, split, combine (USUBJID), derivation (AGE), lookup/recode (SEX, RACE), transpose (if applicable), and variable attribute mapping
4. System converts natural language derivation descriptions into executable transformations
5. Mapping specification has full source-to-target traceability (every SDTM variable in DM traces back to origin)

**Plans:** (created by /gsd:plan-phase)

---

### Phase 4: Human Review Gate

**Goal:** A human reviewer can inspect every proposed mapping, approve or correct it interactively, and resume an interrupted review session -- the quality control layer that makes the system trustworthy in a regulated environment.
**Depends on:** Phase 3 (needs mapping specifications to review)
**Requirements:** HITL-01, HITL-02, CLI-02, CLI-03

**Success Criteria:**
1. System pauses after each domain's mapping and presents a formatted table of proposed mappings with confidence scores highlighted, waiting for human approval or correction
2. User can approve individual mappings, correct wrong mappings (specifying what was wrong and what is correct), and the system captures structured correction metadata
3. User can quit a review session and resume it later, picking up exactly where they left off (LangGraph checkpoint)

**Plans:** (created by /gsd:plan-phase)

---

### Phase 5: Event and Intervention Domains

**Goal:** The system maps all Events-class and Interventions-class SDTM domains -- the domains that primarily use direct, rename, recode, and derivation patterns (no transpose required).
**Depends on:** Phase 4 (needs human review gate for domain-by-domain approval)
**Requirements:** DOM-02, DOM-03, DOM-04, DOM-08, DOM-09, DOM-11, DOM-12, DOM-13

**Success Criteria:**
1. System produces complete, reviewable mapping specifications for AE, CM, EX, MH, DS, IE, CE, and DV domains
2. AE domain correctly maps start/end dates, severity, causality, seriousness, and outcome variables with appropriate controlled terminology
3. CM domain correctly maps dose, route, frequency, and indication with CT lookups
4. All 8 domains pass human review and generate correct SDTM datasets with valid variable attributes

**Plans:** (created by /gsd:plan-phase)

---

### Phase 6: Findings Domains and Complex Transformations

**Goal:** The system maps all Findings-class domains (requiring horizontal-to-vertical transpose), generates SUPPQUAL and RELREC datasets, and handles trial design domains -- the technically hardest transformations in the pipeline.
**Depends on:** Phase 5 (proven domain expansion pattern; transpose builds on mapping engine)
**Requirements:** DOM-05, DOM-06, DOM-07, DOM-10, DOM-14, DOM-15, DOM-16

**Success Criteria:**
1. System correctly transposes wide-format lab data into tall SDTM LB format with LBTESTCD, LBTEST, LBORRES, LBORRESU, LBSTRESC, LBSTRESN, LBSTRESU, and normal range variables -- including merging multiple source lab files into a single LB domain
2. System correctly transposes VS and EG domains with standardized results and handles pre-dose/post-dose EG records
3. System generates SUPPQUAL datasets when non-standard variables require supplemental qualifiers, and RELREC datasets for cross-domain relationships
4. System maps PE, SV, and trial design domains (TA, TE, TV, TI, TS) correctly

**Plans:** (created by /gsd:plan-phase)

---

### Phase 7: Validation and Submission Readiness

**Goal:** The system runs comprehensive P21-style conformance validation on all output datasets and generates the regulatory submission artifacts (define.xml, validation report) required for FDA submission.
**Depends on:** Phase 6 (needs all domains generated to validate cross-domain consistency)
**Requirements:** VAL-01, VAL-02, VAL-03, VAL-04, VAL-05, VAL-06, VAL-07, VAL-08

**Success Criteria:**
1. System runs terminology, presence, consistency, limit, and format validation rules on every generated dataset and reports issues with severity levels (Error/Warning/Notice) and fix suggestions
2. System validates during mapping (predict-and-prevent) in addition to post-generation validation
3. System generates a complete define.xml (v2.0+) with dataset metadata, variable metadata, codelists, value-level metadata, and computational methods
4. System produces a pre-submission validation report that a statistical programmer can use to confirm submission readiness

**Plans:** (created by /gsd:plan-phase)

---

### Phase 8: Learning System

**Goal:** The system learns from accumulated human corrections across studies, retrieves relevant past corrections when mapping new data, and measurably improves accuracy over time -- the core differentiator that makes Astraea better with every use.
**Depends on:** Phase 7 (needs correction data accumulated from Phases 4-7; needs validation metrics as learning signal)
**Requirements:** HITL-03, HITL-04, HITL-05, HITL-06, HITL-07

**Success Criteria:**
1. Human corrections are stored in a structured database with full metadata (what was wrong, what is correct, why, domain, variable type)
2. When mapping a new study, the system retrieves similar past corrections and uses them as few-shot examples in prompts, demonstrably improving mapping proposals
3. System builds a cross-study template library from approved mappings that can be applied to new studies
4. System accuracy improves measurably between the first and third study processed (tracked metric)

**Plans:** (created by /gsd:plan-phase)

---

## Progress

| Phase | Status | Completed |
|-------|--------|-----------|
| 1 - Foundation and Data Infrastructure | Complete | 2026-02-26 |
| 2 - Source Parsing and Domain Classification | UAT gap closure | 2026-02-26 |
| 3 - Core Mapping Engine (Demographics) | Not started | -- |
| 4 - Human Review Gate | Not started | -- |
| 5 - Event and Intervention Domains | Not started | -- |
| 6 - Findings Domains and Complex Transformations | Not started | -- |
| 7 - Validation and Submission Readiness | Not started | -- |
| 8 - Learning System | Not started | -- |

---

*Roadmap for milestone: v1.0*
