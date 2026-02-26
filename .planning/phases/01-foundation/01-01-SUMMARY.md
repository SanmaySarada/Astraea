---
phase: 01-foundation
plan: 01
subsystem: core-models
tags: [pydantic, project-setup, data-models, sdtm, controlled-terminology]
dependency-graph:
  requires: []
  provides: [installable-package, pydantic-models, test-infrastructure]
  affects: [01-02, 01-03, 01-04, 01-05]
tech-stack:
  added: [pyreadstat, pandas, pydantic, typer, rich, loguru, anthropic, langgraph, langchain-anthropic, openpyxl, pytest, ruff, mypy]
  patterns: [src-layout, pydantic-v2-models, re-export-init]
key-files:
  created:
    - pyproject.toml
    - src/astraea/__init__.py
    - src/astraea/models/metadata.py
    - src/astraea/models/profiling.py
    - src/astraea/models/sdtm.py
    - src/astraea/models/controlled_terms.py
    - src/astraea/models/__init__.py
    - src/astraea/cli/app.py
    - tests/test_models/test_metadata.py
  modified: []
decisions:
  - id: D-0101-01
    description: "Used setuptools.build_meta as build backend instead of legacy backend"
  - id: D-0101-02
    description: "storage_width Field uses ge=1 (not ge=0) since width of 0 bytes is invalid"
  - id: D-0101-03
    description: "VariableSpec.order uses ge=1 since SDTM variable ordering is 1-based"
metrics:
  duration: "3 minutes"
  completed: "2026-02-26"
---

# Phase 1 Plan 1: Project Setup and Data Models Summary

**One-liner:** Installable Python package with 13 Pydantic v2 models covering SAS metadata, profiling, SDTM-IG specs, and controlled terminology -- all importable from `astraea.models`.

## What Was Done

### Task 1: Project Structure and pyproject.toml
- Created full src-layout package structure with all subpackages (models, io, profiling, reference, transforms, cli, agents, validation)
- Configured pyproject.toml with all dependencies from CLAUDE.md stack
- Fixed build-backend from legacy to `setuptools.build_meta`
- Added `openpyxl>=3.1` per project requirements
- Set `python_requires >= 3.12` per CDISC rules engine constraint
- Verified: `pip install -e ".[dev]"` succeeds, `import astraea` works, pytest discovers tests

### Task 2: Pydantic Data Models
Created 4 model files with 13 total models:

| File | Models | Purpose |
|------|--------|---------|
| `metadata.py` | VariableMetadata, DatasetMetadata | Raw SAS file metadata from pyreadstat |
| `profiling.py` | ValueDistribution, VariableProfile, DatasetProfile | Statistical profiling output with EDC column detection |
| `sdtm.py` | DomainClass, CoreDesignation, VariableSpec, DomainSpec, SDTMIGPackage | SDTM-IG reference specifications |
| `controlled_terms.py` | CodelistTerm, Codelist, CTPackage | NCI controlled terminology with extensibility flag |

All models use Pydantic v2 syntax (Field, model_dump, model_validate). Validation constraints include ge/le bounds on counts and percentages, Literal types for dtype enums, and str Enums for SDTM classifications.

### Tests
- 13 tests in `test_metadata.py` covering:
  - Valid construction of numeric and character variables
  - Default values (empty label, None format)
  - Validation rejection of invalid dtype and negative counts
  - model_dump() serialization roundtrip
  - model_validate() from raw dict

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

1. **Build backend**: Used `setuptools.build_meta` instead of `setuptools.backends._legacy:_Backend` which was in the existing pyproject.toml. The legacy backend is deprecated.
2. **storage_width ge=1**: A variable with 0 bytes storage width is invalid in SAS, so minimum is 1 (not 0).
3. **VariableSpec.order ge=1**: SDTM-IG variable ordering starts at 1.

## Verification Results

```
pip install -e ".[dev]"          -- SUCCESS
import astraea                   -- SUCCESS (version 0.1.0)
pytest --collect-only            -- SUCCESS (13 tests discovered)
pytest tests/test_models/ -v     -- SUCCESS (13/13 passed)
from astraea.models import ...   -- SUCCESS (all 13 models importable)
```

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `86986b9` | Project structure and pyproject.toml |
| 2 | `014503b` | All Pydantic data models with tests |

## Next Phase Readiness

All downstream plans can now:
- Import `from astraea.models import VariableMetadata, DatasetProfile, DomainSpec, Codelist`
- Run `pip install -e ".[dev]"` to get all dependencies
- Add tests to `tests/test_models/` or other test directories
