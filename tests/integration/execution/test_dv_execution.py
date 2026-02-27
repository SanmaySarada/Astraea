"""End-to-end DV (Protocol Deviations) domain execution integration test.

Creates a synthetic DV mapping scenario with non-standard column names
(Subject_ID, Site_Number instead of Subject, SiteNumber). Validates that
custom site_col/subject_col parameters work correctly for USUBJID generation.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.executor import DatasetExecutor
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation
from astraea.reference import load_ct_reference


def _mapping(
    *,
    var: str,
    pattern: MappingPattern,
    label: str,
    source: str | None = None,
    assigned: str | None = None,
    derivation: str | None = None,
    codelist: str | None = None,
    order: int,
    core: CoreDesignation = CoreDesignation.REQ,
) -> VariableMapping:
    return VariableMapping(
        sdtm_variable=var,
        sdtm_label=label,
        sdtm_data_type="Char",
        core=core,
        source_variable=source,
        mapping_pattern=pattern,
        mapping_logic="test",
        assigned_value=assigned,
        derivation_rule=derivation,
        codelist_code=codelist,
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="test",
        order=order,
    )


@pytest.fixture()
def dv_spec() -> DomainMappingSpec:
    """DV domain spec with 8 variables."""
    mappings = [
        _mapping(
            var="STUDYID",
            pattern=MappingPattern.ASSIGN,
            label="Study Identifier",
            assigned="PHA022121-C301",
            order=1,
        ),
        _mapping(
            var="DOMAIN",
            pattern=MappingPattern.ASSIGN,
            label="Domain Abbreviation",
            assigned="DV",
            order=2,
        ),
        _mapping(
            var="USUBJID",
            pattern=MappingPattern.DERIVATION,
            label="Unique Subject Identifier",
            derivation="generate_usubjid",
            order=3,
        ),
        _mapping(
            var="DVSEQ",
            pattern=MappingPattern.DERIVATION,
            label="Sequence Number",
            derivation="generate_seq",
            order=4,
        ),
        _mapping(
            var="DVTERM",
            pattern=MappingPattern.DIRECT,
            label="Reported Term for the Protocol Deviation",
            source="Description",
            order=5,
        ),
        _mapping(
            var="DVDECOD",
            pattern=MappingPattern.DIRECT,
            label="Dictionary-Derived Term",
            source="Category",
            order=6,
        ),
        _mapping(
            var="DVCAT",
            pattern=MappingPattern.DIRECT,
            label="Category for Protocol Deviation",
            source="Category",
            order=7,
        ),
        _mapping(
            var="DVSTDTC",
            pattern=MappingPattern.REFORMAT,
            label="Start Date/Time of Deviation",
            source="Date_Occurred_RAW",
            derivation="parse_string_date_to_iso",
            order=8,
        ),
    ]
    return DomainMappingSpec(
        domain="DV",
        domain_label="Protocol Deviations",
        domain_class="Events",
        structure="One record per deviation per subject",
        study_id="PHA022121-C301",
        source_datasets=["dv.sas7bdat"],
        variable_mappings=mappings,
        total_variables=8,
        required_mapped=6,
        expected_mapped=1,
        high_confidence_count=8,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_dv_df() -> pd.DataFrame:
    """Raw DV data with non-standard column names (2 rows)."""
    return pd.DataFrame(
        {
            "Subject_ID": ["001", "002"],  # NOT "Subject"
            "Site_Number": ["101", "101"],  # NOT "SiteNumber"
            "Description": ["Missed visit Window 3", "Wrong dose administered"],
            "Category": ["VISIT WINDOW DEVIATION", "DOSING ERROR"],
            "Date_Occurred_RAW": ["15 Mar 2022", "20 Apr 2022"],
            "Deviation_Id": ["DV001", "DV002"],
        }
    )


class TestDVEndToEnd:
    def test_output_has_correct_columns(
        self,
        dv_spec: DomainMappingSpec,
        raw_dv_df: pd.DataFrame,
    ) -> None:
        """Output should have exactly the 8 mapped columns."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dv_spec,
            {"dv": raw_dv_df},
            study_id="PHA022121-C301",
            site_col="Site_Number",
            subject_col="Subject_ID",
        )
        expected_cols = {
            "STUDYID",
            "DOMAIN",
            "USUBJID",
            "DVSEQ",
            "DVTERM",
            "DVDECOD",
            "DVCAT",
            "DVSTDTC",
        }
        assert set(result.columns) == expected_cols

    def test_two_rows_preserved(
        self,
        dv_spec: DomainMappingSpec,
        raw_dv_df: pd.DataFrame,
    ) -> None:
        """Both deviation rows should be in output."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dv_spec,
            {"dv": raw_dv_df},
            study_id="PHA022121-C301",
            site_col="Site_Number",
            subject_col="Subject_ID",
        )
        assert len(result) == 2

    def test_usubjid_from_custom_columns(
        self,
        dv_spec: DomainMappingSpec,
        raw_dv_df: pd.DataFrame,
    ) -> None:
        """USUBJID should be correctly generated from Subject_ID + Site_Number."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dv_spec,
            {"dv": raw_dv_df},
            study_id="PHA022121-C301",
            site_col="Site_Number",
            subject_col="Subject_ID",
        )
        # USUBJID format: STUDYID-SITEID-SUBJID
        usubjids = set(result["USUBJID"].values)
        assert "PHA022121-C301-101-001" in usubjids
        assert "PHA022121-C301-101-002" in usubjids

    def test_dvterm_from_description(
        self,
        dv_spec: DomainMappingSpec,
        raw_dv_df: pd.DataFrame,
    ) -> None:
        """DVTERM should contain values from the Description column."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dv_spec,
            {"dv": raw_dv_df},
            study_id="PHA022121-C301",
            site_col="Site_Number",
            subject_col="Subject_ID",
        )
        expected_terms = {"Missed visit Window 3", "Wrong dose administered"}
        assert set(result["DVTERM"].values) == expected_terms

    def test_dvcat_from_category(
        self,
        dv_spec: DomainMappingSpec,
        raw_dv_df: pd.DataFrame,
    ) -> None:
        """DVCAT should contain values from the Category column."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dv_spec,
            {"dv": raw_dv_df},
            study_id="PHA022121-C301",
            site_col="Site_Number",
            subject_col="Subject_ID",
        )
        expected_cats = {"VISIT WINDOW DEVIATION", "DOSING ERROR"}
        assert set(result["DVCAT"].values) == expected_cats

    def test_dates_converted(
        self,
        dv_spec: DomainMappingSpec,
        raw_dv_df: pd.DataFrame,
    ) -> None:
        """DVSTDTC should be in ISO 8601 format."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dv_spec,
            {"dv": raw_dv_df},
            study_id="PHA022121-C301",
            site_col="Site_Number",
            subject_col="Subject_ID",
        )
        dates = set(result["DVSTDTC"].dropna().values)
        assert "2022-03-15" in dates
        assert "2022-04-20" in dates

    def test_dvseq_generated(
        self,
        dv_spec: DomainMappingSpec,
        raw_dv_df: pd.DataFrame,
    ) -> None:
        """DVSEQ should be present with values starting at 1."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dv_spec,
            {"dv": raw_dv_df},
            study_id="PHA022121-C301",
            site_col="Site_Number",
            subject_col="Subject_ID",
        )
        assert "DVSEQ" in result.columns
        for _, group in result.groupby("USUBJID"):
            seqs = sorted(group["DVSEQ"].dropna().tolist())
            assert seqs[0] == 1

    def test_no_raw_columns_leak(
        self,
        dv_spec: DomainMappingSpec,
        raw_dv_df: pd.DataFrame,
    ) -> None:
        """Raw columns like Subject_ID, Site_Number, Deviation_Id should NOT leak."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dv_spec,
            {"dv": raw_dv_df},
            study_id="PHA022121-C301",
            site_col="Site_Number",
            subject_col="Subject_ID",
        )
        assert "Subject_ID" not in result.columns
        assert "Site_Number" not in result.columns
        assert "Deviation_Id" not in result.columns
