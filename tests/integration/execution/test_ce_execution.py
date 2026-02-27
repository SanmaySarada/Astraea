"""End-to-end CE (Clinical Events) domain execution integration test.

Creates a synthetic CE mapping scenario with HAE attack events, testing
assigned category/prespecified flags, LOOKUP_RECODE for Y/N codelist,
and date conversion.
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
def ce_spec() -> DomainMappingSpec:
    """CE domain spec with 11 variables including assigned and recode patterns."""
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
            assigned="CE",
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
            var="CESEQ",
            pattern=MappingPattern.DERIVATION,
            label="Sequence Number",
            derivation="generate_seq",
            order=4,
        ),
        _mapping(
            var="CETERM",
            pattern=MappingPattern.DIRECT,
            label="Reported Term for the Clinical Event",
            source="CETERM",
            order=5,
        ),
        _mapping(
            var="CEDECOD",
            pattern=MappingPattern.DIRECT,
            label="Dictionary-Derived Term",
            source="CEDECOD",
            order=6,
        ),
        _mapping(
            var="CECAT",
            pattern=MappingPattern.ASSIGN,
            label="Category for Clinical Event",
            assigned="HAE ATTACK",
            order=7,
        ),
        _mapping(
            var="CEPRESP",
            pattern=MappingPattern.ASSIGN,
            label="Clinical Event Pre-Specified",
            assigned="Y",
            order=8,
            core=CoreDesignation.PERM,
        ),
        _mapping(
            var="CEOCCUR",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Clinical Event Occurrence",
            source="CEOCCUR_STD",
            codelist="C66742",
            order=9,
            core=CoreDesignation.PERM,
        ),
        _mapping(
            var="CESTDTC",
            pattern=MappingPattern.REFORMAT,
            label="Start Date/Time of Clinical Event",
            source="CESTDAT_RAW",
            derivation="parse_string_date_to_iso",
            order=10,
        ),
        _mapping(
            var="CEENDTC",
            pattern=MappingPattern.REFORMAT,
            label="End Date/Time of Clinical Event",
            source="CEENDAT_RAW",
            derivation="parse_string_date_to_iso",
            order=11,
        ),
    ]
    return DomainMappingSpec(
        domain="CE",
        domain_label="Clinical Events",
        domain_class="Events",
        structure="One record per event per subject",
        study_id="PHA022121-C301",
        source_datasets=["ce.sas7bdat"],
        variable_mappings=mappings,
        total_variables=11,
        required_mapped=6,
        expected_mapped=3,
        high_confidence_count=11,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_ce_df() -> pd.DataFrame:
    """Raw CE data with 4 HAE attack events."""
    return pd.DataFrame(
        {
            "Subject": ["001", "001", "002", "003"],
            "SiteNumber": ["101", "101", "101", "102"],
            "CETERM": [
                "HAE Attack - Abdominal",
                "HAE Attack - Peripheral",
                "HAE Attack - Laryngeal",
                "HAE Attack - Facial",
            ],
            "CEDECOD": ["HAE ATTACK", "HAE ATTACK", "HAE ATTACK", "HAE ATTACK"],
            "CEOCCUR_STD": ["Y", "Y", "Y", "N"],
            "CESTDAT_RAW": ["10 Jan 2022", "05 Feb 2022", "20 Jan 2022", ""],
            "CEENDAT_RAW": ["12 Jan 2022", "07 Feb 2022", "22 Jan 2022", ""],
            "projectid": [1, 1, 1, 1],
        }
    )


class TestCEEndToEnd:
    def test_output_has_correct_columns(
        self,
        ce_spec: DomainMappingSpec,
        raw_ce_df: pd.DataFrame,
    ) -> None:
        """Output should have exactly the 11 mapped columns."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ce_spec,
            {"ce": raw_ce_df},
            study_id="PHA022121-C301",
        )
        expected_cols = {
            "STUDYID",
            "DOMAIN",
            "USUBJID",
            "CESEQ",
            "CETERM",
            "CEDECOD",
            "CECAT",
            "CEPRESP",
            "CEOCCUR",
            "CESTDTC",
            "CEENDTC",
        }
        assert set(result.columns) == expected_cols

    def test_four_rows_preserved(
        self,
        ce_spec: DomainMappingSpec,
        raw_ce_df: pd.DataFrame,
    ) -> None:
        """All 4 event rows should be in output."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ce_spec,
            {"ce": raw_ce_df},
            study_id="PHA022121-C301",
        )
        assert len(result) == 4

    def test_cecat_assigned(
        self,
        ce_spec: DomainMappingSpec,
        raw_ce_df: pd.DataFrame,
    ) -> None:
        """All CECAT values should be the assigned constant 'HAE ATTACK'."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ce_spec,
            {"ce": raw_ce_df},
            study_id="PHA022121-C301",
        )
        assert all(result["CECAT"] == "HAE ATTACK")

    def test_cepresp_assigned(
        self,
        ce_spec: DomainMappingSpec,
        raw_ce_df: pd.DataFrame,
    ) -> None:
        """All CEPRESP values should be the assigned constant 'Y'."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ce_spec,
            {"ce": raw_ce_df},
            study_id="PHA022121-C301",
        )
        assert all(result["CEPRESP"] == "Y")

    def test_ceoccur_recoded(
        self,
        ce_spec: DomainMappingSpec,
        raw_ce_df: pd.DataFrame,
    ) -> None:
        """CEOCCUR should be recoded via C66742 to Y/N values."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ce_spec,
            {"ce": raw_ce_df},
            study_id="PHA022121-C301",
        )
        valid_values = {"Y", "N"}
        occur_values = set(result["CEOCCUR"].dropna().unique())
        assert occur_values <= valid_values

    def test_dates_converted(
        self,
        ce_spec: DomainMappingSpec,
        raw_ce_df: pd.DataFrame,
    ) -> None:
        """CESTDTC should be in ISO 8601 format for non-empty dates."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ce_spec,
            {"ce": raw_ce_df},
            study_id="PHA022121-C301",
        )
        non_empty_dates = result["CESTDTC"].dropna()
        non_empty_dates = non_empty_dates[non_empty_dates != ""]
        assert len(non_empty_dates) >= 3
        # "10 Jan 2022" -> "2022-01-10"
        assert "2022-01-10" in non_empty_dates.values

    def test_ceseq_generated(
        self,
        ce_spec: DomainMappingSpec,
        raw_ce_df: pd.DataFrame,
    ) -> None:
        """CESEQ should be present and monotonic per USUBJID."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            ce_spec,
            {"ce": raw_ce_df},
            study_id="PHA022121-C301",
        )
        assert "CESEQ" in result.columns
        for _, group in result.groupby("USUBJID"):
            seqs = sorted(group["CESEQ"].dropna().tolist())
            assert seqs[0] == 1
