# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Given any clinical study's raw data and eCRF, produce accurate SDTM-compliant datasets with minimal human intervention -- and get better with every correction.
**Current focus:** Phase 2.1 Complete -- Ready for Phase 3 (Mapping Engine)

## Current Position

Phase: 2.1 of 8 (Reference Data Fixes)
Plan: 4 of 4
Status: Phase complete
Last activity: 2026-02-27 -- Completed 02.1-04-PLAN.md (domains.json corrections + key_variables)

Progress: [█████████████████████░░░░░░░░░░░░░░░░░░░] ~40%

## Performance Metrics

**Velocity:**
- Total plans completed: 17
- Average duration: ~3.1 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 5/5 | ~18 min | ~3.5 min |
| 02-source-parsing | 8/8 | ~26 min | ~3.3 min |
| 02.1-ref-data-fixes | 4/4 | ~13 min | ~3.3 min |

## Phase 1 Deliverables

| Component | Module | Tests |
|-----------|--------|-------|
| Pydantic data models | src/astraea/models/ | 35 |
| SAS reader + profiler | src/astraea/io/, src/astraea/profiling/ | 42 |
| SDTM-IG + CT reference | src/astraea/reference/ | 59 |
| Date conversion + USUBJID | src/astraea/transforms/ | 80 |
| XPT writer + CLI | src/astraea/io/xpt_writer.py, src/astraea/cli/ | -- |
| **Total** | | **216 tests passing** |

CLI commands available: `astraea profile`, `astraea reference`, `astraea codelist`

## Phase 2 Deliverables

| Component | Module | Tests | Status |
|-----------|--------|-------|--------|
| eCRF + classification models | src/astraea/models/ecrf.py, classification.py | 35 | Done |
| LLM client wrapper | src/astraea/llm/client.py | 8 | Done |
| PDF extraction | src/astraea/parsing/pdf_extractor.py | 15 | Done |
| eCRF parsing | src/astraea/parsing/ecrf_parser.py | 13 | Done |
| Heuristic domain scorer | src/astraea/classification/heuristic.py | 29 | Done |
| Form-dataset matcher | src/astraea/parsing/form_dataset_matcher.py | 13 | Done |
| LLM domain classifier | src/astraea/classification/classifier.py | 14 | Done |
| CLI commands (parse-ecrf, classify) | src/astraea/cli/app.py, display.py | 17 | Done |
| **Total** | | **144 tests** | **Complete** |

CLI commands available: `astraea parse-ecrf`, `astraea classify`

## Phase 2.1 Deliverables

| Component | Module | Tests | Status |
|-----------|--------|-------|--------|
| CT codelist C-code fixes | src/astraea/data/ct/codelists.json | 13 | Done |
| Date conversion bug fixes | src/astraea/transforms/dates.py | 9 | Done |
| USUBJID NaN fix + EDC columns | src/astraea/transforms/usubjid.py, profiling/ | 15 | Done |
| domains.json corrections + keys | src/astraea/data/sdtm_ig/domains.json | 50 | Done |
| DomainSpec key_variables | src/astraea/models/sdtm.py | -- | Done |
| **Total** | | **87 new tests** | **Complete** |

**Combined test suite: 490 tests passing**

## Accumulated Context

### Decisions

