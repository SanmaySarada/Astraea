# Requirements: Astraea-SDTM

**Defined:** 2026-02-26
**Core Value:** Given any clinical study's raw data and eCRF, produce accurate SDTM-compliant datasets with minimal human intervention — and get better with every correction.

## v1 Requirements

### Data Infrastructure

- [ ] **DATA-01**: System reads SAS (.sas7bdat) files and extracts variable metadata (names, types, labels, formats, lengths)
- [ ] **DATA-02**: System profiles raw datasets automatically (row counts, value distributions, missing data patterns, date formats detected)
- [ ] **DATA-03**: System bundles CDISC SDTM-IG metadata as structured reference (domain definitions, variable specs, core designations, class assignments)
- [ ] **DATA-04**: System bundles NCI CDISC Controlled Terminology codelists (extensible vs non-extensible, codelist-to-variable mappings)
- [ ] **DATA-05**: System converts dates/times to ISO 8601 format deterministically, including partial date handling per SDTM-IG rules
- [ ] **DATA-06**: System generates USUBJID correctly (STUDYID + SITEID + SUBJID) and validates consistency across all domains
- [ ] **DATA-07**: System produces valid SAS Transport v5 (.xpt) files that pass structural validation

### eCRF Parsing

- [ ] **ECRF-01**: System parses eCRF PDF files and extracts form-level metadata (form names, visit associations)
- [ ] **ECRF-02**: System extracts field-level metadata from eCRF (field names, data types, SAS labels, coded value lists, field OIDs)
- [ ] **ECRF-03**: System associates eCRF forms with raw datasets (matching form fields to dataset variables)
- [ ] **ECRF-04**: System handles variable eCRF layouts across studies (not hardcoded to one PDF format)

### Domain Classification

- [ ] **CLSF-01**: System automatically classifies raw datasets to SDTM domains using eCRF context, variable names, and data content
- [ ] **CLSF-02**: System handles all three SDTM domain classes: Interventions (CM, EX), Events (AE, CE, MH, DV), Findings (LB, VS, EG, PE)
- [ ] **CLSF-03**: System detects when multiple raw datasets map to a single SDTM domain (e.g., lb_biochem + lb_hem + lb_urin → LB)
- [ ] **CLSF-04**: System provides confidence score and reasoning for each domain classification

### Mapping Engine

- [ ] **MAP-01**: System handles direct copy mapping (source variable → SDTM variable, same name and content)
- [ ] **MAP-02**: System handles rename mapping (different variable name, same content — e.g., GENDER → SEX)
- [ ] **MAP-03**: System handles reformat mapping (same value, different representation — e.g., SAS date → ISO 8601)
- [ ] **MAP-04**: System handles split mapping (one source variable → multiple SDTM variables)
- [ ] **MAP-05**: System handles combine mapping (multiple source variables → one SDTM variable — e.g., USUBJID construction)
- [ ] **MAP-06**: System handles derivation mapping (calculated fields — e.g., AGE from birth date and consent date)
- [ ] **MAP-07**: System handles lookup/recode mapping (source values → CDISC CT terms — e.g., "Male" → "M")
- [ ] **MAP-08**: System handles transpose mapping (wide-format source → tall SDTM Findings format with --TESTCD, --TEST, --ORRES rows)
- [ ] **MAP-09**: System handles variable attribute mapping (label, type, length adjustments per SDTM-IG spec)
- [ ] **MAP-10**: System provides confidence score (HIGH/MEDIUM/LOW) for every mapping decision
- [ ] **MAP-11**: System provides natural language explanation for every mapping decision (why this source maps to this target)
- [ ] **MAP-12**: System handles natural language derivation descriptions ("Calculate AGE from birth date and consent date") and generates executable transformations

### SDTM Domain Coverage

- [ ] **DOM-01**: System maps Demographics (DM) domain including all required/expected variables
- [ ] **DOM-02**: System maps Adverse Events (AE) domain with start/end dates, severity, causality, seriousness, outcome
- [ ] **DOM-03**: System maps Concomitant Medications (CM) domain with dose, route, frequency, indication
- [ ] **DOM-04**: System maps Exposure (EX) domain with precise dosing records per protocol
- [ ] **DOM-05**: System maps Laboratory Results (LB) domain with transpose, unit standardization, normal ranges
- [ ] **DOM-06**: System maps Vital Signs (VS) domain with transpose, standardized results
- [ ] **DOM-07**: System maps ECG (EG) domain with pre-dose/post-dose handling
- [ ] **DOM-08**: System maps Medical History (MH) domain
- [ ] **DOM-09**: System maps Disposition (DS) domain with protocol milestones
- [ ] **DOM-10**: System maps Physical Examination (PE) domain
- [ ] **DOM-11**: System maps Inclusion/Exclusion (IE) domain
- [ ] **DOM-12**: System maps Clinical Events (CE) domain
- [ ] **DOM-13**: System maps Protocol Deviations (DV) domain
- [ ] **DOM-14**: System generates SUPPQUAL datasets when non-standard variables require supplemental qualifiers
- [ ] **DOM-15**: System generates RELREC datasets for cross-domain record relationships
- [ ] **DOM-16**: System handles Subject Visits (SV) and other trial design domains (TA, TE, TV, TI, TS)

