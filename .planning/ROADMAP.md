# Roadmap

**Project:** Astraea-SDTM
**Created:** 2026-02-26
**Phases:** 15

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
- [x] 04.1-01-PLAN.md -- Derivation utilities (--DY, --SEQ, EPOCH, VISITNUM)
- [x] 04.1-02-PLAN.md -- Model extensions (origin, computational_method), imputation flags, missing CT codelists
- [x] 04.1-03-PLAN.md -- Execution pipeline core (pattern handlers + DatasetExecutor)
- [x] 04.1-04-PLAN.md -- XPT compliance utilities (ASCII validation, character length optimization)
- [x] 04.1-05-PLAN.md -- Integration: wire XPT compliance into executor, CLI execute-domain, DM integration test

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

**Plans:** 7 plans

Plans:
- [x] 05-01-PLAN.md -- Infrastructure gaps: numeric_to_yn transform, row filtering, column alignment
- [x] 05-02-PLAN.md -- AE + DS domain execution tests (synthetic data, most complex + multi-source)
- [x] 05-03-PLAN.md -- CM + EX domain execution tests (synthetic data, partial dates + row filtering)
- [x] 05-04-PLAN.md -- MH + IE + CE + DV domain execution tests (synthetic data, simpler domains)
- [x] 05-05-PLAN.md -- Cross-domain validation, EPOCH derivation, origin metadata, XPT output
- [x] 05-06-PLAN.md -- LLM mapping spec generation for AE, CM, EX, DS (real Fakedata, requires API key)
- [x] 05-07-PLAN.md -- LLM mapping spec generation for MH, IE, CE, DV (real Fakedata, requires API key)

---

### Phase 6: Findings Domains and Complex Transformations

**Goal:** The system maps all Findings-class domains (LB, EG, PE), generates SUPPQUAL datasets with referential integrity, populates the mandatory TS (Trial Summary) domain, builds SV (Subject Visits) from EDC metadata, and produces actual SDTM .xpt files for all Findings domains -- the technically hardest transformations in the pipeline.
**Depends on:** Phase 5 (proven domain expansion pattern; transpose builds on mapping engine)
**Requirements:** DOM-05, DOM-06, DOM-07, DOM-10, DOM-14, DOM-15, DOM-16

**Success Criteria:**
1. System correctly transposes wide-format lab data into tall SDTM LB format with LBTESTCD, LBTEST, LBORRES, LBORRESU, LBSTRESC, LBSTRESN, LBSTRESU, and normal range variables -- including merging multiple source lab files into a single LB domain, with unit consistency validation across same test codes
2. System correctly transposes VS and EG domains with standardized results, position codes (C71148), specimen condition (C66789), laterality (C66785), and handles pre-dose/post-dose EG records
3. System generates SUPPQUAL datasets with verified referential integrity: every SUPPQUAL record references an existing parent domain record via RDOMAIN/USUBJID/IDVAR/IDVARVAL, correct QNAM naming (max 8 chars), and proper QORIG values
4. System populates the mandatory TS (Trial Summary) domain with all required parameters: SSTDTC, SENDTC, SPONSOR, INDIC, TRT, PCLAS, STYPE, SDTMVER, and conditional parameters per FDA Business Rules -- missing TS triggers automatic FDA rejection
5. System maps PE, SV, and trial design domains (TA, TE, TV, TI) correctly with proper sort order and variable order
6. All generated Findings datasets include --DY, --SEQ, EPOCH, VISITNUM, LBNRIND/VSNRIND (normal range indicators), and date imputation flags where applicable

**Plans:** 6 plans

Plans:
- [x] 06-01-PLAN.md -- TRANSPOSE handler + SUPPQUAL generator (foundational components)
- [x] 06-02-PLAN.md -- LB + EG + VS domain execution (FindingsExecutor, multi-source merge, CT codelist verification, date imputation flags)
- [x] 06-03-PLAN.md -- TS domain builder + PE domain execution (config-driven TS, minimal PE)
- [x] 06-04-PLAN.md -- SUPPQUAL integration + Findings XPT output tests (SUPPLB, SUPPEG, VS, date imputation flag roundtrips)
- [x] 06-05-PLAN.md -- LLM mapping specs for LB, EG, PE, VS with CT codelist verification (requires API key)
- [x] 06-06-PLAN.md -- SV domain builder, trial design domains (TA/TE/TV/TI), RELREC stub, TS integration

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

