# Feature Landscape: Astraea-SDTM

**Domain:** Clinical data standardization / SDTM mapping (agentic AI)
**Researched:** 2026-02-26
**Overall confidence:** MEDIUM-HIGH

---

## Table Stakes

Features users expect from any SDTM mapping tool. Missing any of these means the product is not viable for real-world use.

| # | Feature | Why Expected | Complexity | Dependencies | Notes |
|---|---------|--------------|------------|--------------|-------|
| T1 | **All 9 Mapping Transformation Types** | The 9 scenarios (direct copy, rename, reformat, split, combine, derivation, lookup/recode, transpose, variable attribute mapping) are the fundamental unit of work. Every mapping tool must handle all 9 | High | None (foundational) | Transpose and derivation are the hardest; direct copy/rename are trivial. See detailed section below |
| T2 | **SDTM Domain Coverage (Core Domains)** | Must handle DM, AE, CM, EX, LB, VS, MH, DS, EG, PE, IE, CE, DV and other standard SDTMIG domains. Users will not adopt a tool that only handles a subset | High | T1 | Each domain has its own structural rules. Findings class (LB, VS, EG) requires transpose. Events class (AE, CE, MH) and Interventions class (CM, EX) each have distinct patterns |
| T3 | **CDISC Controlled Terminology Application** | CDISC CT codelists are mandatory for regulatory submission. Tool must apply correct CT version, map source values to controlled terms, flag non-standard values | Medium | T7 | NCI-EVS publishes CT quarterly. Must support pinning to a specific CT version per study. Extensible vs non-extensible codelists have different rules |
| T4 | **Mapping Specification Output** | Must produce a standard mapping specification document (Excel workbook with per-domain sheets). Industry standard columns: Domain, Variable, Label, Type, Length, Origin, Source Dataset, Source Variable, Derivation Algorithm, Comment | Medium | T1, T2 | This is the primary deliverable reviewers and programmers consume. See format section below |
| T5 | **define.xml Generation** | FDA requires define.xml (v2.0+) with every SDTM submission. Must produce valid define.xml including dataset metadata, variable metadata, codelists, value-level metadata, computational methods | High | T4, T3 | define.xml is "arguably the most important part of the electronic dataset submission" per FDA Technical Conformance Guide |
| T6 | **Pinnacle 21 (P21) Validation Integration** | P21 is the de facto industry standard validator. Output datasets must pass P21 checks or the tool is useless. At minimum: ability to run P21 validation and surface results | High | T2 | See validation section below. 5 rule categories: Terminology, Presence, Consistency, Limit, Format. Severity: Error (High), Warning (Medium/Low), Notice |
| T7 | **CDISC Library / Metadata Repository** | Must have access to the SDTM IG metadata (domain structures, variable definitions, core designations, controlled terminology) as a structured reference | Medium | None | CDISC Library API exists. sdtm.oak uses metadata specs. This is the "brain" that knows what valid SDTM looks like |
| T8 | **SAS Transport (XPT) File Output** | FDA requires datasets in SAS Transport v5 (XPT) format. Must produce compliant XPT files | Low-Medium | T2 | Well-understood format. Libraries exist in Python (xport, pyreadstat). Character variable length truncation at 200 chars is a known constraint |
| T9 | **Source Data Ingestion (SAS7BDAT, CSV, XPT)** | Raw clinical data arrives in SAS7BDAT (most common), CSV, or XPT. Must read all three | Low-Medium | None | pyreadstat handles SAS7BDAT. The project already has SAS7BDAT files in Fakedata/ |
| T10 | **Traceability (Source-to-Target Lineage)** | FDA requires traceability from analysis results back through ADaM to SDTM to raw data. Every SDTM variable must trace back to its source | Medium | T4 | Traceability must be documented in mapping specs AND define.xml origin fields. "Collected", "Derived", "Assigned", "Predecessor" are the four origin types |
| T11 | **USUBJID Generation** | USUBJID (unique subject identifier) is the most critical variable in SDTM. Must be constructed correctly (typically STUDYID + SITEID + SUBJID) and consistent across all domains | Low | T2 | Seems simple but errors here cascade everywhere. Must be identical across every domain dataset |
| T12 | **ISO 8601 Date/Time Handling** | All SDTM dates must be ISO 8601 format (YYYY-MM-DDThh:mm:ss). Must handle partial dates, date imputation rules, and conversion from various source formats | Medium | None | Partial dates (e.g., only month/year known) require specific handling per SDTMIG rules. --DTC variables are character, not numeric |

