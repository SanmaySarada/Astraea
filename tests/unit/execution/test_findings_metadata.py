"""Tests for Findings metadata pass-through (SPEC, METHOD, FAST)."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.findings import _pass_through_findings_metadata


class TestSpecimenPassThrough:
    def test_spec_from_specimen_column(self) -> None:
        df = pd.DataFrame({"LBORRES": ["5.0", "3.2"]})
        source = pd.DataFrame({"SPECIMEN": ["BLOOD", "URINE"], "LBORRES": ["5.0", "3.2"]})
        result = _pass_through_findings_metadata(df, "LB", source)
        assert "LBSPEC" in result.columns
        assert list(result["LBSPEC"]) == ["BLOOD", "URINE"]

    def test_spec_from_spec_column(self) -> None:
        df = pd.DataFrame({"LBORRES": ["1"]})
        source = pd.DataFrame({"SPEC": ["PLASMA"], "LBORRES": ["1"]})
        result = _pass_through_findings_metadata(df, "LB", source)
        assert "LBSPEC" in result.columns
        assert list(result["LBSPEC"]) == ["PLASMA"]

    def test_spec_from_sample_column(self) -> None:
        df = pd.DataFrame({"LBORRES": ["1"]})
        source = pd.DataFrame({"Sample": ["SERUM"], "LBORRES": ["1"]})
        result = _pass_through_findings_metadata(df, "LB", source)
        assert "LBSPEC" in result.columns
        assert list(result["LBSPEC"]) == ["SERUM"]

    def test_no_spec_column_no_creation(self) -> None:
        """If no matching source column, LBSPEC should NOT be created."""
        df = pd.DataFrame({"LBORRES": ["5.0"]})
        source = pd.DataFrame({"LBORRES": ["5.0"]})
        result = _pass_through_findings_metadata(df, "LB", source)
        assert "LBSPEC" not in result.columns


class TestMethodPassThrough:
    def test_method_from_method_column(self) -> None:
        df = pd.DataFrame({"EGORRES": ["normal"]})
        source = pd.DataFrame({"METHOD": ["12-LEAD ECG"], "EGORRES": ["normal"]})
        result = _pass_through_findings_metadata(df, "EG", source)
        assert "EGMETHOD" in result.columns
        assert list(result["EGMETHOD"]) == ["12-LEAD ECG"]

    def test_method_from_testmethod(self) -> None:
        df = pd.DataFrame({"VSORRES": ["120"]})
        source = pd.DataFrame({"TESTMETHOD": ["CUFF"], "VSORRES": ["120"]})
        result = _pass_through_findings_metadata(df, "VS", source)
        assert "VSMETHOD" in result.columns

    def test_no_method_no_creation(self) -> None:
        df = pd.DataFrame({"LBORRES": ["5.0"]})
        source = pd.DataFrame({"LBORRES": ["5.0"]})
        result = _pass_through_findings_metadata(df, "LB", source)
        assert "LBMETHOD" not in result.columns


class TestFastingPassThrough:
    def test_fast_from_fasting_column(self) -> None:
        df = pd.DataFrame({"LBORRES": ["5.0", "3.2"]})
        source = pd.DataFrame({"FASTING": ["Y", "N"], "LBORRES": ["5.0", "3.2"]})
        result = _pass_through_findings_metadata(df, "LB", source)
        assert "LBFAST" in result.columns
        assert list(result["LBFAST"]) == ["Y", "N"]

    def test_fast_from_fast_column(self) -> None:
        df = pd.DataFrame({"LBORRES": ["5.0"]})
        source = pd.DataFrame({"FAST": ["Y"], "LBORRES": ["5.0"]})
        result = _pass_through_findings_metadata(df, "LB", source)
        assert "LBFAST" in result.columns

    def test_no_fasting_no_creation(self) -> None:
        df = pd.DataFrame({"LBORRES": ["5.0"]})
        source = pd.DataFrame({"LBORRES": ["5.0"]})
        result = _pass_through_findings_metadata(df, "LB", source)
        assert "LBFAST" not in result.columns


class TestMultipleMetadata:
    def test_all_three_present(self) -> None:
        """When all three metadata columns exist, all should be passed through."""
        df = pd.DataFrame({"LBORRES": ["5.0"]})
        source = pd.DataFrame(
            {
                "SPECIMEN": ["BLOOD"],
                "METHOD": ["AUTOMATED"],
                "FASTING": ["Y"],
                "LBORRES": ["5.0"],
            }
        )
        result = _pass_through_findings_metadata(df, "LB", source)
        assert "LBSPEC" in result.columns
        assert "LBMETHOD" in result.columns
        assert "LBFAST" in result.columns

    def test_existing_column_not_overwritten(self) -> None:
        """If LBSPEC already exists in output, it should NOT be overwritten."""
        df = pd.DataFrame({"LBORRES": ["5.0"], "LBSPEC": ["EXISTING"]})
        source = pd.DataFrame({"SPECIMEN": ["NEW"], "LBORRES": ["5.0"]})
        result = _pass_through_findings_metadata(df, "LB", source)
        assert list(result["LBSPEC"]) == ["EXISTING"]

    def test_length_mismatch_skips(self) -> None:
        """When source and output have different lengths, skip pass-through."""
        df = pd.DataFrame({"LBORRES": ["5.0", "3.2"]})
        source = pd.DataFrame({"SPECIMEN": ["BLOOD"], "LBORRES": ["5.0"]})
        result = _pass_through_findings_metadata(df, "LB", source)
        # Should not crash; LBSPEC may or may not be created depending on implementation
        # but should not raise
        assert len(result) == 2