**Plans:** 7 plans

Plans:
- [ ] 07-01-PLAN.md -- Validation framework: rule models, engine orchestrator, report model
- [ ] 07-02-PLAN.md -- Terminology, Presence, Limit, Format rules (VAL-01, VAL-02, VAL-04, VAL-05)
- [ ] 07-03-PLAN.md -- Cross-domain consistency rules (VAL-03), FDA Business Rules, FDA TRC pre-checks
- [ ] 07-04-PLAN.md -- Predict-and-prevent validation (VAL-06) wired into mapping engine
- [ ] 07-05-PLAN.md -- define.xml 2.0 generator from DomainMappingSpec (VAL-08)
- [ ] 07-06-PLAN.md -- cSDRG template generator, submission package assembly, validation report export
- [ ] 07-07-PLAN.md -- CLI commands (validate, generate-define, generate-csdrg) and integration tests

---

### Phase 7.1: Auto-Fix Validation Issues (INSERTED)

**Goal:** When the Phase 7 validation engine detects issues, the system automatically fixes deterministic/mechanical issues (wrong CT case, missing DOMAIN column, truncated labels, missing required ASSIGN variables) without human intervention, and re-validates — creating a validate→fix→re-validate loop that reduces the human review burden to only genuinely ambiguous problems.
**Depends on:** Phase 7 (needs validation framework, rules, and report infrastructure)
**Requirements:** None (enhancement to existing VAL requirements)
**Blocked by:** Nothing (Phase 7 complete)
**Blocks:** Phase 8

**Success Criteria:**
1. Auto-fixer classifies each validation issue as auto-fixable (deterministic) or needs-human (ambiguous), with clear categorization rules
2. Auto-fixable issues include: CT case normalization, missing DOMAIN/STUDYID/USUBJID ASSIGN columns, variable name/label truncation, date format corrections, file renaming to lowercase conventions
3. System runs validate→fix→re-validate loop (max 3 iterations) and reports what was fixed, what remains
4. Needs-human issues are presented with context and suggested fixes (not just error messages)
5. Fix actions are logged with before/after values for audit trail
6. CLI command `astraea auto-fix` runs the loop on generated datasets; `astraea validate --auto-fix` combines validation with auto-fixing in one step

**Plans:** 3 plans

Plans:
- [x] 07.1-01-PLAN.md -- AutoFixer core: issue classification, fix functions, FixAction audit model, unit tests
- [x] 07.1-02-PLAN.md -- FixLoopEngine: validate-fix-revalidate loop, XPT writeback, audit trail export, unit tests
- [x] 07.1-03-PLAN.md -- CLI commands (auto-fix, validate --auto-fix), Rich display helpers, CLI tests

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

**Plans:** 5 plans

Plans:
- [x] 08-01-PLAN.md -- Pydantic models, SQLite example store, ChromaDB vector store
- [x] 08-02-PLAN.md -- LearningRetriever and MappingEngine integration (few-shot RAG)
- [x] 08-03-PLAN.md -- Accuracy metrics tracker and review-to-learning ingestion pipeline
- [x] 08-04-PLAN.md -- Cross-study domain template library
- [x] 08-05-PLAN.md -- DSPy prompt optimizer and CLI commands (learn-ingest, learn-stats, learn-optimize)

---

### Phase 9: CLI Wiring — Close Audit Gaps

**Goal:** Wire all orphaned modules into the CLI so that every built capability is reachable by users — closing the 3 integration gaps identified in the v1 milestone audit that prevent Trial Design/TS generation, learning feedback, and SUPPQUAL generation through the CLI workflow.
**Depends on:** Phase 8 (all modules must exist)
**Requirements:** DOM-14 (SUPPQUAL via CLI), DOM-16 (Trial Design via CLI), HITL-04 (few-shot RAG in mapping)
**Gap Closure:** Closes GAP-1, GAP-2, GAP-3 from v1-MILESTONE-AUDIT.md

