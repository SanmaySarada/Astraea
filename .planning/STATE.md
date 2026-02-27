# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Given any clinical study's raw data and eCRF, produce accurate SDTM-compliant datasets with minimal human intervention -- and get better with every correction.
**Current focus:** Phase 2 gap closure -- fixing UAT findings (7/11 plans done)

## Current Position

Phase: 2 of 8 (Source Parsing and Domain Classification) -- Gap closure
Plan: 8 of 11 (eCRF Parse Resilience and CLI Single Extraction) -- COMPLETE
Status: In progress, gap closure plans 07, 09-11 remaining
Last activity: 2026-02-27 -- Completed 02-08-PLAN.md (eCRF Parse Resilience and CLI Single Extraction)

Progress: [██████████████████████░░░░░░░░░░░░░░░░░░] ~43%

## Performance Metrics

**Velocity:**
- Total plans completed: 12
- Average duration: ~3.1 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 5/5 | ~18 min | ~3.5 min |
| 02-source-parsing | 7/11 | ~23 min | ~3.3 min |

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

**Combined test suite: 379 tests passing**

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

### Pending Todos

(None)

### Blockers/Concerns

- Python 3.12 compatibility verified: all dependencies install cleanly on 3.12.12
- CDISC Rules Engine integration complexity unknown -- may need Phase 7 research spike

## Session Continuity

Last session: 2026-02-27 03:37 UTC
Stopped at: Completed 02-08-PLAN.md -- eCRF Parse Resilience and CLI Single Extraction
Resume file: None
