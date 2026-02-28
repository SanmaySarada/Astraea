"""Tests for DTF and TMF date/time imputation flag generation in DatasetExecutor.

Verifies that _generate_dtf_tmf_flags correctly creates empty DTF/TMF columns
when the mapping spec includes --DTF or --TMF variables, preserves existing
columns, and does nothing when no flag variables are in the spec.
"""

from __future__ import annotations

import pandas as pd

from astraea.execution.executor import DatasetExecutor
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation


def _make_spec(domain: str, mappings: list[VariableMapping]) -> DomainMappingSpec:
    """Create a minimal DomainMappingSpec for testing."""
    return DomainMappingSpec(
        domain=domain,
        domain_label=f"{domain} domain",
        domain_class="Events",
        structure="One record per event",
        study_id="TEST-001",
        source_datasets=["test"],
        variable_mappings=mappings,
        total_variables=len(mappings),
        required_mapped=0,
        expected_mapped=0,
        high_confidence_count=len(mappings),
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00Z",
        model_used="test",
    )


def _make_mapping(var_name: str, order: int = 0) -> VariableMapping:
    """Create a minimal VariableMapping for a given SDTM variable."""
    return VariableMapping(
        sdtm_variable=var_name,
        sdtm_label=f"Label for {var_name}",
        sdtm_data_type="Char",
        core=CoreDesignation.PERM,
        mapping_pattern=MappingPattern.DIRECT,
        mapping_logic="test mapping",
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="test",
        order=order,
    )


class TestDTFGeneration:
    """Tests for --DTF flag column generation."""

    def test_dtf_column_created(self) -> None:
        """Spec includes AEDTF -> result DataFrame gets AEDTF column with empty strings."""
        executor = DatasetExecutor()
        result_df = pd.DataFrame({"AESTDTC": ["2022-03-30", "2022-04-01"]})
        spec = _make_spec("AE", [_make_mapping("AESTDTC"), _make_mapping("AEDTF")])

        result = executor._generate_dtf_tmf_flags(result_df, spec)

        assert "AEDTF" in result.columns
        assert (result["AEDTF"] == "").all()
        assert len(result) == 2

    def test_dtf_not_created_when_not_in_spec(self) -> None:
        """Spec has no --DTF variables -> no flag columns added."""
        executor = DatasetExecutor()
        result_df = pd.DataFrame({"AESTDTC": ["2022-03-30"]})
        spec = _make_spec("AE", [_make_mapping("AESTDTC"), _make_mapping("AETERM")])

        result = executor._generate_dtf_tmf_flags(result_df, spec)

        # No DTF or TMF columns should exist
        flag_cols = [c for c in result.columns if c.endswith("DTF") or c.endswith("TMF")]
        assert flag_cols == []

    def test_dtf_preserves_existing(self) -> None:
        """If AEDTF column already exists in result, it is NOT overwritten."""
        executor = DatasetExecutor()
        result_df = pd.DataFrame({
            "AESTDTC": ["2022-03-30", "2022-04-01"],
            "AEDTF": ["D", "M"],
        })
        spec = _make_spec("AE", [_make_mapping("AESTDTC"), _make_mapping("AEDTF")])

        result = executor._generate_dtf_tmf_flags(result_df, spec)

        assert "AEDTF" in result.columns
        assert list(result["AEDTF"]) == ["D", "M"]


class TestTMFGeneration:
    """Tests for --TMF flag column generation."""

    def test_tmf_column_created(self) -> None:
        """Spec includes AETMF -> result DataFrame gets AETMF column with empty strings."""
        executor = DatasetExecutor()
        result_df = pd.DataFrame({"AESTDTC": ["2022-03-30T10:30:00"]})
        spec = _make_spec("AE", [_make_mapping("AESTDTC"), _make_mapping("AETMF")])

        result = executor._generate_dtf_tmf_flags(result_df, spec)

        assert "AETMF" in result.columns
        assert (result["AETMF"] == "").all()


class TestMultipleFlagColumns:
    """Tests for multiple DTF/TMF columns in one spec."""

    def test_multiple_flag_columns(self) -> None:
        """Spec with AESTDTF, AEENDTF, and AESTTMF -- all three created."""
        executor = DatasetExecutor()
        result_df = pd.DataFrame({
            "AESTDTC": ["2022-03-30"],
            "AEENDTC": ["2022-04-01"],
        })
        spec = _make_spec("AE", [
            _make_mapping("AESTDTC"),
            _make_mapping("AEENDTC"),
            _make_mapping("AESTDTF"),
            _make_mapping("AEENDTF"),
            _make_mapping("AESTTMF"),
        ])

        result = executor._generate_dtf_tmf_flags(result_df, spec)

        assert "AESTDTF" in result.columns
        assert "AEENDTF" in result.columns
        assert "AESTTMF" in result.columns
        assert (result["AESTDTF"] == "").all()
        assert (result["AEENDTF"] == "").all()
        assert (result["AESTTMF"] == "").all()

    def test_mixed_existing_and_new(self) -> None:
        """One flag column exists, another does not -- only new one created."""
        executor = DatasetExecutor()
        result_df = pd.DataFrame({
            "AESTDTC": ["2022-03-30"],
            "AESTDTF": ["D"],  # Already exists
        })
        spec = _make_spec("AE", [
            _make_mapping("AESTDTC"),
            _make_mapping("AESTDTF"),
            _make_mapping("AEENDTF"),
        ])

        result = executor._generate_dtf_tmf_flags(result_df, spec)

        # Existing column preserved
        assert list(result["AESTDTF"]) == ["D"]
        # New column created with empty string
        assert "AEENDTF" in result.columns
        assert (result["AEENDTF"] == "").all()
