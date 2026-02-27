"""Tests for date and time imputation flag utilities."""

from __future__ import annotations

import pytest

from astraea.transforms.imputation import (
    get_date_imputation_flag,
    get_time_imputation_flag,
)


class TestGetDateImputationFlag:
    """Tests for get_date_imputation_flag."""

    def test_full_date_no_imputation(self) -> None:
        """Full date (YYYY-MM-DD) requires no imputation."""
        assert get_date_imputation_flag("2022-03-30", "2022-03-30") is None

    def test_full_datetime_no_imputation(self) -> None:
        """Full datetime has complete date portion -- no imputation."""
        assert get_date_imputation_flag("2022-03-30T14:30:00", "2022-03-30T14:30:00") is None

    def test_year_month_day_imputed(self) -> None:
        """Year-month only (YYYY-MM) -- day was imputed."""
        assert get_date_imputation_flag("2022-03", "2022-03-15") == "D"

    def test_year_only_month_imputed(self) -> None:
        """Year only (YYYY) -- month was imputed."""
        assert get_date_imputation_flag("2022", "2022-06-15") == "M"

    def test_short_string_year_imputed(self) -> None:
        """Very short string (< 4 chars) -- year was imputed."""
        assert get_date_imputation_flag("20", "2022-01-01") == "Y"

    def test_empty_original_returns_none(self) -> None:
        """Empty original DTC returns None."""
        assert get_date_imputation_flag("", "2022-03-30") is None

    def test_empty_imputed_returns_none(self) -> None:
        """Empty imputed DTC returns None."""
        assert get_date_imputation_flag("2022-03", "") is None

    def test_both_empty_returns_none(self) -> None:
        """Both empty returns None."""
        assert get_date_imputation_flag("", "") is None


class TestGetTimeImputationFlag:
    """Tests for get_time_imputation_flag."""

    def test_full_time_no_imputation(self) -> None:
        """Full datetime with complete time -- no imputation."""
        assert get_time_imputation_flag("2022-03-30T14:30:00", "2022-03-30T14:30:00") is None

    def test_time_hour_imputed(self) -> None:
        """No T in original, T in imputed -- hour was imputed."""
        assert get_time_imputation_flag("2022-03-30", "2022-03-30T00:00:00") == "H"

    def test_no_time_either_side(self) -> None:
        """No T in either -- no time imputation."""
        assert get_time_imputation_flag("2022-03-30", "2022-03-30") is None

    def test_time_minute_imputed(self) -> None:
        """Time with hour only (HH) -- minute was imputed."""
        assert get_time_imputation_flag("2022-03-30T14", "2022-03-30T14:00:00") == "M"

    def test_time_second_imputed(self) -> None:
        """Time with hour:minute (HH:MM) -- second was imputed."""
        assert get_time_imputation_flag("2022-03-30T14:30", "2022-03-30T14:30:00") == "S"

    def test_empty_original_returns_none(self) -> None:
        """Empty original returns None."""
        assert get_time_imputation_flag("", "2022-03-30T14:30:00") is None

    def test_empty_imputed_returns_none(self) -> None:
        """Empty imputed returns None."""
        assert get_time_imputation_flag("2022-03-30T14:30", "") is None

    def test_time_with_colons_full(self) -> None:
        """Time with colons HH:MM:SS is full -- no imputation."""
        assert get_time_imputation_flag("2022-03-30T14:30:45", "2022-03-30T14:30:45") is None