---

## Differentiators

Features that would make Astraea-SDTM stand out from Pinnacle 21, Formedix ryze, d-Wise, and Nurocor.

| # | Feature | Value Proposition | Complexity | Dependencies | Notes |
|---|---------|-------------------|------------|--------------|-------|
| D1 | **Automated eCRF/aCRF PDF Parsing** | Existing tools (Formedix ryze) require manual aCRF annotation or structured metadata input. Automatically parsing eCRF PDFs to extract form structure, field names, data types, and visit schedules eliminates a major manual bottleneck | High | None | Project already has ECRF.pdf and ECRF_text.txt. PDF structure is semi-structured (tables with Field Name, Data Type, SAS Label, Values columns). This is where LLM vision/NLP shines |
| D2 | **RL from Human Corrections (Learning System)** | No existing tool learns from corrections. When a human reviewer fixes a mapping, that correction trains the model for future studies. Over time, the system gets smarter per organization | Very High | T1, T4 | This is the stated key differentiator. Requires: correction capture interface, feedback loop to model, study-over-study improvement tracking. HITL + RL is emerging in this space but no commercial tool does it yet |
| D3 | **Intelligent Domain Assignment** | Automatically determine which SDTM domain each source dataset/form maps to (e.g., "Adverse Events" form maps to AE domain, "Lab Results" maps to LB). Current tools require manual domain assignment or use simple name matching | Medium | D1, T7 | LLM can use form names, field names, and question text to infer domain. The eCRF text has form names like "Adverse Event", "Concomitant Medication" that directly map |
| D4 | **Natural Language Derivation Descriptions** | Instead of requiring SAS code or proprietary mapping language, accept natural language descriptions of derivations ("Calculate AGE from birth date and informed consent date") and generate executable transformations | High | T1 | Formedix ryze uses a "purpose-built language" for mappings. LLM-powered natural language is far more accessible to non-programmers (clinical data managers, biostatisticians) |
| D5 | **Cross-Study Learning / Template Library** | Automatically build a library of mapping patterns from completed studies. When a new study arrives, suggest mappings based on similar past studies in the same therapeutic area | High | D2, T4 | Nurocor and Pinnacle 21 support "reusing mapping specs" but require manual template management. AI-powered similarity matching across studies is a genuine leap |
| D6 | **Automated SUPPQUAL Decision-Making** | Automatically determine when a non-standard variable should go to SUPPQUAL vs. a custom domain vs. Findings About (FA). This is a judgment call that trips up even experienced programmers | Medium | T2, T7 | Rules: minimize SUPPQUAL use; if many non-standard vars, consider custom domain (X-/Y-/Z- prefix); FA domain for findings about events/interventions. LLM can apply these heuristics |
| D7 | **Pre-Submission Validation Report** | Generate a comprehensive validation report that predicts P21 findings BEFORE running P21, with explanations and fix suggestions. Current tools validate after-the-fact; predict-and-prevent is better | High | T6, T2 | Requires encoding P21's ~1000+ validation rules. Categories: Terminology, Presence, Consistency, Limit, Format. Build validation into the mapping process, not as a post-hoc step |
| D8 | **Confidence Scoring Per Mapping** | For every mapping decision the AI makes, provide a confidence score (HIGH/MEDIUM/LOW) so reviewers know where to focus attention. No existing tool does this | Medium | T1 | Critical for trust and adoption. Reviewers should see "95% confident this is a direct copy" vs "40% confident on this derivation -- please review". Reduces review time dramatically |
| D9 | **Multi-Source Merge Intelligence** | Automatically detect when multiple source datasets need to be merged to create a single SDTM domain (e.g., multiple lab datasets lb_biochem, lb_coagulation, lb_hem, lb_urin into single LB domain) | Medium-High | T1, T9 | The project's Fakedata has exactly this pattern: lb_biochem.sas7bdat, lb_coagulation.sas7bdat, lb_hem.sas7bdat, lb_urin.sas7bdat, lb_urin_ole.sas7bdat all mapping to LB |
| D10 | **Explain-the-Mapping Feature** | For every mapping decision, provide a natural language explanation: "AESTDAT is mapped from AE.AESTDTC because it is the adverse event start date collected on the AE form, reformatted from DD-MON-YYYY to ISO 8601" | Low-Medium | T1, T4 | Builds trust. LLMs are naturally good at this. Also serves as auto-documentation for define.xml ComputationMethod entries |

