---
phase: 01-foundation
plan: 03
subsystem: reference-data
tags: [sdtm-ig, controlled-terminology, json, lookup, cdisc, nci-evs]
dependency-graph:
  requires: [01-01]
  provides: [sdtm-reference-lookup, ct-reference-lookup, bundled-reference-data]
  affects: [01-04, 01-05, 02-01, 02-02, 02-03]
tech-stack:
  added: []
  patterns: [bundled-json-reference, path-based-data-loading, reverse-lookup-index]
key-files:
  created:
    - src/astraea/data/sdtm_ig/domains.json
    - src/astraea/data/sdtm_ig/version.json
    - src/astraea/data/ct/codelists.json
    - src/astraea/data/ct/version.json
    - src/astraea/reference/sdtm_ig.py
    - src/astraea/reference/controlled_terms.py
    - src/astraea/reference/loader.py
    - tests/test_reference/test_sdtm_ig.py
    - tests/test_reference/test_controlled_terms.py
  modified:
    - src/astraea/reference/__init__.py
decisions:
  - id: D-0103-01
    description: "Used Path(__file__) approach for locating bundled data (not importlib.resources) for simplicity and directness"
  - id: D-0103-02
    description: "Country codelist uses ISO 3166-1 alpha-3 codes (USA, GBR, DEU) not alpha-2 (US, GB, DE) per SDTM-IG v3.4 requirement"
  - id: D-0103-03
    description: "Extensible codelist validate_term() always returns True -- any value is allowed, not just listed terms"
metrics:
  duration: "4 minutes"
  completed: "2026-02-26"
---

# Phase 1 Plan 3: SDTM-IG and CT Reference Data Summary

**One-liner:** Bundled SDTM-IG v3.4 specs (10 domains, 26 DM vars) and NCI CT (11 codelists with extensibility flags) as queryable JSON with Python lookup classes -- zero network dependency.

## What Was Done

### Task 1: Bundled JSON Reference Data
Created 4 JSON files with comprehensive CDISC reference data:

**domains.json** -- 10 SDTM domains with full variable specifications:

| Domain | Class | Variables | Description |
|--------|-------|-----------|-------------|
| DM | Special-Purpose | 26 | Demographics (complete) |
| AE | Events | 26 | Adverse Events |
| CM | Interventions | 17 | Concomitant Medications |
| EX | Interventions | 14 | Exposure |
| LB | Findings | 22 | Laboratory Test Results |
| VS | Findings | 16 | Vital Signs |
| EG | Findings | 15 | ECG Test Results |
| MH | Events | 14 | Medical History |
| DS | Events | 10 | Disposition |
| IE | Findings | 12 | Inclusion/Exclusion |

**codelists.json** -- 11 NCI CT codelists:

| Code | Name | Extensible | Terms |
|------|------|------------|-------|
| C66731 | Sex | No | M, F, U, UNDIFFERENTIATED |
| C66790 | No Yes Response | No | N, Y |
| C66767 | Race | No | 9 race categories |
| C66728 | Ethnicity | No | 4 ethnicity values |
| C66742 | Country | Yes | 11 ISO alpha-3 codes |
| C66726 | Age Unit | No | YEARS, MONTHS, WEEKS, DAYS, HOURS |
| C66769 | Route of Administration | Yes | 11 routes |
| C66734 | Severity/Intensity | No | MILD, MODERATE, SEVERE |
| C66768 | Outcome of Event | No | 6 outcome values |
| C66781 | Unit | Yes | 22 common clinical units |
| C66770 | Frequency | Yes | 9 dosing frequencies |

**Version manifests** lock SDTM-IG v3.4 with CT 2025-09-26.

### Task 2: Reference Lookup Classes
Implemented 3 Python modules with full test coverage:

**SDTMReference** (sdtm_ig.py):
- `get_domain_spec(domain)` -- full DomainSpec Pydantic model
- `get_required_variables(domain)` -- Req-only variable names
- `get_expected_variables(domain)` -- Exp-only variable names
- `get_variable_spec(domain, variable)` -- single variable detail
- `list_domains()` -- all 10 domain codes
- `get_domain_class(domain)` -- Events/Findings/Interventions/Special-Purpose

**CTReference** (controlled_terms.py):
- `lookup_codelist(code)` -- full Codelist Pydantic model
- `validate_term(code, value)` -- exact match for non-extensible, always True for extensible
- `is_extensible(code)` -- bool check
- `get_codelist_for_variable(var_name)` -- reverse lookup via pre-built index
- `list_codelists()` -- all 11 codelist codes

**Tests:** 44 tests across 2 test files, all passing.

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

1. **Path-based data loading**: Used `Path(__file__).parent.parent / "data"` approach rather than `importlib.resources`. Simpler, works with editable installs, no compatibility concerns.
2. **ISO alpha-3 country codes**: Country codelist uses USA/GBR/DEU (alpha-3) per SDTM-IG v3.4 requirement, not US/GB/DE.
3. **Extensible codelist validation**: `validate_term()` returns True for any value on extensible codelists. This matches CDISC rules -- extensible codelists accept study-specific values beyond the published list.

## Verification Results

```
pytest tests/test_reference/ -v                -- 44/44 passed (0.10s)
load_sdtm_reference().get_required_variables('DM')  -- ['STUDYID', 'DOMAIN', 'USUBJID', ...]
load_ct_reference().validate_term('C66731', 'M')    -- True
load_ct_reference().is_extensible('C66731')          -- False
```

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `c9ef6e9` | Bundle SDTM-IG v3.4 and NCI CT reference data as JSON |
| 2 | `06539c7` | Implement reference lookup classes with 44 tests |

## Next Phase Readiness

All downstream plans can now:
- `from astraea.reference import load_sdtm_reference, load_ct_reference`
- Query any of 10 SDTM domains for variable specs, core designations, domain classes
- Validate controlled terminology values against proper extensibility rules
- Look up which codelist applies to a given SDTM variable name
