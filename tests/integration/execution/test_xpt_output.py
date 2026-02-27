"""XPT file output integration tests for AE and CM domains.

Verifies that execute_to_xpt produces valid, readable .xpt files with
correct shape, labels, table names, and XPT v5 constraints.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyreadstat
import pytest

from astraea.execution.executor import DatasetExecutor
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)
from astraea.models.sdtm import CoreDesignation
from astraea.reference import load_ct_reference, load_sdtm_reference

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _mapping(
    *,
    var: str,
    pattern: MappingPattern,
    label: str,
    source: str | None = None,
    assigned: str | None = None,
    derivation: str | None = None,
    order: int,
    core: CoreDesignation = CoreDesignation.REQ,
    dtype: str = "Char",
) -> VariableMapping:
    return VariableMapping(
        sdtm_variable=var,
        sdtm_label=label,
        sdtm_data_type=dtype,
        core=core,
        source_variable=source,
        mapping_pattern=pattern,
        mapping_logic="test",
        assigned_value=assigned,
        derivation_rule=derivation,
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="test",
        order=order,
        origin=VariableOrigin.CRF,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def executor() -> DatasetExecutor:
    return DatasetExecutor(
        sdtm_ref=load_sdtm_reference(),
        ct_ref=load_ct_reference(),
    )


@pytest.fixture()
def ae_spec() -> DomainMappingSpec:
    """Minimal AE spec with 6 variables."""
    return DomainMappingSpec(
        domain="AE",
        domain_label="Adverse Events",
        domain_class="Events",
        structure="One record per adverse event per subject",
        study_id="PHA022121-C301",
        source_datasets=["ae"],
        variable_mappings=[
            _mapping(var="STUDYID", pattern=MappingPattern.ASSIGN,
                     label="Study Identifier", assigned="PHA022121-C301", order=1),
            _mapping(var="DOMAIN", pattern=MappingPattern.ASSIGN,
                     label="Domain Abbreviation", assigned="AE", order=2),
            _mapping(var="USUBJID", pattern=MappingPattern.DERIVATION,
                     label="Unique Subject Identifier", derivation="generate_usubjid", order=3),
            _mapping(var="AESEQ", pattern=MappingPattern.DERIVATION,
                     label="Sequence Number", derivation="generate_seq", order=4, dtype="Num"),
            _mapping(var="AETERM", pattern=MappingPattern.DIRECT,
                     label="Reported Term for the Adverse Event", source="AETERM", order=5),
            _mapping(var="AESTDTC", pattern=MappingPattern.DIRECT,
                     label="Start Date/Time of Adverse Event", source="AESTDTC", order=6),
        ],
        total_variables=6,
        required_mapped=4,
        expected_mapped=1,
        high_confidence_count=6,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def cm_spec() -> DomainMappingSpec:
    """Minimal CM spec with 6 variables."""
    return DomainMappingSpec(
        domain="CM",
        domain_label="Concomitant Medications",
        domain_class="Interventions",
        structure="One record per medication per subject",
        study_id="PHA022121-C301",
        source_datasets=["cm"],
        variable_mappings=[
            _mapping(var="STUDYID", pattern=MappingPattern.ASSIGN,
                     label="Study Identifier", assigned="PHA022121-C301", order=1),
            _mapping(var="DOMAIN", pattern=MappingPattern.ASSIGN,
                     label="Domain Abbreviation", assigned="CM", order=2),
            _mapping(var="USUBJID", pattern=MappingPattern.DERIVATION,
                     label="Unique Subject Identifier", derivation="generate_usubjid", order=3),
            _mapping(var="CMSEQ", pattern=MappingPattern.DERIVATION,
                     label="Sequence Number", derivation="generate_seq", order=4, dtype="Num"),
            _mapping(var="CMTRT", pattern=MappingPattern.DIRECT,
                     label="Reported Name of Drug, Med, or Therapy", source="CMTRT", order=5),
            _mapping(var="CMSTDTC", pattern=MappingPattern.DIRECT,
                     label="Start Date/Time of Medication", source="CMSTDTC", order=6),
        ],
        total_variables=6,
        required_mapped=4,
        expected_mapped=1,
        high_confidence_count=6,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_ae_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Subject": ["001", "002", "003"],
        "SiteNumber": ["101", "101", "102"],
        "AETERM": ["Headache", "Nausea", "Fatigue"],
        "AESTDTC": ["2022-01-15", "2022-02-01", "2022-03-15"],
    })


@pytest.fixture()
def raw_cm_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Subject": ["001", "002", "003"],
        "SiteNumber": ["101", "101", "102"],
        "CMTRT": ["ASPIRIN", "IBUPROFEN", "ACETAMINOPHEN"],
        "CMSTDTC": ["2022-01-10", "2022-01-20", "2022-02-05"],
    })


# ===========================================================================
# Test class: XPT Output
# ===========================================================================


class TestXPTOutput:
    """Verify execute_to_xpt produces valid, readable .xpt files."""

    def test_ae_xpt_created(
        self, executor: DatasetExecutor, ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame, tmp_path: Path,
    ) -> None:
        """execute_to_xpt produces ae.xpt file that exists."""
        xpt_path = tmp_path / "ae.xpt"
        result_path = executor.execute_to_xpt(
            ae_spec, {"ae": raw_ae_df}, xpt_path,
        )
        assert result_path.exists()
        assert result_path.stat().st_size > 0

    def test_ae_xpt_readable(
        self, executor: DatasetExecutor, ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame, tmp_path: Path,
    ) -> None:
        """pyreadstat can read the produced AE XPT file with correct shape."""
        xpt_path = tmp_path / "ae.xpt"
        executor.execute_to_xpt(ae_spec, {"ae": raw_ae_df}, xpt_path)

        df, meta = pyreadstat.read_xport(str(xpt_path))
        assert df.shape == (3, 6)

    def test_ae_xpt_labels_present(
        self, executor: DatasetExecutor, ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame, tmp_path: Path,
    ) -> None:
        """Column labels (STUDYID, AETERM) are preserved in XPT metadata."""
        xpt_path = tmp_path / "ae.xpt"
        executor.execute_to_xpt(ae_spec, {"ae": raw_ae_df}, xpt_path)

        _, meta = pyreadstat.read_xport(str(xpt_path))
        labels = dict(zip(meta.column_names, meta.column_labels, strict=True))
        assert labels["STUDYID"] == "Study Identifier"
        assert labels["AETERM"] == "Reported Term for the Adverse Event"

    def test_ae_xpt_table_name(
        self, executor: DatasetExecutor, ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame, tmp_path: Path,
    ) -> None:
        """XPT metadata table_name is AE."""
        xpt_path = tmp_path / "ae.xpt"
        executor.execute_to_xpt(ae_spec, {"ae": raw_ae_df}, xpt_path)

        _, meta = pyreadstat.read_xport(str(xpt_path))
        assert meta.table_name == "AE"

    def test_cm_xpt_created(
        self, executor: DatasetExecutor, cm_spec: DomainMappingSpec,
        raw_cm_df: pd.DataFrame, tmp_path: Path,
    ) -> None:
        """execute_to_xpt produces cm.xpt file."""
        xpt_path = tmp_path / "cm.xpt"
        result_path = executor.execute_to_xpt(
            cm_spec, {"cm": raw_cm_df}, xpt_path,
        )
        assert result_path.exists()

    def test_cm_xpt_readable(
        self, executor: DatasetExecutor, cm_spec: DomainMappingSpec,
        raw_cm_df: pd.DataFrame, tmp_path: Path,
    ) -> None:
        """CM XPT file is readable with correct shape."""
        xpt_path = tmp_path / "cm.xpt"
        executor.execute_to_xpt(cm_spec, {"cm": raw_cm_df}, xpt_path)

        df, meta = pyreadstat.read_xport(str(xpt_path))
        assert df.shape == (3, 6)

    def test_xpt_variable_names_valid(
        self, executor: DatasetExecutor, ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame, tmp_path: Path,
    ) -> None:
        """All variable names in produced XPT are <= 8 chars."""
        xpt_path = tmp_path / "ae.xpt"
        executor.execute_to_xpt(ae_spec, {"ae": raw_ae_df}, xpt_path)

        df, _ = pyreadstat.read_xport(str(xpt_path))
        for col in df.columns:
            assert len(col) <= 8, f"Variable name '{col}' exceeds 8 characters"

    def test_xpt_labels_valid(
        self, executor: DatasetExecutor, ae_spec: DomainMappingSpec,
        raw_ae_df: pd.DataFrame, tmp_path: Path,
    ) -> None:
        """All labels in produced XPT are <= 40 chars."""
        xpt_path = tmp_path / "ae.xpt"
        executor.execute_to_xpt(ae_spec, {"ae": raw_ae_df}, xpt_path)

        _, meta = pyreadstat.read_xport(str(xpt_path))
        for label in meta.column_labels:
            assert len(label) <= 40, f"Label '{label}' exceeds 40 characters"
