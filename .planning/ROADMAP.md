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

### Phase 2.1: Reference Data Fixes (Critical for Phase 3) (INSERTED)

**Goal:** Fix all Tier 1 reference data errors identified in the Phase 2 comprehensive audit — 9 wrong NCI C-codes, 19 wrong codelist assignments, 15 wrong core designations, missing codelist assignments, DA domain class fix, missing natural keys, EDC column gaps, and critical code bugs (USUBJID NaN, date validation, SAS numeric rounding) — so the Phase 3 mapper has correct reference data to produce valid SDTM output.
**Depends on:** Phase 2 (audit findings require Phase 2 infrastructure to exist)
**Requirements:** Audit Tier 1 items (14 fixes) — see .planning/PHASE2_AUDIT.md §9
**Blocked by:** Nothing (Phase 2 complete)
**Blocks:** Phase 3 (mapper cannot produce correct output with wrong reference data)

**Success Criteria:**
1. All 11 CT codelists in codelists.json have correct NCI C-codes verified against NCI EVS
2. All codelist assignments in domains.json match SDTM-IG v3.4 specification (19 fixes)
3. All core designations (Req/Exp/Perm) match SDTM-IG v3.4 for every variable (15 fixes)
4. DA domain class corrected to Findings
5. All null codelist assignments filled where SDTM-IG specifies a codelist (16+ variables)
6. Natural key_variables defined for all 9 core domains
7. EDC column set updated (6 missing columns + 1 typo fix)
8. USUBJID NaN bug fixed, date range validation added, SAS numeric rounding fixed, partial date patterns added
9. All existing tests still pass + new tests for each fix

**Plans:** 4 plans

Plans:
- [x] 02.1-01-PLAN.md -- Fix all 9 NCI C-codes in codelists.json + Race extensibility + NY "U" term
- [x] 02.1-02-PLAN.md -- Fix date conversion bugs (round(), validation, UN UNK, datetime strings)
- [x] 02.1-03-PLAN.md -- Fix USUBJID NaN bug + EDC column set updates
- [x] 02.1-04-PLAN.md -- Fix domains.json (codelist assignments, core designations, DA class, null codelists, key_variables)

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

**Plans:** 5 plans

Plans:
- [x] 03-01-PLAN.md -- Mapping specification Pydantic models (9 patterns, confidence scoring, LLM output schema)
- [x] 03-02-PLAN.md -- Context builder (assembles focused LLM prompts from domain spec + profiles + eCRF + CT)
- [x] 03-03-PLAN.md -- Mapping engine core (LLM call orchestrator, system prompt, post-proposal validation/enrichment)
- [x] 03-04-PLAN.md -- Excel/JSON exporters and CLI map-domain command with Rich display
- [x] 03-05-PLAN.md -- Integration test on real DM data with human verification of mapping quality

---

### Phase 3.1: Audit Fixes + Architectural Wiring (INSERTED)

**Goal:** Fix all issues from .planning/PHASE3_AUDIT.md (5 CRITICAL + 14 HIGH + 8 MEDIUM + 3 architectural gaps) so Phase 4 has a complete, correct foundation.
**Depends on:** Phase 3 (complete)
**Blocks:** Phase 4
**Requirements:** All items from PHASE3_AUDIT.md sections 2-6 and 9

**Success Criteria:**
1. TS domain in domains.json with full variable list
2. 16 missing codelists added to codelists.json; C66742 has only N,Y
3. All core designations match SDTM-IG v3.4
4. Trial Design domains (TA, TE, TV, TI) + SE + CO added
5. DomainMappingSpec has missing_required_variables; VariableMapping has order + length
6. SUPPQUAL label bug, profiler date detection, XPT writer gaps all fixed
7. transforms/ wired into production code (currently zero production imports)
8. All 579+ tests pass; ruff clean

**Plans:** 5 plans

Plans:
- [x] 03.1-01-PLAN.md -- Add 16 missing CT codelists + fix C66742 invalid "U" term
- [x] 03.1-02-PLAN.md -- Add TS, Trial Design, SE, CO, SUPPQUAL domains to domains.json
- [x] 03.1-03-PLAN.md -- Fix core designations, labels, missing variables, null key_variables
- [x] 03.1-04-PLAN.md -- Add model fields (order, length, missing_required) + fix SUPPQUAL label bug
- [x] 03.1-05-PLAN.md -- Fix profiler date bug, XPT writer gaps, docstrings, transform wiring

---

### Phase 4: Human Review Gate

**Goal:** A human reviewer can inspect every proposed mapping, approve or correct it interactively, and resume an interrupted review session -- the quality control layer that makes the system trustworthy in a regulated environment.
**Depends on:** Phase 3 (needs mapping specifications to review)
**Requirements:** HITL-01, HITL-02, CLI-02, CLI-03

