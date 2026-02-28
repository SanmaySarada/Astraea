---
phase: 15
plan: 04
subsystem: execution
tags: [LC, LB, FDA, SDTCG, dual-lab, validation]
requires: [15-01]
provides: [LC domain generation, FDAB-LC01 validation, CLI LB->LC auto-gen]
affects: [define.xml, cSDRG]
tech-stack:
  added: []
  patterns: [structural-copy-domain, auto-generation-trigger]
key-files:
  created:
    - src/astraea/execution/lc_domain.py
    - tests/unit/execution/test_lc_domain.py
  modified:
    - src/astraea/validation/rules/fda_business.py
    - src/astraea/cli/app.py
    - tests/unit/cli/test_execute_findings.py
    - tests/unit/validation/test_fda_rules.py
decisions:
  - id: D-1504-01
    choice: "LC as structural copy with warning, not unit conversion"
    rationale: "v1 scope -- actual SI-to-conventional conversion deferred"
metrics:
  duration: "7 min"
  completed: "2026-02-28"
---

# Phase 15 Plan 04: LC Domain Generation Summary

LC domain generator producing conventional-unit lab data from LB, with FDAB-LC01 validation warning for missing unit conversion and CLI auto-generation wiring.

## What Was Done

### Task 1: LC domain generator with identity validation warning
- Created `src/astraea/execution/lc_domain.py` with `generate_lc_from_lb()`, `get_lb_to_lc_rename_map()`, `generate_lc_mapping_spec()`, and `LC_DOMAIN_DEFINITION`
- LB-prefixed columns renamed to LC-prefixed (LBTESTCD -> LCTESTCD, LBSEQ -> LCSEQ, etc.)
- Common columns (STUDYID, DOMAIN, USUBJID, VISITNUM, etc.) excluded from rename
- DOMAIN set to "LC", row count validated against LB
- `lc_unit_conversion_performed` attr set on DataFrame for validation detection
- Added `FDABLC01Rule` to `fda_business.py` -- fires WARNING when unit conversion not performed
- 29 tests covering rename mapping, generation, spec creation, and validation rule

### Task 2: LC domain registration and CLI auto-generation wiring
- CLI `execute-domain` for LB now auto-generates LC domain (writes lc.xpt to same output dir)
- LC added to `_FINDINGS_DOMAINS` set so existing Findings validation rules apply
- LC column labels derived from LB labels for XPT metadata
- Updated 3 existing tests to account for new LC auto-generation (write count changes)

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-1504-01 | LC generated as structural copy with warning | v1 scope -- actual unit conversion is complex and deferred. WARNING explicitly flags this for reviewer attention. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing CLI test expectations for LC auto-generation**
- **Found during:** Task 2
- **Issue:** `test_execute_domain_lb_with_suppqual` expected 2 XPT writes, now gets 3 (lb + supplb + lc). `test_execute_domain_lb_no_suppqual` expected 1 write, now gets 2 (lb + lc).
- **Fix:** Updated assertions to account for LC auto-generation
- **Files modified:** tests/unit/cli/test_execute_findings.py

**2. [Rule 1 - Bug] Updated FDA rule count test**
- **Found during:** Task 2
- **Issue:** `test_returns_six_rules` expected 6 rules, now 7 with FDAB-LC01
- **Fix:** Updated to `test_returns_seven_rules` with correct rule set
- **Files modified:** tests/unit/validation/test_fda_rules.py

## Pre-existing Issue

- `tests/integration/submission/test_define_xml_integration.py::TestDefineXmlGeneration::test_define_xml_multi_domain` was already failing before this plan (18 ItemDefs vs expected 14). Not introduced by this plan.

## Test Results

- 33 new LC domain tests: all passing
- Full suite: 1979 passed, 119 skipped (1 pre-existing failure deselected)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 3623cfe | LC domain generator with FDAB-LC01 validation warning |
| 2 | 089a3d6 | LC domain registration and CLI auto-generation wiring |
