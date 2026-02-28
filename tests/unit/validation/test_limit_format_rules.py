"""Tests for limit and format validation rules (VAL-04, VAL-05).

Tests VariableNameLengthRule, VariableLabelLengthRule, CharacterLengthRule,
DatasetSizeRule, DateFormatRule, ASCIIRule, and FileNamingRule.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.models.mapping import DomainMappingSpec, MappingPattern, VariableMapping
from astraea.models.sdtm import CoreDesignation
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.validation.rules.base import RuleCategory, RuleSeverity
from astraea.validation.rules.format import (
    ASCIIRule,
    DateFormatRule,
    FileNamingRule,
    get_format_rules,
)
from astraea.validation.rules.limits import (
    CharacterLengthRule,
    DatasetSizeRule,
    VariableLabelLengthRule,
    VariableNameLengthRule,
    get_limit_rules,
)


@pytest.fixture()
def sdtm_ref() -> SDTMReference:
    return SDTMReference()


@pytest.fixture()
def ct_ref() -> CTReference:
    return CTReference()


def _make_mapping(
    var: str,
    label: str = "Test Label",
) -> VariableMapping:
    return VariableMapping(
        sdtm_variable=var,
        sdtm_label=label,
        sdtm_data_type="Char",
        core=CoreDesignation.REQ,
        mapping_pattern=MappingPattern.DIRECT,
        mapping_logic="Test",
        confidence=0.9,
        confidence_level="high",
        confidence_rationale="Test",
    )


def _make_spec(
    domain: str = "AE",
    mappings: list[VariableMapping] | None = None,
) -> DomainMappingSpec:
    vm = mappings or []
    return DomainMappingSpec(
        domain=domain,
        domain_label="Test Domain",
        domain_class="Events",
        structure="One record per event",
        study_id="TEST-001",
        source_datasets=["test.sas7bdat"],
        variable_mappings=vm,
        total_variables=len(vm),
        required_mapped=0,
        expected_mapped=0,
        high_confidence_count=0,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


# === VAL-04: Limit Rules ===


class TestVariableNameLengthRule:
    """Tests for VariableNameLengthRule (ASTR-L001)."""

    def test_rule_metadata(self) -> None:
        rule = VariableNameLengthRule()
        assert rule.rule_id == "ASTR-L001"
        assert rule.category == RuleCategory.LIMIT
        assert rule.severity == RuleSeverity.ERROR

    def test_valid_names_no_findings(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AETERM": ["x"], "AEDECOD": ["y"], "SEX": ["M"]})
        spec = _make_spec()
        rule = VariableNameLengthRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_long_name_error(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"TOOLONGNAME": ["x"], "AETERM": ["y"]})
        spec = _make_spec()
        rule = VariableNameLengthRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert results[0].variable == "TOOLONGNAME"
        assert results[0].p21_equivalent == "SD0006"

    def test_exactly_8_chars_valid(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AESTDTC1": ["x"]})  # 8 chars
        spec = _make_spec()
        rule = VariableNameLengthRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0


class TestVariableLabelLengthRule:
    """Tests for VariableLabelLengthRule (ASTR-L002)."""

    def test_rule_metadata(self) -> None:
        rule = VariableLabelLengthRule()
        assert rule.rule_id == "ASTR-L002"
        assert rule.category == RuleCategory.LIMIT

    def test_valid_labels_no_findings(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        spec = _make_spec(mappings=[_make_mapping("AETERM", "Adverse Event Term")])
        df = pd.DataFrame({"AETERM": ["x"]})
        rule = VariableLabelLengthRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_long_label_error(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        long_label = "A" * 41
        spec = _make_spec(mappings=[_make_mapping("AETERM", long_label)])
        df = pd.DataFrame({"AETERM": ["x"]})
        rule = VariableLabelLengthRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert results[0].variable == "AETERM"

    def test_exactly_40_chars_valid(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        label_40 = "A" * 40
        spec = _make_spec(mappings=[_make_mapping("AETERM", label_40)])
        df = pd.DataFrame({"AETERM": ["x"]})
        rule = VariableLabelLengthRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0


class TestCharacterLengthRule:
    """Tests for CharacterLengthRule (ASTR-L003)."""

    def test_rule_metadata(self) -> None:
        rule = CharacterLengthRule()
        assert rule.rule_id == "ASTR-L003"

    def test_short_values_no_findings(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AETERM": ["Headache", "Nausea"]})
        spec = _make_spec()
        rule = CharacterLengthRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_long_values_error(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        long_val = "X" * 201
        df = pd.DataFrame({"AETERM": [long_val, "Short"]})
        spec = _make_spec()
        rule = CharacterLengthRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert results[0].affected_count == 1

    def test_numeric_columns_skipped(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AESTDY": [1, 2, 3]})
        spec = _make_spec()
        rule = CharacterLengthRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_null_only_column_skipped(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AETERM": pd.Series([None, None], dtype="object")})
        spec = _make_spec()
        rule = CharacterLengthRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0


class TestDatasetSizeRule:
    """Tests for DatasetSizeRule (ASTR-L004)."""

    def test_rule_metadata(self) -> None:
        rule = DatasetSizeRule()
        assert rule.rule_id == "ASTR-L004"
        assert rule.severity == RuleSeverity.NOTICE

    def test_small_dataset_no_findings(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AETERM": ["Headache"] * 10})
        spec = _make_spec()
        rule = DatasetSizeRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0


# === VAL-05: Format Rules ===


class TestDateFormatRule:
    """Tests for DateFormatRule (ASTR-F001)."""

    def test_rule_metadata(self) -> None:
        rule = DateFormatRule()
        assert rule.rule_id == "ASTR-F001"
        assert rule.category == RuleCategory.FORMAT
        assert rule.severity == RuleSeverity.ERROR

    def test_valid_iso8601_full(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AESTDTC": ["2022-03-30T14:30:00"]})
        spec = _make_spec()
        rule = DateFormatRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_valid_iso8601_date_only(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AESTDTC": ["2022-03-30"]})
        spec = _make_spec()
        rule = DateFormatRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_valid_iso8601_partial_year_month(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AESTDTC": ["2022-03"]})
        spec = _make_spec()
        rule = DateFormatRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_valid_iso8601_year_only(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AESTDTC": ["2022"]})
        spec = _make_spec()
        rule = DateFormatRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_invalid_date_format_error(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AESTDTC": ["30-Mar-2022", "2022-03-30"]})
        spec = _make_spec()
        rule = DateFormatRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert results[0].affected_count == 1
        assert results[0].p21_equivalent == "SD0020"

    def test_non_dtc_columns_skipped(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AETERM": ["30-Mar-2022"]})
        spec = _make_spec()
        rule = DateFormatRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_null_dates_skipped(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AESTDTC": [None, "2022-03-30", None]})
        spec = _make_spec()
        rule = DateFormatRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_multiple_dtc_columns(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({
            "AESTDTC": ["BAD_DATE"],
            "AEENDTC": ["ALSO_BAD"],
        })
        spec = _make_spec()
        rule = DateFormatRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 2


class TestASCIIRule:
    """Tests for ASCIIRule (ASTR-F002)."""

    def test_rule_metadata(self) -> None:
        rule = ASCIIRule()
        assert rule.rule_id == "ASTR-F002"
        assert rule.severity == RuleSeverity.WARNING

    def test_ascii_only_no_findings(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AETERM": ["Headache", "Nausea"]})
        spec = _make_spec()
        rule = ASCIIRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_non_ascii_warning(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"AETERM": ["Headache", "Na\u00fcsea"]})
        spec = _make_spec()
        rule = ASCIIRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.WARNING
        assert results[0].variable == "AETERM"
        assert "fix_common_non_ascii" in (results[0].fix_suggestion or "")


class TestFileNamingRule:
    """Tests for FileNamingRule (ASTR-F003)."""

    def test_rule_metadata(self) -> None:
        rule = FileNamingRule()
        assert rule.rule_id == "ASTR-F003"
        assert rule.category == RuleCategory.FORMAT

    def test_valid_domain_code(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"STUDYID": ["TEST"]})
        spec = _make_spec(domain="AE")
        rule = FileNamingRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_invalid_domain_code_with_numbers(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"STUDYID": ["TEST"]})
        spec = _make_spec(domain="A1")
        rule = FileNamingRule()
        results = rule.evaluate("A1", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR

    def test_too_short_domain_code(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        df = pd.DataFrame({"STUDYID": ["TEST"]})
        spec = _make_spec(domain="A")
        rule = FileNamingRule()
        results = rule.evaluate("A", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1

    def test_suppqual_domain_valid(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """SUPPAE, SUPPDM etc should be valid (2-8 alpha)."""
        df = pd.DataFrame({"STUDYID": ["TEST"]})
        spec = _make_spec(domain="SUPPAE")
        rule = FileNamingRule()
        results = rule.evaluate("SUPPAE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0


# === Factory function tests ===


class TestGetLimitRules:
    def test_returns_all_rules(self) -> None:
        rules = get_limit_rules()
        assert len(rules) == 4
        ids = {r.rule_id for r in rules}
        assert "ASTR-L001" in ids
        assert "ASTR-L002" in ids
        assert "ASTR-L003" in ids
        assert "ASTR-L004" in ids


class TestGetFormatRules:
    def test_returns_all_rules(self) -> None:
        rules = get_format_rules()
        assert len(rules) == 3
        ids = {r.rule_id for r in rules}
        assert "ASTR-F001" in ids
        assert "ASTR-F002" in ids
        assert "ASTR-F003" in ids
