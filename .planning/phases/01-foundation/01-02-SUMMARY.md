---
phase: 01-foundation
plan: 02
subsystem: data-ingestion
tags: [pyreadstat, sas-reader, profiling, edc-detection, date-detection]
dependency-graph:
  requires: [01-01]
  provides: [sas-reader, dataset-profiler, edc-column-detection, date-format-detection]
  affects: [01-03, 01-04, 01-05, 02-01]
tech-stack:
  added: []
  patterns: [pyreadstat-disable-datetime, frozenset-lookup, regex-date-detection]
key-files:
  created:
    - src/astraea/io/sas_reader.py
    - src/astraea/profiling/profiler.py
    - tests/test_io/test_sas_reader.py
    - tests/test_profiling/test_profiler.py
  modified:
    - src/astraea/io/__init__.py
    - src/astraea/profiling/__init__.py
decisions:
  - id: D-0102-01
    description: "pyreadstat labels can be None (not just missing from dict) -- use `or ''` instead of `.get(key, '')`"
  - id: D-0102-02
    description: "EDC column matching uses frozenset of 25 known column names with lowercase comparison"
  - id: D-0102-03
    description: "String date detection limited to _RAW columns containing DAT in the name -- avoids false positives on other _RAW columns"
metrics:
  duration: "4 minutes"
  completed: "2026-02-26"
---

# Phase 1 Plan 2: SAS Reader and Dataset Profiler Summary

**One-liner:** pyreadstat-based SAS reader with disable_datetime_conversion=True and dataset profiler detecting 25 EDC system columns plus date variables from both SAS format metadata and string pattern analysis.

## What Was Done

### Task 1: SAS Reader with Metadata Extraction
- Implemented `read_sas_with_metadata()` using pyreadstat.read_sas7bdat with `disable_datetime_conversion=True` to preserve raw numeric dates
- Extracts variable names, labels, SAS formats, dtypes (character via "$" prefix, else numeric), encoding, row/column counts
- Handles None labels from pyreadstat gracefully (some files have None values in column_names_to_labels dict)
- Implemented `read_all_sas_files()` to read entire Fakedata/ directory (36 files), keyed by filename stem
- Both functions accept str or Path arguments
- 20 integration tests all passing against Fakedata/

### Task 2: Dataset Profiler with EDC Column and Date Detection
- Implemented `profile_dataset()` producing DatasetProfile with per-variable statistics
- Per variable: n_total, n_missing, n_unique, missing_pct, sample_values (first 10 unique), top_values (top 5 for variables with <=100 unique values)
- EDC system column detection: 25 known Rave/EDC column names matched case-insensitively via frozenset lookup
- Date detection from SAS format: recognizes DATETIME, DATE, TIME, and variant formats
- String date detection: for *_RAW columns containing "DAT", uses regex to identify DD Mon YYYY, YYYY-MM-DD, DD-Mon-YYYY, DD/MM/YYYY patterns
- `detect_date_format()` helper exposed for reuse
- 25 integration tests all passing against Fakedata/dm.sas7bdat and ae.sas7bdat

### Verification Results
```
pytest tests/test_io/ tests/test_profiling/ -v     -- 45/45 passed (2.14s)
read_sas_with_metadata('Fakedata/dm.sas7bdat')     -- 3 rows, 61 cols
profile_dataset(dm)                                  -- 25 EDC columns, 6 date variables
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] pyreadstat returns None labels in column_names_to_labels dict**
- **Found during:** Task 1 (read_all_sas_files failed on dv.sas7bdat)
- **Issue:** Some SAS files have None as the label value in the dict (key present, value is None). Using `.get(key, "")` returns None, not "".
- **Fix:** Changed to `meta.column_names_to_labels.get(col_name) or ""` which handles both missing keys and None values
- **Files modified:** src/astraea/io/sas_reader.py
- **Commit:** 18dc1e8

## Decisions Made

1. **None-safe label extraction (D-0102-01):** pyreadstat's `column_names_to_labels` dict can have None values (not just missing keys). Used `or ""` pattern instead of `.get(key, default)`.
2. **EDC column set (D-0102-02):** Hardcoded 25 known Rave/EDC system column names. Matches case-insensitively. This set covers all EDC columns observed in the Fakedata/ sample files.
3. **String date column heuristic (D-0102-03):** Only check `_RAW` columns containing "DAT" for string date patterns. This avoids false positives on columns like `AEACNOCM_RAW` which contain "0"/"1" values, not dates.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `18dc1e8` | SAS reader with metadata extraction (20 tests) |
| 2 | `eccc3eb` | Dataset profiler with EDC and date detection (25 tests) |

## Next Phase Readiness

All downstream plans can now:
- `from astraea.io import read_sas_with_metadata, read_all_sas_files`
- `from astraea.profiling import profile_dataset, detect_date_format`
- Read any .sas7bdat file and get (DataFrame, DatasetMetadata) tuple
- Profile any dataset for variable statistics, EDC column flags, and date detection
