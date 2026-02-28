---
phase: 10-tech-debt
plan: 01
subsystem: code-quality
tags: [ruff, mypy, type-safety, lint, StrEnum, openpyxl]
dependency_graph:
  requires: []
  provides: [zero-lint-violations, zero-type-errors, clean-ci-baseline]
  affects: []
tech_stack:
  added: []
  patterns: [StrEnum-for-string-enums, Literal-type-annotations, TYPE_CHECKING-guards]
key_files:
  created: []
  modified:
    - src/astraea/models/sdtm.py
    - src/astraea/models/mapping.py
    - src/astraea/io/sas_reader.py
    - src/astraea/llm/client.py
    - src/astraea/mapping/exporters.py
    - src/astraea/mapping/engine.py
    - src/astraea/mapping/validation.py
    - src/astraea/mapping/transform_registry.py
    - src/astraea/classification/classifier.py
    - src/astraea/cli/app.py
    - src/astraea/cli/display.py
    - src/astraea/execution/executor.py
    - src/astraea/execution/pattern_handlers.py
    - src/astraea/parsing/pdf_extractor.py
    - src/astraea/validation/predict.py
    - src/astraea/validation/rules/fda_business.py
    - src/astraea/validation/rules/fda_trc.py
    - src/astraea/validation/rules/consistency.py
    - src/astraea/learning/retriever.py
    - src/astraea/learning/vector_store.py
    - src/astraea/learning/metrics.py
    - src/astraea/learning/example_store.py
    - src/astraea/learning/ingestion.py
    - src/astraea/learning/template_library.py
    - src/astraea/learning/dspy_optimizer.py
    - src/astraea/review/display.py
    - src/astraea/review/session.py
    - src/astraea/submission/package.py
    - tests/unit/validation/test_fda_rules.py
    - tests/integration/validation/test_validation_integration.py
    - tests/unit/execution/test_trial_design.py
    - tests/unit/learning/test_dspy_optimizer.py
    - tests/test_parsing/test_ecrf_parser.py
    - tests/unit/learning/test_retriever.py
decisions:
  - id: D-10-01-01
    description: "exporters.py fully rewritten with proper openpyxl Worksheet type annotations instead of 30+ type:ignore comments"
  - id: D-10-01-02
    description: "fda_business.py changed get_codelist -> lookup_codelist and fixed dict iteration (codelist.terms keys are submission values)"
  - id: D-10-01-03
    description: "consistency.py and fda_trc.py return types changed from list[object] to list[ValidationRule] for proper type safety"
metrics:
  duration: ~8 minutes
  completed: 2026-02-28
---

# Phase 10 Plan 01: Lint and Type Error Cleanup Summary

**One-liner:** Zero ruff violations and zero mypy errors across 96 source files via StrEnum migration, openpyxl typing, Literal annotations, and 30+ generic type fixes.

## What Was Done

### Task 1: Fix all 139 ruff violations (commit be4bb26)

Used a three-pass strategy:

1. **Auto-fix pass** (`ruff check --fix`): Fixed 44 violations automatically (26 F401 unused imports, 17 I001 unsorted imports, 1 SIM300 Yoda condition).

2. **Manual fix pass**: Fixed 9 remaining non-E501 violations:
   - SIM108: Converted if/else to ternary in sas_reader.py
   - UP042: Changed `DomainClass(str, Enum)` and `CoreDesignation(str, Enum)` to `StrEnum` in sdtm.py
   - B905: Added `strict=True` to zip() in usubjid.py
   - F841: Prefixed unused variable with underscore in test_validation_integration.py
   - B017: Changed `pytest.raises(Exception)` to `pytest.raises(ValueError)` in test_trial_design.py
   - E402: Added `noqa: E402` comments for intentional late imports in test_dspy_optimizer.py

3. **Format pass** (`ruff format`): Fixed all 86 E501 line-length violations, plus 8 manual line breaks for strings too long for the formatter to split.

### Task 2: Fix all 122 mypy type errors (commit 5c25ca5)

Fixed errors across 28 files in these categories:

1. **exporters.py (30+ errors):** Complete rewrite with proper `openpyxl.worksheet.worksheet.Worksheet` type annotations, removing all `# type: ignore[union-attr]` comments.

2. **engine.py (5 errors):** Added `DomainSpec` import via TYPE_CHECKING guard, fixed parameter type from `object` to proper `DomainSpec`.

3. **Bare generic types (~40 errors):** Added type parameters across 20+ files: `dict` -> `dict[str, Any]`, `list` -> `list[Any]`, `Callable` -> `Callable[..., object]`.

4. **Literal type annotations (3 errors):** Added `Literal["numeric", "character"]` in sas_reader.py, `Literal["Char", "Num"]` in mapping/validation.py, `Literal["direct", "merge", "transpose", "mixed"]` in classifier.py.

5. **fda_business.py (2 errors):** Changed `get_codelist` to `lookup_codelist` (matching CTReference API), fixed dict iteration to use `.keys()` instead of iterating values.

6. **Return type fixes (4 errors):** Changed `get_consistency_rules` and `get_fda_trc_rules` from `list[object]` to `list[ValidationRule]`, fixed `results_to_issue_dicts` return type, updated `predict_prevent_issues` model field.

7. **cli/app.py (4 errors):** Fixed invalid `__import__("pandas").DataFrame` annotation, added proper `LearningRetriever` return type, type narrowing for session_id.

8. **llm/client.py (1 error):** Added `# type: ignore[call-overload]` for anthropic SDK kwargs dispatch (SDK overloads don't support `**kwargs` pattern).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed fda_business.py calling non-existent get_codelist method**
- **Found during:** Task 2
- **Issue:** `CTReference` has `lookup_codelist()`, not `get_codelist()`. The original code also iterated `codelist.terms` directly (gets dict keys as strings) but tried `.submission_value` on them.
- **Fix:** Changed to `lookup_codelist()` and `set(codelist.terms.keys())` since dict keys ARE submission values.
- **Files modified:** src/astraea/validation/rules/fda_business.py, tests/unit/validation/test_fda_rules.py
- **Commit:** 5c25ca5

**2. [Rule 1 - Bug] Fixed test mock mismatched with production API**
- **Found during:** Task 2
- **Issue:** Test mock used `get_codelist` and `codelist.terms` as a list of objects with `.submission_value`. After fixing production code, mock needed updating to match real `Codelist.terms` dict structure.
- **Fix:** Updated mock to use `lookup_codelist` and dict-keyed terms.
- **Files modified:** tests/unit/validation/test_fda_rules.py
- **Commit:** 5c25ca5

## Verification Results

| Check | Result |
|-------|--------|
| `ruff check src/ tests/` | All checks passed |
| `ruff format --check src/ tests/` | 231 files already formatted |
| `mypy src/ --ignore-missing-imports` | Success: no issues found in 96 source files |
| `pytest tests/ -x -q` | 1567 passed, 119 skipped |

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | be4bb26 | style(10-01): fix all 139 ruff lint violations |
| 2 | 5c25ca5 | fix(10-01): resolve all 122 mypy type errors across 28 files |
