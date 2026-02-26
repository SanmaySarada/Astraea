---
phase: 01-foundation
plan: 04
subsystem: transforms
tags: [date-conversion, iso-8601, usubjid, sdtm, deterministic-transforms]
dependency-graph:
  requires: [01-01]
  provides: [date-conversion-utilities, usubjid-utilities, partial-date-handling]
  affects: [01-05, 02-01, 02-02]
tech-stack:
  added: []
  patterns: [pure-functions, sas-epoch-arithmetic, right-truncation-partial-dates]
key-files:
  created:
    - src/astraea/transforms/dates.py
    - src/astraea/transforms/usubjid.py
    - tests/test_transforms/test_dates.py
    - tests/test_transforms/test_usubjid.py
  modified:
    - src/astraea/transforms/__init__.py
decisions:
  - id: D-0104-01
    description: "Ambiguous slash-separated dates (both fields <= 12) default to DD/MM/YYYY"
  - id: D-0104-02
    description: "extract_usubjid_components with >3 parts joins remainder as subjid (best-effort)"
  - id: D-0104-03
    description: "SAS DATETIME uses UTC timezone internally for arithmetic, output is timezone-naive per SDTM convention"
metrics:
  duration: "4 minutes"
  completed: "2026-02-26"
---

# Phase 1 Plan 4: Date Conversion and USUBJID Utilities Summary

**One-liner:** Deterministic ISO 8601 date converters (SAS DATE/DATETIME/string/partial) and USUBJID generation with cross-domain consistency validation -- 80 tests, zero LLM dependency.

## What Was Done

### Task 1: ISO 8601 Date Conversion (53 tests)

Created `src/astraea/transforms/dates.py` with 5 pure functions:

| Function | Purpose | Key Detail |
|----------|---------|------------|
| `sas_date_to_iso` | SAS DATE (days since 1960-01-01) to ISO 8601 | Returns "YYYY-MM-DD" |
| `sas_datetime_to_iso` | SAS DATETIME (seconds since 1960-01-01) to ISO 8601 | Returns "YYYY-MM-DDTHH:MM:SS"; critical to not confuse with DATE |
| `parse_string_date_to_iso` | String dates (DD Mon YYYY, YYYY-MM-DD, slash formats, partials) | Handles "30 Mar 2022" format from Fakedata _RAW columns |
| `format_partial_iso8601` | Build truncated ISO 8601 from optional components | Per SDTM-IG: no gaps allowed, truncate at first None |
| `detect_date_format` | Identify date format from sample values | Used by profiler to annotate date columns |

Critical verification: `sas_datetime_to_iso(1964217600.0)` correctly produces `2022-03-30T00:00:00` (not year 5000+ from DATE/DATETIME confusion).

### Task 2: USUBJID Generation and Validation (27 tests)

Created `src/astraea/transforms/usubjid.py` with 4 functions:

| Function | Purpose | Key Detail |
|----------|---------|------------|
| `generate_usubjid` | STUDYID + SITEID + SUBJID concatenation | Strips whitespace, configurable delimiter |
| `extract_usubjid_components` | Parse USUBJID back to components | Best-effort for non-standard formats with warnings |
| `generate_usubjid_column` | DataFrame-level USUBJID generation | Supports constant or column-based STUDYID |
| `validate_usubjid_consistency` | Cross-domain validation | Checks orphans, duplicates in DM, format consistency |

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

1. **Ambiguous slash dates**: When both fields <= 12 (e.g., "05/06/2022"), default to DD/MM/YYYY with a debug log. This is the more common format in international clinical trials.
2. **USUBJID >3 parts**: When a USUBJID has more than 2 delimiters, first part = studyid, second = siteid, remainder joined = subjid. Logs a warning.
3. **Timezone handling**: SAS DATETIME arithmetic uses UTC internally but output is timezone-naive per SDTM convention (no "Z" suffix).

## Verification Results

```
pytest tests/test_transforms/ -v                             -- 80/80 passed
sas_datetime_to_iso(1964217600.0)                            -- "2022-03-30T00:00:00"
parse_string_date_to_iso("30 Mar 2022")                      -- "2022-03-30"
format_partial_iso8601(2023, 3, None)                         -- "2023-03"
generate_usubjid("301", "04401", "01")                        -- "301-04401-01"
```

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `ed82d52` | ISO 8601 date conversion utilities with 53 tests |
| 2 | `27b881d` | USUBJID generation and cross-domain validation with 27 tests |

## Next Phase Readiness

All downstream plans can now:
- `from astraea.transforms.dates import sas_datetime_to_iso, parse_string_date_to_iso, format_partial_iso8601`
- `from astraea.transforms.usubjid import generate_usubjid, validate_usubjid_consistency`
- All functions are pure with no external dependencies beyond pandas (for DataFrame operations)
