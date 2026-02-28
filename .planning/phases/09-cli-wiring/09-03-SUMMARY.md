---
phase: 09-cli-wiring
plan: 03
subsystem: cli
tags: [findings, executor, suppqual, xpt, routing]

dependency_graph:
  requires: [06-findings-domains]
  provides: [findings-cli-routing, suppqual-xpt-output]
  affects: []

tech_stack:
  added: []
  patterns: [domain-specific-dispatch, lazy-import-branching]

key_files:
  created:
    - tests/unit/cli/test_execute_findings.py
  modified:
    - src/astraea/cli/app.py

decisions:
  - id: D-09-03-01
    description: "_FINDINGS_DOMAINS set defined inside function body (not module level) for lazy import consistency"
  - id: D-09-03-02
    description: "SUPPQUAL column labels hardcoded as dict in CLI (standard SUPPQUAL labels are fixed per SDTM-IG)"
  - id: D-09-03-03
    description: "Char width summary removed for Findings path since FindingsExecutor wraps DatasetExecutor internally"

metrics:
  duration: ~6 min
  completed: 2026-02-28
---

# Phase 09 Plan 03: Findings Routing in execute-domain Summary

Route LB/VS/EG domains through FindingsExecutor in execute-domain CLI, enabling multi-source merge, column normalization, and SUPPQUAL XPT output via CLI workflow.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Route Findings domains through FindingsExecutor | 426bf8a | src/astraea/cli/app.py |
| 2 | Add unit tests for Findings routing | 80a7b41 | tests/unit/cli/test_execute_findings.py |

## Changes Made

### Task 1: Findings Routing in execute-domain
Modified the Step 4 (Executing mapping) block of execute-domain to detect Findings domains (LB, VS, EG) and dispatch to FindingsExecutor instead of DatasetExecutor.

Key changes:
- Defined `_FINDINGS_DOMAINS = {"LB", "VS", "EG"}` inside the function body
- Added lazy imports for `FindingsExecutor` and `write_xpt_v5` inside the Findings branch
- Domain-specific dispatch via dict mapping: LB -> execute_lb, VS -> execute_vs, EG -> execute_eg
- Main domain XPT written with column labels from spec
- SUPPQUAL XPT written as `supp{domain}.xpt` when FindingsExecutor returns non-empty supplemental data
- Non-Findings domains continue through DatasetExecutor.execute_to_xpt unchanged
- Summary display indicates FindingsExecutor usage for Findings domains

### Task 2: Unit Tests
Created 5 tests covering all routing scenarios:
1. LB routes through FindingsExecutor.execute_lb
2. EG routes through FindingsExecutor.execute_eg
3. DM routes through generic DatasetExecutor (unchanged behavior)
4. LB with SUPPQUAL data writes two XPT files (lb.xpt + supplb.xpt)
5. LB without SUPPQUAL data writes only one XPT file (lb.xpt)

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-09-03-01 | _FINDINGS_DOMAINS defined inside function body | Consistent with project's lazy import pattern -- no module-level imports for execution modules |
| D-09-03-02 | SUPPQUAL column labels hardcoded in CLI | SUPPQUAL structure is fixed per SDTM-IG (STUDYID, RDOMAIN, USUBJID, IDVAR, IDVARVAL, QNAM, QLABEL, QVAL, QORIG, QEVAL) -- labels never vary |
| D-09-03-03 | Char width summary removed for Findings path | FindingsExecutor wraps DatasetExecutor via composition; char widths are internal to the wrapped executor and not easily accessible at CLI level |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed test spec JSON fixture missing required fields**
- **Found during:** Task 2
- **Issue:** The plan's suggested spec JSON fixture was incomplete -- DomainMappingSpec requires domain_class, structure, total_variables, required_mapped, expected_mapped, confidence counts, mapping_timestamp, and VariableMapping requires sdtm_data_type, core, confidence_level, confidence_rationale
- **Fix:** Built complete spec fixture with all required fields using a `_make_var` helper function
- **Files modified:** tests/unit/cli/test_execute_findings.py

**2. [Rule 3 - Blocking] Fixed mock patch targets for lazy imports**
- **Found during:** Task 2
- **Issue:** Patching `astraea.cli.app.read_sas_with_metadata` fails because the function is imported lazily inside the command function, not at module level
- **Fix:** Changed patch targets to source modules (`astraea.io.sas_reader.read_sas_with_metadata`, `astraea.reference.load_sdtm_reference`, etc.)
- **Files modified:** tests/unit/cli/test_execute_findings.py

## Verification

- `ruff check src/astraea/cli/app.py tests/unit/cli/test_execute_findings.py` -- zero violations
- `pytest tests/unit/cli/test_execute_findings.py -x -q` -- 5/5 pass
- `pytest tests/ -q --ignore=tests/unit/cli/test_trial_design_cli.py` -- 1562 passed, 119 skipped (pre-existing trial design test failure unrelated)
- `python -c "from astraea.cli.app import app; print('OK')"` -- no import errors

## GAP Closure

GAP-3 from v1-MILESTONE-AUDIT.md is closed: execute-domain now routes Findings domains through FindingsExecutor with full multi-source merge, column normalization, and SUPPQUAL generation support.