---

## Anti-Features

Features to deliberately NOT build. Common traps in this domain.

| # | Anti-Feature | Why Avoid | What to Do Instead |
|---|--------------|-----------|-------------------|
| A1 | **Full EDC System / Data Collection** | Formedix ryze went end-to-end from EDC to SDTM. Building data collection is a massive scope expansion that competes with Medidata Rave, Oracle InForm, Veeva Vault CDMS. It's a different product entirely | Accept source data as-is (SAS7BDAT, CSV, XPT). Be the best at mapping, not at collection |
| A2 | **ADaM Dataset Generation** | ADaM (Analysis Data Model) is the next step after SDTM but is a fundamentally different problem (analysis-oriented vs tabulation-oriented). Trying to do both halves the quality of each | Produce SDTM only. Ensure output is ADaM-ready (proper SDTM structure enables downstream ADaM). Could be a future product |
| A3 | **Custom SAS Code Generation** | Many legacy tools generate SAS programs. This locks users into SAS licenses ($$$) and a dying ecosystem. Python/R are the future of clinical data science | Generate datasets directly via Python. Provide mapping specs that any language can implement. sdtm.oak (R) and open-source Python tools prove the industry is moving away from SAS |
| A4 | **MedDRA / WHODrug Coding Engine** | Medical coding (mapping AE terms to MedDRA, medications to WHODrug) is a specialized problem with dedicated tools (IQVIA AutoEncoder, Medidata Coder). Building a coder is a massive undertaking | Accept pre-coded data (source datasets should already have MedDRA/WHODrug codes). Validate that coded variables are present and correctly placed in SDTM. Integrate with existing coding tools if needed |
| A5 | **Real-Time Data Pipeline / Streaming** | Clinical data is batch-oriented (database locks, snapshots). Building real-time streaming adds complexity with zero user demand | Process data in batch mode. Accept a data snapshot, produce SDTM datasets. This matches how the industry actually works |
| A6 | **Multi-Tenant SaaS Platform (Day 1)** | Building cloud infrastructure, user management, billing, etc. before the core mapping engine works is premature optimization | Start as a CLI / local tool. Add web UI later. SaaS can come once the mapping engine is proven |
| A7 | **Visual Drag-and-Drop Mapping UI** | Many legacy tools have complex visual mapping interfaces that take months to build and are actually slower than a well-designed spec-based workflow | Provide a clean review/edit interface for mapping specs, not a visual flow builder. The AI should propose mappings; humans should review and correct, not drag-and-drop |
| A8 | **Protocol PDF Parsing (Day 1)** | Protocol documents are 200+ page PDFs with highly variable structure. Parsing them is a separate NLP challenge | Start with eCRF parsing (semi-structured, predictable format). Protocol parsing can enhance mappings later but is not required for core functionality |

---

## The 9 Mapping Transformation Scenarios (Detailed)

These are the fundamental operations any SDTM mapping system must perform. Each has different complexity and automation potential.

### Scenario 1: Direct Copy (Carry Forward)
**What:** Source variable is already SDTM-compliant. Copy as-is.
**Example:** STUDYID in source -> STUDYID in SDTM DM domain
**Complexity:** Trivial
**AI Automation Potential:** Very High -- pattern matching on variable names and content
**Detection Heuristic:** Same name, same content, same type/length

