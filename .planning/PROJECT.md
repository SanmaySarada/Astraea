# Astraea-SDTM

## What This Is

An agentic AI system that maps raw clinical trial data to CDISC SDTM format. It takes raw SAS datasets and an eCRF PDF as input, runs them through a pipeline of specialized LLM agents (parser, domain classifier, mapper, derivation engine, validator), presents a mapping specification for human review, and produces submission-ready SDTM datasets. The system learns from human corrections through reinforcement learning, improving accuracy over time.

## Core Value

Given any clinical study's raw data and eCRF, the system produces accurate SDTM-compliant datasets with minimal human intervention — and gets better with every correction.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Parse eCRF PDFs to extract form/field metadata (field names, data types, SAS labels, coded values, OIDs)
- [ ] Read raw SAS (.sas7bdat) files and profile their structure (variables, types, distributions)
- [ ] Classify raw datasets to SDTM domains (DM, AE, LB, VS, CM, EX, EG, MH, DS, etc.)
- [ ] Map raw variables to SDTM variables using SDTM-IG rules, CT codelists, and eCRF context
- [ ] Handle all 5 mapping patterns: direct carry, rename, transpose (horizontal→vertical), derivation, merging
- [ ] Convert dates/times to ISO 8601 format
- [ ] Apply CDISC Controlled Terminology (NCI codelists) for coded values
- [ ] Generate mapping specification document for human review before dataset creation
- [ ] Support human review gate: present proposed mappings, accept corrections
- [ ] Generate final SDTM datasets (.xpt format) after mapping approval
- [ ] Run built-in P21-style CDISC conformance validation on output datasets
- [ ] Support all standard SDTM domains (including SUPPQUAL, RELREC, custom domains)
- [ ] Store human corrections and use them to improve future mappings (RL/fine-tuning pipeline)
- [ ] Work as a CLI tool: point at a data folder with raw SAS files + eCRF PDF, get SDTM output
- [ ] Be generalizable: handle any study's data, not hardcoded to a specific trial

### Out of Scope

- Web UI — deferred to future milestone, CLI first
- Real-time streaming/dashboard — batch processing is sufficient
- Non-SAS input formats (CSV, Excel) — add later
- Protocol/SAP PDF parsing (USDM) — eCRF is the primary context source for v1
- Integration with external EDC systems (Medidata Rave, Oracle InForm) — standalone tool for now
- Mobile app

## Context

**Domain:** Clinical data standardization for FDA/regulatory submission. CDISC SDTM is the required format for submitting clinical trial data to the FDA. Currently, SDTM mapping is done manually by statistical programmers using SAS — it's expensive, slow, and error-prone.

**Sample Data:** 36 raw SAS datasets from a Phase 3 HAE (Hereditary Angioedema) trial (Study PHA022121-C301), plus a 189-page annotated eCRF. Datasets include: ae, cm, dm, ds, dv, ecg_results, ecoa, eg (pre/post), epro, ex, haemh, ie, irt, lab_results, lb (biochem/coagulation/hematology/urinalysis), lg, llb, mh, ole, pe, pg, c1_inh, ctest, da_disp, ds2, eg3.

**eCRF Structure:** Standard format across studies — each form contains field names, data types, SAS labels, units, coded values, and field OIDs. Forms cover: Subject Enrollment, Demographics, Medical History, Vital Signs, ECGs, Labs, Adverse Events, Concomitant Medications, Study Drug Administration, PK, Disposition, and more.

**Key Technical Challenges:**
- eCRF PDF parsing: extracting structured metadata from a 189-page PDF with mixed table/text layouts
- Variable name matching: raw names (e.g., WT_LBS) to SDTM targets (VSORRES) requires semantic understanding
- Horizontal-to-vertical transpose: pivoting wide lab/vital sign tables into lean SDTM format
- Controlled Terminology mapping: matching free-text values to NCI codelist terms
- Agent learning: implementing RL from human corrections to improve mapping accuracy over time

**Architecture Vision:** LLM as agentic orchestrator coordinating specialized agents:
1. Parser Agent — reads eCRF PDF and SAS files, extracts metadata
2. Domain Classifier Agent — classifies raw datasets to SDTM domains
3. Mapping Agent (per domain) — proposes variable-level mappings
4. Derivation Agent — handles calculated fields, transposes, merges, ISO dates
5. Validator Agent — runs P21-style conformance checks (deterministic rules, not LLM)
6. Human Review Gate — presents mapping spec, captures corrections
7. Dataset Generator — produces final SDTM .xpt files

**Two Big Technical Bets:**
- Bet 1: Well-prompted LLM agents with SDTM-IG + CT + eCRF context can accurately propose mappings
- Bet 2: RL from human corrections can make those agents improve over time

## Constraints

- **Tech Stack**: Python — pandas for data manipulation, LLM framework (TBD after research — LangGraph, AutoGen, DSPy candidates), Claude API for LLM reasoning
- **Data Format**: SAS (.sas7bdat) input, XPT (.xpt) output
- **Standards**: Must comply with CDISC SDTM-IG (latest version), NCI Controlled Terminology
- **Bundled Reference**: CDISC CT codelists shipped with the tool (not fetched at runtime)
- **Interface**: CLI for v1
- **Learning**: RL/fine-tuning approach TBD after research phase — need to investigate AutoGen, DSPy, OpenAI fine-tuning API, and other agent learning frameworks

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Agentic orchestrator architecture | Most flexible — LLM coordinates specialized tools rather than monolithic rules or pure LLM | — Pending |
| Python stack | Natural fit for data (pandas) + LLM (LangChain/LangGraph) + clinical data (sas7bdat) | — Pending |
| CLI first | Fastest to build, prove the core mapping logic before investing in UI | — Pending |
| Bundle CT codelists | Avoid runtime dependency on external services, ensure offline capability | — Pending |
| RL from human corrections | Core differentiator — system gets better with use. Approach TBD after research. | — Pending |
| Built-in validation | Catch conformance issues before output, reduce back-and-forth with P21 | — Pending |
| SAS-only input for v1 | Industry standard format, covers vast majority of clinical data | — Pending |

---
*Last updated: 2026-02-26 after initialization*
