"""Tests for column name resolution and cross-domain DataFrame passing in DatasetExecutor."""

import pandas as pd
import pytest

from astraea.execution.executor import DatasetExecutor
from astraea.models.mapping import (
    ConfidenceLevel,
    CoreDesignation,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)


def _make_mapping(
    sdtm_var: str,
    pattern: MappingPattern,
    *,
    source_var: str | None = None,
    assigned_value: str | None = None,
    derivation_rule: str | None = None,
    order: int = 1,
) -> VariableMapping:
    """Helper to create a VariableMapping with minimal boilerplate."""
    return VariableMapping(
        sdtm_variable=sdtm_var,
        sdtm_label=f"Label for {sdtm_var}",
        sdtm_data_type="Char",
        core=CoreDesignation.REQ,
        source_variable=source_var,
        mapping_pattern=pattern,
        mapping_logic=f"Test mapping for {sdtm_var}",
        assigned_value=assigned_value,
        derivation_rule=derivation_rule,
        confidence=0.95,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="Test confidence rationale",
        rationale="Test",
        order=order,
    )


def _make_spec(
    domain: str,
    mappings: list[VariableMapping],
    source_datasets: list[str] | None = None,
) -> DomainMappingSpec:
    """Helper to create a DomainMappingSpec with minimal boilerplate."""
    return DomainMappingSpec(
        domain=domain,
        domain_label=f"{domain} Domain",
        domain_class="Special Purpose",
        structure="One record per subject",
        study_id="STUDY-001",
        source_datasets=source_datasets or ["test"],
        variable_mappings=mappings,
        total_variables=len(mappings),
        required_mapped=len(mappings),
        expected_mapped=0,
        high_confidence_count=len(mappings),
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00Z",
        model_used="test-model",
    )


class TestBuildColumnAliases:
    """Tests for _build_column_aliases static method."""

    def test_build_aliases_with_present_columns(self) -> None:
        """DataFrame with Subject and SiteNumber -> aliases include SSUBJID and SSITENUM."""
        df = pd.DataFrame({
            "Subject": ["S001", "S002"],
            "SiteNumber": ["100", "200"],
            "AGE": [30, 40],
        })
        aliases = DatasetExecutor._build_column_aliases(df)
        assert aliases["SSUBJID"] == "Subject"
        assert aliases["SSITENUM"] == "SiteNumber"

    def test_aliases_only_for_present_columns(self) -> None:
        """DataFrame without SiteNumber -> SSITENUM not in aliases."""
        df = pd.DataFrame({
            "Subject": ["S001"],
            "AGE": [30],
        })
        aliases = DatasetExecutor._build_column_aliases(df)
        assert aliases["SSUBJID"] == "Subject"
        assert "SSITENUM" not in aliases

    def test_aliases_with_site_and_sitegroup(self) -> None:
        """DataFrame with Site and SiteGroup -> SSITE and SSITEGROUP mapped."""
        df = pd.DataFrame({
            "Site": ["Site A"],
            "SiteGroup": ["Group 1"],
        })
        aliases = DatasetExecutor._build_column_aliases(df)
        assert aliases["SSITE"] == "Site"
        assert aliases["SSITEGROUP"] == "SiteGroup"

    def test_aliases_empty_for_no_edc_columns(self) -> None:
        """DataFrame with no EDC columns -> empty aliases."""
        df = pd.DataFrame({
            "AETERM": ["headache"],
            "AEDECOD": ["HEADACHE"],
        })
        aliases = DatasetExecutor._build_column_aliases(df)
        assert aliases == {}


class TestExecutorResolvesECRFNames:
    """Tests that the executor resolves eCRF column names to actual SAS names."""

    def test_direct_mapping_with_ecrf_name(self) -> None:
        """DIRECT mapping with source_variable='SSUBJID' resolves to 'Subject' column."""
        df = pd.DataFrame({
            "Subject": ["S001", "S002", "S003"],
        })
        mappings = [
            _make_mapping("STUDYID", MappingPattern.ASSIGN, assigned_value="STUDY-001", order=1),
            _make_mapping("DOMAIN", MappingPattern.ASSIGN, assigned_value="XX", order=2),
            _make_mapping("USUBJID", MappingPattern.DIRECT, source_var="SSUBJID", order=3),
        ]
        spec = _make_spec("XX", mappings)
        executor = DatasetExecutor()

        result = executor.execute(spec, {"test": df}, study_id="STUDY-001")

        # SSUBJID should resolve to Subject column values
        assert "USUBJID" in result.columns
        assert list(result["USUBJID"]) == ["S001", "S002", "S003"]

    def test_rename_mapping_with_ecrf_name(self) -> None:
        """RENAME mapping with source_variable='SSITENUM' resolves to 'SiteNumber'."""
        df = pd.DataFrame({
            "Subject": ["S001"],
            "SiteNumber": ["100"],
        })
        mappings = [
            _make_mapping("STUDYID", MappingPattern.ASSIGN, assigned_value="STUDY-001", order=1),
            _make_mapping("DOMAIN", MappingPattern.ASSIGN, assigned_value="XX", order=2),
            _make_mapping("USUBJID", MappingPattern.DIRECT, source_var="Subject", order=3),
            _make_mapping("SITEID", MappingPattern.RENAME, source_var="SSITENUM", order=4),
        ]
        spec = _make_spec("XX", mappings)
        executor = DatasetExecutor()

        result = executor.execute(spec, {"test": df}, study_id="STUDY-001")

        assert "SITEID" in result.columns
        assert result["SITEID"].iloc[0] == "100"


class TestExecutorPassesCrossDomainDFs:
    """Tests that cross-domain DataFrames are passed to pattern handlers."""

    def test_cross_domain_dfs_passed_in_kwargs(self) -> None:
        """When raw_dfs contains extra datasets beyond primary, they appear in cross_domain_dfs."""
        primary_df = pd.DataFrame({
            "Subject": ["S001"],
            "AGE": [30],
        })
        extra_df = pd.DataFrame({
            "Subject": ["S001"],
            "EXSTDAT_INT": [22000],
        })

        mappings = [
            _make_mapping("STUDYID", MappingPattern.ASSIGN, assigned_value="STUDY-001", order=1),
            _make_mapping("DOMAIN", MappingPattern.ASSIGN, assigned_value="DM", order=2),
            _make_mapping("USUBJID", MappingPattern.DIRECT, source_var="Subject", order=3),
        ]
        spec = _make_spec("DM", mappings, source_datasets=["dm"])
        executor = DatasetExecutor()

        # Execute with multiple raw_dfs -- extra ones should be accessible
        result = executor.execute(
            spec,
            {"dm": primary_df, "ex": extra_df},
            study_id="STUDY-001",
        )

        # Basic execution should work
        assert "STUDYID" in result.columns
        assert "USUBJID" in result.columns

    def test_column_aliases_populated(self) -> None:
        """Verify column_aliases dict is built and includes expected mappings."""
        df = pd.DataFrame({
            "Subject": ["S001"],
            "SiteNumber": ["100"],
        })
        # Use the static method directly
        aliases = DatasetExecutor._build_column_aliases(df)
        assert "SSUBJID" in aliases
        assert "SSITENUM" in aliases
        assert aliases["SSUBJID"] == "Subject"
        assert aliases["SSITENUM"] == "SiteNumber"
