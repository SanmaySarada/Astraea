"""Tests for ValidationEngine rule registration completeness.

Verifies that SUPPQUAL integrity (ASTR-S001) and variable ordering
(ASTR-O001) rules are registered in register_defaults().
"""

from __future__ import annotations

from astraea.reference import load_ct_reference, load_sdtm_reference
from astraea.validation.engine import ValidationEngine


def _make_engine() -> ValidationEngine:
    """Create a ValidationEngine with real reference data."""
    sdtm_ref = load_sdtm_reference()
    ct_ref = load_ct_reference()
    return ValidationEngine(sdtm_ref=sdtm_ref, ct_ref=ct_ref)


def test_engine_registers_suppqual_rule() -> None:
    """ASTR-S001 (SUPPQUAL integrity) should be in the engine's rule list."""
    engine = _make_engine()
    rule_ids = [r.rule_id for r in engine.rules]
    assert "ASTR-S001" in rule_ids, (
        f"ASTR-S001 not found in registered rules: {rule_ids}"
    )


def test_engine_registers_ordering_rule() -> None:
    """ASTR-O001 (variable ordering) should be in the engine's rule list."""
    engine = _make_engine()
    rule_ids = [r.rule_id for r in engine.rules]
    assert "ASTR-O001" in rule_ids, (
        f"ASTR-O001 not found in registered rules: {rule_ids}"
    )


def test_engine_total_rule_count() -> None:
    """Engine should register at least 23 rules (21 FDAB + SUPPQUAL + ordering)."""
    engine = _make_engine()
    count = len(engine.rules)
    assert count >= 23, (
        f"Expected at least 23 registered rules, got {count}"
    )