### Scenario 2: Rename
**What:** Source variable maps directly but has a different name.
**Example:** GENDER in source -> SEX in SDTM DM
**Complexity:** Low
**AI Automation Potential:** Very High -- semantic similarity of names + content validation
**Detection Heuristic:** Different name but same values; semantic match between names

### Scenario 3: Reformat
**What:** Same value, different representation format.
**Example:** SAS date numeric (e.g., 22145) -> ISO 8601 character string (2020-08-15)
**Complexity:** Medium
**AI Automation Potential:** High -- format detection is well-understood
**Detection Heuristic:** Content is equivalent but format differs (dates, number formats)

### Scenario 4: Split
**What:** One source variable becomes two or more SDTM variables.
**Example:** "120/80 mmHg" -> VSORRES="120/80", VSORRESU="mmHg"; or AEDECOD with both term and severity split
**Complexity:** Medium-High
**AI Automation Potential:** Medium -- requires understanding field semantics
**Detection Heuristic:** Source variable contains structured/delimited content

### Scenario 5: Combine
**What:** Multiple source variables become one SDTM variable.
**Example:** STUDYID + SITEID + SUBJID -> USUBJID
**Complexity:** Medium
**AI Automation Potential:** Medium-High -- common patterns are well-known (USUBJID construction)
**Detection Heuristic:** Target variable is a concatenation or computation from multiple sources

### Scenario 6: Derivation
**What:** SDTM variable is calculated/derived from source data using business logic.
**Example:** AGE = floor((RFSTDTC - BRTHDTC) / 365.25); AEDUR derived from start and end dates
**Complexity:** High
**AI Automation Potential:** Medium -- requires domain knowledge; LLM can propose but must validate
**Detection Heuristic:** No single source maps directly; requires algorithmic transformation

### Scenario 7: Lookup / Recode (Value Mapping)
**What:** Source values must be recoded to CDISC controlled terminology.
**Example:** Source "Male"/"Female" -> CT "M"/"F"; or source "1"/"2" -> CT "Y"/"N"
**Complexity:** Medium
**AI Automation Potential:** High -- CT codelists are well-defined; LLM can match synonyms
**Detection Heuristic:** Source values are semantically equivalent to CT terms but use different representations

### Scenario 8: Transpose (Restructure)
**What:** Wide-format source data (one column per test) restructured to tall SDTM format (one row per test).
**Example:** Lab data with columns GLUCOSE, CREATININE, BUN -> LB domain with LBTESTCD, LBORRES, LBORRESU rows
**Complexity:** Very High
**AI Automation Potential:** Medium -- structure detection is possible but mapping each column to the correct test code requires domain knowledge
**Detection Heuristic:** Source has many numeric columns that represent different measurements; target domain is Findings class

### Scenario 9: Variable Attribute Mapping
**What:** Variable attributes (label, type, length, format) adjusted to match SDTM IG specifications.
**Example:** Character variable length adjusted from $200 to $40 per SDTM spec; label changed to match IG-defined label
**Complexity:** Low
**AI Automation Potential:** Very High -- purely metadata-driven, can be automated from SDTM IG reference
**Detection Heuristic:** Always required for all variables; apply SDTM IG metadata

---

## Mapping Specification Format

### Industry Standard: Excel Workbook

The standard SDTM mapping specification is an Excel workbook with the following structure:

**Workbook-level sheets:**
- **TOC / Dataset Metadata:** List of all domains, dataset labels, structure, class, keys
- **Variable Metadata:** Per-domain sheets, one row per variable

**Per-Domain Sheet Columns (Standard):**

| Column | Description | Example |
|--------|-------------|---------|
| Order | Variable sequence number | 1, 2, 3 |
| Dataset | Domain name | DM, AE, LB |
| Variable | SDTM variable name | STUDYID, USUBJID, AEDECOD |
| Label | Variable label | "Study Identifier" |
| Data Type | Char or Num | Char |
| Length | Variable length | 20 |
| Significant Digits | For numeric vars | 0 |
| Format | Display format | |
| Core | Required/Expected/Permissible | Req |
| Origin | Collected/Derived/Assigned/Predecessor | Derived |
| Source Dataset | Raw dataset name | ae.sas7bdat |
| Source Variable | Raw variable name | AESTDAT |
| Derivation Algorithm | Mapping logic description | "Convert DD-MON-YYYY to ISO 8601" |
| Controlled Terminology | Codelist name | NY (Yes/No) |
| Comment | Reviewer notes | |

