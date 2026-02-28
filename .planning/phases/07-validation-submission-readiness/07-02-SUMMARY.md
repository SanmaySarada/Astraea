---
phase: 07-validation-submission-readiness
plan: 02
subsystem: validation
tags: [validation, terminology, presence, limits, format, xpt, iso8601, ct]
depends_on:
  requires: ["07-01"]
  provides: ["VAL-01 terminology rules", "VAL-02 presence rules", "VAL-04 limit rules", "VAL-05 format rules"]
  affects: ["07-03", "07-04", "07-05"]
tech_stack:
  added: []
  patterns: ["ValidationRule subclass pattern", "get_*_rules() factory pattern"]
key_files:
  created:
    - src/astraea/validation/rules/terminology.py
    - src/astraea/validation/rules/presence.py
    - src/astraea/validation/rules/limits.py
    - src/astraea/validation/rules/format.py
    - tests/unit/validation/test_terminology_rules.py
    - tests/unit/validation/test_presence_rules.py
    - tests/unit/validation/test_limit_format_rules.py
  modified:
    - tests/unit/validation/test_engine.py
decisions:
  - id: "D-07-02-01"
    description: "CT validation uses ERROR for non-extensible codelist violations and WARNING for extensible -- matches SDTM-IG semantics"
  - id: "D-07-02-02"
    description: "fix_suggestion only provided for non-extensible codelist violations (up to 5 valid terms shown)"
  - id: "D-07-02-03"
    description: "FileNamingRule validates domain code format (2-8 alpha) not actual file existence -- allows SUPPQUAL domains"
metrics:
  duration: "~5 min"
  completed: "2026-02-28"
---

# Phase 7 Plan 2: Single-Domain Validation Rules Summary

**One-liner:** 13 concrete validation rules across 4 categories (CT, presence, limits, format) with factory registration into ValidationEngine.

## What Was Done

### Task 1: Terminology and Presence Rules (VAL-01, VAL-02)

**terminology.py** -- 2 rules:
- `CTValueRule` (ASTR-T001): Validates CT codelist values per variable mapping. Uses ERROR severity for non-extensible codelists (exact match required), WARNING for extensible. Provides fix_suggestion with up to 5 valid terms. P21 equivalent: SD0065.
- `DomainValueRule` (ASTR-T002): Checks DOMAIN column value matches expected domain code. Catches both missing column and wrong values.

**presence.py** -- 4 rules:
- `RequiredVariableRule` (ASTR-P001): Checks all REQ variables from SDTM-IG exist as columns. Case-insensitive matching. P21 equivalent: SD0083.
- `ExpectedVariableRule` (ASTR-P002): Warns on missing EXP variables. Not an error but should be documented.
- `NoRecordsRule` (ASTR-P003): Warns on empty datasets (zero rows).
- `USUBJIDPresentRule` (ASTR-P004): Checks USUBJID exists and has zero nulls. Critical for cross-domain linkage.

**Tests:** 30 tests covering valid data, violations, edge cases (nulls, missing columns, unknown domains).

### Task 2: Limit and Format Rules (VAL-04, VAL-05)

**limits.py** -- 4 rules:
- `VariableNameLengthRule` (ASTR-L001): Checks column names <= 8 chars. P21 equivalent: SD0006.
- `VariableLabelLengthRule` (ASTR-L002): Checks labels from spec <= 40 chars.
- `CharacterLengthRule` (ASTR-L003): Checks character column max byte length <= 200.
- `DatasetSizeRule` (ASTR-L004): NOTICE at >100MB, WARNING at >500MB.

**format.py** -- 3 rules:
- `DateFormatRule` (ASTR-F001): Validates --DTC columns match ISO 8601 regex. P21 equivalent: SD0020.
- `ASCIIRule` (ASTR-F002): Uses existing validate_ascii() to find non-ASCII characters. Suggests fix_common_non_ascii().
- `FileNamingRule` (ASTR-F003): Validates domain code is 2-8 alphabetic characters.

**Tests:** 34 tests covering boundary conditions (exactly 8/40 chars), invalid data, numeric columns, null handling.

**Engine integration:** All rules auto-register via get_*_rules() factory functions called by ValidationEngine.register_defaults(). Total registered rules: 18 (13 new + 5 pre-existing FDA rules).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] VariableMapping and DomainMappingSpec constructor fields**
- **Found during:** Task 1
- **Issue:** Test helper _make_mapping used uppercase "HIGH" for confidence_level (enum uses lowercase "high"), missed confidence_rationale field; _make_spec missed 8 required fields (total_variables, required_mapped, etc.)
- **Fix:** Updated test helpers to use correct field values
- **Files modified:** test_terminology_rules.py, test_presence_rules.py

**2. [Rule 1 - Bug] Pre-existing engine tests broken by rule auto-registration**
- **Found during:** Task 2
- **Issue:** test_engine.py tests assumed no default rules existed. With new rules auto-registering, result counts changed.
- **Fix:** Engine tests already updated (detected and fixed by pre-commit or prior edit) to filter by rule_id
- **Files modified:** tests/unit/validation/test_engine.py

## Test Results

- 165 validation tests passing (31 from plan 01 + 64 new from plan 02 + 70 from pre-existing engine/base/consistency/FDA tests)
- All new files pass ruff check

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-07-02-01 | ERROR for non-extensible CT violations, WARNING for extensible | Non-extensible codelists require exact match per SDTM-IG; extensible allow study-specific values |
| D-07-02-02 | fix_suggestion shows up to 5 valid terms for non-extensible only | Extensible codelists accept any value so suggestion is meaningless |
| D-07-02-03 | FileNamingRule validates format not file existence | Rule runs before file write; SUPPQUAL domains (SUPPAE, SUPPDM) must pass |

## Next Phase Readiness

Plan 07-03 (cross-domain consistency rules) can proceed. All single-domain rules are now in place.
