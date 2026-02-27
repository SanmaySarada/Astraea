"""End-to-end AE domain execution integration test.

Creates a synthetic AE mapping scenario (no real Fakedata dependency)
and verifies the full pipeline: spec + raw data -> SDTM DataFrame
with correct columns, order, checkbox 0/1->Y/N conversion, MedDRA
term mapping, CT codelist recodes, date conversion, and --SEQ generation.
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
from astraea.reference import load_ct_reference, load_sdtm_reference


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
def ae_spec() -> DomainMappingSpec:
    """AE domain spec with 17 variables covering all Event-class patterns."""
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
            assigned="AE",
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
            var="AESEQ",
            pattern=MappingPattern.DERIVATION,
            label="Sequence Number",
            derivation="generate_seq",
            order=4,
        ),
        _mapping(
            var="AETERM",
            pattern=MappingPattern.DIRECT,
            label="Reported Term for the Adverse Event",
            source="AETERM",
            order=5,
        ),
        _mapping(
            var="AEDECOD",
            pattern=MappingPattern.RENAME,
            label="Dictionary-Derived Term",
            source="AETERM_PT",
            order=6,
        ),
        _mapping(
            var="AEBODSYS",
            pattern=MappingPattern.RENAME,
            label="Body System or Organ Class",
            source="AETERM_SOC",
            order=7,
        ),
        _mapping(
            var="AESEV",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Severity/Intensity",
            source="AESEV_STD",
            codelist="C66769",
            order=8,
        ),
        _mapping(
            var="AESER",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Serious Event",
            source="AESER_STD",
            codelist="C66742",
            order=9,
        ),
        _mapping(
            var="AEACN",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Action Taken with Study Treatment",
            source="AEACN_STD",
            codelist="C66767",
            order=10,
        ),
        _mapping(
            var="AEREL",
            pattern=MappingPattern.DIRECT,
            label="Causality",
            source="AEREL_STD",
            order=11,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="AEOUT",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Outcome of Adverse Event",
            source="AEOUT_STD",
            codelist="C66768",
            order=12,
        ),
        _mapping(
            var="AESDTH",
            pattern=MappingPattern.REFORMAT,
            label="Results in Death",
            source="AESDTH",
            derivation="numeric_to_yn",
            order=13,
        ),
        _mapping(
            var="AESLIFE",
            pattern=MappingPattern.REFORMAT,
            label="Is Life Threatening",
            source="AESLIFE",
            derivation="numeric_to_yn",
            order=14,
        ),
        _mapping(
            var="AESHOSP",
            pattern=MappingPattern.REFORMAT,
            label="Requires or Prolongs Hospitalization",
            source="AESHOSP",
            derivation="numeric_to_yn",
            order=15,
        ),
        _mapping(
            var="AESTDTC",
            pattern=MappingPattern.REFORMAT,
            label="Start Date/Time of Adverse Event",
            source="AESTDAT_RAW",
            derivation="parse_string_date_to_iso",
            order=16,
        ),
        _mapping(
            var="AEENDTC",
            pattern=MappingPattern.REFORMAT,
            label="End Date/Time of Adverse Event",
            source="AEENDAT_RAW",
            derivation="parse_string_date_to_iso",
            order=17,
        ),
    ]
    return DomainMappingSpec(
        domain="AE",
        domain_label="Adverse Events",
        domain_class="Events",
        structure="One record per adverse event per subject",
        study_id="PHA022121-C301",
        source_datasets=["ae.sas7bdat"],
        variable_mappings=mappings,
        total_variables=17,
        required_mapped=12,
        expected_mapped=1,
        high_confidence_count=17,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_ae_df() -> pd.DataFrame:
    """Raw AE data with 4 synthetic adverse event rows."""
    return pd.DataFrame(
        {
            "Subject": ["001", "001", "002", "003"],
            "SiteNumber": ["101", "101", "101", "102"],
            "AETERM": ["Headache", "Nausea", "Fatigue", "Dizziness"],
            "AETERM_PT": ["Headache", "Nausea", "Fatigue", "Dizziness"],
            "AETERM_SOC": [
                "Nervous system disorders",
                "Gastrointestinal disorders",
                "General disorders",
                "Nervous system disorders",
            ],
            "AESEV_STD": ["MILD", "MODERATE", "MILD", "SEVERE"],
            "AESER_STD": ["N", "N", "N", "Y"],
            "AEACN_STD": [
                "DOSE NOT CHANGED",
                "DOSE NOT CHANGED",
                "DOSE NOT CHANGED",
                "DRUG WITHDRAWN",
            ],
            "AEREL_STD": [
                "POSSIBLY RELATED",
                "NOT RELATED",
                "RELATED",
                "POSSIBLY RELATED",
            ],
            "AEOUT_STD": [
                "RECOVERED/RESOLVED",
                "RECOVERED/RESOLVED",
                "NOT RECOVERED/NOT RESOLVED",
                "RECOVERING/RESOLVING",
            ],
            "AESDTH": [0.0, 0.0, 0.0, 0.0],
            "AESLIFE": [0.0, 0.0, 0.0, 1.0],
            "AESHOSP": [0.0, 0.0, 0.0, 1.0],
            "AESTDAT_RAW": ["15 Jan 2022", "20 Feb 2022", "01 Mar 2022", "10 Apr 2022"],
            "AEENDAT_RAW": ["18 Jan 2022", "25 Feb 2022", "", ""],
            # EDC system columns that should be filtered out
            "projectid": [1, 1, 1, 1],
            "instanceId": [10, 11, 20, 30],
        }
    )


@pytest.fixture()
def ae_executor() -> DatasetExecutor:
    """Executor with both SDTM and CT references loaded."""
    return DatasetExecutor(
        sdtm_ref=load_sdtm_reference(),
        ct_ref=load_ct_reference(),
    )


class TestAEEndToEnd:
    def test_output_has_correct_columns(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """Output should have exactly the 17 mapped SDTM variables."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        expected_cols = {
            "STUDYID", "DOMAIN", "USUBJID", "AESEQ",
            "AETERM", "AEDECOD", "AEBODSYS",
            "AESEV", "AESER", "AEACN", "AEREL", "AEOUT",
            "AESDTH", "AESLIFE", "AESHOSP",
            "AESTDTC", "AEENDTC",
        }
        assert set(result.columns) == expected_cols

    def test_studyid_constant(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """STUDYID should be the assigned constant for all rows."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        assert all(result["STUDYID"] == "PHA022121-C301")

    def test_domain_is_ae(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """DOMAIN should be 'AE' for all rows."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        assert all(result["DOMAIN"] == "AE")

    def test_aeterm_direct_copy(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """AETERM should be a direct copy of the raw AETERM column."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        assert list(result["AETERM"]) == ["Headache", "Nausea", "Fatigue", "Dizziness"]

    def test_aedecod_from_pt(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """AEDECOD should come from AETERM_PT (MedDRA Preferred Term)."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        assert list(result["AEDECOD"]) == ["Headache", "Nausea", "Fatigue", "Dizziness"]

    def test_aebodsys_from_soc(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """AEBODSYS should come from AETERM_SOC (MedDRA System Organ Class)."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        assert list(result["AEBODSYS"]) == [
            "Nervous system disorders",
            "Gastrointestinal disorders",
            "General disorders",
            "Nervous system disorders",
        ]

    def test_seriousness_yn_conversion(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """Seriousness checkbox 0/1 should convert to N/Y via numeric_to_yn."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        # AESDTH: all 0.0 -> all "N"
        assert list(result["AESDTH"]) == ["N", "N", "N", "N"]
        # AESLIFE: row 3 is 1.0 -> "Y", rest "N"
        assert list(result["AESLIFE"]) == ["N", "N", "N", "Y"]
        # AESHOSP: row 3 is 1.0 -> "Y", rest "N"
        assert list(result["AESHOSP"]) == ["N", "N", "N", "Y"]

    def test_severity_recoded(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """AESEV should contain valid C66769 submission values."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        severity_values = set(result["AESEV"].dropna().unique())
        assert severity_values == {"MILD", "MODERATE", "SEVERE"}

    def test_outcome_recoded(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """AEOUT should contain valid C66768 submission values."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        outcome_values = set(result["AEOUT"].dropna().unique())
        valid_outcomes = {
            "RECOVERED/RESOLVED",
            "RECOVERING/RESOLVING",
            "NOT RECOVERED/NOT RESOLVED",
        }
        assert outcome_values == valid_outcomes

    def test_dates_converted_to_iso(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """Date columns should be converted to ISO 8601 format."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        assert result["AESTDTC"].iloc[0] == "2022-01-15"
        assert result["AESTDTC"].iloc[1] == "2022-02-20"
        assert result["AESTDTC"].iloc[2] == "2022-03-01"
        assert result["AESTDTC"].iloc[3] == "2022-04-10"
        # End dates: first two have values, last two are empty
        assert result["AEENDTC"].iloc[0] == "2022-01-18"
        assert result["AEENDTC"].iloc[1] == "2022-02-25"

    def test_no_edc_columns_leak(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """EDC system columns should not appear in output."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        assert "projectid" not in result.columns
        assert "instanceId" not in result.columns

    def test_columns_in_sdtm_order(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """Columns should follow SDTM-IG order (by mapping order field)."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        cols = list(result.columns)
        assert cols.index("STUDYID") < cols.index("DOMAIN")
        assert cols.index("DOMAIN") < cols.index("USUBJID")
        assert cols.index("USUBJID") < cols.index("AESEQ")
        assert cols.index("AESEQ") < cols.index("AETERM")
        assert cols.index("AETERM") < cols.index("AEDECOD")
        assert cols.index("AESTDTC") < cols.index("AEENDTC")

    def test_aeseq_generated(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """AESEQ should be present and monotonically increasing per USUBJID."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        assert "AESEQ" in result.columns
        # Subject 001 has 2 AEs -> seq 1, 2
        subj_001 = result[result["USUBJID"].str.endswith("001")]
        assert len(subj_001) == 2
        seq_values = list(subj_001["AESEQ"])
        assert seq_values == sorted(seq_values)
        assert seq_values[0] == 1

    def test_four_rows_preserved(
        self,
        ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame,
        ae_executor: DatasetExecutor,
    ) -> None:
        """All 4 AE records from raw data should be in output."""
        result = ae_executor.execute(ae_spec, {"ae": raw_ae_df}, study_id="PHA022121-C301")
        assert len(result) == 4
