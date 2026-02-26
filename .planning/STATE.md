# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Given any clinical study's raw data and eCRF, produce accurate SDTM-compliant datasets with minimal human intervention -- and get better with every correction.
**Current focus:** Phase 2 IN PROGRESS -- eCRF Parsing and Domain Classification (plan 3/5 complete)

## Current Position

Phase: 2 of 8 (Source Parsing and Domain Classification)
Plan: 3 of 5 (Heuristic Domain Scorer)
Status: In progress
Last activity: 2026-02-26 -- Completed 02-03-PLAN.md (Heuristic Domain Scorer)

Progress: [████████████████░░░░░░░░░░░░░░░░░░░░░░░░] ~28%

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: ~3.3 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 5/5 | ~18 min | ~3.5 min |
| 02-source-parsing | 3/5 | ~9 min | ~3 min |

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

## Phase 2 Deliverables (In Progress)

| Component | Module | Tests | Status |
|-----------|--------|-------|--------|
| eCRF + classification models | src/astraea/models/ecrf.py, classification.py | 35 | Done |
| LLM client wrapper | src/astraea/llm/client.py | 8 | Done |
| PDF extraction | src/astraea/parsing/pdf_extractor.py | -- | Pending |
| eCRF parsing | src/astraea/parsing/ecrf_parser.py | -- | Pending |
| Heuristic domain scorer | src/astraea/classification/heuristic.py | 29 | Done |
| LLM domain classification | src/astraea/classification/ | -- | Pending |
| CLI commands | src/astraea/cli/app.py | -- | Pending |

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
- 2026-02-26: [D-0203-01] Segment-boundary matching for filename contains-check prevents false positives
- 2026-02-26: [D-0203-02] UNCLASSIFIED threshold at 0.3 -- scores below this trigger UNCLASSIFIED return
- 2026-02-26: [D-0203-03] Common identifiers excluded from variable overlap scoring

### Pending Todos

(None)

### Blockers/Concerns

- eCRF PDF parsing quality unknown -- prototype early in Phase 2 with real ECRF.pdf
- Python 3.12 compatibility verified: all dependencies install cleanly on 3.12.12
- CDISC Rules Engine integration complexity unknown -- may need Phase 7 research spike

## Session Continuity

Last session: 2026-02-26 21:57 UTC
Stopped at: Completed 02-03-PLAN.md -- Heuristic Domain Scorer
Resume file: None