**Success Criteria:**
1. System pauses after each domain's mapping and presents a formatted table of proposed mappings with confidence scores highlighted, waiting for human approval or correction
2. User can approve individual mappings, correct wrong mappings (specifying what was wrong and what is correct), and the system captures structured correction metadata
3. User can quit a review session and resume it later, picking up exactly where they left off (SQLite session persistence)

**Plans:** 3 plans

Plans:
- [x] 04-01-PLAN.md -- Review data models (HumanCorrection, ReviewSession) and SQLite session persistence
- [x] 04-02-PLAN.md -- Review display layer and core reviewer logic (two-tier review, correction capture)
- [x] 04-03-PLAN.md -- CLI commands (review-domain, resume, sessions) and interactive verification

---

### Phase 4.1: FDA Compliance Infrastructure (INSERTED)

**Goal:** Close all foundational gaps identified by comparing the codebase against FDA SDTM submission requirements -- the missing derivation utilities (--DY, --SEQ, EPOCH, VISITNUM), dataset execution pipeline (spec -> DataFrame -> XPT), variable/sort order enforcement, origin tracking, date imputation flags, character length optimization, ASCII validation, and missing CT codelists -- so that Phase 5+ domain expansion produces submission-ready output, not just mapping specifications.
**Depends on:** Phase 4 (complete)
**Blocks:** Phase 5 (every domain needs --DY, --SEQ, sort order, execution pipeline)
**Requirements:** FDA TRC compliance, P21 validation readiness

**Success Criteria:**
1. --DY (study day) calculation utility exists in transforms/ and correctly computes INT((--DTC - RFSTDTC) + 1) with day-1 convention, negative pre-treatment days, and partial date handling
2. --SEQ generation utility produces unique monotonic integer sequences within USUBJID for any domain
3. EPOCH derivation maps dates to study epochs (SCREENING, BASELINE, TREATMENT, FOLLOW-UP) from SE milestones
4. VISITNUM/VISIT variables derived from TV (Trial Visits) domain structure or raw visit data
5. Dataset execution pipeline transforms approved DomainMappingSpec + raw DataFrames into SDTM-compliant DataFrames (applying all mapping patterns: direct, rename, reformat, derivation, lookup/recode, assign)
6. XPT writer enforces SDTM-IG sort order per domain (DM: STUDYID/USUBJID, AE: STUDYID/USUBJID/AEDECOD/AESTDTC, etc.) and variable column order per domain spec
7. VariableMapping model extended with origin field (CRF/Derived/Assigned/Protocol/eDT) and computational_method field for define.xml MethodDef
8. Date imputation flags (--DTF/--TMF) generated when partial dates are converted
9. Character variable lengths optimized to max observed (not padded to 200) before XPT write
10. ASCII encoding validated on all character data before XPT write
11. Missing CT codelists added: C66785 (Laterality), C66789 (Specimen Condition)
12. Cross-domain USUBJID validation confirms all USUBJIDs in any domain exist in DM
13. All existing 764+ tests pass + new tests for each utility

**Plans:** 5 plans

Plans:
- [ ] 04.1-01-PLAN.md -- Derivation utilities (--DY, --SEQ, EPOCH, VISITNUM)
- [ ] 04.1-02-PLAN.md -- Model extensions (origin, computational_method), imputation flags, missing CT codelists
- [ ] 04.1-03-PLAN.md -- Execution pipeline core (pattern handlers + DatasetExecutor)
- [ ] 04.1-04-PLAN.md -- XPT compliance utilities (ASCII validation, character length optimization)
- [ ] 04.1-05-PLAN.md -- Integration: wire XPT compliance into executor, CLI execute-domain, DM integration test

---

### Phase 5: Event and Intervention Domains

**Goal:** The system maps all Events-class and Interventions-class SDTM domains -- the domains that primarily use direct, rename, recode, and derivation patterns (no transpose required) -- AND executes approved specs to produce actual SDTM datasets using the Phase 4.1 execution pipeline.
**Depends on:** Phase 4.1 (needs --DY, --SEQ, sort order, execution pipeline, missing codelists)
**Requirements:** DOM-02, DOM-03, DOM-04, DOM-08, DOM-09, DOM-11, DOM-12, DOM-13

**Success Criteria:**
1. System produces complete, reviewable mapping specifications for AE, CM, EX, MH, DS, IE, CE, and DV domains
2. AE domain correctly maps start/end dates, severity, causality, seriousness, and outcome variables with appropriate controlled terminology (including C101854 Outcome, C66767 Action Taken)
3. CM domain correctly maps dose, route, frequency, and indication with CT lookups
4. All 8 domains pass human review and generate correct SDTM datasets (actual .xpt files) with --DY, --SEQ, EPOCH, correct sort order, and valid variable attributes
5. All generated datasets include variable origin metadata for define.xml traceability

**Plans:** (created by /gsd:plan-phase)

---

### Phase 6: Findings Domains and Complex Transformations

