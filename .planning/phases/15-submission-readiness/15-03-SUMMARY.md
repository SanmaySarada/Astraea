---
phase: 15-submission-readiness
plan: 03
subsystem: mapping-validation-profiling
tags: [dm-arm, sdtm-detection, validation, profiling]
depends_on:
  requires: [01-foundation, 02-source-parsing, 03-core-mapping-engine, 07-validation-submission]
  provides: [DM ARM enforcement at prompt and validation levels, pre-mapped SDTM detection]
  affects: [mapping-agent-prompts, validation-pipeline, profiler-output]
tech_stack:
  added: []
  patterns: [domain-specific prompt injection, findings-pattern detection]
key_files:
  created:
    - tests/unit/mapping/test_dm_arm_enforcement.py
    - tests/unit/profiling/test_sdtm_detection.py
  modified:
    - src/astraea/mapping/context.py
    - src/astraea/validation/rules/presence.py
    - src/astraea/profiling/profiler.py
    - src/astraea/models/profiling.py
    - tests/unit/validation/test_presence_rules.py
decisions:
  - id: D-1503-01
    decision: "ARM enforcement uses both prompt-level and validation-level approach"
    rationale: "Prompt prevents LLM from omitting ARM vars; validation is safety net"
  - id: D-1503-02
    decision: "SDTM detection uses 3-suffix threshold for Findings domains"
    rationale: "3 of 5 indicators (TESTCD, TEST, ORRES, STRESC, STRESN) provides strong signal without false positives"
  - id: D-1503-03
    decision: "DM ARM copy-paste rule uses WARNING not ERROR severity"
    rationale: "ACTARM == ARM is legitimate when all patients received planned treatment"
metrics:
  duration: ~5 min
  completed: 2026-02-28
  tests_added: 20
  tests_total_after: 1928
---

# Phase 15 Plan 03: DM ARM Enforcement and SDTM Detection Summary

DM-specific ARM/ARMCD/ACTARM/ACTARMCD enforcement at mapping prompt and validation levels, plus Findings-domain pattern detection in the profiler.

## What Was Done

### Task 1: DM ARM Variable Enforcement

**Part A: Mapping Prompt Context (MED-14)**
- Added `_format_dm_arm_enforcement()` function to `context.py`
- Injected DM-specific block into `MappingContextBuilder.build_prompt()` when `domain == "DM"`
- Block explicitly lists ARM, ARMCD, ACTARM, ACTARMCD as Required with FDA warning
- Includes instruction that ACTARM must be independently derived, not copied from ARM

**Part B: Post-Mapping Validation Rules**
- Added `DMArmPresenceRule` (ASTR-P010): ERROR severity when any of the four ARM variables missing from DM
- Added `DMArmCopyPasteRule` (ASTR-P011): WARNING severity when ACTARM == ARM for all rows
- Both rules only apply to DM domain
- Registered in `get_presence_rules()`

### Task 2: Pre-Mapped SDTM Data Detection

- Added `detect_sdtm_format()` to `profiler.py` checking Findings domain patterns (LB, EG, VS, PE, QS prefixes with TESTCD/TEST/ORRES/STRESC/STRESN suffixes)
- Threshold: 3+ suffix matches for any Findings prefix triggers detection
- Also detects DOMAIN column with valid SDTM domain code
- Added `is_sdtm_preformatted: bool` field to `DatasetProfile` model
- Integrated into `profile_dataset()` pipeline

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated presence rules count test**
- **Found during:** Verification
- **Issue:** `test_returns_all_rules` expected 6 rules, now 8 after adding P010/P011
- **Fix:** Updated assertion count and added P010/P011 rule ID checks
- **Files modified:** `tests/unit/validation/test_presence_rules.py`
- **Commit:** 5a950be

**2. [Rule 3 - Blocking] Ruff SIM102 lint violation**
- **Found during:** Verification
- **Issue:** Nested `if` statements in `detect_sdtm_format()` flagged by ruff
- **Fix:** Combined into single `if` with `and`
- **Files modified:** `src/astraea/profiling/profiler.py`
- **Commit:** 5a950be

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-1503-01 | Dual enforcement: prompt + validation | Prompt prevents omission; validation catches it if prompt fails |
| D-1503-02 | 3-suffix threshold for SDTM detection | Strong signal: 3 of 5 Findings indicators matches reliably |
| D-1503-03 | WARNING for copy-paste, not ERROR | ACTARM == ARM is legitimate when planned == actual |

## Verification

- 20 new tests: 10 for DM ARM enforcement, 10 for SDTM detection
- 1928 total tests passing (119 skipped)
- 1 pre-existing integration failure (define_xml) unrelated to changes
- Ruff clean on all modified files
