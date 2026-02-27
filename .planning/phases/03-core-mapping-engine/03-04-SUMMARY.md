---
phase: 03-core-mapping-engine
plan: 04
subsystem: mapping-output
tags: [excel, json, cli, rich, export, openpyxl]
depends_on: ["03-03"]
provides: ["mapping-exporters", "cli-map-domain", "mapping-display"]
affects: ["03-05", "04-human-review"]
tech_stack:
  added: []
  patterns: ["conditional-formatting", "source-file-heuristic", "cross-domain-profiling"]
key_files:
  created:
    - src/astraea/mapping/exporters.py
    - tests/unit/mapping/test_exporters.py
    - tests/unit/cli/__init__.py
    - tests/unit/cli/test_display.py
  modified:
    - src/astraea/cli/app.py
    - src/astraea/cli/display.py
metrics:
  duration: ~5 min
  completed: 2026-02-27
---

# Phase 3 Plan 4: Mapping Output Layer Summary

Excel/JSON export of mapping specs plus CLI map-domain command with Rich display and source file auto-detection.

## Tasks Completed

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Create Excel and JSON exporters | 05d242a | exporters.py, test_exporters.py |
| 2 | Add CLI map-domain command with Rich display | bc91899 | app.py, display.py, test_display.py |

## What Was Built

### Task 1: Exporters (exporters.py)

- **export_to_json**: Pydantic model_dump_json with round-trip fidelity
- **export_to_excel**: 3-sheet openpyxl workbook:
  - Sheet 1 "Mapping Spec": 15 columns with auto-filter, conditional formatting (GREEN/YELLOW/RED for HIGH/MEDIUM/LOW confidence)
  - Sheet 2 "Unmapped Variables": unmapped source vars + SUPPQUAL candidates with disposition labels
  - Sheet 3 "Summary": domain metadata, confidence distribution, source datasets
- Both create parent directories automatically

### Task 2: CLI map-domain Command

- Full mapping pipeline wired: profile SAS, parse eCRF, call MappingEngine, export results
- **Source file heuristic**: exact match (dm.sas7bdat), prefix match (dm_*.sas7bdat), or --source-file override
- **Cross-domain profiling**: for DM domain, auto-profiles ex, ie, irt, ds
- **eCRF integration**: parses PDF (or loads cache), matches forms to primary dataset
- **display_mapping_spec**: Rich Panel header + Table with color-coded confidence + summary footer + unmapped/SUPPQUAL info
- ANTHROPIC_API_KEY validation follows existing pattern

## Tests

| File | Tests | Status |
|------|-------|--------|
| tests/unit/mapping/test_exporters.py | 7 | Pass |
| tests/unit/cli/test_display.py | 5 | Pass |
| **Total new tests** | **12** | **Pass** |

Full suite: 564 passed, 15 skipped.

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

- [D-0304-01] ANSI escape codes stripped in display tests using regex helper (_strip_ansi) since Rich embeds bold/dim codes even with no_color=True
- [D-0304-02] Cross-domain datasets hardcoded as dict (DM: [ex, ie, irt, ds]) -- generic resolver deferred to future phases
- [D-0304-03] map-domain (hyphenated) used as command name to avoid Python keyword conflict with "map"

## Next Phase Readiness

Plan 03-05 (integration test) can proceed. All mapping infrastructure is now complete:
- Models (03-01), context assembly (03-02), engine (03-03), output layer (03-04)
- CLI command available for end-to-end testing with real data
