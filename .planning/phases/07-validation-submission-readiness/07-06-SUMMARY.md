---
phase: 07-validation-submission-readiness
plan: 06
subsystem: submission
tags: [csdrg, package, validation-report, false-positives, fda, submission-readiness]
depends_on: ["07-03"]
provides: ["csdrg-generator", "package-validator", "known-false-positives", "report-markdown"]
affects: ["07-07"]
tech_stack:
  added: ["jinja2>=3.1"]
  patterns: ["jinja2-template-rendering", "json-whitelist-config", "size-validation"]
key_files:
  created:
    - src/astraea/submission/csdrg.py
    - src/astraea/submission/package.py
    - src/astraea/validation/known_false_positives.json
    - tests/unit/submission/test_csdrg.py
    - tests/unit/submission/test_package.py
  modified:
    - src/astraea/validation/report.py
    - src/astraea/validation/rules/base.py
    - src/astraea/submission/__init__.py
    - pyproject.toml
decisions:
  - id: D-07-06-01
    description: "Jinja2 inline string template for cSDRG (not file-based) to keep template co-located with generator logic"
  - id: D-07-06-02
    description: "known_false_positive field added directly to RuleResult (not post-processing wrapper) for clean downstream access"
  - id: D-07-06-03
    description: "SPLIT_GUIDANCE uses base domain code (strip underscore suffixes) for lookup to handle split domain files like lb_chem.xpt"
metrics:
  duration: "~7 minutes"
  completed: "2026-02-28"
  tests_added: 23
---

# Phase 7 Plan 6: cSDRG, Package Assembly, and Submission Reporting Summary

**One-liner:** cSDRG template generator with Jinja2, submission package size validator with domain-specific split guidance, known false-positive whitelist, and Markdown report export.

## What Was Built

### Task 1: cSDRG Template Generator with Known False-Positive Whitelist

**cSDRG Generator** (`src/astraea/submission/csdrg.py`):
- `generate_csdrg()` renders an 8-section PHUSE-structured Markdown document using Jinja2
- Sections: Introduction, Study Description (placeholder), Data Standards, Dataset Overview, Domain-Specific Information, Data Issues, Validation Results Summary, Non-Standard Variables
- Domain-specific sections include mapping pattern breakdown, SUPPQUAL candidates, and missing required variables
- Section 7 includes Known False Positives subsection when flagged results exist
- Pre-processes data into simple dicts for clean template rendering (avoids long Jinja2 lines)

**Known False-Positive Whitelist** (`src/astraea/validation/known_false_positives.json`):
- JSON config with rule_id, domain (nullable), variable (nullable), and reason
- Ships with SD1076/LB/LBSTRESC entry for P21 v2405.2 known issue
- Matching logic: rule_id must match AND (domain null OR matches) AND (variable null OR matches)

**RuleResult Enhancement** (`src/astraea/validation/rules/base.py`):
- Added `known_false_positive: bool = False` field
- Added `known_false_positive_reason: str | None = None` field

**ValidationReport Enhancement** (`src/astraea/validation/report.py`):
- `flag_known_false_positives()` method loads whitelist and flags matching results
- `effective_error_count` / `effective_warning_count` properties exclude flagged results
- `known_false_positive_results` property returns all flagged results
- `from_results()` accepts optional `whitelist_path` and auto-applies default whitelist
- `submission_ready` recalculated after flagging to use effective counts

### Task 2: Submission Package Assembly and Size Check

**Package Utilities** (`src/astraea/submission/package.py`):
- `check_submission_size()` validates total XPT size against 5GB FDA limit
- Per-file check for >1GB with domain-specific split guidance (LB by LBCAT, AE by AESEV, CM by CMCAT, EG by EGTESTCD, VS by VSTESTCD, FA by FATESTCD)
- Generic guidance for unknown domains
- `validate_file_naming()` checks lowercase domain.xpt files exist, flags unexpected files, requires define.xml
- `assemble_package_manifest()` returns file inventory with sizes, domain mapping, and artifact presence flags

**ValidationReport Markdown Export** (`src/astraea/validation/report.py`):
- `to_markdown()` renders full validation report as Markdown
- Includes summary table, per-domain breakdown, per-category breakdown, top 10 issues, known false positives section, and submission readiness assessment
- Uses effective counts (excluding false positives) for summary

## Deviations from Plan

None -- plan executed exactly as written.

## Test Coverage

- 12 tests for cSDRG generation and false-positive flagging
- 11 tests for package size check, file naming, manifest, and report export
- Total: 23 new tests

## Commits

| Hash | Description |
|------|-------------|
| 4f6cfd5 | feat(07-06): add cSDRG template generator and known false-positive whitelist |
| c389a75 | feat(07-06): add submission package assembly and size validation |
