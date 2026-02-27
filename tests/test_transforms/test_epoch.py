"""Tests for SDTM EPOCH derivation."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.transforms.epoch import assign_epoch


@pytest.fixture()
def se_df() -> pd.DataFrame:
    """SE domain DataFrame with three elements for one subject."""
    return pd.DataFrame(
        {
            "USUBJID": ["SUBJ-001", "SUBJ-001", "SUBJ-001"],
            "SESTDTC": ["2022-01-01", "2022-01-15", "2022-07-01"],
            "SEENDTC": ["2022-01-14", "2022-06-30", "2022-09-30"],
            "EPOCH": ["SCREENING", "TREATMENT", "FOLLOW-UP"],
        }
    )


class TestAssignEpoch:
    """Test the assign_epoch function."""

    def test_screening_epoch(self, se_df: pd.DataFrame) -> None:
        """Observation date in screening range maps to SCREENING."""
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "AESTDTC": ["2022-01-10"],
            }
        )
        result = assign_epoch(df, se_df, "AESTDTC")
        assert result.iloc[0] == "SCREENING"

    def test_treatment_epoch(self, se_df: pd.DataFrame) -> None:
        """Observation date in treatment range maps to TREATMENT."""
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "AESTDTC": ["2022-03-15"],
            }
        )
        result = assign_epoch(df, se_df, "AESTDTC")
        assert result.iloc[0] == "TREATMENT"

    def test_followup_epoch(self, se_df: pd.DataFrame) -> None:
        """Observation date in follow-up range maps to FOLLOW-UP."""
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "AESTDTC": ["2022-08-01"],
            }
        )
        result = assign_epoch(df, se_df, "AESTDTC")
        assert result.iloc[0] == "FOLLOW-UP"

    def test_no_match_outside_range(self, se_df: pd.DataFrame) -> None:
        """Observation date outside all SE ranges returns NaN."""
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "AESTDTC": ["2022-12-01"],
            }
        )
        result = assign_epoch(df, se_df, "AESTDTC")
        assert pd.isna(result.iloc[0])

    def test_partial_date_returns_nan(self, se_df: pd.DataFrame) -> None:
        """Partial date (year-month only) returns NaN."""
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "AESTDTC": ["2022-03"],
            }
        )
        result = assign_epoch(df, se_df, "AESTDTC")
        assert pd.isna(result.iloc[0])

    def test_missing_date_returns_nan(self, se_df: pd.DataFrame) -> None:
        """Missing (NaN) date returns NaN."""
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "AESTDTC": [None],
            }
        )
        result = assign_epoch(df, se_df, "AESTDTC")
        assert pd.isna(result.iloc[0])

    def test_open_ended_se_element(self) -> None:
        """SE element with missing SEENDTC is treated as open-ended."""
        se_open = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "SESTDTC": ["2022-07-01"],
                "SEENDTC": [None],
                "EPOCH": ["FOLLOW-UP"],
            }
        )
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "AESTDTC": ["2023-01-15"],
            }
        )
        result = assign_epoch(df, se_open, "AESTDTC")
        assert result.iloc[0] == "FOLLOW-UP"

    def test_multiple_subjects(self) -> None:
        """Different subjects get epochs from their own SE data."""
        se_multi = pd.DataFrame(
            {
                "USUBJID": ["S001", "S001", "S002", "S002"],
                "SESTDTC": ["2022-01-01", "2022-03-01", "2022-02-01", "2022-05-01"],
                "SEENDTC": ["2022-02-28", "2022-06-30", "2022-04-30", "2022-08-31"],
                "EPOCH": ["SCREENING", "TREATMENT", "SCREENING", "TREATMENT"],
            }
        )
        df = pd.DataFrame(
            {
                "USUBJID": ["S001", "S002"],
                "LBDTC": ["2022-04-15", "2022-03-15"],
            }
        )
        result = assign_epoch(df, se_multi, "LBDTC")
        assert result.iloc[0] == "TREATMENT"  # S001 in treatment range
        assert result.iloc[1] == "SCREENING"  # S002 in screening range

    def test_boundary_dates(self, se_df: pd.DataFrame) -> None:
        """Dates exactly on SE boundaries are included."""
        df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001", "SUBJ-001"],
                "AESTDTC": ["2022-01-01", "2022-01-14"],
            }
        )
        result = assign_epoch(df, se_df, "AESTDTC")
        assert result.iloc[0] == "SCREENING"  # Start boundary
        assert result.iloc[1] == "SCREENING"  # End boundary