**Goal:** The system maps all Findings-class domains (requiring horizontal-to-vertical transpose), generates SUPPQUAL datasets with referential integrity, populates the mandatory TS (Trial Summary) domain, handles trial design domains, and produces actual SDTM .xpt files for all Findings domains -- the technically hardest transformations in the pipeline.
**Depends on:** Phase 5 (proven domain expansion pattern; transpose builds on mapping engine)
**Requirements:** DOM-05, DOM-06, DOM-07, DOM-10, DOM-14, DOM-15, DOM-16

**Success Criteria:**
1. System correctly transposes wide-format lab data into tall SDTM LB format with LBTESTCD, LBTEST, LBORRES, LBORRESU, LBSTRESC, LBSTRESN, LBSTRESU, and normal range variables -- including merging multiple source lab files into a single LB domain, with unit consistency validation across same test codes
2. System correctly transposes VS and EG domains with standardized results, position codes (C71148), specimen condition (C66789), laterality (C66785), and handles pre-dose/post-dose EG records
3. System generates SUPPQUAL datasets with verified referential integrity: every SUPPQUAL record references an existing parent domain record via RDOMAIN/USUBJID/IDVAR/IDVARVAL, correct QNAM naming (max 8 chars), and proper QORIG values
4. System populates the mandatory TS (Trial Summary) domain with all required parameters: SSTDTC, SENDTC, SPONSOR, INDIC, TRT, PCLAS, STYPE, SDTMVER, and conditional parameters per FDA Business Rules -- missing TS triggers automatic FDA rejection
5. System maps PE, SV, and trial design domains (TA, TE, TV, TI) correctly with proper sort order and variable order
6. All generated Findings datasets include --DY, --SEQ, EPOCH, VISITNUM, LBNRIND/VSNRIND (normal range indicators), and date imputation flags where applicable

**Plans:** (created by /gsd:plan-phase)

---

### Phase 7: Validation and Submission Readiness

**Goal:** The system runs comprehensive P21-style conformance validation on all output datasets and generates all regulatory submission artifacts (define.xml v2.0+, validation report, cSDRG) required for FDA submission -- including cross-domain consistency checks, computational method documentation, and Technical Rejection Criteria (TRC) compliance verification.
**Depends on:** Phase 6 (needs all domains generated to validate cross-domain consistency)
**Requirements:** VAL-01, VAL-02, VAL-03, VAL-04, VAL-05, VAL-06, VAL-07, VAL-08

**Success Criteria:**
1. System runs terminology, presence, consistency, limit, and format validation rules on every generated dataset and reports issues with severity levels (Error/Warning/Notice) and fix suggestions
2. System validates during mapping (predict-and-prevent) in addition to post-generation validation
3. System generates a complete define.xml (v2.0+) with: ItemGroupDef (dataset definitions with repeating/structure/purpose), ItemDef (variable definitions with name/label/type/length/format/origin/role/CodeListRef), CodeList definitions (OID/name/extensibility/items), MethodDef (computational methods for all derived variables using formulas from mapping specs), CommentDef (non-standard decisions), ValueListDef (transposed data relationships), WhereClauseDef (subset conditions)
4. Cross-domain USUBJID validation: all USUBJIDs across all domains verified present in DM
5. FDA Technical Rejection Criteria (TRC) pre-check: DM present, TS present with mandatory parameters, define.xml present and machine-readable, STUDYID consistent, filenames follow conventions
6. FDA Business Rule validation: FDAB057 (ethnicity choices), FDAB055 (race self-reported), FDAB039 (normal range boundaries), FDAB009 (paired variables), FDAB030 (standard units)
7. System generates Clinical Study Data Reviewer's Guide (cSDRG) template with domain mapping rationale, non-standard variable justification, and data handling decisions
8. System produces a pre-submission validation report with P21 rule alignment, severity categorization, known false-positive whitelist, and submission readiness score
9. Dataset size validation: total submission size checked against 5GB FDA limit with split recommendations for large domains
10. All file naming conventions enforced (lowercase domain codes, .xpt extension)

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
| 2 - Source Parsing and Domain Classification | Complete | 2026-02-27 |
| 2.1 - Reference Data Fixes (INSERTED) | Complete | 2026-02-27 |
| 3 - Core Mapping Engine (Demographics) | Complete | 2026-02-27 |
| 3.1 - Audit Fixes + Architectural Wiring (INSERTED) | Complete | 2026-02-27 |
| 4 - Human Review Gate | Complete | 2026-02-27 |
| 4.1 - FDA Compliance Infrastructure (INSERTED) | Not started | -- |
| 5 - Event and Intervention Domains | Not started | -- |
| 6 - Findings Domains and Complex Transformations | Not started | -- |
| 7 - Validation and Submission Readiness | Not started | -- |
| 8 - Learning System | Not started | -- |

---

*Roadmap for milestone: v1.0*
