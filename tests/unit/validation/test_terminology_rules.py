"""Tests for terminology validation rules (VAL-01).

Tests CTValueRule and DomainValueRule against synthetic DataFrames
with known CT violations and correct data.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.models.mapping import DomainMappingSpec, MappingPattern, VariableMapping
from astraea.models.sdtm import CoreDesignation
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.validation.rules.base import RuleCategory, RuleSeverity
from astraea.validation.rules.terminology import (
    CTValueRule,
    DomainValueRule,
    get_terminology_rules,
)


@pytest.fixture()
def sdtm_ref() -> SDTMReference:
    """Load real SDTM-IG reference."""
    return SDTMReference()


@pytest.fixture()
def ct_ref() -> CTReference:
    """Load real CT reference."""
    return CTReference()


def _make_spec(
    domain: str = "AE",
    mappings: list[VariableMapping] | None = None,
) -> DomainMappingSpec:
    """Build a minimal DomainMappingSpec for testing."""
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


def _make_mapping(
    var: str,
    codelist_code: str | None = None,
    pattern: MappingPattern = MappingPattern.DIRECT,
) -> VariableMapping:
    """Build a minimal VariableMapping for testing."""
    return VariableMapping(
        sdtm_variable=var,
        sdtm_label="Test Label",
        sdtm_data_type="Char",
        core=CoreDesignation.REQ,
        mapping_pattern=pattern,
        mapping_logic="Test",
        codelist_code=codelist_code,
        confidence=0.9,
        confidence_level="high",
        confidence_rationale="Test mapping",
    )


class TestCTValueRule:
    """Tests for CTValueRule (ASTR-T001)."""

    def test_rule_metadata(self) -> None:
        rule = CTValueRule()
        assert rule.rule_id == "ASTR-T001"
        assert rule.category == RuleCategory.TERMINOLOGY
        assert rule.severity == RuleSeverity.ERROR

    def test_valid_ct_values_no_findings(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Valid CT values should produce no findings."""
        # SEX codelist C66731 has "M", "F", "U", "UNDIFFERENTIATED"
        df = pd.DataFrame({"SEX": ["M", "F", "M", "U"]})
        spec = _make_spec(
            domain="DM",
            mappings=[_make_mapping("SEX", codelist_code="C66731")],
        )
        rule = CTValueRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_invalid_non_extensible_ct_error(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Invalid values in non-extensible codelist should be ERROR."""
        # SEX (C66731) is non-extensible; "MALE" is not a valid term
        df = pd.DataFrame({"SEX": ["M", "MALE", "F", "MALE"]})
        spec = _make_spec(
            domain="DM",
            mappings=[_make_mapping("SEX", codelist_code="C66731")],
        )
        rule = CTValueRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert results[0].variable == "SEX"
        assert results[0].affected_count == 2
        assert results[0].p21_equivalent == "SD0065"
        assert results[0].fix_suggestion is not None
        assert "MALE" in results[0].message

    def test_invalid_extensible_ct_warning(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Invalid values in extensible codelist should be WARNING."""
        # Find an extensible codelist in the reference
        extensible_code = None
        for code in ct_ref.list_codelists():
            cl = ct_ref.lookup_codelist(code)
            if cl and cl.extensible and len(cl.terms) > 0:
                extensible_code = code
                break

        if extensible_code is None:
            pytest.skip("No extensible codelist found in CT reference")

        cl = ct_ref.lookup_codelist(extensible_code)
        assert cl is not None  # for type checker
        var_name = cl.variable_mappings[0] if cl.variable_mappings else "TESTVAR"

        df = pd.DataFrame({var_name: ["COMPLETELY_INVALID_VALUE_XYZ"]})
        spec = _make_spec(
            domain="AE",
            mappings=[_make_mapping(var_name, codelist_code=extensible_code)],
        )
        rule = CTValueRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.WARNING
        # Extensible codelists should NOT have fix_suggestion
        assert results[0].fix_suggestion is None

    def test_no_codelist_code_skipped(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Variables without codelist_code should be skipped."""
        df = pd.DataFrame({"AETERM": ["Headache", "Nausea"]})
        spec = _make_spec(
            domain="AE",
            mappings=[_make_mapping("AETERM", codelist_code=None)],
        )
        rule = CTValueRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_missing_codelist_warning(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Unknown codelist code should produce a WARNING."""
        df = pd.DataFrame({"TESTVAR": ["A", "B"]})
        spec = _make_spec(
            domain="AE",
            mappings=[_make_mapping("TESTVAR", codelist_code="C99999_FAKE")],
        )
        rule = CTValueRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.WARNING
        assert "not found" in results[0].message

    def test_null_values_ignored(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Null values should not be validated against CT."""
        df = pd.DataFrame({"SEX": ["M", None, "F", None]})
        spec = _make_spec(
            domain="DM",
            mappings=[_make_mapping("SEX", codelist_code="C66731")],
        )
        rule = CTValueRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_variable_not_in_dataframe_skipped(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Variable in spec but not in DataFrame should be skipped."""
        df = pd.DataFrame({"OTHER": ["A"]})
        spec = _make_spec(
            domain="DM",
            mappings=[_make_mapping("SEX", codelist_code="C66731")],
        )
        rule = CTValueRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_all_values_empty_skipped(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """All-null column should be skipped."""
        df = pd.DataFrame({"SEX": [None, None]})
        spec = _make_spec(
            domain="DM",
            mappings=[_make_mapping("SEX", codelist_code="C66731")],
        )
        rule = CTValueRule()
        results = rule.evaluate("DM", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0


class TestDomainValueRule:
    """Tests for DomainValueRule (ASTR-T002)."""

    def test_rule_metadata(self) -> None:
        rule = DomainValueRule()
        assert rule.rule_id == "ASTR-T002"
        assert rule.category == RuleCategory.TERMINOLOGY

    def test_correct_domain_value(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Correct DOMAIN values should produce no findings."""
        df = pd.DataFrame({"DOMAIN": ["AE", "AE", "AE"]})
        spec = _make_spec(domain="AE")
        rule = DomainValueRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_wrong_domain_value(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Wrong DOMAIN values should produce ERROR."""
        df = pd.DataFrame({"DOMAIN": ["AE", "DM", "AE"]})
        spec = _make_spec(domain="AE")
        rule = DomainValueRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert results[0].affected_count == 1
        assert "'DM'" in results[0].message

    def test_missing_domain_column(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Missing DOMAIN column should produce ERROR."""
        df = pd.DataFrame({"USUBJID": ["SUBJ-001"]})
        spec = _make_spec(domain="AE")
        rule = DomainValueRule()
        results = rule.evaluate("AE", df, spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert "missing" in results[0].message


class TestGetTerminologyRules:
    """Tests for the get_terminology_rules factory."""

    def test_returns_all_rules(self) -> None:
        rules = get_terminology_rules()
        assert len(rules) == 2
        rule_ids = {r.rule_id for r in rules}
        assert "ASTR-T001" in rule_ids
        assert "ASTR-T002" in rule_ids
