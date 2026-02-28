"""End-to-end VS domain execution integration test.

NOTE: No vs.sas7bdat or vital_signs.sas7bdat exists in the Fakedata directory.
All VS tests use synthetic data. This ensures the VS normalizer and executor
work correctly for general-purpose use with other studies.

Creates synthetic vital signs data and verifies the full Findings pipeline:
column normalization, spec execution, VSSEQ generation, column order,
position CT C71148 verification, and normal range indicator passthrough.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.executor import DatasetExecutor
from astraea.execution.findings import normalize_vs_columns
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
def vs_spec() -> DomainMappingSpec:
    """VS domain spec with Findings-class mappings."""
    mappings = [
        _mapping(var="STUDYID", pattern=MappingPattern.ASSIGN, label="Study Identifier", assigned="PHA022121-C301", order=1),
        _mapping(var="DOMAIN", pattern=MappingPattern.ASSIGN, label="Domain Abbreviation", assigned="VS", order=2),
        _mapping(var="USUBJID", pattern=MappingPattern.DERIVATION, label="Unique Subject Identifier", derivation="generate_usubjid", order=3),
        _mapping(var="VSSEQ", pattern=MappingPattern.DERIVATION, label="Sequence Number", derivation="generate_seq", order=4),
        _mapping(var="VSTESTCD", pattern=MappingPattern.DIRECT, label="Vital Signs Test Short Name", source="VSTESTCD", order=5),
        _mapping(var="VSTEST", pattern=MappingPattern.DIRECT, label="Vital Signs Test Name", source="VSTEST", order=6),
        _mapping(var="VSORRES", pattern=MappingPattern.DIRECT, label="Result or Finding in Original Units", source="VSORRES", order=7, core=CoreDesignation.EXP),
        _mapping(var="VSORRESU", pattern=MappingPattern.DIRECT, label="Original Units", source="VSORRESU", order=8, core=CoreDesignation.EXP),
        _mapping(var="VSSTRESC", pattern=MappingPattern.DIRECT, label="Character Result/Finding in Std Format", source="VSSTRESC", order=9, core=CoreDesignation.EXP),
        _mapping(var="VSSTRESN", pattern=MappingPattern.DIRECT, label="Numeric Result/Finding in Std Units", source="VSSTRESN", order=10, core=CoreDesignation.EXP),
        _mapping(var="VSSTRESU", pattern=MappingPattern.DIRECT, label="Standard Units", source="VSSTRESU", order=11, core=CoreDesignation.EXP),
        _mapping(var="VSPOS", pattern=MappingPattern.DIRECT, label="Position of Subject During Observation", source="VSPOS", order=12, core=CoreDesignation.PERM),
        _mapping(var="VSLOC", pattern=MappingPattern.DIRECT, label="Location of Vital Signs Measurement", source="VSLOC", order=13, core=CoreDesignation.PERM),
        _mapping(var="VSBLFL", pattern=MappingPattern.DIRECT, label="Baseline Flag", source="VSBLFL", order=14, core=CoreDesignation.EXP),
        _mapping(var="VSDTC", pattern=MappingPattern.DIRECT, label="Date/Time of Measurements", source="VSDTC", order=15),
        _mapping(var="VSNRIND", pattern=MappingPattern.DIRECT, label="Reference Range Indicator", source="VSNRIND", order=16, core=CoreDesignation.EXP),
    ]
    return DomainMappingSpec(
        domain="VS",
        domain_label="Vital Signs",
        domain_class="Findings",
        structure="One record per vital sign measurement per time point per visit per subject",
        study_id="PHA022121-C301",
        source_datasets=["vs_synthetic"],
        variable_mappings=mappings,
        total_variables=16,
        required_mapped=4,
        expected_mapped=8,
        high_confidence_count=16,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_vs_data() -> pd.DataFrame:
    """Synthetic VS data: 12 rows, 2 subjects, 3 visits, 4 test codes.

    Includes VSPOS from CT C71148 (SUPINE, STANDING, SITTING), VSLOC,
    and numeric results with units.
    """
    subjects = ["001"] * 6 + ["002"] * 6
    sites = ["101"] * 12
    testcds = ["SYSBP", "DIABP", "PULSE", "WEIGHT"] * 3
    tests = [
        "Systolic Blood Pressure", "Diastolic Blood Pressure", "Pulse Rate", "Weight",
        "Systolic Blood Pressure", "Diastolic Blood Pressure", "Pulse Rate", "Weight",
        "Systolic Blood Pressure", "Diastolic Blood Pressure", "Pulse Rate", "Weight",
    ]
    results = ["120", "80", "72", "75", "125", "82", "70", "75", "118", "78", "68", "80"]
    units = ["mmHg", "mmHg", "beats/min", "kg"] * 3
    positions = [
        "SUPINE", "SUPINE", "SUPINE", None,
        "STANDING", "STANDING", "SITTING", None,
        "SUPINE", "SUPINE", "SITTING", None,
    ]
    locations = ["ARM", "ARM", None, None, "ARM", "ARM", None, None, "LEG", "LEG", None, None]
    baselines = ["Y", "Y", "Y", "Y", "", "", "", "", "Y", "Y", "Y", "Y"]
    dates = [
        "2022-01-15", "2022-01-15", "2022-01-15", "2022-01-15",
        "2022-02-15", "2022-02-15", "2022-02-15", "2022-02-15",
        "2022-01-20", "2022-01-20", "2022-01-20", "2022-01-20",
    ]
    nrinds = [
        "NORMAL", "NORMAL", "NORMAL", "NORMAL",
        "HIGH", "NORMAL", "NORMAL", "NORMAL",
        "NORMAL", "LOW", "NORMAL", "HIGH",
    ]

    return pd.DataFrame({
        "Subject": subjects,
        "SiteNumber": sites,
        "VSTESTCD": testcds,
        "VSTEST": tests,
        "VSORRES": results,
        "VSORRESU": units,
        "VSSTRESC": results,
        "VSSTRESN": [float(r) for r in results],
        "VSSTRESU": units,
        "VSPOS": positions,
        "VSLOC": locations,
        "VSBLFL": baselines,
        "VSDTC": dates,
        "VSNRIND": nrinds,
    })


@pytest.fixture()
def raw_vs_crf_style() -> pd.DataFrame:
    """VS data with CRF-style column names for normalization testing."""
    return pd.DataFrame({
        "Subject": ["001", "001"],
        "SiteNumber": ["101", "101"],
        "VSTEST": ["Systolic Blood Pressure", "Diastolic Blood Pressure"],
        "VSORRES": ["120", "80"],
        "VSORRESU": ["mmHg", "mmHg"],
        "VSDAT": ["2022-01-15", "2022-01-15"],
        "VSTIM": ["08:30", "08:30"],
        "VSPERF": ["Y", "Y"],
    })


@pytest.fixture()
def vs_executor() -> DatasetExecutor:
    """Executor with both SDTM and CT references loaded."""
    return DatasetExecutor(
        sdtm_ref=load_sdtm_reference(),
        ct_ref=load_ct_reference(),
    )


class TestVSExecution:
    """VS domain execution tests with synthetic data.

    NOTE: VS is tested entirely with synthetic data because no
    vs.sas7bdat or vital_signs.sas7bdat exists in the Fakedata directory.
    """

    def test_vs_basic_execution(
        self,
        vs_spec: DomainMappingSpec,
        raw_vs_data: pd.DataFrame,
        vs_executor: DatasetExecutor,
    ) -> None:
        """Execute spec, verify row count and SDTM columns present."""
        result = vs_executor.execute(
            vs_spec, {"vs": raw_vs_data}, study_id="PHA022121-C301"
        )
        assert len(result) == 12
        assert "STUDYID" in result.columns
        assert "DOMAIN" in result.columns
        assert "USUBJID" in result.columns
        assert "VSTESTCD" in result.columns
        assert "VSTEST" in result.columns
        assert "VSORRES" in result.columns
        assert "VSDTC" in result.columns

    def test_vs_seq_generation(
        self,
        vs_spec: DomainMappingSpec,
        raw_vs_data: pd.DataFrame,
        vs_executor: DatasetExecutor,
    ) -> None:
        """Verify VSSEQ unique per USUBJID, monotonically increasing."""
        result = vs_executor.execute(
            vs_spec, {"vs": raw_vs_data}, study_id="PHA022121-C301"
        )
        assert "VSSEQ" in result.columns
        for _, group in result.groupby("USUBJID"):
            seq_values = list(group["VSSEQ"])
            assert seq_values == sorted(seq_values)
            assert seq_values[0] == 1
            assert len(seq_values) == len(set(seq_values))

    def test_vs_domain_assign(
        self,
        vs_spec: DomainMappingSpec,
        raw_vs_data: pd.DataFrame,
        vs_executor: DatasetExecutor,
    ) -> None:
        """Verify DOMAIN = 'VS' for all rows."""
        result = vs_executor.execute(
            vs_spec, {"vs": raw_vs_data}, study_id="PHA022121-C301"
        )
        assert all(result["DOMAIN"] == "VS")

    def test_vs_column_order(
        self,
        vs_spec: DomainMappingSpec,
        raw_vs_data: pd.DataFrame,
        vs_executor: DatasetExecutor,
    ) -> None:
        """Verify columns in spec order."""
        result = vs_executor.execute(
            vs_spec, {"vs": raw_vs_data}, study_id="PHA022121-C301"
        )
        cols = list(result.columns)
        assert cols.index("STUDYID") < cols.index("DOMAIN")
        assert cols.index("DOMAIN") < cols.index("USUBJID")
        assert cols.index("USUBJID") < cols.index("VSSEQ")
        assert cols.index("VSSEQ") < cols.index("VSTESTCD")
        assert cols.index("VSTESTCD") < cols.index("VSTEST")
        assert cols.index("VSDTC") < cols.index("VSNRIND")

    def test_vs_position_ct_c71148(
        self,
        vs_spec: DomainMappingSpec,
        raw_vs_data: pd.DataFrame,
        vs_executor: DatasetExecutor,
    ) -> None:
        """Verify all VSPOS values are valid terms from CT C71148."""
        result = vs_executor.execute(
            vs_spec, {"vs": raw_vs_data}, study_id="PHA022121-C301"
        )
        assert "VSPOS" in result.columns
        valid_positions = {"SUPINE", "STANDING", "SITTING"}
        actual_positions = set(result["VSPOS"].dropna().unique())
        assert actual_positions.issubset(valid_positions), (
            f"VSPOS has values not in C71148: {actual_positions - valid_positions}"
        )

    def test_vs_nrind_present(
        self,
        vs_spec: DomainMappingSpec,
        raw_vs_data: pd.DataFrame,
        vs_executor: DatasetExecutor,
    ) -> None:
        """Verify VSNRIND column exists and is populated with NORMAL, LOW, HIGH."""
        result = vs_executor.execute(
            vs_spec, {"vs": raw_vs_data}, study_id="PHA022121-C301"
        )
        assert "VSNRIND" in result.columns
        nrind_values = set(result["VSNRIND"].dropna().unique())
        assert "NORMAL" in nrind_values
        assert "LOW" in nrind_values
        assert "HIGH" in nrind_values

    def test_vs_normalize_columns(
        self,
        raw_vs_crf_style: pd.DataFrame,
    ) -> None:
        """Test normalize_vs_columns on CRF-style data (VSDAT->VSDTC, etc.)."""
        normalized = normalize_vs_columns(raw_vs_crf_style, "vs_crf")
        # VSDAT should be renamed to VSDTC
        assert "VSDTC" in normalized.columns
        assert "VSDAT" not in normalized.columns
        # VSTIM should be appended to VSDTC
        assert "VSTIM" not in normalized.columns
        assert "T" in normalized["VSDTC"].iloc[0]  # Date+Time combined
        # VSPERF -> VSSTAT
        assert "VSSTAT" in normalized.columns
        assert "VSPERF" not in normalized.columns
        # VSTESTCD derived from VSTEST
        assert "VSTESTCD" in normalized.columns

    def test_vs_no_fakedata_note(self) -> None:
        """VS is tested with synthetic data because no vs.sas7bdat exists in Fakedata."""
        # This test documents the design decision. The absence of VS raw data
        # in Fakedata means VS testing relies entirely on synthetic data.
        # The VS normalizer and executor are designed for general-purpose use
        # with any study that has vital signs data.
        assert True
