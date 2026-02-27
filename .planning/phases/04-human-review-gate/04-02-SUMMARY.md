---
phase: 04-human-review-gate
plan: 02
subsystem: review
tags: [rich-display, interactive-review, two-tier, corrections, crash-recovery]

dependency_graph:
  requires: [04-01]
  provides: [review-display, domain-reviewer, review-interrupted]
  affects: [04-03, 08-learning-loop]

tech_stack:
  added: []
  patterns: [two-tier-review, per-variable-persistence, input-callback-testing]

key_files:
  created:
    - src/astraea/review/display.py
    - src/astraea/review/reviewer.py
    - tests/unit/review/test_display.py
    - tests/unit/review/test_reviewer.py
  modified:
    - src/astraea/review/models.py

decisions:
  - id: D-0402-01
    description: "ReviewDecision validator allows None corrected_mapping for REJECT correction type"
  - id: D-0402-02
    description: "DomainReviewer uses input_callback injection for testability (replaces Rich Prompt.ask)"
  - id: D-0402-03
    description: "Per-variable save_domain_review after every decision for crash recovery"

metrics:
  duration: "5 minutes"
  completed: "2026-02-27"
---

# Phase 4 Plan 2: Review Display + Reviewer Logic Summary

**One-liner:** Rich display layer with status-annotated mapping tables and DomainReviewer driving two-tier review (batch HIGH, individual MEDIUM/LOW) with per-variable crash recovery.

## What Was Done

### Task 1: Review Display Functions
Created `src/astraea/review/display.py` with 4 display functions:

- **display_review_table()**: Domain mapping table with Status column (OK/FIX/--/...), color-coded confidence (green/yellow/red), core designation (Req/Exp/Perm), and progress counts
- **display_variable_detail()**: Full panel for single variable showing source, pattern, confidence, logic, derivation rule, codelist, and rationale
- **display_review_summary()**: Domain review progress panel with approved/corrected/skipped/pending counts and corrections list
- **display_session_list()**: Session table with color-coded status (in_progress=yellow, completed=green, abandoned=red)

19 tests using `Console(file=StringIO())` capture pattern with ANSI stripping.

### Task 2: Core Reviewer Logic
Created `src/astraea/review/reviewer.py` with `DomainReviewer` class and `ReviewInterrupted` exception:

- **review_domain()**: Entry point -- displays table, prompts for action (approve-all/review/skip/quit)
- **_review_two_tier()**: Partitions by confidence, batch approves HIGH, individual reviews MEDIUM/LOW
- **_collect_correction()**: Captures source_change (new source variable, confidence=1.0), reject (None mapping), or logic_change (original preserved)
- **_prompt()**: Delegates to input_callback (test) or Rich Prompt.ask (production)
- **ReviewInterrupted**: Exception with session_id for CLI resume message

16 tests covering: approve-all, two-tier batch+individual, source change correction, reject, skip (domain and variable), quit with partial progress saved, resume skipping already-reviewed variables, logic change correction.

### Model Fix (Deviation)
Updated `ReviewDecision` model validator in `models.py` to allow `corrected_mapping=None` when `correction_type=REJECT`. REJECT means the variable is removed, not replaced, so there is no corrected mapping.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ReviewDecision validator rejected REJECT corrections**
- **Found during:** Task 2
- **Issue:** The model validator required `corrected_mapping` for all CORRECTED status decisions, but REJECT corrections intentionally have no corrected mapping
- **Fix:** Updated validator to skip `corrected_mapping` check when `correction_type == CorrectionType.REJECT`
- **Files modified:** `src/astraea/review/models.py`
- **Commit:** 3935f0b

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-0402-01 | REJECT corrections allow None corrected_mapping | REJECT means removal, not replacement -- no mapping to provide |
| D-0402-02 | input_callback injection pattern for DomainReviewer | Enables deterministic testing without mocking Rich Prompt.ask internals |
| D-0402-03 | save_domain_review after every variable decision | Crash recovery: Ctrl+C loses at most one decision, not the entire session |

## Test Results

```
65 passed in 0.36s (19 display + 16 reviewer + 17 models + 13 session)
ruff: All checks passed!
```

## Next Phase Readiness

Plan 04-03 (CLI commands: review-domain, resume) can proceed. It will import:
- `display_review_table`, `display_review_summary`, `display_session_list` from `astraea.review.display`
- `DomainReviewer`, `ReviewInterrupted` from `astraea.review.reviewer`
- `SessionStore` from `astraea.review.session`
