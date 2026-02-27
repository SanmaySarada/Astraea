"""End-to-end MH (Medical History) domain execution integration test.

Creates a synthetic MH mapping scenario with two source files (mh + haemh)
and verifies multi-source merge, MedDRA term mapping, partial date handling,
and correct sequence generation.
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
def mh_spec() -> DomainMappingSpec:
    """MH domain spec with 8 variables including MedDRA terms."""
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
            assigned="MH",
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
            var="MHSEQ",
            pattern=MappingPattern.DERIVATION,
            label="Sequence Number",
            derivation="generate_seq",
            order=4,
        ),
        _mapping(
            var="MHTERM",
            pattern=MappingPattern.DIRECT,
            label="Reported Term for the Medical History",
            source="MHTERM",
            order=5,
        ),
        _mapping(
            var="MHDECOD",
            pattern=MappingPattern.RENAME,
            label="Dictionary-Derived Term",
            source="MHTERM_PT",
            order=6,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="MHBODSYS",
            pattern=MappingPattern.RENAME,
            label="Body System or Organ Class",
            source="MHTERM_SOC",
            order=7,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="MHSTDTC",
            pattern=MappingPattern.REFORMAT,
            label="Start Date/Time of Medical History Event",
            source="MHSTDAT_RAW",
            derivation="parse_string_date_to_iso",
            order=8,
            core=CoreDesignation.EXP,
        ),
    ]
    return DomainMappingSpec(
        domain="MH",
        domain_label="Medical History",
        domain_class="Events",
        structure="One record per medical history event per subject",
        study_id="PHA022121-C301",
        source_datasets=["mh.sas7bdat", "haemh.sas7bdat"],
        variable_mappings=mappings,
        total_variables=8,
        required_mapped=5,
        expected_mapped=3,
        high_confidence_count=8,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def mh_df() -> pd.DataFrame:
    """General medical history source data (3 rows)."""
    return pd.DataFrame(
        {
            "Subject": ["001", "002", "003"],
            "SiteNumber": ["101", "101", "102"],
            "MHTERM": ["Hypertension", "Type 2 diabetes", "Asthma"],
            "MHTERM_PT": ["Hypertension", "Type 2 diabetes mellitus", "Asthma"],
            "MHTERM_SOC": [
                "Vascular disorders",
                "Metabolism disorders",
                "Respiratory disorders",
            ],
            "MHSTDAT_RAW": ["un UNK 2015", "01 Jan 2010", "un Mar 2018"],
            "projectid": [1, 1, 1],
        }
    )


@pytest.fixture()
def haemh_df() -> pd.DataFrame:
    """HAE-specific medical history source data (2 rows)."""
    return pd.DataFrame(
        {
            "Subject": ["001", "002"],
            "SiteNumber": ["101", "101"],
            "MHTERM": ["HAE Type I", "HAE Type II"],
            "MHTERM_PT": [
                "Hereditary angioedema type I",
                "Hereditary angioedema type II",
            ],
            "MHTERM_SOC": ["Immune system disorders", "Immune system disorders"],
            "MHSTDAT_RAW": ["un UNK 2005", "un UNK 2010"],
            "projectid": [1, 1],
        }
    )


class TestMHEndToEnd:
    def test_five_rows_from_two_sources(
        self,
        mh_spec: DomainMappingSpec,
        mh_df: pd.DataFrame,
        haemh_df: pd.DataFrame,
    ) -> None:
        """Merging mh (3 rows) + haemh (2 rows) should produce 5 rows."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            mh_spec,
            {"mh": mh_df, "haemh": haemh_df},
            study_id="PHA022121-C301",
        )
        assert len(result) == 5

    def test_mhdecod_from_pt(
        self,
        mh_spec: DomainMappingSpec,
        mh_df: pd.DataFrame,
        haemh_df: pd.DataFrame,
    ) -> None:
        """MHDECOD should contain MedDRA Preferred Terms from MHTERM_PT."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            mh_spec,
            {"mh": mh_df, "haemh": haemh_df},
            study_id="PHA022121-C301",
        )
        expected_pts = {
            "Hypertension",
            "Type 2 diabetes mellitus",
            "Asthma",
            "Hereditary angioedema type I",
            "Hereditary angioedema type II",
        }
        assert set(result["MHDECOD"].values) == expected_pts

    def test_mhbodsys_from_soc(
        self,
        mh_spec: DomainMappingSpec,
        mh_df: pd.DataFrame,
        haemh_df: pd.DataFrame,
    ) -> None:
        """MHBODSYS should contain SOC values from MHTERM_SOC."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            mh_spec,
            {"mh": mh_df, "haemh": haemh_df},
            study_id="PHA022121-C301",
        )
        expected_socs = {
            "Vascular disorders",
            "Metabolism disorders",
            "Respiratory disorders",
            "Immune system disorders",
        }
        assert set(result["MHBODSYS"].values) == expected_socs

    def test_partial_date_year_only(
        self,
        mh_spec: DomainMappingSpec,
        mh_df: pd.DataFrame,
        haemh_df: pd.DataFrame,
    ) -> None:
        """Dates like 'un UNK 2015' should produce year-only ISO: '2015'."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            mh_spec,
            {"mh": mh_df, "haemh": haemh_df},
            study_id="PHA022121-C301",
        )
        # Find the row with Hypertension (from mh_df, "un UNK 2015")
        hyp_rows = result[result["MHTERM"] == "Hypertension"]
        assert len(hyp_rows) == 1
        assert hyp_rows.iloc[0]["MHSTDTC"] == "2015"

    def test_partial_date_year_month(
        self,
        mh_spec: DomainMappingSpec,
        mh_df: pd.DataFrame,
        haemh_df: pd.DataFrame,
    ) -> None:
        """Dates like 'un Mar 2018' should produce year-month ISO: '2018-03'."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            mh_spec,
            {"mh": mh_df, "haemh": haemh_df},
            study_id="PHA022121-C301",
        )
        asthma_rows = result[result["MHTERM"] == "Asthma"]
        assert len(asthma_rows) == 1
        assert asthma_rows.iloc[0]["MHSTDTC"] == "2018-03"

    def test_mhseq_generated(
        self,
        mh_spec: DomainMappingSpec,
        mh_df: pd.DataFrame,
        haemh_df: pd.DataFrame,
    ) -> None:
        """MHSEQ should be present and monotonic per USUBJID."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            mh_spec,
            {"mh": mh_df, "haemh": haemh_df},
            study_id="PHA022121-C301",
        )
        assert "MHSEQ" in result.columns
        # Each USUBJID should have sequential values starting from 1
        for _, group in result.groupby("USUBJID"):
            seqs = sorted(group["MHSEQ"].dropna().tolist())
            assert seqs[0] == 1
            # Values should be monotonically increasing
            for i in range(1, len(seqs)):
                assert seqs[i] > seqs[i - 1]

    def test_columns_correct(
        self,
        mh_spec: DomainMappingSpec,
        mh_df: pd.DataFrame,
        haemh_df: pd.DataFrame,
    ) -> None:
        """Output should have exactly the 8 mapped columns."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            mh_spec,
            {"mh": mh_df, "haemh": haemh_df},
            study_id="PHA022121-C301",
        )
        expected_cols = {
            "STUDYID",
            "DOMAIN",
            "USUBJID",
            "MHSEQ",
            "MHTERM",
            "MHDECOD",
            "MHBODSYS",
            "MHSTDTC",
        }
        assert set(result.columns) == expected_cols
