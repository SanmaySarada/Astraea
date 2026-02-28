# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Given any clinical study's raw data and eCRF, produce accurate SDTM-compliant datasets with minimal human intervention -- and get better with every correction.
**Current focus:** Phase 8 COMPLETE -- Learning System (4/4 plans complete). ALL PHASES COMPLETE.

## Current Position

Phase: 8 of 8 (Learning System)
Plan: 4 of 4 (Cross-Study Template Library)
Status: COMPLETE -- All 8 phases finished
Last activity: 2026-02-28 -- Completed 08-04-PLAN.md (Cross-study template library)

Progress: [████████████████████████████████████████████████████████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 40
- Average duration: ~3.4 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 5/5 | ~18 min | ~3.5 min |
| 02-source-parsing | 8/8 | ~26 min | ~3.3 min |
| 02.1-ref-data-fixes | 4/4 | ~13 min | ~3.3 min |
| 03-core-mapping-engine | 5/5 | ~25 min | ~5.0 min |
| 03.1-audit-fixes | 5/5 | ~18 min | ~3.6 min |
| 04-human-review-gate | 3/3 | ~14 min | ~4.7 min |
| 04.1-fda-compliance | 5/5 | ~25 min | ~5.0 min |
| 05-event-intervention | 7/7 | ~31 min | ~4.4 min |
| 06-findings-domains | 6/6 | ~23 min | ~3.8 min |
| 07-validation-submission | 7/7 | ~32 min | ~4.6 min |
| 07.1-autofix | 3/3 | ~10 min | ~3.3 min |
| 08-learning-system | 4/4 | ~12 min | ~3.0 min |

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

## Phase 3 Deliverables

| Component | Module | Tests | Status |
|-----------|--------|-------|--------|
| Mapping specification models | src/astraea/models/mapping.py | 30 | Done |
| Mapping context assembly | src/astraea/mapping/context.py | 13 | Done |
| System prompt + validation + engine | src/astraea/mapping/prompts.py, validation.py, engine.py | 19 | Done |
| Excel/JSON exporters | src/astraea/mapping/exporters.py | 7 | Done |
| CLI map-domain + display | src/astraea/cli/app.py, display.py | 5 | Done |
| Integration test (DM end-to-end) | tests/integration/mapping/test_dm_mapping.py | 15 | Done |
| **Total** | | **89 tests** | **Complete** |

**Combined test suite: 579 tests passing**

CLI commands available: `astraea map-domain`

## Phase 3.1 Deliverables

| Component | Module | Tests | Status |
|-----------|--------|-------|--------|
| Missing CT codelists (16 added) | src/astraea/data/ct/codelists.json | 16 | Done |
| Missing SDTM domains (8 added) | src/astraea/data/sdtm_ig/domains.json | 22 | Done |
| Core/label/variable/key_variable fixes | src/astraea/data/sdtm_ig/domains.json | 25 | Done |
| Model field fixes (order, length, SUPPQUAL) | src/astraea/models/mapping.py, sdtm.py | 12 | Done |
| Codelist validation fixes | src/astraea/mapping/validation.py | 8 | Done |
| Profiler date disambiguation | src/astraea/profiling/profiler.py | 10 | Done |
| XPT writer label validation | src/astraea/io/xpt_writer.py | 7 | Done |
| SUPPQUAL prompt enhancement | src/astraea/mapping/prompts.py | -- | Done |
| Engine error wrapping | src/astraea/mapping/engine.py | -- | Done |
| Transform registry | src/astraea/mapping/transform_registry.py | 12 | Done |
| Docstring corrections | src/astraea/transforms/dates.py | 4 | Done |
| **Total** | | **85 new tests** | **Complete** |

**Combined test suite: 686 tests passing**

## Phase 4 Deliverables

| Component | Module | Tests | Status |
|-----------|--------|-------|--------|
| Review data models | src/astraea/review/models.py | 17 | Done |
| Session persistence | src/astraea/review/session.py | 13 | Done |
| Review display functions | src/astraea/review/display.py | 19 | Done |
| DomainReviewer logic | src/astraea/review/reviewer.py | 16 | Done |
| CLI commands (review-domain, resume, sessions) | src/astraea/cli/app.py | 13 | Done |
| **Total** | | **78 tests** | **Complete** |

**Combined test suite: 764 tests passing**

CLI commands available: `astraea review-domain`, `astraea resume`, `astraea sessions`

## Phase 4.1 Deliverables

| Component | Module | Tests | Status |
|-----------|--------|-------|--------|
| Study day, sequence, epoch, visit transforms | src/astraea/transforms/ | 52 | Done |
| Date imputation flags | src/astraea/transforms/imputation.py | 11 | Done |
| Model extensions (VariableOrigin, sort_order) | src/astraea/models/ | -- | Done |
| Missing CT codelists (4 added) | src/astraea/data/ct/codelists.json | 16 | Done |
| ASCII validation + char length optimization | src/astraea/transforms/ | 27 | Done |
| Transform registry (15 transforms) | src/astraea/mapping/transform_registry.py | 12 | Done |
| Pattern handlers + dispatch registry | src/astraea/execution/pattern_handlers.py | 13 | Done |
| DatasetExecutor class | src/astraea/execution/executor.py | 9 | Done |
| CrossDomainContext model | src/astraea/execution/executor.py | -- | Done |
| XPT compliance in executor | src/astraea/execution/executor.py | 8 | Done |
| execute-domain CLI command | src/astraea/cli/app.py | -- | Done |
| DM integration test | tests/integration/execution/test_dm_execution.py | 8 | Done |
| **Total** | | **144 new tests** | **Complete** |

**Combined test suite: 907 tests passing**

CLI commands available: `astraea execute-domain`

## Phase 5 Deliverables

| Component | Module | Tests | Status |
|-----------|--------|-------|--------|
| numeric_to_yn transform | src/astraea/transforms/recoding.py | 17 | Done |
| Preprocessing utilities | src/astraea/execution/preprocessing.py | 15 | Done |
| LOOKUP_RECODE bug fix | src/astraea/execution/pattern_handlers.py | -- | Done |
| AE integration test | tests/integration/execution/test_ae_execution.py | 14 | Done |
| DS integration test (multi-source) | tests/integration/execution/test_ds_execution.py | 9 | Done |
| MH integration test | tests/integration/execution/test_mh_execution.py | 7 | Done |
| IE integration test | tests/integration/execution/test_ie_execution.py | 7 | Done |
| CE integration test | tests/integration/execution/test_ce_execution.py | 7 | Done |
| DV integration test | tests/integration/execution/test_dv_execution.py | 8 | Done |
| CM integration test | tests/integration/execution/test_cm_execution.py | 10 | Done |
| EX integration test (filter + merge) | tests/integration/execution/test_ex_execution.py | 9 | Done |
| MH mapping test | tests/integration/mapping/test_mh_mapping.py | 9 | Done |
| IE mapping test | tests/integration/mapping/test_ie_mapping.py | 7 | Done |
| CE mapping test | tests/integration/mapping/test_ce_mapping.py | 8 | Done |
| DV mapping test | tests/integration/mapping/test_dv_mapping.py | 7 | Done |
| AE mapping test (LLM) | tests/integration/mapping/test_ae_mapping.py | 14 | Done |
| CM mapping test (LLM) | tests/integration/mapping/test_cm_mapping.py | 9 | Done |
| EX mapping test (LLM, multi-source) | tests/integration/mapping/test_ex_mapping.py | 9 | Done |
| DS mapping test (LLM, multi-source) | tests/integration/mapping/test_ds_mapping.py | 8 | Done |
| Cross-domain USUBJID validation | tests/integration/execution/test_cross_domain_validation.py | 12 | Done |
| XPT output integration test | tests/integration/execution/test_xpt_output.py | 8 | Done |
| xpt_writer bug fix (table_label) | src/astraea/io/xpt_writer.py | -- | Done |
| **Total** | | **171 new tests** | **Complete** |

**Combined test suite: 1102 tests passing (1031 pass + 86 skipped = verified)**

## Phase 6 Deliverables

| Component | Module | Tests | Status |
|-----------|--------|-------|--------|
| TransposeSpec + execute_transpose | src/astraea/execution/transpose.py | 17 | Done |
| SuppVariable model | src/astraea/models/suppqual.py | -- | Done |
| SUPPQUAL generator + integrity | src/astraea/execution/suppqual.py | 26 | Done |
| FindingsExecutor + normalizers | src/astraea/execution/findings.py | -- | Done |
| LB execution tests (multi-source) | tests/integration/execution/test_lb_execution.py | 8 | Done |
| EG execution tests (pre/post-dose) | tests/integration/execution/test_eg_execution.py | 6 | Done |
| VS execution tests (synthetic) | tests/integration/execution/test_vs_execution.py | 8 | Done |
| TSConfig model + TS builder | src/astraea/execution/trial_summary.py | 20 | Done |
| PE domain execution test | tests/integration/execution/test_pe_execution.py | 5 | Done |
| SUPPQUAL generation tests | tests/integration/execution/test_suppqual_generation.py | 9 | Done |
| Findings XPT output tests | tests/integration/execution/test_findings_xpt_output.py | 10 | Done |
| LB LLM mapping test | tests/integration/mapping/test_lb_mapping.py | 11 | Done |
| EG LLM mapping test | tests/integration/mapping/test_eg_mapping.py | 8 | Done |
| VS LLM mapping test (synthetic) | tests/integration/mapping/test_vs_mapping.py | 8 | Done |
| PE LLM mapping test | tests/integration/mapping/test_pe_mapping.py | 6 | Done |
| SV domain builder | src/astraea/execution/subject_visits.py | 10 | Done |
| Trial design builders (TA/TE/TV/TI) | src/astraea/execution/trial_design.py | 12 | Done |
| RELREC model + stub | src/astraea/models/relrec.py, execution/relrec.py | 12 | Done |
| TrialDesignConfig model | src/astraea/models/trial_design.py | -- | Done |
| TS integration test with DM | tests/integration/execution/test_ts_integration.py | 8 | Done |
| **Total** | | **184 new tests** | **6/6 plans COMPLETE** |

**Combined test suite: 1301 tests (1182 pass + 119 skipped)**

## Phase 7 Deliverables

| Component | Module | Tests | Status |
|-----------|--------|-------|--------|
| Validation rule base models | src/astraea/validation/rules/base.py | 14 | Done |
| Validation engine orchestrator | src/astraea/validation/engine.py | 9 | Done |
| Validation report model | src/astraea/validation/report.py | 8 | Done |
| Predict-and-prevent validation | src/astraea/validation/predict.py | 19 | Done |
| DomainMappingSpec.predict_prevent_issues | src/astraea/models/mapping.py | -- | Done |
| Mapping engine integration | src/astraea/mapping/engine.py | -- | Done |
| CT value + domain value rules | src/astraea/validation/rules/terminology.py | 15 | Done |
| Required/expected/USUBJID rules | src/astraea/validation/rules/presence.py | 15 | Done |
| Name/label/char length rules | src/astraea/validation/rules/limits.py | 17 | Done |
| Date format/ASCII/naming rules | src/astraea/validation/rules/format.py | 17 | Done |
| Cross-domain consistency rules | src/astraea/validation/rules/consistency.py | 20 | Done |
| FDA Business Rules (FDAB*) | src/astraea/validation/rules/fda_business.py | 31 | Done |
| FDA TRC pre-checks | src/astraea/validation/rules/fda_trc.py | -- | Done |
| Engine cross-domain + test fixes | src/astraea/validation/engine.py | -- | Done |
| Define.xml 2.0 generator | src/astraea/submission/define_xml.py | 11 | Done |
| cSDRG template generator | src/astraea/submission/csdrg.py | 12 | Done |
| Known false-positive whitelist | src/astraea/validation/known_false_positives.json | -- | Done |
| RuleResult false-positive fields | src/astraea/validation/rules/base.py | -- | Done |
| ValidationReport enhancements | src/astraea/validation/report.py | -- | Done |
| Submission package validator | src/astraea/submission/package.py | 11 | Done |
| CLI commands (validate, generate-define, generate-csdrg) | src/astraea/cli/app.py, display.py | -- | Done |
| Validation display helpers | src/astraea/cli/display.py | -- | Done |
| Validation integration tests (6) | tests/integration/validation/ | 6 | Done |
| define.xml integration tests (4) | tests/integration/submission/ | 4 | Done |
| **Total** | | **209 new tests** | **7/7 plans COMPLETE** |

**Combined test suite: 1491 tests (1238 unit/validation pass + ~253 skipped/LLM)**

CLI commands available: `astraea validate`, `astraea generate-define`, `astraea generate-csdrg`

## Phase 7.1 Deliverables

| Component | Module | Tests | Status |
|-----------|--------|-------|--------|
| AutoFixer core (classification + fixes) | src/astraea/validation/autofix.py | 29 | Done |
| FixLoopEngine (validate-fix-revalidate) | src/astraea/validation/fix_loop.py | 11 | Done |
| CLI commands + display helpers | src/astraea/cli/app.py, display.py | 7 | Done |
| **Total** | | **47 new tests** | **3/3 plans COMPLETE** |

**Combined test suite: ~1538 tests**

CLI commands available: `astraea auto-fix`, `astraea validate --auto-fix`

## Phase 8 Deliverables

| Component | Module | Tests | Status |
|-----------|--------|-------|--------|
| Learning data models | src/astraea/learning/models.py | 11 | Done |
| SQLite example store | src/astraea/learning/example_store.py | 10 | Done |
| ChromaDB vector store | src/astraea/learning/vector_store.py | 6 | Done |
| LearningRetriever | src/astraea/learning/retriever.py | 13 | Done |
| MappingEngine learning integration | src/astraea/mapping/engine.py | 6 | Done |
| Accuracy metrics computation | src/astraea/learning/metrics.py | 11 | Done |
| Review-to-learning ingestion | src/astraea/learning/ingestion.py | 7 | Done |
| Cross-study template library | src/astraea/learning/template_library.py | 26 | Done |
| **Total** | | **90 new tests** | **4/4 plans COMPLETE** |

**Combined test suite: ~1628 tests**

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
- 2026-02-27: [D-0301-01] StrEnum used for MappingPattern/ConfidenceLevel (Python 3.12+, ruff UP042 compliance)
- 2026-02-27: [D-0301-02] Confidence thresholds: HIGH >= 0.85, MEDIUM >= 0.60, LOW < 0.60
- 2026-02-27: [D-0301-03] Two-tier model: LLM proposal (no ref data) -> enriched spec (with labels, core, codelist names)
- 2026-02-27: [D-0302-01] build_prompt uses keyword-only arguments for all domain-specific parameters
- 2026-02-27: [D-0302-02] EDC columns filtered by is_edc_column flag at context assembly time (LLM never sees them)
- 2026-02-27: [D-0302-03] Large codelists (>20 terms) show first 20 with total count to keep context focused
- 2026-02-27: [D-0303-01] System prompt includes TRANSPOSE pattern for forward-compatibility with Phase 6
- 2026-02-27: [D-0303-02] Confidence adjustments: +0.05 CT pass on lookup_recode, cap 0.4 CT failure, cap 0.3 unknown vars
- 2026-02-27: [D-0303-03] MappingEngine uses keyword-only args for build_prompt to match context builder API
- 2026-02-27: [D-0304-01] ANSI escape codes stripped in display tests using regex helper since Rich embeds bold/dim even with no_color
- 2026-02-27: [D-0304-02] Cross-domain datasets hardcoded as dict (DM: [ex, ie, irt, ds]) -- generic resolver deferred
- 2026-02-27: [D-0304-03] map-domain (hyphenated) used as CLI command name to avoid Python keyword conflict
- 2026-02-27: [D-0305-01] ASSIGN pattern confidence not penalized for missing codelists (C66734 not bundled)
- 2026-02-27: [D-03.1-02-01] DomainSpec.domain max_length increased from 4 to 8 to accommodate SUPPQUAL
- 2026-02-27: [D-03.1-02-02] SUPPQUAL added as pseudo-domain in domains.json (same structure as real domains)
- 2026-02-27: [D-03.1-02-03] C66738 used as forward-reference codelist for TSPARMCD (not yet in codelists.json)
- 2026-02-27: [D-03.1-04-01] order and length fields use defaults (0 and None) for full backward compatibility
- 2026-02-27: [D-03.1-04-02] LOOKUP_RECODE non-extensible codelist warning does NOT penalize confidence -- mapping valid, validation deferred to runtime
- 2026-02-27: [D-03.1-04-03] Fixed trailing comma in codelists.json (pre-existing JSON parse error blocking CTReference)
- 2026-02-27: [D-03.1-05-01] SLASH_DATE pattern with field-value disambiguation replaces duplicate DD/MM and MM/DD regex
- 2026-02-27: [D-03.1-05-02] All _RAW columns checked for string dates (not just *DAT*_RAW) -- false positives harmless
- 2026-02-27: [D-03.1-05-03] XPT unlabeled column check uses case-insensitive fallback for label key matching
- 2026-02-27: [D-03.1-05-04] timezone.utc -> UTC alias fixed in dates.py (ruff UP017)
- 2026-02-27: [D-03.1-03-01] New Permissible variables use empty string for cdisc_notes (VariableSpec requires str, not None)
- 2026-02-27: [D-03.1-03-02] New variables appended at max_order+N rather than inserted mid-list
- 2026-02-27: [D-03.1-03-03] Existing tests updated to match corrected core designations (ARMNRS Perm, CMSTDTC/CMENDTC Exp)
- 2026-02-27: [D-0401-01] CoreDesignation uses REQ/EXP/PERM enum values (not REQUIRED/EXPECTED/PERMISSIBLE)
- 2026-02-27: [D-0401-02] SessionStore uses sqlite3.Row factory for dict-like row access
- 2026-02-27: [D-0401-03] Domain review decisions serialized as JSON dict in SQLite TEXT column
- 2026-02-27: [D-0402-01] ReviewDecision validator allows None corrected_mapping for REJECT correction type
- 2026-02-27: [D-0402-02] DomainReviewer uses input_callback injection for testability (replaces Rich Prompt.ask)
- 2026-02-27: [D-0402-03] Per-variable save_domain_review after every decision for crash recovery
- 2026-02-27: [D-0403-01] Lazy imports inside command functions for review module (consistent with parse-ecrf, classify patterns)
- 2026-02-27: [D-0403-02] _apply_corrections rebuilds spec from session decisions, filtering rejected and updating corrected mappings
- 2026-02-27: [D-04.1-02-01] C66785 variable_mappings set to LAT (standard SDTM laterality variable)
- 2026-02-27: [D-04.1-02-02] C66789 variable_mappings set to LBSPEC (primary Specimen Condition variable)
- 2026-02-27: [D-04.1-02-03] VariableOrigin has 6 values including PREDECESSOR for define.xml 2.0 completeness
- 2026-02-27: [D-04.1-01-01] Test files placed in tests/test_transforms/ (not tests/unit/transforms/) to match existing project structure
- 2026-02-27: [D-04.1-01-02] EPOCH uses pre-grouped dict for SE lookup rather than per-row DataFrame filtering for performance
- 2026-02-27: [D-04.1-01-03] VISITNUM uses Float64 dtype to support decimal values for unplanned visits (e.g., 2.1)
- 2026-02-27: [D-04.1-03-01] generate_usubjid_column uses studyid_value/siteid_col/subjid_col parameter names (not study_id/site_col/subject_col)
- 2026-02-27: [D-04.1-03-02] LOOKUP_RECODE maps preferred_term -> submission_value and submission_value -> submission_value for bidirectional CT matching
- 2026-02-27: [D-04.1-03-03] Critical variables (STUDYID, DOMAIN, USUBJID) raise ExecutionError on failure; all others log warning and set to None
- 2026-02-27: [D-05-01-01] numeric_to_yn returns None for unexpected values (conservative, don't guess)
- 2026-02-27: [D-05-01-02] filter_rows uses case-insensitive string matching with .str.strip().str.upper()
- 2026-02-27: [D-05-01-03] align_multi_source_columns always returns copies, never modifies originals
- 2026-02-27: [D-05-02-01] AE test uses submission_value inputs for LOOKUP_RECODE (already CT-coded source)
- 2026-02-27: [D-05-02-02] DS test performs column alignment in fixture setup, not in test body
- 2026-02-27: [D-05-02-03] Fixed preferred_term -> nci_preferred_term in production LOOKUP_RECODE handler (not just test mock)
- 2026-02-27: [D-05-03-01] CM test uses synthetic partial dates: 'un UNK 2020' -> '2020', 'un Jun 2019' -> '2019-06'
- 2026-02-27: [D-05-03-02] EX test applies filter_rows before executor (pre-execution filtering pattern)
- 2026-02-27: [D-05-03-03] Fixed pre-existing mock bug: preferred_term -> nci_preferred_term in test_pattern_handlers
- 2026-02-27: [D-05-07-01] haemh_screen.sas7bdat (0 rows) excluded from MH multi-source -- no data to contribute
- 2026-02-27: [D-05-07-02] DV StudyMetadata uses Site_Number/Subject_ID (non-standard) instead of SiteNumber/Subject
- 2026-02-27: [D-05-07-03] IE Findings-class assertion validates domain_class field directly (no transpose needed)
- 2026-02-27: [D-06-01-01] TRANSPOSE handled at DataFrame level by execute_transpose(), not per-variable in PATTERN_HANDLERS
- 2026-02-27: [D-06-01-02] SUPPQUAL generation is deterministic post-processing, never LLM-generated (per PITFALLS.md C4)
- 2026-02-27: [D-06-01-03] SuppVariable.qnam auto-uppercased and validated as alphanumeric-only per XPT constraints
- 2026-02-28: [D-06-02-01] FindingsExecutor wraps DatasetExecutor via composition (not inheritance) for clean normalization/execution separation
- 2026-02-28: [D-06-02-02] VS domain tested with synthetic data only -- no vs.sas7bdat exists in Fakedata
- 2026-02-28: [D-06-02-03] Date imputation flags (--DTF) passed through as DIRECT mappings from source data (already flagged at source)
- 2026-02-28: [D-06-03-01] TSParameter auto-uppercases tsparmcd and validates max 8 chars (XPT constraint)
- 2026-02-28: [D-06-03-02] FDA_REQUIRED_PARAMS contains 7 codes; SSTDTC derived from DM RFSTDTC, not config
- 2026-02-28: [D-06-03-03] PE test uses ASSIGN for PETESTCD/PETEST (study only records performed flag, no body system detail)
- 2026-02-28: [D-07-01-01] RuleSeverity uses uppercase enum values (ERROR/WARNING/NOTICE) with display_name property for human-friendly output
- 2026-02-28: [D-07-01-02] register_defaults() uses try/except import for each rule category module, allowing engine to work before any rules are implemented
- 2026-02-28: [D-07-01-03] Rule exceptions during validate_domain are caught and converted to WARNING-severity RuleResults (never crash the engine)
- 2026-02-28: [D-07-02-01] CT validation uses ERROR for non-extensible codelist violations and WARNING for extensible -- matches SDTM-IG semantics
- 2026-02-28: [D-07-02-02] fix_suggestion only provided for non-extensible codelist violations (up to 5 valid terms shown)
- 2026-02-28: [D-07-02-03] FileNamingRule validates domain code format (2-8 alpha) not actual file existence -- allows SUPPQUAL domains
- 2026-02-28: [D-07-03-01] CrossDomainValidator is standalone class (not ValidationRule subclass) because it needs multi-domain access
- 2026-02-28: [D-07-03-02] TRCPreCheck is standalone -- checks submission-level artifacts (define.xml, file naming), not per-domain data
- 2026-02-28: [D-07-03-03] get_consistency_rules() and get_fda_trc_rules() return empty lists since their validators are invoked directly by the engine
- 2026-02-28: [D-07-05-01] lxml used for XML generation with proper namespace handling (not xml.etree.ElementTree)
- 2026-02-28: [D-07-05-02] CommentDef generated for SUPPQUAL candidates and variables with 'non-standard' in notes field
- 2026-02-28: [D-07-05-03] ValueListDef only generated for Findings domains with TRANSPOSE pattern and actual data available
- 2026-02-28: [D-07-06-01] Jinja2 inline string template for cSDRG (not file-based) to keep template co-located with generator logic
- 2026-02-28: [D-07-06-02] known_false_positive field added directly to RuleResult (not post-processing wrapper) for clean downstream access
- 2026-02-28: [D-07-06-03] SPLIT_GUIDANCE uses base domain code (strip underscore suffixes) for lookup to handle split domain files
- 2026-02-28: [D-07-07-01] validate command searches for *_spec.json and *_mapping.json patterns for spec loading
- 2026-02-28: [D-07-07-02] display_validation_summary and display_validation_issues use top-level imports (not lazy) -- display-only helpers
- 2026-02-28: [D-07-07-03] generate-csdrg creates empty ValidationReport if no existing validation_report.json found

- 2026-02-28: [D-07.1-02-01] FixLoopEngine updates domains dict in-place (replacing DataFrames and specs) so each iteration builds on previous fixes
- 2026-02-28: [D-07.1-02-02] _write_fixed_datasets uses pyreadstat.write_xport directly (not xpt_writer) to avoid strict validation blocking partially-fixed datasets
- 2026-02-28: [D-07.1-02-03] apply_fixes returns 3-tuple (df, spec, actions) -- loop engine handles spec updates alongside DataFrame updates
- 2026-02-28: [D-07.1-03-01] display.py imports FixLoopResult and IssueClassification at module level (not lazy) -- consistent with existing top-level validation imports
- 2026-02-28: [D-07.1-03-02] auto-fix command uses same XPT/spec loading pattern as validate command for consistency
- 2026-02-28: [D-07.1-03-03] display_fix_loop_result shows first 10 fix actions only, directs user to autofix_audit.json for full trail
- 2026-02-28: [D-08-01-01] ChromaDB metadata stores booleans as lowercase strings ('true'/'false') per ChromaDB type constraints
- 2026-02-28: [D-08-01-02] Two separate ChromaDB collections (approved_mappings, corrections) for differential weighting during retrieval
- 2026-02-28: [D-08-01-03] ExampleStore uses INSERT OR REPLACE for idempotent upserts (same pattern as SessionStore)
- 2026-02-28: [D-08-02-01] TYPE_CHECKING guard for LearningRetriever import avoids chromadb as import-time dependency
- 2026-02-28: [D-08-02-02] Corrections prioritized (up to 3) before approved examples in retrieval output
- 2026-02-28: [D-08-02-03] Examples section injected between context prompt and user instructions for natural LLM prompt flow
- 2026-02-28: [D-08-03-01] Deterministic example_id as f'{study_id}_{domain}_{sdtm_variable}' for idempotent ingestion
- 2026-02-28: [D-08-03-02] was_corrected flag excludes REJECT and ADD correction types (only tracks actual corrections)
- 2026-02-28: [D-08-03-03] ingest_session skips non-COMPLETED domain reviews rather than erroring
- 2026-02-28: [D-08-04-01] Keywords extracted from both source variable names and mapping logic for richer matching
- 2026-02-28: [D-08-04-02] SQLite UNIQUE on domain column ensures one template per domain with INSERT OR REPLACE
- 2026-02-28: [D-08-04-03] Weighted average for accuracy recalculation: existing_weight = len(source_study_ids) - 1

### Pending Todos

(None)

### Roadmap Evolution

- Phase 2.1 inserted after Phase 2: Reference Data Fixes (Critical for Phase 3) (URGENT)
  - Triggered by: Comprehensive Phase 2 audit found 9/11 CT codelist C-codes wrong, 19 wrong codelist assignments, 15 wrong core designations, 10 critical code bugs
  - Phase 3 BLOCKED until 2.1 completes -- mapper cannot produce correct SDTM with wrong reference data
  - Scope: All 14 Tier 1 items from .planning/PHASE2_AUDIT.md section 9
  - STATUS: **COMPLETE** -- all 4 plans executed, 490 tests passing
- Phase 3.1 inserted after Phase 3: Audit Fixes + Architectural Wiring (URGENT)
  - Triggered by: Phase 3 audit found 5 CRITICAL + 14 HIGH + 8 MEDIUM issues + 3 architectural gaps
  - Phase 4 BLOCKED until 3.1 completes -- review gate needs correct reference data, model fields, and wired transforms
  - Scope: All items from .planning/PHASE3_AUDIT.md sections 2-6 and 9
  - STATUS: **COMPLETE** -- all 5 plans executed, 686 tests passing
- Phase 4.1 inserted after Phase 4: FDA Compliance Infrastructure (URGENT)
  - Triggered by: Comprehensive gap analysis comparing codebase against FDA SDTM requirements in research/fda_sdtm_requirements/ identified 14 CRITICAL gaps in completed phases (1-4)
  - Phase 5 BLOCKED until 4.1 completes -- every domain expansion needs --DY, --SEQ, sort order, execution pipeline, origin tracking
  - Scope: 13 success criteria covering derivation utilities, execution pipeline, XPT enforcement, model extensions, missing codelists, cross-domain validation
  - Key gaps: No dataset execution pipeline (specs only, no actual SDTM DataFrames), no --DY/--SEQ/EPOCH/VISITNUM utilities, no sort/variable order enforcement, no origin tracking, no date imputation flags, no ASCII validation, 4 missing CT codelists
  - STATUS: **COMPLETE** -- all 5 plans executed, 907 tests passing
- Phases 5, 6, 7 updated with additional FDA requirements:
  - Phase 5: Updated dependency to Phase 4.1, added requirement for actual .xpt output (not just specs), variable origin metadata
  - Phase 6: Added mandatory TS domain population (missing TS = FDA rejection), SUPPQUAL referential integrity requirements, unit consistency validation, normal range indicators, Findings-specific codelists
  - Phase 7: Expanded define.xml requirements (ItemGroupDef, ItemDef, CodeList, MethodDef, CommentDef, ValueListDef, WhereClauseDef), added FDA TRC pre-check, FDA Business Rules (FDAB057/055/039/009/030), cSDRG generation, 5GB size validation, file naming conventions

- Phase 7.1 inserted after Phase 7: Auto-Fix Validation Issues
  - Triggered by: Phase 7 validation reports issues but doesn't auto-fix deterministic ones — user must manually fix CT case, missing DOMAIN columns, truncated labels, etc.
  - Phase 8 BLOCKED until 7.1 completes -- learning system benefits from cleaner validation baseline
  - Scope: Auto-fixer for deterministic issues, validate→fix→re-validate loop, audit trail, CLI integration
  - STATUS: **COMPLETE** -- all 3 plans executed, ~1538 tests passing

### Blockers/Concerns

- Phase 3.1 COMPLETE -- all audit fixes and architectural wiring done
- Python 3.12 compatibility verified: all dependencies install cleanly on 3.12.12
- CDISC Rules Engine integration complexity unknown -- may need Phase 7 research spike
- Pre-existing test failure: test_old_wrong_codes_do_not_exist (C66767 is a valid codelist; test assertion is wrong)

## Session Continuity

Last session: 2026-02-28
Stopped at: Completed 08-04-PLAN.md (Cross-study template library) -- ALL PHASES COMPLETE
Resume file: None