### sdtm.oak Format (Source-to-Target)

sdtm.oak uses a different orientation -- source-to-target rather than target-to-source:
- raw_source_model, raw_dataset, raw_variable
- target_domain, target_sdtm_variable, target_sdtm_variable_role
- mapping_algorithm (condition_add, assign_ct, hardcode_ct, etc.)
- annotation_text, origin
- Conditional parameters, merge parameters, hardcoded values

**Recommendation for Astraea:** Generate BOTH formats. The traditional Excel spec for human reviewers and a structured JSON/YAML mapping definition for programmatic execution. This bridges the gap between what humans expect and what machines need.

---

## Validation Features (Pinnacle 21 Model)

### P21 Validation Rule Categories

| Category | What It Checks | Example |
|----------|---------------|---------|
| **Terminology** | Values match CDISC controlled terminology | SEX must be "M", "F", or "U" (not "Male") |
| **Presence** | Required variables/records exist | USUBJID must be present in every domain |
| **Consistency** | Values are consistent across domains/records | RFSTDTC in DM must match earliest exposure date |
| **Limit** | Values within expected ranges | Variable length does not exceed SDTM IG specification |
| **Format** | Values follow required format patterns | Dates must be ISO 8601; variable names must be <= 8 characters |

### P21 Severity Levels

| Severity | Regulatory Impact | Action Required |
|----------|------------------|-----------------|
| **Error** (High) | Will trigger FDA rejection or query | Must fix before submission |
| **Warning** (Medium) | May cause reviewer questions | Should fix; document if intentional |
| **Warning** (Low) | Minor quality issue | Fix if possible; document rationale |
| **Notice** | Informational | Review; no action typically required |

### Key Validation Rules to Internalize

Astraea-SDTM should check these DURING mapping, not after:

- **SD1001:** Duplicate SUBJID check
- **Controlled Terminology violations:** Non-extensible codelist values must match exactly
- **Missing required variables:** Core="Required" variables must be populated
- **Date format compliance:** All --DTC variables in ISO 8601
- **Dataset key uniqueness:** Each domain has defined keys that must be unique
- **Cross-domain consistency:** DM.RFSTDTC consistent with EX dates; USUBJID consistent everywhere
- **Variable attribute compliance:** Labels, types, lengths per SDTM IG
- **SUPPQUAL structure:** QNAM, QLABEL, QVAL, QORIG, QEVAL must follow rules

---

## eCRF/aCRF Annotation Features

### What Existing Tools Do

**Formedix ryze:** Generates aCRFs automatically from its internal metadata when forms are designed in the platform. aCRF annotations link CRF fields to SDTM variables in a searchable PDF. This requires using Formedix for form design (lock-in).

**Traditional Process:** A human SAS programmer manually annotates a blank CRF PDF using Adobe Acrobat, adding text annotations that reference SDTM dataset.variable for each field. This takes 2-4 weeks per study.

**CDISC aCRF Guideline v1.0:** Standardizes annotation format. Annotations must be:
- Searchable text (not images)
- Format: DOMAIN.VARIABLE (e.g., "AE.AETERM")
- Include visit mapping (VISIT, VISITNUM)
- Include special annotations for derived variables

### What Astraea Should Do (Differentiator)

