"""End-to-end PE (Physical Examination) domain execution test.

Creates a synthetic PE mapping scenario with minimal CRF data
(performed flag + date only). PE is the simplest Findings domain
in this study -- it records whether a physical exam was performed
and the collection date, without individual body system findings.
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
def pe_spec() -> DomainMappingSpec:
    """PE domain spec -- minimal Findings-class domain (performed + date)."""
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
            assigned="PE",
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
            var="PESEQ",
            pattern=MappingPattern.DERIVATION,
            label="Sequence Number",
            derivation="generate_seq",
            order=4,
        ),
        _mapping(
            var="PETESTCD",
            pattern=MappingPattern.ASSIGN,
            label="PE Test Short Name",
            assigned="PEPERF",
            order=5,
        ),
        _mapping(
            var="PETEST",
            pattern=MappingPattern.ASSIGN,
            label="PE Test Name",
            assigned="Physical Exam Performed",
            order=6,
        ),
        _mapping(
            var="PEORRES",
            pattern=MappingPattern.DIRECT,
            label="Result or Finding in Original Units",
            source="PEPERF",
            order=7,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="PEDTC",
            pattern=MappingPattern.REFORMAT,
            label="Date/Time of Collection",
            source="PEDAT_RAW",
            derivation="parse_string_date_to_iso",
            order=8,
            core=CoreDesignation.EXP,
        ),
    ]
    return DomainMappingSpec(
        domain="PE",
        domain_label="Physical Examination",
        domain_class="Findings",
        structure="One record per body system per visit per subject",
        study_id="PHA022121-C301",
        source_datasets=["pe.sas7bdat"],
        variable_mappings=mappings,
        total_variables=8,
        required_mapped=6,
        expected_mapped=2,
        high_confidence_count=8,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_pe_df() -> pd.DataFrame:
    """Synthetic PE data: 4 rows, 2 subjects, 2 visits each."""
    return pd.DataFrame(
        {
            "Subject": ["001", "001", "002", "002"],
            "SiteNumber": ["101", "101", "101", "102"],
            "PEPERF": ["Y", "Y", "Y", "Y"],
            "PEDAT_RAW": [
                "15 Jan 2022",
                "15 Apr 2022",
                "20 Jan 2022",
                "20 Apr 2022",
            ],
            # EDC system column
            "projectid": [1, 1, 1, 1],
        }
    )


class TestPEEndToEnd:
    def test_pe_basic_execution(
        self,
        pe_spec: DomainMappingSpec,
        raw_pe_df: pd.DataFrame,
    ) -> None:
        """Execute PE spec, verify 4 rows with correct columns."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            pe_spec,
            {"pe": raw_pe_df},
            study_id="PHA022121-C301",
        )
        assert len(result) == 4
        expected_cols = {
            "STUDYID",
            "DOMAIN",
            "USUBJID",
            "PESEQ",
            "PETESTCD",
            "PETEST",
            "PEORRES",
            "PEDTC",
        }
        assert set(result.columns) == expected_cols

    def test_pe_seq_generation(
        self,
        pe_spec: DomainMappingSpec,
        raw_pe_df: pd.DataFrame,
    ) -> None:
        """PESEQ should be unique per USUBJID."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            pe_spec,
            {"pe": raw_pe_df},
            study_id="PHA022121-C301",
        )
        assert "PESEQ" in result.columns
        for _, group in result.groupby("USUBJID"):
            seqs = sorted(group["PESEQ"].dropna().tolist())
            # Should start at 1 and be unique
            assert seqs[0] == 1
            assert len(seqs) == len(set(seqs))

    def test_pe_domain_assign(
        self,
        pe_spec: DomainMappingSpec,
        raw_pe_df: pd.DataFrame,
    ) -> None:
        """DOMAIN should be 'PE' for all rows."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            pe_spec,
            {"pe": raw_pe_df},
            study_id="PHA022121-C301",
        )
        assert all(result["DOMAIN"] == "PE")

    def test_pe_column_order(
        self,
        pe_spec: DomainMappingSpec,
        raw_pe_df: pd.DataFrame,
    ) -> None:
        """Columns should be in spec order."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            pe_spec,
            {"pe": raw_pe_df},
            study_id="PHA022121-C301",
        )
        cols = list(result.columns)
        assert cols.index("STUDYID") < cols.index("DOMAIN")
        assert cols.index("DOMAIN") < cols.index("USUBJID")
        assert cols.index("USUBJID") < cols.index("PESEQ")
        assert cols.index("PESEQ") < cols.index("PETESTCD")
        assert cols.index("PETESTCD") < cols.index("PETEST")
        assert cols.index("PETEST") < cols.index("PEORRES")
        assert cols.index("PEORRES") < cols.index("PEDTC")

    def test_pe_performed_flag(
        self,
        pe_spec: DomainMappingSpec,
        raw_pe_df: pd.DataFrame,
    ) -> None:
        """PEORRES should be 'Y' from source PEPERF."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            pe_spec,
            {"pe": raw_pe_df},
            study_id="PHA022121-C301",
        )
        assert all(result["PEORRES"] == "Y")