- 2026-02-26: Split domain expansion into two phases (5: Events/Interventions, 6: Findings) to isolate transpose complexity
- 2026-02-26: Human Review Gate as standalone phase (4) since it is the quality control layer all subsequent domain work depends on
- 2026-02-26: Validation as Phase 7 (after all domains) since cross-domain consistency checks require all datasets present
- 2026-02-26: [D-0101-01] Used setuptools.build_meta as build backend (not legacy)
- 2026-02-26: [D-0101-02] VariableMetadata.storage_width ge=1 (0 bytes invalid in SAS)
- 2026-02-26: [D-0101-03] VariableSpec.order ge=1 (SDTM ordering is 1-based)
- 2026-02-26: [D-0102-01] pyreadstat labels can be None -- use `or ''` not `.get(key, '')`
- 2026-02-26: [D-0102-02] EDC column matching uses frozenset of 25 known column names with lowercase comparison
- 2026-02-26: [D-0102-03] String date detection limited to _RAW columns containing DAT in the name
- 2026-02-26: [D-0103-01] Path(__file__) approach for bundled data loading (not importlib.resources)
- 2026-02-26: [D-0103-02] Country codelist uses ISO 3166-1 alpha-3 codes per SDTM-IG v3.4
- 2026-02-26: [D-0103-03] Extensible codelist validate_term() always returns True for any value
- 2026-02-26: [D-0104-01] Ambiguous slash-separated dates default to DD/MM/YYYY
- 2026-02-26: [D-0104-02] extract_usubjid_components with >3 parts joins remainder as subjid
- 2026-02-26: [D-0104-03] SAS DATETIME uses UTC internally, output is timezone-naive per SDTM convention
- 2026-02-26: [D-0105-01] XPT writer performs mandatory read-back verification after every write
- 2026-02-26: [D-0105-02] CLI uses typer.Argument/Option with Rich console for all output formatting
- 2026-02-26: [D-0201-01] ECRFField.field_name validated for no-spaces (SAS variable names)
- 2026-02-26: [D-0201-02] ECRFExtractionResult.total_fields as computed @property
- 2026-02-26: [D-0201-03] DomainClassification includes heuristic_scores for two-stage classification traceability
- 2026-02-26: [D-0201-04] AstraeaLLMClient.parse() uses keyword-only arguments
- 2026-02-26: [D-0202-01] Escaped curly braces in ECRF_EXTRACTION_PROMPT for str.format() compatibility
- 2026-02-26: [D-0202-02] _MIN_FORM_TEXT_LENGTH=50 chars threshold for skipping trivial form pages
- 2026-02-26: [D-0202-03] Multi-page form concatenation uses markdown horizontal rule separator
- 2026-02-26: [D-0203-01] Segment-boundary matching for filename contains-check prevents false positives
- 2026-02-26: [D-0203-02] UNCLASSIFIED threshold at 0.3 -- scores below this trigger UNCLASSIFIED return
- 2026-02-26: [D-0203-03] Common identifiers excluded from variable overlap scoring
- 2026-02-26: [D-0204-01] Form-dataset matching uses field_name overlap ratio (form fields / clinical vars)
- 2026-02-26: [D-0204-02] Heuristic-LLM disagreement with heuristic >= 0.8 reduces confidence by min * 0.7
- 2026-02-26: [D-0204-03] Findings domains (LB, VS, EG, PE, QS, SC, FA) auto-detect transpose pattern
- 2026-02-27: [D-0205-01] LLM client uses tool-use with forced tool_choice for structured output (not messages.parse)
- 2026-02-27: [D-0205-02] CLI commands require ANTHROPIC_API_KEY with clear error messages when missing
- 2026-02-27: [D-0205-03] Classification display includes merge groups panel for multi-source domains
- 2026-02-27: [D-0206-01] Digits accepted as valid right-boundary only (not left) in _is_segment_match
- 2026-02-27: [D-0208-01] Failed forms get empty-field ECRFForm placeholder (not silently dropped)
- 2026-02-27: [D-0208-02] pre_extracted_pages parameter avoids redundant PDF extraction in CLI
- 2026-02-27: [D-0207-01] Heuristic override threshold set at 0.95 (not 0.9) to avoid false overrides
- 2026-02-27: [D-0207-02] Override replaces LLM domain and uses heuristic score as confidence
- 2026-02-27: [D-02.1-01-01] Race codelist uses C74457 (not C66767 which is Action Taken)
- 2026-02-27: [D-02.1-01-02] Country codelist uses ISO3166 key (not a retired NCI C-code)
- 2026-02-27: [D-02.1-01-03] Age Unit (C66781) variable_mappings narrowed to AGEU only; general Unit is C71620
- 2026-02-27: [D-02102-01] Plan 02.1-02 expected value for sas_date_to_iso(22738.9999) corrected from "2022-03-30" to "2022-04-04"
- 2026-02-27: [D-02.1-03-01] ValueError raised for NaN/None/empty USUBJID components (fail-fast over silent corruption)
- 2026-02-27: [D-02.1-03-02] pd.NA used for invalid USUBJID column rows (preserves pandas NA semantics)
- 2026-02-27: [D-02.1-03-03] EDC column set expanded from 25 to 29 (subject, sitenumber, site, sitegroup)
- 2026-02-27: [D-02.1-04-01] Forward-reference codelist codes allowed in domains.json for not-yet-populated codelists
- 2026-02-27: [D-02.1-04-02] DOMAIN variable gets C66734 codelist, EPOCH gets C99079 across all domains
- 2026-02-27: [D-02.1-04-03] Non-core domains get key_variables: null (to be populated when actively mapped)

### Pending Todos

(None)

### Roadmap Evolution

- Phase 2.1 inserted after Phase 2: Reference Data Fixes (Critical for Phase 3) (URGENT)
  - Triggered by: Comprehensive Phase 2 audit found 9/11 CT codelist C-codes wrong, 19 wrong codelist assignments, 15 wrong core designations, 10 critical code bugs
  - Phase 3 BLOCKED until 2.1 completes -- mapper cannot produce correct SDTM with wrong reference data
  - Scope: All 14 Tier 1 items from .planning/PHASE2_AUDIT.md section 9
  - STATUS: **COMPLETE** -- all 4 plans executed, 490 tests passing

### Blockers/Concerns

- Phase 3 now UNBLOCKED -- reference data corrected
- Python 3.12 compatibility verified: all dependencies install cleanly on 3.12.12
- CDISC Rules Engine integration complexity unknown -- may need Phase 7 research spike

## Session Continuity

Last session: 2026-02-27
Stopped at: Completed 02.1-04-PLAN.md (domains.json corrections + key_variables) -- Phase 2.1 COMPLETE
Resume file: None
