"""Tests for Findings domain derivation functions: STRESC, STRESN, STRESU, NRIND.

Covers numeric, text, mixed, missing-range, partial-range, and multi-prefix cases.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from astraea.execution.findings import derive_nrind, derive_standardized_results

# ---------- derive_standardized_results ----------


class TestStandardizedResults:
    """Tests for derive_standardized_results."""

    def test_stresc_copies_orres(self) -> None:
        """STRESC should be an exact character copy of ORRES."""
        df = pd.DataFrame({"LBORRES": ["5.2", "YELLOW", "3.1"]})
        result = derive_standardized_results(df, "LB")
        assert list(result["LBSTRESC"]) == ["5.2", "YELLOW", "3.1"]

    def test_stresn_numeric_parse(self) -> None:
        """STRESN should be numeric for numeric strings, NaN otherwise."""
        df = pd.DataFrame({"LBORRES": ["5.2", "YELLOW", "3.1", None, ""]})
        result = derive_standardized_results(df, "LB")
        stresn = result["LBSTRESN"].tolist()
        assert stresn[0] == pytest.approx(5.2)
        assert math.isnan(stresn[1])  # text -> NaN
        assert stresn[2] == pytest.approx(3.1)
        assert math.isnan(stresn[3])  # None -> NaN
        assert math.isnan(stresn[4])  # empty -> NaN

    def test_stresu_copies_orresu(self) -> None:
        """STRESU should copy ORRESU when it exists."""
        df = pd.DataFrame({
            "LBORRES": ["5.2", "3.1", "1.0"],
            "LBORRESU": ["mg/dL", "mg/dL", None],
        })
        result = derive_standardized_results(df, "LB")
        stresu = result["LBSTRESU"].tolist()
        assert stresu[0] == "mg/dL"
        assert stresu[1] == "mg/dL"
        assert pd.isna(stresu[2])

    def test_stresu_absent_when_no_orresu(self) -> None:
        """STRESU should NOT be created when ORRESU column is absent."""
        df = pd.DataFrame({"LBORRES": ["5.2"]})
        result = derive_standardized_results(df, "LB")
        assert "LBSTRESU" not in result.columns

    def test_no_orres_returns_unchanged(self) -> None:
        """DataFrame without ORRES column should be returned unchanged."""
        df = pd.DataFrame({"OTHER_COL": [1, 2, 3]})
        result = derive_standardized_results(df, "LB")
        assert "LBSTRESC" not in result.columns
        assert "LBSTRESN" not in result.columns
        assert list(result["OTHER_COL"]) == [1, 2, 3]


# ---------- derive_nrind ----------


class TestNRIND:
    """Tests for derive_nrind."""

    def test_nrind_normal(self) -> None:
        """Result within range should be NORMAL."""
        df = pd.DataFrame({
            "LBSTRESN": [5.0],
            "LBSTNRLO": [3.0],
            "LBSTNRHI": [7.0],
        })
        result = derive_nrind(df, "LB")
        assert result["LBNRIND"].iloc[0] == "NORMAL"

    def test_nrind_low(self) -> None:
        """Result below low bound should be LOW."""
        df = pd.DataFrame({
            "LBSTRESN": [1.0],
            "LBSTNRLO": [3.0],
            "LBSTNRHI": [7.0],
        })
        result = derive_nrind(df, "LB")
        assert result["LBNRIND"].iloc[0] == "LOW"

    def test_nrind_high(self) -> None:
        """Result above high bound should be HIGH."""
        df = pd.DataFrame({
            "LBSTRESN": [10.0],
            "LBSTNRLO": [3.0],
            "LBSTNRHI": [7.0],
        })
        result = derive_nrind(df, "LB")
        assert result["LBNRIND"].iloc[0] == "HIGH"

    def test_nrind_null_when_no_ranges(self) -> None:
        """NRIND should be null when no range columns exist."""
        df = pd.DataFrame({"LBSTRESN": [5.0]})
        result = derive_nrind(df, "LB")
        assert pd.isna(result["LBNRIND"].iloc[0])

    def test_nrind_null_for_non_numeric(self) -> None:
        """NRIND should be null when STRESN is NaN."""
        df = pd.DataFrame({
            "LBSTRESN": [float("nan")],
            "LBSTNRLO": [3.0],
            "LBSTNRHI": [7.0],
        })
        result = derive_nrind(df, "LB")
        assert pd.isna(result["LBNRIND"].iloc[0])

    def test_nrind_partial_range_low_only(self) -> None:
        """With only STNRLO: LOW when result < lo, null otherwise."""
        df = pd.DataFrame({
            "LBSTRESN": [1.0, 5.0],
            "LBSTNRLO": [3.0, 3.0],
        })
        result = derive_nrind(df, "LB")
        assert result["LBNRIND"].iloc[0] == "LOW"
        assert pd.isna(result["LBNRIND"].iloc[1])

    def test_nrind_partial_range_high_only(self) -> None:
        """With only STNRHI: HIGH when result > hi, null otherwise."""
        df = pd.DataFrame({
            "LBSTRESN": [10.0, 5.0],
            "LBSTNRHI": [7.0, 7.0],
        })
        result = derive_nrind(df, "LB")
        assert result["LBNRIND"].iloc[0] == "HIGH"
        assert pd.isna(result["LBNRIND"].iloc[1])

    def test_mixed_results_vectorized(self) -> None:
        """Verify correct NRIND for mixed numeric/text with varying ranges."""
        df = pd.DataFrame({
            "LBSTRESN": [1.0, 5.0, 10.0, float("nan"), 3.0],
            "LBSTNRLO": [3.0, 3.0, 3.0, 3.0, None],
            "LBSTNRHI": [7.0, 7.0, 7.0, 7.0, None],
        })
        result = derive_nrind(df, "LB")
        nrind = result["LBNRIND"].tolist()
        assert nrind[0] == "LOW"
        assert nrind[1] == "NORMAL"
        assert nrind[2] == "HIGH"
        assert pd.isna(nrind[3])  # NaN STRESN
        assert pd.isna(nrind[4])  # NaN ranges

    def test_no_stresn_returns_unchanged(self) -> None:
        """DataFrame without STRESN should be returned unchanged."""
        df = pd.DataFrame({"OTHER_COL": [1, 2, 3]})
        result = derive_nrind(df, "LB")
        assert "LBNRIND" not in result.columns

    def test_eg_prefix(self) -> None:
        """Verify domain-agnostic behavior with EG prefix."""
        df = pd.DataFrame({"EGORRES": ["120", "NORMAL", "85"]})
        df = derive_standardized_results(df, "EG")

        assert "EGSTRESC" in df.columns
        assert "EGSTRESN" in df.columns
        assert list(df["EGSTRESC"]) == ["120", "NORMAL", "85"]
        assert df["EGSTRESN"].iloc[0] == pytest.approx(120.0)
        assert math.isnan(df["EGSTRESN"].iloc[1])

        # Add ranges and derive NRIND
        df["EGSTNRLO"] = [60.0, 60.0, 60.0]
        df["EGSTNRHI"] = [100.0, 100.0, 100.0]
        df = derive_nrind(df, "EG")
        assert df["EGNRIND"].iloc[0] == "HIGH"
        assert pd.isna(df["EGNRIND"].iloc[1])  # NaN STRESN
        assert df["EGNRIND"].iloc[2] == "NORMAL"

    def test_nrind_boundary_values(self) -> None:
        """Values exactly at boundaries should be NORMAL (inclusive)."""
        df = pd.DataFrame({
            "LBSTRESN": [3.0, 7.0],
            "LBSTNRLO": [3.0, 3.0],
            "LBSTNRHI": [7.0, 7.0],
        })
        result = derive_nrind(df, "LB")
        assert result["LBNRIND"].iloc[0] == "NORMAL"
        assert result["LBNRIND"].iloc[1] == "NORMAL"
