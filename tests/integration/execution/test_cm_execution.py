"""End-to-end CM domain execution integration test.

Creates a synthetic CM mapping scenario (no real Fakedata dependency)
and verifies the full pipeline: spec + raw data -> SDTM DataFrame
with correct columns, partial date handling, and CT codelist recodes
for route, frequency, and dose unit.
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
def cm_spec() -> DomainMappingSpec:
    """CM domain spec with 12 variables covering ASSIGN, DIRECT, DERIVATION,
    LOOKUP_RECODE, and REFORMAT patterns."""
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
            assigned="CM",
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
            var="CMSEQ",
            pattern=MappingPattern.DERIVATION,
            label="Sequence Number",
            derivation="generate_seq",
            order=4,
        ),
        _mapping(
            var="CMTRT",
            pattern=MappingPattern.DIRECT,
            label="Reported Name of Drug, Med, or Therapy",
            source="CMTRT",
            order=5,
        ),
        _mapping(
            var="CMDOSE",
            pattern=MappingPattern.DIRECT,
            label="Dose per Administration",
            source="CMDOSE",
            order=6,
            core=CoreDesignation.PERM,
        ),
        _mapping(
            var="CMDOSU",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Dose Units",
            source="CMDOSU_STD",
            codelist="C71620",
            order=7,
            core=CoreDesignation.PERM,
        ),
        _mapping(
            var="CMROUTE",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Route of Administration",
            source="CMROUTE_STD",
            codelist="C66729",
            order=8,
            core=CoreDesignation.PERM,
        ),
        _mapping(
            var="CMDOSFRQ",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Dosing Frequency per Interval",
            source="CMDOSFRQ_STD",
            codelist="C71113",
            order=9,
            core=CoreDesignation.PERM,
        ),
        _mapping(
            var="CMSTDTC",
            pattern=MappingPattern.REFORMAT,
            label="Start Date/Time of Medication",
            source="CMSTDAT_RAW",
            derivation="parse_string_date_to_iso",
            order=10,
        ),
        _mapping(
            var="CMENDTC",
            pattern=MappingPattern.REFORMAT,
            label="End Date/Time of Medication",
            source="CMENDAT_RAW",
            derivation="parse_string_date_to_iso",
            order=11,
        ),
        _mapping(
            var="CMINDC",
            pattern=MappingPattern.DIRECT,
            label="Indication",
            source="CMINDC",
            order=12,
            core=CoreDesignation.PERM,
        ),
    ]
    return DomainMappingSpec(
        domain="CM",
        domain_label="Concomitant Medications",
        domain_class="Interventions",
        structure="One record per medication occurrence or constant-dosing interval per subject",
        study_id="PHA022121-C301",
        source_datasets=["cm.sas7bdat"],
        variable_mappings=mappings,
        total_variables=12,
        required_mapped=4,
        expected_mapped=0,
        high_confidence_count=12,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_cm_df() -> pd.DataFrame:
    """Raw CM data with 5 rows including partial dates and EDC columns."""
    return pd.DataFrame(
        {
            "Subject": ["001", "001", "002", "002", "003"],
            "SiteNumber": ["101", "101", "101", "101", "102"],
            "CMTRT": ["IBUPROFEN", "PARACETAMOL", "ASPIRIN", "LISINOPRIL", "METFORMIN"],
            "CMDOSE": ["400", "500", "325", "10", "500"],
            "CMDOSU_STD": ["mg", "mg", "mg", "mg", "mg"],
            "CMROUTE_STD": ["ORAL", "ORAL", "ORAL", "ORAL", "ORAL"],
            "CMDOSFRQ_STD": ["BID", "QD", "PRN", "QD", "BID"],
            "CMSTDAT_RAW": [
                "15 Jan 2022",
                "un UNK 2020",
                "01 Mar 2022",
                "un Jun 2019",
                "10 Apr 2022",
            ],
            "CMENDAT_RAW": ["30 Jun 2022", "", "15 Apr 2022", "", ""],
            "CMINDC": ["Headache", "Pain", "Cardioprotection", "Hypertension", "Diabetes"],
            "projectid": [1, 1, 1, 1, 1],
        }
    )


class TestCMEndToEnd:
    """Integration tests for CM domain execution pipeline."""

    def _execute(
        self, cm_spec: DomainMappingSpec, raw_cm_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Helper to execute the CM spec and return the result."""
        sdtm_ref = load_sdtm_reference()
        ct_ref = load_ct_reference()
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        return executor.execute(
            cm_spec,
            {"cm": raw_cm_df},
            study_id="PHA022121-C301",
        )

    def test_output_has_correct_columns(
        self, cm_spec: DomainMappingSpec, raw_cm_df: pd.DataFrame
    ) -> None:
        """Output should have exactly the 12 mapped columns."""
        result = self._execute(cm_spec, raw_cm_df)
        expected_cols = {
            "STUDYID", "DOMAIN", "USUBJID", "CMSEQ",
            "CMTRT", "CMDOSE", "CMDOSU", "CMROUTE",
            "CMDOSFRQ", "CMSTDTC", "CMENDTC", "CMINDC",
        }
        assert set(result.columns) == expected_cols

    def test_five_rows_preserved(
        self, cm_spec: DomainMappingSpec, raw_cm_df: pd.DataFrame
    ) -> None:
        """All 5 rows from raw data should be preserved."""
        result = self._execute(cm_spec, raw_cm_df)
        assert len(result) == 5

    def test_cmtrt_direct_copy(
        self, cm_spec: DomainMappingSpec, raw_cm_df: pd.DataFrame
    ) -> None:
        """CMTRT should be a direct copy of the source column."""
        result = self._execute(cm_spec, raw_cm_df)
        expected = ["IBUPROFEN", "PARACETAMOL", "ASPIRIN", "LISINOPRIL", "METFORMIN"]
        # Sort by CMTRT to compare deterministically
        actual = sorted(result["CMTRT"].tolist())
        assert actual == sorted(expected)

    def test_partial_date_year_only(
        self, cm_spec: DomainMappingSpec, raw_cm_df: pd.DataFrame
    ) -> None:
        """Row with 'un UNK 2020' should produce CMSTDTC = '2020' (year-only partial)."""
        result = self._execute(cm_spec, raw_cm_df)
        # Find the PARACETAMOL row (which has the year-only date)
        paracetamol_rows = result[result["CMTRT"] == "PARACETAMOL"]
        assert len(paracetamol_rows) == 1
        cmstdtc = paracetamol_rows.iloc[0]["CMSTDTC"]
        assert cmstdtc == "2020"

    def test_partial_date_year_month(
        self, cm_spec: DomainMappingSpec, raw_cm_df: pd.DataFrame
    ) -> None:
        """Row with 'un Jun 2019' should produce CMSTDTC = '2019-06' (year-month partial)."""
        result = self._execute(cm_spec, raw_cm_df)
        # Find the LISINOPRIL row (which has the year-month date)
        lisinopril_rows = result[result["CMTRT"] == "LISINOPRIL"]
        assert len(lisinopril_rows) == 1
        cmstdtc = lisinopril_rows.iloc[0]["CMSTDTC"]
        assert cmstdtc == "2019-06"

    def test_full_date_converted(
        self, cm_spec: DomainMappingSpec, raw_cm_df: pd.DataFrame
    ) -> None:
        """Row with '15 Jan 2022' should produce CMSTDTC = '2022-01-15'."""
        result = self._execute(cm_spec, raw_cm_df)
        ibuprofen_rows = result[result["CMTRT"] == "IBUPROFEN"]
        assert len(ibuprofen_rows) == 1
        cmstdtc = ibuprofen_rows.iloc[0]["CMSTDTC"]
        assert cmstdtc == "2022-01-15"

    def test_route_recoded(
        self, cm_spec: DomainMappingSpec, raw_cm_df: pd.DataFrame
    ) -> None:
        """CMROUTE values should match C66729 submission values (ORAL -> ORAL)."""
        result = self._execute(cm_spec, raw_cm_df)
        route_values = set(result["CMROUTE"].dropna().unique())
        assert "ORAL" in route_values

    def test_frequency_recoded(
        self, cm_spec: DomainMappingSpec, raw_cm_df: pd.DataFrame
    ) -> None:
        """CMDOSFRQ values should include standard CT terms (BID, QD, PRN)."""
        result = self._execute(cm_spec, raw_cm_df)
        freq_values = set(result["CMDOSFRQ"].dropna().unique())
        assert freq_values <= {"BID", "QD", "PRN"}
        assert len(freq_values) == 3

    def test_cmseq_generated(
        self, cm_spec: DomainMappingSpec, raw_cm_df: pd.DataFrame
    ) -> None:
        """CMSEQ should be generated, with subject 001 having seq 1 and 2."""
        result = self._execute(cm_spec, raw_cm_df)
        assert "CMSEQ" in result.columns
        # Subject 001 (site 101) has 2 medications -> seq 1 and 2
        subj_001 = result[result["USUBJID"].str.endswith("001")]
        assert len(subj_001) == 2
        seq_values = sorted(subj_001["CMSEQ"].tolist())
        assert seq_values == [1, 2]

    def test_no_edc_columns(
        self, cm_spec: DomainMappingSpec, raw_cm_df: pd.DataFrame
    ) -> None:
        """EDC columns like 'projectid' should not appear in output."""
        result = self._execute(cm_spec, raw_cm_df)
        assert "projectid" not in result.columns
        assert "CMDOSU_STD" not in result.columns
        assert "CMROUTE_STD" not in result.columns