### Mapping Specification

- [ ] **SPEC-01**: System produces mapping specification as Excel workbook (per-domain sheets with standard columns: Variable, Label, Type, Length, Origin, Source, Derivation Algorithm, CT)
- [ ] **SPEC-02**: System produces mapping specification as structured JSON/YAML for programmatic use
- [ ] **SPEC-03**: System documents full source-to-target traceability (every SDTM variable traces to its origin)
- [ ] **SPEC-04**: System presents mapping spec to human reviewer with confidence scores and explanations highlighted

### Validation

- [ ] **VAL-01**: System runs Terminology validation (values match CDISC CT, non-extensible codelists enforced)
- [ ] **VAL-02**: System runs Presence validation (required variables/records exist per SDTM-IG)
- [ ] **VAL-03**: System runs Consistency validation (cross-domain checks — e.g., RFSTDTC matches earliest EX date)
- [ ] **VAL-04**: System runs Limit validation (variable lengths within SDTM-IG spec)
- [ ] **VAL-05**: System runs Format validation (ISO 8601 dates, variable name length ≤ 8 chars)
- [ ] **VAL-06**: System validates during mapping (predict-and-prevent), not just post-hoc
- [ ] **VAL-07**: System generates pre-submission validation report with severity levels (Error/Warning/Notice) and fix suggestions
- [ ] **VAL-08**: System generates define.xml (v2.0+) with dataset metadata, variable metadata, codelists, value-level metadata, computational methods

### Human Review & Learning

- [ ] **HITL-01**: System presents proposed mappings to human reviewer at each domain, pausing for approval/correction
- [ ] **HITL-02**: System captures human corrections with structured metadata (what was wrong, what's correct, why)
- [ ] **HITL-03**: System stores corrections in vector database (ChromaDB) for future retrieval
- [ ] **HITL-04**: System retrieves similar past corrections when mapping new studies (few-shot RAG)
- [ ] **HITL-05**: System optimizes prompts from accumulated corrections using DSPy
- [ ] **HITL-06**: System builds cross-study template library from approved mappings
- [ ] **HITL-07**: System improves accuracy measurably over successive studies

### CLI Interface

- [ ] **CLI-01**: User can run system from terminal: point at data folder (SAS files + eCRF PDF), get SDTM output
- [ ] **CLI-02**: User can review and approve/correct mappings interactively in terminal
- [ ] **CLI-03**: User can resume a mapping session (pick up where they left off)
- [ ] **CLI-04**: System displays progress through pipeline stages clearly

## v2 Requirements

### Web UI

- **WEB-01**: Upload raw data through browser interface
- **WEB-02**: Visual mapping review with side-by-side source/target comparison
- **WEB-03**: Drag-and-drop correction interface
- **WEB-04**: Dashboard showing mapping progress and validation status

### Extended Input Formats

- **INPUT-01**: Read CSV files as raw data source
- **INPUT-02**: Read Excel files as raw data source
- **INPUT-03**: Parse protocol PDFs (USDM) for additional study context

### Advanced Learning

- **LEARN-01**: Fine-tune models on organization-specific mapping patterns (when supported by LLM provider)
- **LEARN-02**: Active learning — system identifies which corrections would be most valuable

### ADaM Bridge

- **ADAM-01**: Generate ADaM-ready SDTM structures
- **ADAM-02**: Suggest ADaM derivations based on SDTM output

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full EDC / data collection system | Different product entirely — compete with Medidata Rave, Oracle InForm |
| ADaM dataset generation | Fundamentally different problem (analysis vs tabulation) — future product |
| SAS code generation | Locks users into SAS licenses; industry moving to Python/R |
| MedDRA / WHODrug coding engine | Specialized tools exist (IQVIA AutoEncoder); accept pre-coded data |
| Real-time streaming pipeline | Clinical data is batch-oriented; no user demand for streaming |
| Multi-tenant SaaS (day 1) | Prove the engine first as CLI tool |
| Visual drag-and-drop mapping UI | AI should propose; humans review — not manual drag-and-drop |
| Mobile app | Not relevant for clinical data programmers |

## Traceability

(To be populated by roadmap creation)

| Requirement | Phase | Status |
|-------------|-------|--------|
| — | — | — |

**Coverage:**
- v1 requirements: 54 total
- Mapped to phases: 0
- Unmapped: 54 ⚠️

---
*Requirements defined: 2026-02-26*
*Last updated: 2026-02-26 after initial definition*
