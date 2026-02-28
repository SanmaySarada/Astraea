"""Tests for LC (Laboratory Conventional) domain generation.

Validates LB -> LC column renaming, DOMAIN assignment, 1:1 pairing,
unit conversion warning, mapping spec generation, and FDAB-LC01
validation rule.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.lc_domain import (
    LC_DOMAIN_DEFINITION,
    generate_lc_from_lb,
    generate_lc_mapping_spec,
    get_lb_to_lc_rename_map,
)
from astraea.models.mapping import (
    ConfidenceLevel,
    CoreDesignation,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)
from astraea.validation.rules.fda_business import FDABLC01Rule


@pytest.fixture()
def sample_lb_df() -> pd.DataFrame:
    """Create a sample LB DataFrame for testing."""
    return pd.DataFrame({
        "STUDYID": ["STUDY01", "STUDY01", "STUDY01"],
        "DOMAIN": ["LB", "LB", "LB"],
        "USUBJID": ["STUDY01-001", "STUDY01-001", "STUDY01-002"],
        "LBSEQ": [1, 2, 1],
        "LBTESTCD": ["ALB", "ALP", "ALB"],
        "LBTEST": ["Albumin", "Alkaline Phosphatase", "Albumin"],
        "LBORRES": ["4.2", "85", "3.8"],
        "LBORRESU": ["g/dL", "U/L", "g/dL"],
        "LBSTRESC": ["4.2", "85", "3.8"],
        "LBSTRESN": [4.2, 85.0, 3.8],
        "LBSTRESU": ["g/dL", "U/L", "g/dL"],
        "LBBLFL": ["Y", "", "Y"],
        "VISITNUM": [1, 1, 1],
        "VISIT": ["Screening", "Screening", "Screening"],
    })


@pytest.fixture()
def sample_lb_spec() -> DomainMappingSpec:
    """Create a sample LB mapping spec for testing."""
    mappings = [
        VariableMapping(
            sdtm_variable="STUDYID",
            sdtm_label="Study Identifier",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            mapping_pattern=MappingPattern.ASSIGN,
            mapping_logic="Assign study ID",
            assigned_value="STUDY01",
            confidence=1.0,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Constant assignment",
            origin=VariableOrigin.ASSIGNED,
        ),
        VariableMapping(
            sdtm_variable="LBTESTCD",
            sdtm_label="Lab Test or Examination Short Name",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            mapping_pattern=MappingPattern.DIRECT,
            mapping_logic="Direct from source",
            source_variable="LBTESTCD",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Direct mapping",
            origin=VariableOrigin.CRF,
        ),
        VariableMapping(
            sdtm_variable="LBORRES",
            sdtm_label="Result or Finding in Original Units",
            sdtm_data_type="Char",
            core=CoreDesignation.EXP,
            mapping_pattern=MappingPattern.DIRECT,
            mapping_logic="Direct from source",
            source_variable="LBORRES",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Direct mapping",
            origin=VariableOrigin.CRF,
        ),
    ]
    return DomainMappingSpec(
        domain="LB",
        domain_label="Laboratory Test Results",
        domain_class="Findings",
        structure="One record per subject per visit per lab test per time point",
        study_id="STUDY01",
        source_datasets=["lab_results.sas7bdat"],
        variable_mappings=mappings,
        total_variables=3,
        required_mapped=2,
        expected_mapped=1,
        high_confidence_count=3,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00Z",
        model_used="claude-sonnet-4-20250514",
    )


# --- get_lb_to_lc_rename_map tests ---


class TestGetLbToLcRenameMap:
    """Tests for the column rename mapping builder."""

    def test_basic_lb_columns_renamed(self) -> None:
        columns = ["LBTESTCD", "LBTEST", "LBORRES", "LBORRESU", "LBSEQ"]
        result = get_lb_to_lc_rename_map(columns)
        assert result == {
            "LBTESTCD": "LCTESTCD",
            "LBTEST": "LCTEST",
            "LBORRES": "LCORRES",
            "LBORRESU": "LCORRESU",
            "LBSEQ": "LCSEQ",
        }

    def test_common_columns_not_renamed(self) -> None:
        columns = ["STUDYID", "DOMAIN", "USUBJID", "VISITNUM", "VISIT", "EPOCH"]
        result = get_lb_to_lc_rename_map(columns)
        assert result == {}

    def test_mixed_columns(self) -> None:
        columns = ["STUDYID", "LBTESTCD", "USUBJID", "LBORRES"]
        result = get_lb_to_lc_rename_map(columns)
        assert "STUDYID" not in result
        assert "USUBJID" not in result
        assert result["LBTESTCD"] == "LCTESTCD"
        assert result["LBORRES"] == "LCORRES"

    def test_empty_columns(self) -> None:
        result = get_lb_to_lc_rename_map([])
        assert result == {}

    def test_lbblfl_renamed(self) -> None:
        """LBBLFL should be renamed to LCBLFL."""
        columns = ["LBBLFL"]
        result = get_lb_to_lc_rename_map(columns)
        assert result == {"LBBLFL": "LCBLFL"}


# --- generate_lc_from_lb tests ---


class TestGenerateLcFromLb:
    """Tests for the LC domain generator."""

    def test_basic_column_renaming(self, sample_lb_df: pd.DataFrame) -> None:
        lc_df, _ = generate_lc_from_lb(sample_lb_df, "STUDY01")
        assert "LCTESTCD" in lc_df.columns
        assert "LCTEST" in lc_df.columns
        assert "LCORRES" in lc_df.columns
        assert "LCORRESU" in lc_df.columns
        assert "LCSEQ" in lc_df.columns
        # LB-prefixed columns should be gone
        assert "LBTESTCD" not in lc_df.columns
        assert "LBTEST" not in lc_df.columns

    def test_domain_set_to_lc(self, sample_lb_df: pd.DataFrame) -> None:
        lc_df, _ = generate_lc_from_lb(sample_lb_df, "STUDY01")
        assert (lc_df["DOMAIN"] == "LC").all()

    def test_lcseq_matches_lbseq(self, sample_lb_df: pd.DataFrame) -> None:
        lc_df, _ = generate_lc_from_lb(sample_lb_df, "STUDY01")
        assert list(lc_df["LCSEQ"]) == list(sample_lb_df["LBSEQ"])

    def test_row_count_matches(self, sample_lb_df: pd.DataFrame) -> None:
        lc_df, _ = generate_lc_from_lb(sample_lb_df, "STUDY01")
        assert len(lc_df) == len(sample_lb_df)

    def test_common_columns_not_renamed(self, sample_lb_df: pd.DataFrame) -> None:
        lc_df, _ = generate_lc_from_lb(sample_lb_df, "STUDY01")
        assert "STUDYID" in lc_df.columns
        assert "USUBJID" in lc_df.columns
        assert "VISITNUM" in lc_df.columns
        assert "VISIT" in lc_df.columns

    def test_warning_generated_when_no_unit_conversion(
        self, sample_lb_df: pd.DataFrame
    ) -> None:
        _, warnings = generate_lc_from_lb(sample_lb_df, "STUDY01")
        assert len(warnings) == 1
        assert "Unit conversion" in warnings[0]
        assert "not performed" in warnings[0]

    def test_no_warning_when_unit_conversion_true(
        self, sample_lb_df: pd.DataFrame
    ) -> None:
        _, warnings = generate_lc_from_lb(
            sample_lb_df, "STUDY01", unit_conversion=True
        )
        assert len(warnings) == 0

    def test_empty_lb_produces_empty_lc(self) -> None:
        empty_lb = pd.DataFrame(
            columns=["STUDYID", "DOMAIN", "USUBJID", "LBTESTCD", "LBSEQ"]
        )
        lc_df, warnings = generate_lc_from_lb(empty_lb, "STUDY01")
        assert lc_df.empty
        assert "LCTESTCD" in lc_df.columns
        assert "LCSEQ" in lc_df.columns
        assert len(warnings) == 0  # No warning for empty DF

    def test_attrs_flag_set_false(self, sample_lb_df: pd.DataFrame) -> None:
        lc_df, _ = generate_lc_from_lb(sample_lb_df, "STUDY01")
        assert lc_df.attrs.get("lc_unit_conversion_performed") is False

    def test_attrs_flag_set_true(self, sample_lb_df: pd.DataFrame) -> None:
        lc_df, _ = generate_lc_from_lb(
            sample_lb_df, "STUDY01", unit_conversion=True
        )
        assert lc_df.attrs.get("lc_unit_conversion_performed") is True

    def test_data_values_preserved(self, sample_lb_df: pd.DataFrame) -> None:
        """LC data values should be identical to LB (no conversion in v1)."""
        lc_df, _ = generate_lc_from_lb(sample_lb_df, "STUDY01")
        assert list(lc_df["LCORRES"]) == list(sample_lb_df["LBORRES"])
        assert list(lc_df["LCORRESU"]) == list(sample_lb_df["LBORRESU"])


# --- generate_lc_mapping_spec tests ---


class TestGenerateLcMappingSpec:
    """Tests for LC mapping spec generation from LB spec."""

    def test_domain_set_to_lc(self, sample_lb_spec: DomainMappingSpec) -> None:
        lc_spec = generate_lc_mapping_spec(sample_lb_spec)
        assert lc_spec.domain == "LC"

    def test_domain_label(self, sample_lb_spec: DomainMappingSpec) -> None:
        lc_spec = generate_lc_mapping_spec(sample_lb_spec)
        assert lc_spec.domain_label == "Laboratory Test Results - Conventional Units"

    def test_variable_names_renamed(self, sample_lb_spec: DomainMappingSpec) -> None:
        lc_spec = generate_lc_mapping_spec(sample_lb_spec)
        var_names = [vm.sdtm_variable for vm in lc_spec.variable_mappings]
        assert "LCTESTCD" in var_names
        assert "LCORRES" in var_names
        # Non-LB prefixed should remain unchanged
        assert "STUDYID" in var_names

    def test_study_id_preserved(self, sample_lb_spec: DomainMappingSpec) -> None:
        lc_spec = generate_lc_mapping_spec(sample_lb_spec)
        assert lc_spec.study_id == sample_lb_spec.study_id

    def test_counts_preserved(self, sample_lb_spec: DomainMappingSpec) -> None:
        lc_spec = generate_lc_mapping_spec(sample_lb_spec)
        assert lc_spec.total_variables == sample_lb_spec.total_variables
        assert lc_spec.required_mapped == sample_lb_spec.required_mapped

    def test_serialization_roundtrip(
        self, sample_lb_spec: DomainMappingSpec
    ) -> None:
        lc_spec = generate_lc_mapping_spec(sample_lb_spec)
        json_str = lc_spec.model_dump_json()
        restored = DomainMappingSpec.model_validate_json(json_str)
        assert restored.domain == "LC"
        assert len(restored.variable_mappings) == len(lc_spec.variable_mappings)


# --- LC domain definition tests ---


class TestLCDomainDefinition:
    """Tests for the LC domain definition constant."""

    def test_domain_code(self) -> None:
        assert LC_DOMAIN_DEFINITION["domain"] == "LC"

    def test_domain_class(self) -> None:
        assert LC_DOMAIN_DEFINITION["domain_class"] == "Findings"

    def test_has_required_keys(self) -> None:
        required = {"domain", "domain_label", "domain_class", "structure"}
        assert required.issubset(LC_DOMAIN_DEFINITION.keys())


# --- FDAB-LC01 validation rule tests ---


class TestFDABLC01Rule:
    """Tests for the FDAB-LC01 validation rule."""

    @pytest.fixture()
    def rule(self) -> FDABLC01Rule:
        return FDABLC01Rule()

    @pytest.fixture()
    def mock_spec(self) -> DomainMappingSpec:
        return DomainMappingSpec(
            domain="LC",
            domain_label="Laboratory Test Results - Conventional Units",
            domain_class="Findings",
            structure="One record per subject per visit per lab test per time point",
            study_id="STUDY01",
            variable_mappings=[],
            total_variables=0,
            required_mapped=0,
            expected_mapped=0,
            high_confidence_count=0,
            medium_confidence_count=0,
            low_confidence_count=0,
            mapping_timestamp="2026-02-28T00:00:00Z",
            model_used="test",
        )

    def test_fires_warning_for_unconverted_lc(
        self,
        rule: FDABLC01Rule,
        mock_spec: DomainMappingSpec,
    ) -> None:
        lc_df = pd.DataFrame({
            "LCORRES": ["4.2", "85"],
            "LCORRESU": ["g/dL", "U/L"],
        })
        lc_df.attrs["lc_unit_conversion_performed"] = False

        from astraea.reference.controlled_terms import CTReference
        from astraea.reference.sdtm_ig import SDTMReference

        sdtm_ref = SDTMReference()
        ct_ref = CTReference()

        results = rule.evaluate("LC", lc_df, mock_spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB-LC01"
        assert results[0].severity.value == "WARNING"
        assert "SDTCG v5.7" in results[0].message
        assert "not performed" in results[0].message

    def test_no_warning_when_conversion_performed(
        self,
        rule: FDABLC01Rule,
        mock_spec: DomainMappingSpec,
    ) -> None:
        lc_df = pd.DataFrame({
            "LCORRES": ["42", "85"],
            "LCORRESU": ["mg/L", "U/L"],
        })
        lc_df.attrs["lc_unit_conversion_performed"] = True

        from astraea.reference.controlled_terms import CTReference
        from astraea.reference.sdtm_ig import SDTMReference

        sdtm_ref = SDTMReference()
        ct_ref = CTReference()

        results = rule.evaluate("LC", lc_df, mock_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_skips_non_lc_domains(
        self,
        rule: FDABLC01Rule,
        mock_spec: DomainMappingSpec,
    ) -> None:
        lb_df = pd.DataFrame({"LBORRES": ["4.2"]})

        from astraea.reference.controlled_terms import CTReference
        from astraea.reference.sdtm_ig import SDTMReference

        sdtm_ref = SDTMReference()
        ct_ref = CTReference()

        results = rule.evaluate("LB", lb_df, mock_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_default_attr_fires_warning(
        self,
        rule: FDABLC01Rule,
        mock_spec: DomainMappingSpec,
    ) -> None:
        """When attr is missing, should default to False and fire warning."""
        lc_df = pd.DataFrame({"LCORRES": ["4.2"]})
        # No attrs set -- should default to False

        from astraea.reference.controlled_terms import CTReference
        from astraea.reference.sdtm_ig import SDTMReference

        sdtm_ref = SDTMReference()
        ct_ref = CTReference()

        results = rule.evaluate("LC", lc_df, mock_spec, sdtm_ref, ct_ref)
        assert len(results) == 1