**Success Criteria:**
1. New CLI command `astraea generate-trial-design` produces TS, TA, TE, TV, TI, SV datasets from config — TS includes all FDA-mandatory parameters (GAP-1)
2. `astraea map-domain` automatically loads `LearningRetriever` when a learning DB exists, injecting past corrections as few-shot examples into mapping prompts (GAP-2)
3. `astraea execute-domain` routes Findings domains (LB, VS, EG) through `FindingsExecutor` instead of generic `DatasetExecutor`, enabling SUPPQUAL generation in the CLI path (GAP-3)
4. Integration tests verify each wiring path end-to-end
5. All ~1652 existing tests still pass

**Plans:** 3 plans

Plans:
- [x] 09-01-PLAN.md -- Wire trial design domains into CLI (GAP-1: generate-trial-design command)
- [x] 09-02-PLAN.md -- Wire LearningRetriever into map-domain CLI (GAP-2: feedback loop closure)
- [x] 09-03-PLAN.md -- Route Findings through FindingsExecutor in CLI (GAP-3: SUPPQUAL generation)

---

### Phase 10: Tech Debt Cleanup

**Goal:** Clean up accumulated tech debt identified across all phases — ruff style violations, orphaned modules, stale documentation, incomplete REQUIREMENTS.md checkboxes, and validation infrastructure gaps — so the codebase is clean and consistent for milestone completion.
**Depends on:** Phase 9 (gap closure first, cleanup second)
**Requirements:** None (quality improvement, not functional)

**Success Criteria:**
1. Zero ruff violations across `src/` and `tests/` (139 violations: E501, F401, I001, UP042, etc.)
2. Zero mypy errors across `src/` (122 errors: unused type:ignore, missing type params, attr-defined)
3. REQUIREMENTS.md checkboxes all checked `[x]` (DATA-01 through DATA-07, CLI-01, CLI-04 currently unchecked)
4. `known_false_positives.json` expanded with common P21 false positives (currently 1 entry)
5. All tests pass, ruff clean, mypy clean

**Plans:** 2 plans

Plans:
- [x] 10-01-PLAN.md -- Fix all ruff lint violations (139) and mypy type errors (122)
- [x] 10-02-PLAN.md -- Update REQUIREMENTS.md checkboxes + expand known_false_positives.json

---

### Phase 11: Execution Contract

**Goal:** Make the execution pipeline actually produce valid SDTM data from LLM-generated mapping specs — defining a formal derivation rule vocabulary that both the LLM and executor agree on, implementing all rules in pattern_handlers, adding column name resolution (eCRF names → actual SAS column names), and fixing critical bugs in date conversion and false-positive matching.
**Depends on:** Phase 10 (clean codebase baseline)
**Requirements:** CRIT-01, CRIT-02, CRIT-03, HIGH-01, HIGH-02, HIGH-10, HIGH-17, MED-18
**Blocked by:** Nothing (Phase 10 complete)
**Blocks:** Phase 12 (validation fixes need working execution pipeline)

**Success Criteria:**
1. Formal derivation rule vocabulary defined (CONCAT, MIN_DATE, MAX_DATE, RACE_CHECKBOX, ISO8601_DATE, ISO8601_PARTIAL_DATE, LAST_DISPOSITION_DATE, etc.) with documentation for each rule
2. All derivation rules implemented in pattern_handlers.py — executing DM mapping spec on real Fakedata/dm.sas7bdat produces non-NULL USUBJID and at least 14/18 columns populated
3. Column name resolution layer maps eCRF field names (SSUBJID, SSITENUM, SCOUNTRY) to actual SAS column names (Subject, SiteNumber, etc.)
4. LLM mapping prompts constrained to only use recognized derivation rules from the vocabulary
5. known_false_positives.json wildcard `"*"` matching fixed (CRIT-01 — 1-line fix)
6. `format_partial_iso8601` fixed for hour-without-minute case (HIGH-17)
7. DDMonYYYY (no-space) date format supported (MED-18)
8. USUBJID auto-fix classification bug fixed (HIGH-10)
9. All existing 1567+ tests pass + new tests for each fix

