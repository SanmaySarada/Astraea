# Phase 7 Plan 1: Validation Framework Foundation Summary

**One-liner:** Pydantic-based validation rule engine with severity/category enums, rule registry, domain/study validation, and structured reports with submission readiness scoring.

## What Was Built

### Validation Rule Base Models (`src/astraea/validation/rules/base.py`)
- `RuleSeverity(StrEnum)`: ERROR, WARNING, NOTICE with display_name property
- `RuleCategory(StrEnum)`: TERMINOLOGY, PRESENCE, CONSISTENCY, LIMIT, FORMAT, FDA_BUSINESS, FDA_TRC
- `RuleResult(BaseModel)`: Structured finding with rule_id, severity, domain, variable, message, affected_count, fix_suggestion, p21_equivalent
- `ValidationRule(BaseModel)`: Abstract base with `evaluate()` accepting domain, DataFrame, DomainMappingSpec, SDTMReference, CTReference

### Validation Engine (`src/astraea/validation/engine.py`)
- `ValidationEngine`: Orchestrator with rule registry
- `register()`: Add individual rules
- `register_defaults()`: Try/except import pattern for 7 rule module categories (all gracefully handle missing modules)
- `validate_domain()`: Run all rules against one domain, catch rule exceptions gracefully
- `validate_all()`: Run across dict of {domain: (DataFrame, spec)} pairs
- `filter_results()`: Filter by category, severity, domain (combinable)

### Validation Report (`src/astraea/validation/report.py`)
- `ValidationReport.from_results()`: Computes error/warning/notice counts, pass_rate (% domains with zero errors), submission_ready flag, summary_by_domain, summary_by_category, generated_at timestamp

### Package Exports (`src/astraea/validation/__init__.py`)
- Exports: ValidationEngine, ValidationRule, RuleResult, RuleSeverity, RuleCategory

## Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| test_base_rules.py | 14 | RuleSeverity (3), RuleCategory (2), RuleResult (3), ValidationRule subclass (4), abstract instantiation (1), pass rule (1) |
| test_engine.py | 17 | Engine creation (1), register (1), validate_domain (2), validate_all (1), exception handling (1), filter by category/severity/domain/combined (4), ValidationReport (8) |
| **Total** | **31** | All models, engine, and report |

## Decisions Made

- [D-07-01-01] RuleSeverity uses uppercase enum values (ERROR/WARNING/NOTICE) with display_name property for human-friendly output
- [D-07-01-02] register_defaults() uses try/except import for each rule category module, allowing the engine to work before any rules are implemented
- [D-07-01-03] Rule exceptions during validate_domain are caught and converted to WARNING-severity RuleResults (never crash the engine)

## Deviations from Plan

None -- plan executed exactly as written.

## Files Created

- `src/astraea/validation/__init__.py` (updated)
- `src/astraea/validation/rules/__init__.py`
- `src/astraea/validation/rules/base.py`
- `src/astraea/validation/engine.py`
- `src/astraea/validation/report.py`
- `tests/unit/validation/__init__.py`
- `tests/unit/validation/test_base_rules.py`
- `tests/unit/validation/test_engine.py`

## Commits

| Hash | Message |
|------|---------|
| 3c71444 | feat(07-01): validation rule base models and engine |
| e09016c | test(07-01): ValidationReport model and 31 unit tests |

## Duration

~4 minutes

## Next Phase Readiness

The validation framework is ready for plans 07-02 and 07-03 to register concrete rules (terminology, presence, consistency, limits, format). The register_defaults() pattern means new rule modules just need to export a `get_*_rules()` function returning a list of ValidationRule instances.
