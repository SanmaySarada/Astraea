---
phase: 06-findings-domains
plan: 06
subsystem: execution
tags: [sv, trial-design, ta, te, tv, ti, relrec, pydantic, pandas]

# Dependency graph
requires:
  - phase: 06-findings-domains (06-04)
    provides: SUPPQUAL generation + Findings XPT output tests
provides:
  - SV domain builder from EDC visit metadata
  - Config-driven trial design builders (TA, TE, TV, TI)
  - RELREC model + stub generator with deferral documentation
  - TS integration test with DM-derived dates
affects: [07-validation, define-xml, submission-readiness]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Config-driven domain builders: TrialDesignConfig -> DataFrame"
    - "EDC metadata extraction from raw files (InstanceName/FolderName/FolderSeq)"
    - "Explicit stub pattern with deferral documentation for complex deferred features"

key-files:
  created:
    - src/astraea/execution/subject_visits.py
    - src/astraea/execution/trial_design.py
    - src/astraea/execution/relrec.py
    - src/astraea/models/relrec.py
    - tests/unit/execution/test_subject_visits.py
    - tests/unit/execution/test_trial_design.py
    - tests/unit/execution/test_relrec.py
    - tests/integration/execution/test_ts_integration.py
  modified:
    - src/astraea/models/trial_design.py

key-decisions:
  - "SV visit dates extracted from EDC InstanceName/FolderName/FolderSeq columns across all raw files"
  - "Trial design domains use config-driven builders (not LLM) since they describe study structure"
  - "RELREC deferred to Phase 7+ per PITFALLS.md m2 -- stub with empty DataFrame and deferral warning"
  - "TrialDesignConfig validates non-empty arms/elements/visits; I/E criteria optional (None = empty TI)"

patterns-established:
  - "Config-driven builders: Pydantic config -> deterministic SDTM DataFrame"
  - "Stub pattern: empty DataFrame + loguru warning + validation-only for deferred features"

# Metrics
duration: 4min
completed: 2026-02-28
---

# Phase 6 Plan 06: Special Purpose & Trial Design Domains Summary

**SV domain builder from EDC visit metadata, config-driven trial design builders (TA/TE/TV/TI), RELREC stub, and TS-DM integration tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-28T01:48:15Z
- **Completed:** 2026-02-28T01:52:15Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- SV domain builder extracts visit dates from InstanceName/FolderName/FolderSeq metadata across all raw EDC files
- Trial design domain builders (TA, TE, TV, TI) produce valid SDTM DataFrames from TrialDesignConfig model
- TrialDesignConfig with ArmDef, ElementDef, VisitDef, IEDef sub-models added to trial_design.py
- RELREC model (RelRecRecord, RelRecConfig) and stub generator with explicit Phase 7+ deferral
- TS domain integration tests verify DM-derived SSTDTC/SENDTC and XPT roundtrip

## Task Commits

1. **Task 1: SV domain builder, trial design builders, RELREC model + stub** - `6cbcc15` (feat)
2. **Task 2: TS domain integration test with DM data** - `d7c9521` (test)

## Files Created/Modified
- `src/astraea/execution/subject_visits.py` - SV domain builder (extract_visit_dates + build_sv_domain)
- `src/astraea/execution/trial_design.py` - Trial design builders (build_ta/te/tv/ti_domain)
- `src/astraea/execution/relrec.py` - RELREC stub generator (generate_relrec_stub)
- `src/astraea/models/trial_design.py` - Added ArmDef, ElementDef, VisitDef, IEDef, TrialDesignConfig models
- `src/astraea/models/relrec.py` - RelRecRecord, RelRecRelationship, RelRecConfig models
- `tests/unit/execution/test_subject_visits.py` - 10 SV builder tests
- `tests/unit/execution/test_trial_design.py` - 12 trial design builder tests
- `tests/unit/execution/test_relrec.py` - 12 RELREC model and stub tests
- `tests/integration/execution/test_ts_integration.py` - 8 TS-DM integration tests

## Decisions Made
- SV visit dates use string comparison for date min/max (ISO 8601 strings sort correctly)
- TrialDesignConfig requires non-empty arms, elements, visits lists (min_length=1)
- IEDef.iecat validates against "INCLUSION"/"EXCLUSION" only
- RELREC stub validates domain codes against a comprehensive set of valid SDTM domains
- TA TABESSION derived as counter per arm (arm-level session numbering)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All Phase 6 plans (06-01 through 06-06) now complete
- Phase 6 delivers: transpose engine, SUPPQUAL generator, findings executor, TS builder, SV builder, trial design builders, RELREC stub
- Combined test suite: 1182 passed, 119 skipped
- Ready for Phase 7 (Validation)

---
*Phase: 06-findings-domains*
*Completed: 2026-02-28*
