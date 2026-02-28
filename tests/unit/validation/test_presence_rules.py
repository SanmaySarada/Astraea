"""Tests for presence validation rules (VAL-02).

Tests RequiredVariableRule, ExpectedVariableRule, NoRecordsRule,
and USUBJIDPresentRule against synthetic DataFrames.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.models.mapping import DomainMappingSpec, MappingPattern, VariableMapping
from astraea.models.sdtm import CoreDesignation
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.validation.rules.base import RuleCategory, RuleSeverity
from astraea.validation.rules.presence import (
    ExpectedVariableRule,
    NoRecordsRule,
    RequiredVariableRule,
    USUBJIDPresentRule,
    get_presence_rules,
)


@pytest.fixture()
def sdtm_ref() -> SDTMReference:
    return SDTMReference()


@pytest.fixture()
def ct_ref() -> CTReference:
    return CTReference()


def _make_spec(domain: str = "DM") -> DomainMappingSpec:
    return DomainMappingSpec(
        domain=domain,
        domain_label="Test Domain",
        domain_class="Special Purpose",
        structure="One record per subject",
        study_id="TEST-001",
        source_datasets=["test.sas7bdat"],
        variable_mappings=[],
        total_variables=0,
        required_mapped=0,
        expected_mapped=0,
        high_confidence_count=0,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


class TestRequiredVariableRule:
    """Tests for RequiredVariableRule (ASTR-P001)."""

    def test_rule_metadata(self) -> None:
        rule = RequiredVariableRule()
        assert rule.rule_id == "ASTR-P001"
        assert rule.category == RuleCategory.PRESENCE
        assert rule.severity == RuleSeverity.ERROR

    def test_all_required_present(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """All required variables present should produce no findings."""
        required = sdtm_ref.get_required_variables("DM")
        assert len(required) > 0, "DM should have required variables"

        data = {var: ["val"] for var in required}
        df = pd.DataFrame(data)
        spec = _make_spec("DM")
        rule = RequiredVariableRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_missing_required_variable(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Missing required variable should produce ERROR."""
        required = sdtm_ref.get_required_variables("DM")
        assert len(required) > 1

        # Include all but one required variable
        missing_var = required[0]
        data = {var: ["val"] for var in required[1:]}
        df = pd.DataFrame(data)
        spec = _make_spec("DM")
        rule = RequiredVariableRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)

        assert len(results) >= 1
        missing_result = [r for r in results if r.variable == missing_var]
        assert len(missing_result) == 1
        assert missing_result[0].severity == RuleSeverity.ERROR
        assert missing_result[0].p21_equivalent == "SD0083"

    def test_unknown_domain_no_findings(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Unknown domain should produce no findings (no spec to check against)."""
        df = pd.DataFrame({"A": [1]})
        spec = _make_spec("ZZ")
        rule = RequiredVariableRule()
        results = rule.evaluate("ZZ", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_case_insensitive_column_matching(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Column names should be compared case-insensitively."""
        required = sdtm_ref.get_required_variables("DM")
        # Use lowercase column names
        data = {var.lower(): ["val"] for var in required}
        df = pd.DataFrame(data)
        spec = _make_spec("DM")
        rule = RequiredVariableRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0


class TestExpectedVariableRule:
    """Tests for ExpectedVariableRule (ASTR-P002)."""

    def test_rule_metadata(self) -> None:
        rule = ExpectedVariableRule()
        assert rule.rule_id == "ASTR-P002"
        assert rule.category == RuleCategory.PRESENCE
        assert rule.severity == RuleSeverity.WARNING

    def test_missing_expected_variable_warning(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Missing expected variable should produce WARNING."""
        expected = sdtm_ref.get_expected_variables("DM")
        if not expected:
            pytest.skip("DM has no expected variables")

        df = pd.DataFrame({"STUDYID": ["TEST"]})
        spec = _make_spec("DM")
        rule = ExpectedVariableRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)

        assert len(results) >= 1
        for r in results:
            assert r.severity == RuleSeverity.WARNING
            assert r.variable in expected

    def test_all_expected_present_no_findings(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """All expected variables present should produce no findings."""
        expected = sdtm_ref.get_expected_variables("DM")
        if not expected:
            pytest.skip("DM has no expected variables")

        data = {var: ["val"] for var in expected}
        df = pd.DataFrame(data)
        spec = _make_spec("DM")
        rule = ExpectedVariableRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0


class TestNoRecordsRule:
    """Tests for NoRecordsRule (ASTR-P003)."""

    def test_rule_metadata(self) -> None:
        rule = NoRecordsRule()
        assert rule.rule_id == "ASTR-P003"
        assert rule.severity == RuleSeverity.WARNING

    def test_empty_dataframe_warning(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Empty DataFrame should produce WARNING."""
        df = pd.DataFrame({"STUDYID": pd.Series([], dtype=str)})
        spec = _make_spec("AE")
        rule = NoRecordsRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.WARNING
        assert "zero records" in results[0].message

    def test_nonempty_dataframe_no_findings(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Non-empty DataFrame should produce no findings."""
        df = pd.DataFrame({"STUDYID": ["TEST"]})
        spec = _make_spec("AE")
        rule = NoRecordsRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0


class TestUSUBJIDPresentRule:
    """Tests for USUBJIDPresentRule (ASTR-P004)."""

    def test_rule_metadata(self) -> None:
        rule = USUBJIDPresentRule()
        assert rule.rule_id == "ASTR-P004"
        assert rule.severity == RuleSeverity.ERROR

    def test_usubjid_present_and_complete(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Complete USUBJID should produce no findings."""
        df = pd.DataFrame({"USUBJID": ["SUBJ-001", "SUBJ-002", "SUBJ-003"]})
        spec = _make_spec("DM")
        rule = USUBJIDPresentRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_usubjid_missing_column(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Missing USUBJID column should produce ERROR."""
        df = pd.DataFrame({"STUDYID": ["TEST"]})
        spec = _make_spec("DM")
        rule = USUBJIDPresentRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert results[0].variable == "USUBJID"
        assert "missing" in results[0].message

    def test_usubjid_with_nulls(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """USUBJID with null values should produce ERROR."""
        df = pd.DataFrame({"USUBJID": ["SUBJ-001", None, "SUBJ-003", None]})
        spec = _make_spec("DM")
        rule = USUBJIDPresentRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert results[0].affected_count == 2
        assert "2 null" in results[0].message


class TestGetPresenceRules:
    """Tests for the get_presence_rules factory."""

    def test_returns_all_rules(self) -> None:
        rules = get_presence_rules()
        assert len(rules) == 4
        rule_ids = {r.rule_id for r in rules}
        assert "ASTR-P001" in rule_ids
        assert "ASTR-P002" in rule_ids
        assert "ASTR-P003" in rule_ids
        assert "ASTR-P004" in rule_ids