**Plans:** 4 plans

Plans:
- [x] 11-01-PLAN.md -- Bug fixes: wildcard matching, ISO 8601 partial date, DDMonYYYY format, USUBJID auto-fix
- [x] 11-02-PLAN.md -- Derivation rule parser, column resolution helper, and all rule handler implementations
- [x] 11-03-PLAN.md -- LLM prompt vocabulary constraint and executor column name resolution
- [x] 11-04-PLAN.md -- DM real-data integration test and full test suite verification

---

### Phase 12: Validation and Severity Fixes

**Goal:** Add missing validation rules and fix severity misclassifications so the validation engine catches real FDA submission issues and doesn't cry wolf on false positives.
**Depends on:** Phase 11 (execution pipeline must produce valid data to validate)
**Requirements:** HIGH-06, HIGH-07, HIGH-08, HIGH-09, HIGH-16, MED-01, MED-04, MED-05
**Blocked by:** Phase 11
**Blocks:** Phase 13

**Success Criteria:**
1. DM.SEX codelist validation rule added (C66731 non-extensible, HIGH-07)
2. --SEQ uniqueness check added (P21 SD0007 equivalent, HIGH-08)
3. DM one-record-per-subject validation rule added (MED-05)
4. FDAB057 (ETHNIC) severity corrected to ERROR (HIGH-09)
5. ASTR-F002 (ASCII) severity corrected to ERROR (MED-01)
6. FDA-mandatory TS parameters expanded from 7 to 26+ (HIGH-06)
7. TRC checks expanded beyond SSTDTC to include SDTMVER, STYPE, TITLE (HIGH-16)
8. TRCPreCheck integrated into validate_all() (MED-04)
9. All existing tests pass + new tests for each rule/fix

**Plans:** 3 plans

Plans:
- [ ] 12-01-PLAN.md -- Severity fixes (FDAB057, ASTR-F002) + new rules (SEX, SEQ, DM one-record)
- [ ] 12-02-PLAN.md -- TS parameter expansion (7 to 26+) + TRC check expansion (SDTMVER, STYPE, TITLE)
- [ ] 12-03-PLAN.md -- TRCPreCheck integration into validate_all() + full regression verification

---

### Phase 13: Define.xml and Findings Completeness

**Goal:** Fix structural define.xml errors and add missing Findings domain derivations (standardized results, normal range indicators, date imputation flags) so generated datasets and metadata pass P21 define.xml validation.
**Depends on:** Phase 12 (validation rules needed to verify fixes)
**Requirements:** HIGH-03, HIGH-04, HIGH-05, HIGH-11, HIGH-12, HIGH-13, MED-06, MED-07, MED-08, MED-09, MED-10
**Blocked by:** Phase 12
**Blocks:** Phase 14

**Success Criteria:**
1. ValueListDef placed on result variables (--ORRES, --STRESC, --STRESN) not --TESTCD (HIGH-11)
2. NCI C-codes emitted on CodeListItem elements (HIGH-12)
3. Missing ItemDef for ValueListDef ItemRef targets created (HIGH-13)
4. --DTF/--TMF date imputation flags generated in executor (HIGH-03)
5. --STRESC/--STRESN/--STRESU standardized results derived for Findings domains (HIGH-04)
6. --NRIND normal range indicator derived from reference ranges (HIGH-05)
7. Define.xml attribute completeness: KeySequence, def:Label, integer DataType for --SEQ, def:Origin Source, ODM Originator/AsOfDateTime (MED-06 through MED-10)
8. All existing tests pass + new tests for each fix

**Plans:** TBD

---

### Phase 14: Reference Data and Transforms

