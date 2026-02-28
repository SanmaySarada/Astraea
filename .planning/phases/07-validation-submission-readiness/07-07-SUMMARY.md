---
phase: 07-validation-submission-readiness
plan: 07
subsystem: cli-integration
tags: [cli, validation, define-xml, csdrg, integration-testing]
depends_on:
  requires: ["07-01", "07-02", "07-03", "07-04", "07-05", "07-06"]
  provides: ["CLI commands for validation and submission artifacts", "End-to-end integration tests"]
  affects: ["Phase 8 - learning loop"]
tech-stack:
  added: []
  patterns: ["CLI command pattern with lazy imports", "Synthetic test data fixtures"]
key-files:
  created:
    - tests/integration/validation/__init__.py
    - tests/integration/validation/test_validation_integration.py
    - tests/integration/submission/__init__.py
    - tests/integration/submission/test_define_xml_integration.py
  modified:
    - src/astraea/cli/app.py
    - src/astraea/cli/display.py
decisions:
  - id: "D-07-07-01"
    description: "validate command searches for *_spec.json and *_mapping.json patterns for spec loading"
  - id: "D-07-07-02"
    description: "display_validation_summary and display_validation_issues use top-level imports (not lazy) since they are display-only helpers"
  - id: "D-07-07-03"
    description: "generate-csdrg creates empty ValidationReport if no existing validation_report.json found"
metrics:
  duration: "~5 min"
  completed: "2026-02-28"
---

# Phase 7 Plan 7: CLI Integration and End-to-End Tests Summary

CLI commands wiring all Phase 7 validation and submission capabilities into user-accessible commands, with integration tests proving end-to-end correctness on synthetic multi-domain data.

## What Was Done

### Task 1: CLI Commands for Validation and Submission Artifacts

Added three new CLI commands to `src/astraea/cli/app.py`:

**`astraea validate <output-dir>`** -- Full validation pipeline:
- Loads .xpt files via pyreadstat
- Loads mapping specs (*_spec.json, *_mapping.json)
- Runs ValidationEngine.validate_all() for per-domain rules
- Runs TRCPreCheck for FDA Technical Rejection Criteria
- Runs package size and file naming checks
- Generates ValidationReport with known false-positive flagging
- Displays Rich summary table and top issues
- Supports --format=markdown and --format=json for export
- Exit code 0 if submission-ready, 1 if not

**`astraea generate-define <output-dir>`** -- define.xml 2.0 generation:
- Loads mapping specs and .xpt files for ValueListDef
- Calls generate_define_xml() with CT reference
- Displays element count panel (ItemGroupDefs, ItemDefs, CodeLists, etc.)

**`astraea generate-csdrg <output-dir>`** -- cSDRG template generation:
- Loads mapping specs and optional validation report
- Generates PHUSE-structured Markdown document

Added two display helpers to `src/astraea/cli/display.py`:
- `display_validation_summary()`: Rich table with severity counts, pass rate, per-domain breakdown
- `display_validation_issues()`: Rich table of top issues sorted by severity, filtered for false positives

### Task 2: Integration Tests

**test_validation_integration.py** -- 6 tests on synthetic 3-domain data (DM, AE, LB):
1. Full pipeline validation catches issues across multiple domains
2. Cross-domain USUBJID orphan detection (AE subject not in DM)
3. TRC pre-check passes when DM/TS/define.xml present
4. TRC pre-check fails when required artifacts missing
5. ValidationReport generation with correct summary statistics
6. Markdown report output with expected headers

**test_define_xml_integration.py** -- 4 tests with realistic specs:
1. Multi-domain define.xml with correct ItemGroupDef/ItemDef/CodeList/MethodDef counts
2. Namespace verification (ODM, def:, xlink:)
3. Findings ValueListDef with WhereClauseDef for 4 test codes
4. OID roundtrip consistency (all ItemRef/MethodOID references resolve)

Synthetic data includes intentional issues:
- AE with orphan USUBJID (TEST-001-001-999 not in DM)
- DM with invalid ETHNIC value (INVALID_ETHNIC not in C66790)
- LB with invalid specimen type (TOTALLY_INVALID_SPECIMEN)
- AE missing AEDECOD (Required variable)

## Decisions Made

| ID | Decision |
|----|----------|
| D-07-07-01 | validate command searches for *_spec.json and *_mapping.json patterns |
| D-07-07-02 | Display helpers use top-level imports (not lazy) -- they are always used when called |
| D-07-07-03 | generate-csdrg creates empty ValidationReport if no existing report found |

## Deviations from Plan

None -- plan executed exactly as written.

## Test Results

- 10 new integration tests (6 validation + 4 define.xml)
- All 1238 tests pass (full suite excluding LLM integration tests)
- Ruff clean on all modified files

## Commits

| Hash | Description |
|------|-------------|
| 833b981 | feat(07-07): add validate, generate-define, generate-csdrg CLI commands |
| 8a75c42 | test(07-07): add validation and define.xml integration tests |

## Next Phase Readiness

Phase 7 is now COMPLETE. All 7 plans executed:
1. Validation engine + rule base models
2. CT/presence/limit/format rules
3. Cross-domain consistency + FDA business rules
4. FDA TRC pre-checks
5. define.xml 2.0 generator
6. cSDRG + package assembly + submission reporting
7. CLI integration + end-to-end tests (this plan)

The system now provides a complete validation and submission readiness pipeline accessible via CLI. Phase 8 (Learning Loop) can proceed.
