"""End-to-end EG domain execution integration test.

Creates synthetic ECG data (no real Fakedata dependency) and verifies the
full Findings pipeline: pre/post-dose normalization, spec execution,
EGSEQ generation, column order, position CT C71148 verification, and
date imputation flags.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.executor import DatasetExecutor
from astraea.execution.findings import normalize_ecg_columns
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
def eg_spec() -> DomainMappingSpec:
    """EG domain spec with Findings-class mappings."""
    mappings = [
        _mapping(var="STUDYID", pattern=MappingPattern.ASSIGN, label="Study Identifier", assigned="PHA022121-C301", order=1),
        _mapping(var="DOMAIN", pattern=MappingPattern.ASSIGN, label="Domain Abbreviation", assigned="EG", order=2),
        _mapping(var="USUBJID", pattern=MappingPattern.DERIVATION, label="Unique Subject Identifier", derivation="generate_usubjid", order=3),
        _mapping(var="EGSEQ", pattern=MappingPattern.DERIVATION, label="Sequence Number", derivation="generate_seq", order=4),
        _mapping(var="EGTESTCD", pattern=MappingPattern.DIRECT, label="ECG Test or Examination Short Name", source="EGTESTCD", order=5),
        _mapping(var="EGTEST", pattern=MappingPattern.DIRECT, label="ECG Test or Examination Name", source="EGTEST", order=6),
        _mapping(var="EGORRES", pattern=MappingPattern.DIRECT, label="Result or Finding in Original Units", source="EGORRES", order=7, core=CoreDesignation.EXP),
        _mapping(var="EGORRESU", pattern=MappingPattern.DIRECT, label="Original Units", source="EGORRESU", order=8, core=CoreDesignation.EXP),
        _mapping(var="EGSTRESC", pattern=MappingPattern.DIRECT, label="Character Result/Finding in Std Format", source="EGSTRESC", order=9, core=CoreDesignation.EXP),
        _mapping(var="EGSTRESN", pattern=MappingPattern.DIRECT, label="Numeric Result/Finding in Std Units", source="EGSTRESN", order=10, core=CoreDesignation.EXP),
        _mapping(var="EGSTRESU", pattern=MappingPattern.DIRECT, label="Standard Units", source="EGSTRESU", order=11, core=CoreDesignation.EXP),
        _mapping(var="EGTPT", pattern=MappingPattern.DIRECT, label="Planned Time Point Name", source="EGTPT", order=12, core=CoreDesignation.PERM),
        _mapping(var="EGDTC", pattern=MappingPattern.DIRECT, label="Date/Time of ECG", source="EGDTC", order=13),
        _mapping(var="EGPOS", pattern=MappingPattern.DIRECT, label="Position of Subject During Observation", source="EGPOS", order=14, core=CoreDesignation.PERM),
        _mapping(var="EGDTF", pattern=MappingPattern.DIRECT, label="Date Imputation Flag", source="EGDTF", order=15, core=CoreDesignation.PERM),
    ]
    return DomainMappingSpec(
        domain="EG",
        domain_label="ECG Test Results",
        domain_class="Findings",
        structure="One record per ECG test per time point per visit per subject",
        study_id="PHA022121-C301",
        source_datasets=["ecg_results.sas7bdat"],
        variable_mappings=mappings,
        total_variables=15,
        required_mapped=4,
        expected_mapped=6,
        high_confidence_count=15,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_ecg_results() -> pd.DataFrame:
    """Synthetic ecg_results data: 8 rows, 2 subjects, SDTM-like columns."""
    return pd.DataFrame({
        "Subject": ["001", "001", "001", "001", "002", "002", "002", "002"],
        "SiteNumber": ["101"] * 8,
        "EGTESTCD": ["QTCF", "QRS", "PR", "HR", "QTCF", "QRS", "PR", "HR"],
        "EGTEST": [
            "QTcF Interval", "QRS Duration", "PR Interval", "Heart Rate",
            "QTcF Interval", "QRS Duration", "PR Interval", "Heart Rate",
        ],
        "EGORRES": ["420", "88", "160", "72", "400", "92", "155", "68"],
        "EGORRESU": ["ms", "ms", "ms", "beats/min", "ms", "ms", "ms", "beats/min"],
        "EGSTRESC": ["420", "88", "160", "72", "400", "92", "155", "68"],
        "EGSTRESN": [420.0, 88.0, 160.0, 72.0, 400.0, 92.0, 155.0, 68.0],
        "EGSTRESU": ["ms", "ms", "ms", "beats/min", "ms", "ms", "ms", "beats/min"],
        "EGTPT": ["Pre-dose", "Pre-dose", "Pre-dose", "Pre-dose",
                  "Post-dose", "Post-dose", "Post-dose", "Post-dose"],
        "EGDTC": [
            "2022-01-15T08:00", "2022-01-15T08:00", "2022-01-15T08:00", "2022-01-15T08:00",
            "2022-01-15T10:00", "2022-01-15T10:00", "2022-01-15T10:00", "2022-01-15T10:00",
        ],
        "EGPOS": ["SUPINE", "SUPINE", "SUPINE", "SUPINE",
                  "SUPINE", "SITTING", "SITTING", "STANDING"],
        "EGDTF": ["", "", "", "", "", "", "", ""],
    })


@pytest.fixture()
def raw_eg_pre() -> pd.DataFrame:
    """Synthetic eg_pre CRF data: 3 rows with CRF-style columns."""
    return pd.DataFrame({
        "Subject": ["001", "001", "001"],
        "SiteNumber": ["101", "101", "101"],
        "EGPERF3": ["Y", "Y", "Y"],
        "EGDAT3": ["2022-01-15", "2022-01-15", "2022-01-15"],
        "EGRS3": ["Normal", "Normal", "Normal"],
        "EGABS3": ["", "", ""],
        "EGCS3": ["N", "N", "N"],
        "EG_TPT_PRE": ["Pre-dose", "Pre-dose", "Pre-dose"],
    })


@pytest.fixture()
def raw_ecg_with_partial_dates() -> pd.DataFrame:
    """ECG data with partial dates for date imputation flag testing."""
    return pd.DataFrame({
        "Subject": ["001", "001", "002"],
        "SiteNumber": ["101", "101", "101"],
        "EGTESTCD": ["QTCF", "QRS", "QTCF"],
        "EGTEST": ["QTcF Interval", "QRS Duration", "QTcF Interval"],
        "EGORRES": ["420", "88", "400"],
        "EGORRESU": ["ms", "ms", "ms"],
        "EGSTRESC": ["420", "88", "400"],
        "EGSTRESN": [420.0, 88.0, 400.0],
        "EGSTRESU": ["ms", "ms", "ms"],
        "EGTPT": ["Pre-dose", "Pre-dose", "Pre-dose"],
        "EGDTC": ["2022-03", "2022-01-15T08:00", "2022-03"],
        "EGPOS": ["SUPINE", "SUPINE", "SUPINE"],
        "EGDTF": ["D", "", "D"],
    })


@pytest.fixture()
def eg_executor() -> DatasetExecutor:
    """Executor with both SDTM and CT references loaded."""
    return DatasetExecutor(
        sdtm_ref=load_sdtm_reference(),
        ct_ref=load_ct_reference(),
    )


class TestEGExecution:
    def test_eg_basic_execution(
        self,
        eg_spec: DomainMappingSpec,
        raw_ecg_results: pd.DataFrame,
        eg_executor: DatasetExecutor,
    ) -> None:
        """Execute on ecg_results only, verify output structure."""
        result = eg_executor.execute(
            eg_spec, {"ecg_results": raw_ecg_results}, study_id="PHA022121-C301"
        )
        assert len(result) == 8
        assert "STUDYID" in result.columns
        assert "DOMAIN" in result.columns
        assert "EGTESTCD" in result.columns
        assert "EGTEST" in result.columns
        assert all(result["DOMAIN"] == "EG")

    def test_eg_pre_dose_normalization(
        self,
        raw_eg_pre: pd.DataFrame,
    ) -> None:
        """Test normalize_ecg_columns on eg_pre data, verify EGTPT = Pre-dose."""
        normalized = normalize_ecg_columns(raw_eg_pre, "eg_pre", time_point="Pre-dose")
        # CRF columns should be renamed
        assert "EGPERF" in normalized.columns or "EGPERF3" not in normalized.columns
        assert "EGDTC" in normalized.columns
        assert "EGORRES" in normalized.columns
        # EGTPT should be set to Pre-dose
        assert "EGTPT" in normalized.columns
        assert all(normalized["EGTPT"] == "Pre-dose")

    def test_eg_seq_generation(
        self,
        eg_spec: DomainMappingSpec,
        raw_ecg_results: pd.DataFrame,
        eg_executor: DatasetExecutor,
    ) -> None:
        """Verify EGSEQ monotonic per USUBJID."""
        result = eg_executor.execute(
            eg_spec, {"ecg_results": raw_ecg_results}, study_id="PHA022121-C301"
        )
        assert "EGSEQ" in result.columns
        for _, group in result.groupby("USUBJID"):
            seq_values = list(group["EGSEQ"])
            assert seq_values == sorted(seq_values)
            assert seq_values[0] == 1

    def test_eg_column_order(
        self,
        eg_spec: DomainMappingSpec,
        raw_ecg_results: pd.DataFrame,
        eg_executor: DatasetExecutor,
    ) -> None:
        """Verify spec order."""
        result = eg_executor.execute(
            eg_spec, {"ecg_results": raw_ecg_results}, study_id="PHA022121-C301"
        )
        cols = list(result.columns)
        assert cols.index("STUDYID") < cols.index("DOMAIN")
        assert cols.index("DOMAIN") < cols.index("USUBJID")
        assert cols.index("USUBJID") < cols.index("EGSEQ")
        assert cols.index("EGSEQ") < cols.index("EGTESTCD")
        assert cols.index("EGTESTCD") < cols.index("EGTEST")
        assert cols.index("EGDTC") < cols.index("EGPOS")

    def test_eg_position_ct_c71148(
        self,
        eg_spec: DomainMappingSpec,
        raw_ecg_results: pd.DataFrame,
        eg_executor: DatasetExecutor,
    ) -> None:
        """Verify EGPOS values are valid terms from CT codelist C71148."""
        result = eg_executor.execute(
            eg_spec, {"ecg_results": raw_ecg_results}, study_id="PHA022121-C301"
        )
        assert "EGPOS" in result.columns
        valid_positions = {"SUPINE", "SITTING", "STANDING"}
        actual_positions = set(result["EGPOS"].dropna().unique())
        assert actual_positions.issubset(valid_positions), (
            f"EGPOS has values not in C71148: {actual_positions - valid_positions}"
        )

    def test_eg_date_imputation_flag(
        self,
        eg_spec: DomainMappingSpec,
        raw_ecg_with_partial_dates: pd.DataFrame,
        eg_executor: DatasetExecutor,
    ) -> None:
        """Verify EGDTF column is present and contains 'D' for day-imputed dates."""
        result = eg_executor.execute(
            eg_spec, {"ecg": raw_ecg_with_partial_dates}, study_id="PHA022121-C301"
        )
        assert "EGDTF" in result.columns
        dtf_values = list(result["EGDTF"])
        assert "D" in dtf_values
        assert "" in dtf_values