**Input:** eCRF PDF (like the project's ECRF.pdf -- a blank CRF with form definitions)
**Processing:**
1. Parse PDF to extract form structure (form name, fields, data types, value lists)
2. Use LLM to match forms to SDTM domains
3. Use LLM to match fields to SDTM variables
4. Generate annotated CRF PDF as output
5. Feed parsed structure into mapping engine

**Key insight from project's ECRF_text.txt:** The eCRF has structured metadata:
- Form names ("Subject Enrollment", "Date of Visit", etc.)
- Field names with SAS labels (ENSUBJID, SUBJERR, etc.)
- Data types ($25, $10, numeric)
- Value codelists (Yes/No options)
- Field OIDs

This semi-structured format is highly amenable to LLM parsing.

---

## Domain-Specific Feature Requirements

### SUPPQUAL Handling
- Minimize SUPPQUAL use (CDISC guidance)
- When needed: generate RDOMAIN, QNAM, QLABEL, QVAL, QORIG, QEVAL correctly
- QNAM must be <= 8 characters, unique within domain
- Auto-detect when a non-standard variable should go to SUPPQUAL vs. FA vs. custom domain
- Custom domains use X-/Y-/Z- prefix (e.g., XV for custom vitals)

### RELREC (Related Records)
- Maps relationships between records across domains
- 7 key variables: STUDYID, RDOMAIN, USUBJID, IDVAR, IDVARVAL, RELTYPE, RELID
- Common use: linking AE records to CM records (concomitant medication for an adverse event)
- Complexity: auto-generating RELREC from source data requires understanding inter-domain relationships

### Findings Class Domains (LB, VS, EG, PE)
- Almost always require transpose (wide-to-tall)
- Require --TESTCD, --TEST, --ORRES, --ORRESU, --STRESC, --STRESN, --STRESU
- Standardized results (STRESC/STRESN) require unit conversion logic
- Lab data often has multiple source datasets (project has 7+ lab datasets)
- Normal range handling (--ORNRLO, --ORNRHI)

### Events Class Domains (AE, CE, MH, DV)
- Start/end date handling with partial date support
- Severity/toxicity grading
- Outcome, causality, seriousness flags
- MedDRA coding integration (accept pre-coded)
- Duration derivation

### Interventions Class Domains (CM, EX)
- Dose, route, frequency handling
- WHODrug coding integration (accept pre-coded)
- Start/end date and ongoing medication handling
- EX: requires precise exposure records per protocol schedule

### Trial Design Domains (TA, TE, TV, TI, TS, SE, SV)
- Often one-time setup per study
- TS (Trial Summary) has specific parameters required by FDA
- SV (Subject Visits) links visits to planned schedule
- Lower priority for AI automation (small, formulaic datasets)

---

## Feature Dependencies

```
T7 (CDISC Metadata) ──> T3 (Controlled Terminology)
                    ──> T2 (Domain Coverage)
                    ──> T12 (Date Handling)

T9 (Data Ingestion) ──> T1 (9 Mapping Types) ──> T4 (Mapping Spec Output)
                                               ──> T2 (Domain Coverage)

T4 (Mapping Spec) ──> T5 (define.xml)
                  ──> T10 (Traceability)

T2 (Domain Coverage) ──> T6 (P21 Validation)
                     ──> T8 (XPT Output)

D1 (eCRF Parsing) ──> D3 (Domain Assignment)
                  ──> D9 (Multi-Source Merge)

D2 (RL from Corrections) ──> D5 (Cross-Study Learning)

D8 (Confidence Scoring) ──> D10 (Explain-the-Mapping)

T1 + T7 ──> D4 (NL Derivation Descriptions)
T1 + T6 ──> D7 (Pre-Submission Validation)
```

---

## MVP Recommendation

### Phase 1 -- Core Mapping Engine (Must Ship)
1. **T9** - Source data ingestion (SAS7BDAT, CSV)
2. **T7** - CDISC metadata repository (SDTM IG reference data)
3. **T1** - All 9 mapping transformation types
4. **T2** - Core SDTM domains (DM, AE, CM, EX, LB, VS, MH, DS at minimum)
5. **T11** - USUBJID generation
6. **T12** - ISO 8601 date handling
7. **T3** - Controlled terminology application
8. **T4** - Mapping specification output (Excel)
9. **T8** - XPT file output

### Phase 2 -- AI Intelligence Layer
1. **D1** - eCRF PDF parsing (the "wow" feature for demos)
2. **D3** - Intelligent domain assignment
3. **D8** - Confidence scoring per mapping
4. **D10** - Explain-the-mapping
5. **D9** - Multi-source merge intelligence

### Phase 3 -- Validation and Compliance
1. **T6** - P21 validation integration
2. **D7** - Pre-submission validation report
3. **T5** - define.xml generation
4. **T10** - Full traceability documentation

### Phase 4 -- Learning System
1. **D2** - RL from human corrections
2. **D5** - Cross-study learning / template library
3. **D4** - Natural language derivation descriptions
4. **D6** - Automated SUPPQUAL decision-making

### Defer to Post-MVP Entirely
- A2 (ADaM generation) - different product
- A4 (MedDRA/WHODrug coding) - accept pre-coded data
- A6 (SaaS platform) - prove engine first
- Trial Design domains (TA, TE, TV, TI, TS) - small, can be manual

---

## Competitive Landscape Summary

| Capability | Pinnacle 21 Enterprise | Formedix ryze | Nurocor NCP | sdtm.oak (Open Source) | Astraea-SDTM (Target) |
|------------|----------------------|---------------|-------------|----------------------|----------------------|
| Mapping Spec Management | Yes | Yes | Yes | Partial | Yes |
| SDTM Dataset Generation | Yes | Yes (1-click) | Yes | Yes (R code) | Yes |
| define.xml Generation | Yes | Yes | Yes | No | Yes |
| P21 Validation | Built-in | Integrated | Unknown | No | Integrated |
| aCRF Generation | Manual | Automated (in-platform) | Unknown | No | **Automated from PDF** |
| AI-Powered Mapping | Limited | Limited | Limited | No | **Core capability** |
| Learning from Corrections | No | No | No | No | **Key differentiator** |
| Confidence Scoring | No | No | No | No | **Key differentiator** |
| Cross-Study Learning | Template reuse | Template reuse | MDR-based | No | **AI-powered** |
| Pricing Model | Enterprise ($$$) | Enterprise ($$$) | Enterprise ($$$) | Free/OSS | TBD |

---

## Sources

### HIGH Confidence (Official / Authoritative)
- [CDISC Controlled Terminology](https://www.cdisc.org/standards/terminology/controlled-terminology)
- [CDISC aCRF Guideline v1.0](https://wiki.cdisc.org/download/attachments/113589261/aCRF_Guideline_v1-0_20201120_publish.pdf)
- [Pinnacle 21 SDTM Validation Rules](https://standards.pinnacle21.certara.net/validation-rules/sdtm)
- [sdtm.oak Path to Automation (spec format)](https://pharmaverse.github.io/sdtm.oak/articles/study_sdtm_spec.html)
- [sdtm.oak GitHub](https://github.com/pharmaverse/sdtm.oak)
- [FDA Study Data Technical Conformance Guide](https://www.fda.gov/media/122913/download)

### MEDIUM Confidence (Vendor / Verified Multiple Sources)
- [Pinnacle 21 SDTM Specification Management](https://www.certara.com/pinnacle-21-enterprise-software/sdtm-specification-management/)
- [Formedix ryze Platform](https://www.formedix.com/ryze-clinical-metadata-repository-automation-platform/)
- [Formedix aCRF Features](https://www.formedix.com/annotated-crfs)
- [Nurocor Clinical Platform](https://nurocor.com/products/)
- [Pinnacle 21 + Formedix Acquisition](https://www.pinnacle21.com/P21-Formedix-join-forces)

### LOW Confidence (WebSearch Only / Single Source)
- [AI + HITL for SDTM (Applied Clinical Trials)](https://www.appliedclinicaltrialsonline.com/view/the-future-of-sdtm-transformation-ai-and-hitl) -- Could not fetch full content (403)
- [ML Approach to SDTM Spec Automation (PHUSE 2025)](https://www.lexjansen.com/phuse-us/2025/ml/PAP_ML20.pdf) -- PDF could not be parsed
- [9 SDTM Mapping Scenarios (Formedix/LinkedIn)](https://www.linkedin.com/pulse/9-sdtm-mapping-scenarios-you-need-know-formedix)
- Claims about "35-45 hours manual vs <10 hours AI-assisted" -- single source, unverified