**Goal:** Fix remaining reference data errors and transform gaps — missing codelists, incorrect variable mappings, date format edge cases, and performance bottlenecks.
**Depends on:** Phase 13 (Findings completeness needed for reference data context)
**Requirements:** HIGH-14, HIGH-15, MED-02, MED-03, MED-15, MED-16, MED-17, MED-19, MED-20, MED-21, MED-22, MED-23, MED-24, MED-25
**Blocked by:** Phase 13
**Blocks:** Phase 15

**Success Criteria:**
1. C66738 (Trial Summary Parameter Code) codelist added to codelists.json (HIGH-14)
2. PE and QS key_variables VISITNUM issue fixed (HIGH-15)
3. C66789 variable_mapping corrected from LBSPEC to LBSPCND (MED-15)
4. C66742 variable_mappings expanded with missing variables (MED-16)
5. Reverse lookup collision bug in controlled_terms.py fixed (MED-17)
6. iterrows() replaced with vectorized operations in FDAB009/FDAB030/ASTR-C005 (MED-02)
7. ISO 8601 regex updated with timezone offset support (MED-03)
8. Date format completeness: HH:MM:SS seconds (MED-19), ISO datetime passthrough (MED-20), imputation functions (MED-21)
9. 200-byte max validation in char_length.py (MED-22)
10. EPOCH overlap detection for SE elements (MED-23)
11. SEX, RACE, ETHNIC convenience recoding wrappers (MED-25)
12. All existing tests pass + new tests for each fix

**Plans:** TBD

---

### Phase 15: Submission Readiness

**Goal:** Close remaining submission artifact gaps — define.xml polish, cSDRG content, eCTD directory structure, LC domain support, and expanded FDA Business Rules — making the output genuinely submission-ready.
**Depends on:** Phase 14 (reference data and transforms must be correct)
**Requirements:** MED-06, MED-11, MED-12, MED-13, MED-14, MED-26, MED-27, MED-28, MED-29, LOW items
**Blocked by:** Phase 14

**Success Criteria:**
1. SPLIT pattern implemented (currently stub returning None, MED-11)
2. Multi-source merge supports key-based horizontal joins (MED-12)
3. Specimen type (--SPEC), method (--METHOD), fasting (--FAST) handling added (MED-13)
4. DM mapping prompts enforce Required DM variables ARM/ARMCD/ACTARM/ACTARMCD (MED-14)
5. cSDRG Section 2 (Study Description) and Section 6 (Known Data Issues) populated (MED-26)
6. eCTD directory structure enforcement (`m5/datasets/tabulations/sdtm/`, MED-27)
7. cSDRG non-standard variable justification per variable (MED-28)
8. Pre-mapped SDTM data detection (ecg_results, lab_results, MED-29)
9. LC (Laboratory Conventional) domain support per SDTCG v5.7
10. Expanded FDA Business Rules (target: 20+ of ~45 FDAB rules)
11. All LOW items addressed as time permits
12. All existing tests pass + new tests for each feature

**Plans:** TBD

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
| 4.1 - FDA Compliance Infrastructure (INSERTED) | Complete | 2026-02-27 |
| 5 - Event and Intervention Domains | Complete | 2026-02-27 |
| 6 - Findings Domains and Complex Transformations | Complete | 2026-02-27 |
| 7 - Validation and Submission Readiness | Complete | 2026-02-28 |
| 7.1 - Auto-Fix Validation Issues (INSERTED) | Complete | 2026-02-28 |
| 8 - Learning System | Complete | 2026-02-28 |
| 9 - CLI Wiring — Close Audit Gaps | Complete | 2026-02-27 |
| 10 - Tech Debt Cleanup | Complete | 2026-02-28 |
| 11 - Execution Contract | Complete | 2026-02-28 |
| 12 - Validation and Severity Fixes | Not Started | -- |
| 13 - Define.xml and Findings Completeness | Not Started | -- |
| 14 - Reference Data and Transforms | Not Started | -- |
| 15 - Submission Readiness | Not Started | -- |

---

*Roadmap for milestone: v1.1*
