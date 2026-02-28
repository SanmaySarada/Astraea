"""Tests for DM ARM variable enforcement.

Tests both the mapping prompt context injection (MED-14) and
post-mapping validation rules (DMArmPresenceRule, DMArmCopyPasteRule).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from astraea.validation.rules.base import RuleSeverity
from astraea.validation.rules.presence import DMArmCopyPasteRule, DMArmPresenceRule


@pytest.fixture()
def _mock_refs():
    """Return mock SDTMReference and CTReference."""
    return MagicMock(), MagicMock()


@pytest.fixture()
def _mock_spec():
    """Return a mock DomainMappingSpec."""
    return MagicMock()


# --- DMArmPresenceRule tests ---


class TestDMArmPresenceRule:
    """Tests for ASTR-P010: DM ARM variable presence."""

    def test_fires_when_arm_armcd_missing(self, _mock_refs, _mock_spec):
        rule = DMArmPresenceRule()
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "STUDYID": ["STUDY1"],
            }
        )
        sdtm_ref, ct_ref = _mock_refs
        results = rule.evaluate("DM", df, _mock_spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert "ARM" in results[0].message
        assert "ARMCD" in results[0].message

    def test_fires_when_actarm_actarmcd_missing(self, _mock_refs, _mock_spec):
        rule = DMArmPresenceRule()
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "ARM": ["Treatment A"],
                "ARMCD": ["TRT_A"],
            }
        )
        sdtm_ref, ct_ref = _mock_refs
        results = rule.evaluate("DM", df, _mock_spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert "ACTARM" in results[0].message
        assert "ACTARMCD" in results[0].message

    def test_passes_when_all_four_present(self, _mock_refs, _mock_spec):
        rule = DMArmPresenceRule()
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "ARM": ["Treatment A"],
                "ARMCD": ["TRT_A"],
                "ACTARM": ["Treatment A"],
                "ACTARMCD": ["TRT_A"],
            }
        )
        sdtm_ref, ct_ref = _mock_refs
        results = rule.evaluate("DM", df, _mock_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_does_not_apply_to_non_dm(self, _mock_refs, _mock_spec):
        rule = DMArmPresenceRule()
        df = pd.DataFrame({"USUBJID": ["SUBJ-001"]})
        sdtm_ref, ct_ref = _mock_refs
        for domain in ["AE", "LB", "VS", "CM", "EX"]:
            results = rule.evaluate(domain, df, _mock_spec, sdtm_ref, ct_ref)
            assert len(results) == 0


# --- DMArmCopyPasteRule tests ---


class TestDMArmCopyPasteRule:
    """Tests for ASTR-P011: DM ARM copy-paste detection."""

    def test_warning_when_actarm_equals_arm_all_rows(self, _mock_refs, _mock_spec):
        rule = DMArmCopyPasteRule()
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001", "SUBJ-002", "SUBJ-003"],
                "ARM": ["Treatment A", "Treatment B", "Placebo"],
                "ARMCD": ["TRT_A", "TRT_B", "PBO"],
                "ACTARM": ["Treatment A", "Treatment B", "Placebo"],
                "ACTARMCD": ["TRT_A", "TRT_B", "PBO"],
            }
        )
        sdtm_ref, ct_ref = _mock_refs
        results = rule.evaluate("DM", df, _mock_spec, sdtm_ref, ct_ref)
        assert len(results) == 2  # one for ACTARM, one for ACTARMCD
        assert all(r.severity == RuleSeverity.WARNING for r in results)

    def test_no_warning_when_some_rows_differ(self, _mock_refs, _mock_spec):
        rule = DMArmCopyPasteRule()
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001", "SUBJ-002", "SUBJ-003"],
                "ARM": ["Treatment A", "Treatment B", "Placebo"],
                "ARMCD": ["TRT_A", "TRT_B", "PBO"],
                "ACTARM": ["Treatment A", "Treatment A", "Placebo"],  # SUBJ-002 switched
                "ACTARMCD": ["TRT_A", "TRT_A", "PBO"],  # SUBJ-002 switched
            }
        )
        sdtm_ref, ct_ref = _mock_refs
        results = rule.evaluate("DM", df, _mock_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_does_not_apply_to_non_dm(self, _mock_refs, _mock_spec):
        rule = DMArmCopyPasteRule()
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "ARM": ["Treatment A"],
                "ARMCD": ["TRT_A"],
                "ACTARM": ["Treatment A"],
                "ACTARMCD": ["TRT_A"],
            }
        )
        sdtm_ref, ct_ref = _mock_refs
        results = rule.evaluate("AE", df, _mock_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_skips_when_arm_columns_missing(self, _mock_refs, _mock_spec):
        """No error when ARM columns missing -- that is handled by DMArmPresenceRule."""
        rule = DMArmCopyPasteRule()
        df = pd.DataFrame({"USUBJID": ["SUBJ-001"]})
        sdtm_ref, ct_ref = _mock_refs
        results = rule.evaluate("DM", df, _mock_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_skips_empty_dataframe(self, _mock_refs, _mock_spec):
        rule = DMArmCopyPasteRule()
        df = pd.DataFrame(
            columns=["USUBJID", "ARM", "ARMCD", "ACTARM", "ACTARMCD"]
        )
        sdtm_ref, ct_ref = _mock_refs
        results = rule.evaluate("DM", df, _mock_spec, sdtm_ref, ct_ref)
        assert len(results) == 0


# --- Prompt context tests ---


class TestDMArmPromptContext:
    """Tests for DM ARM enforcement in mapping prompt context."""

    def test_dm_prompt_includes_arm_enforcement(self):
        """Verify _format_dm_arm_enforcement returns ARM instructions."""
        from astraea.mapping.context import _format_dm_arm_enforcement

        text = _format_dm_arm_enforcement()
        assert "ARM" in text
        assert "ARMCD" in text
        assert "ACTARM" in text
        assert "ACTARMCD" in text
        assert "Required" in text
        assert "FDA" in text
