"""End-to-end IE (Inclusion/Exclusion Criteria Not Met) domain execution test.

Creates a synthetic IE mapping scenario proving that Findings-class domains
work correctly without transpose. IE records criteria violations with
test codes, categories, and results.
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
def ie_spec() -> DomainMappingSpec:
    """IE domain spec with 10 variables (Findings-class, no transpose)."""
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
            assigned="IE",
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
            var="IESEQ",
            pattern=MappingPattern.DERIVATION,
            label="Sequence Number",
            derivation="generate_seq",
            order=4,
        ),
        _mapping(
            var="IETESTCD",
            pattern=MappingPattern.DIRECT,
            label="Incl/Excl Criterion Short Name",
            source="IETESTCD",
            order=5,
        ),
        _mapping(
            var="IETEST",
            pattern=MappingPattern.DIRECT,
            label="Incl/Excl Criterion",
            source="IETEST",
            order=6,
        ),
        _mapping(
            var="IECAT",
            pattern=MappingPattern.DIRECT,
            label="Incl/Excl Category",
            source="IECAT",
            order=7,
        ),
        _mapping(
            var="IEORRES",
            pattern=MappingPattern.DIRECT,
            label="Incl/Excl Criterion Original Result",
            source="IEORRES",
            order=8,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="IESTRESC",
            pattern=MappingPattern.DIRECT,
            label="Incl/Excl Criterion Result in Std Format",
            source="IESTRESC",
            order=9,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="IEDTC",
            pattern=MappingPattern.REFORMAT,
            label="Date/Time of Collection",
            source="IEDTC_RAW",
            derivation="parse_string_date_to_iso",
            order=10,
            core=CoreDesignation.EXP,
        ),
    ]
    return DomainMappingSpec(
        domain="IE",
        domain_label="Inclusion/Exclusion Criteria Not Met",
        domain_class="Findings",
        structure="One record per inclusion/exclusion criterion not met per subject",
        study_id="PHA022121-C301",
        source_datasets=["ie.sas7bdat"],
        variable_mappings=mappings,
        total_variables=10,
        required_mapped=7,
        expected_mapped=3,
        high_confidence_count=10,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_ie_df() -> pd.DataFrame:
    """Raw IE data with 3 rows of criteria violations."""
    return pd.DataFrame(
        {
            "Subject": ["002", "003", "003"],
            "SiteNumber": ["101", "102", "102"],
            "IETESTCD": ["INCL01", "EXCL03", "INCL05"],
            "IETEST": [
                "Age >= 18 years",
                "No active hepatitis B",
                "Adequate renal function",
            ],
            "IECAT": ["INCLUSION", "EXCLUSION", "INCLUSION"],
            "IEORRES": ["Y", "N", "Y"],
            "IESTRESC": ["Y", "N", "Y"],
            "IEDTC_RAW": ["15 Dec 2021", "10 Dec 2021", "10 Dec 2021"],
            "projectid": [1, 1, 1],
        }
    )


class TestIEEndToEnd:
    def test_output_has_correct_columns(
        self,
        ie_spec: DomainMappingSpec,
        raw_ie_df: pd.DataFrame,
    ) -> None:
        """Output should have exactly the 10 mapped columns."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ie_spec,
            {"ie": raw_ie_df},
            study_id="PHA022121-C301",
        )
        expected_cols = {
            "STUDYID",
            "DOMAIN",
            "USUBJID",
            "IESEQ",
            "IETESTCD",
            "IETEST",
            "IECAT",
            "IEORRES",
            "IESTRESC",
            "IEDTC",
        }
        assert set(result.columns) == expected_cols

    def test_three_rows_preserved(
        self,
        ie_spec: DomainMappingSpec,
        raw_ie_df: pd.DataFrame,
    ) -> None:
        """All 3 criteria violation rows should be in output."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ie_spec,
            {"ie": raw_ie_df},
            study_id="PHA022121-C301",
        )
        assert len(result) == 3

    def test_ietestcd_values(
        self,
        ie_spec: DomainMappingSpec,
        raw_ie_df: pd.DataFrame,
    ) -> None:
        """IETESTCD should have the expected criterion codes."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ie_spec,
            {"ie": raw_ie_df},
            study_id="PHA022121-C301",
        )
        expected_codes = {"INCL01", "EXCL03", "INCL05"}
        assert set(result["IETESTCD"].values) == expected_codes

    def test_iecat_values(
        self,
        ie_spec: DomainMappingSpec,
        raw_ie_df: pd.DataFrame,
    ) -> None:
        """IECAT should include both INCLUSION and EXCLUSION categories."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ie_spec,
            {"ie": raw_ie_df},
            study_id="PHA022121-C301",
        )
        cats = set(result["IECAT"].values)
        assert "INCLUSION" in cats
        assert "EXCLUSION" in cats

    def test_dates_converted(
        self,
        ie_spec: DomainMappingSpec,
        raw_ie_df: pd.DataFrame,
    ) -> None:
        """IEDTC should be in ISO 8601 format."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ie_spec,
            {"ie": raw_ie_df},
            study_id="PHA022121-C301",
        )
        # "15 Dec 2021" -> "2021-12-15", "10 Dec 2021" -> "2021-12-10"
        dates = set(result["IEDTC"].dropna().values)
        assert "2021-12-15" in dates
        assert "2021-12-10" in dates

    def test_ieseq_generated(
        self,
        ie_spec: DomainMappingSpec,
        raw_ie_df: pd.DataFrame,
    ) -> None:
        """IESEQ should be present and start at 1 per USUBJID."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ie_spec,
            {"ie": raw_ie_df},
            study_id="PHA022121-C301",
        )
        assert "IESEQ" in result.columns
        for _, group in result.groupby("USUBJID"):
            seqs = sorted(group["IESEQ"].dropna().tolist())
            assert seqs[0] == 1

    def test_findings_class_domain(
        self,
        ie_spec: DomainMappingSpec,
        raw_ie_df: pd.DataFrame,
    ) -> None:
        """Proves Findings-class works without transpose -- row count matches input."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ie_spec,
            {"ie": raw_ie_df},
            study_id="PHA022121-C301",
        )
        # No transpose means 3 input rows -> 3 output rows (not multiplied)
        assert len(result) == 3
        # All expected result columns present (Findings-specific: ORRES, STRESC)
        assert "IEORRES" in result.columns
        assert "IESTRESC" in result.columns
