"""Tests for SDTM --DY (study day) calculation."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.transforms.study_day import calculate_study_day, calculate_study_day_column


class TestCalculateStudyDay:
    """Test the scalar calculate_study_day function."""

    def test_day_1_is_rfstdtc(self) -> None:
        """Event on RFSTDTC should be Day 1."""
        assert calculate_study_day("2022-03-30", "2022-03-30") == 1

    def test_day_after_ref(self) -> None:
        """Two days after RFSTDTC should be Day 3."""
        assert calculate_study_day("2022-04-01", "2022-03-30") == 3

    def test_day_before_ref_no_day_zero(self) -> None:
        """Day before RFSTDTC should be Day -1 (no Day 0)."""
        assert calculate_study_day("2022-03-29", "2022-03-30") == -1

    def test_two_days_before(self) -> None:
        """Two days before RFSTDTC should be Day -2."""
        assert calculate_study_day("2022-03-28", "2022-03-30") == -2

    def test_partial_event_date(self) -> None:
        """Partial event date (year-month only) returns None."""
        assert calculate_study_day("2022-03", "2022-03-30") is None

    def test_partial_ref_date(self) -> None:
        """Partial reference date returns None."""
        assert calculate_study_day("2022-03-30", "2022") is None

    def test_empty_dates(self) -> None:
        """Empty string dates return None."""
        assert calculate_study_day("", "2022-03-30") is None

    def test_none_dates(self) -> None:
        """None dates return None."""
        assert calculate_study_day(None, "2022-03-30") is None  # type: ignore[arg-type]
        assert calculate_study_day("2022-03-30", None) is None  # type: ignore[arg-type]

    def test_datetime_event(self) -> None:
        """Datetime string extracts date portion correctly."""
        assert calculate_study_day("2022-03-31T14:30:00", "2022-03-30") == 2

    def test_invalid_date_format(self) -> None:
        """Invalid date format returns None."""
        assert calculate_study_day("not-a-date", "2022-03-30") is None

    def test_both_none(self) -> None:
        """Both None returns None."""
        assert calculate_study_day(None, None) is None  # type: ignore[arg-type]


class TestCalculateStudyDayColumn:
    """Test the vectorized calculate_study_day_column function."""

    def test_column_version(self) -> None:
        """Three subjects with known dates produce correct study days."""
        df = pd.DataFrame(
            {
                "USUBJID": ["S001", "S001", "S002", "S003"],
                "AESTDTC": [
                    "2022-03-30",  # S001: Day 1 (same as RFSTDTC)
                    "2022-04-01",  # S001: Day 3
                    "2022-01-14",  # S002: Day -1 (day before RFSTDTC)
                    "2022-06-15",  # S003: Day 1
                ],
            }
        )
        rfstdtc_lookup = {
            "S001": "2022-03-30",
            "S002": "2022-01-15",
            "S003": "2022-06-15",
        }

        result = calculate_study_day_column(df, "AESTDTC", rfstdtc_lookup)

        assert result.dtype == "Int64"
        assert result.iloc[0] == 1  # S001 same day
        assert result.iloc[1] == 3  # S001 two days after
        assert result.iloc[2] == -1  # S002 day before
        assert result.iloc[3] == 1  # S003 same day

    def test_missing_rfstdtc(self) -> None:
        """Subject not in RFSTDTC lookup gets NaN."""
        df = pd.DataFrame(
            {
                "USUBJID": ["S001", "S999"],
                "AESTDTC": ["2022-03-30", "2022-03-30"],
            }
        )
        rfstdtc_lookup = {"S001": "2022-03-30"}

        result = calculate_study_day_column(df, "AESTDTC", rfstdtc_lookup)

        assert result.iloc[0] == 1
        assert pd.isna(result.iloc[1])

    def test_missing_column_raises(self) -> None:
        """Missing date column raises KeyError."""
        df = pd.DataFrame({"USUBJID": ["S001"]})
        with pytest.raises(KeyError, match="Missing required columns"):
            calculate_study_day_column(df, "NONEXISTENT", {})
