"""Tests for Phase 14 date imputation functions.

Covers impute_partial_date and impute_partial_date_with_flag.
"""

from __future__ import annotations

import pytest

from astraea.transforms.imputation import (
    impute_partial_date,
    impute_partial_date_with_flag,
)


class TestImputePartialDateFirst:
    """Tests for method='first' imputation."""

    def test_impute_year_only_first(self) -> None:
        assert impute_partial_date("2022", method="first") == "2022-01-01"

    def test_impute_year_month_first(self) -> None:
        assert impute_partial_date("2022-03", method="first") == "2022-03-01"

    def test_impute_complete_date_unchanged(self) -> None:
        assert impute_partial_date("2022-03-30", method="first") == "2022-03-30"

    def test_impute_with_time_hour_only_first(self) -> None:
        assert impute_partial_date("2022-03-30T14", method="first") == "2022-03-30T14:00:00"


class TestImputePartialDateLast:
    """Tests for method='last' imputation."""

    def test_impute_year_only_last(self) -> None:
        assert impute_partial_date("2022", method="last") == "2022-12-31"

    def test_impute_year_month_last(self) -> None:
        assert impute_partial_date("2022-03", method="last") == "2022-03-31"

    def test_impute_year_month_last_feb_leap(self) -> None:
        assert impute_partial_date("2024-02", method="last") == "2024-02-29"

    def test_impute_year_month_last_feb_nonleap(self) -> None:
        assert impute_partial_date("2022-02", method="last") == "2022-02-28"

    def test_impute_year_month_last_apr(self) -> None:
        assert impute_partial_date("2022-04", method="last") == "2022-04-30"

    def test_impute_with_time_hour_only_last(self) -> None:
        assert impute_partial_date("2022-03-30T14", method="last") == "2022-03-30T14:59:59"


class TestImputePartialDateMid:
    """Tests for method='mid' imputation."""

    def test_impute_year_only_mid(self) -> None:
        assert impute_partial_date("2022", method="mid") == "2022-06-15"

    def test_impute_year_month_mid(self) -> None:
        assert impute_partial_date("2022-03", method="mid") == "2022-03-15"

    def test_impute_with_time_hour_only_mid(self) -> None:
        assert impute_partial_date("2022-03-30T14", method="mid") == "2022-03-30T14:30:00"


class TestImputePartialDateEdgeCases:
    """Edge cases for impute_partial_date."""

    def test_impute_empty_string(self) -> None:
        assert impute_partial_date("") == ""

    def test_impute_none(self) -> None:
        assert impute_partial_date(None) == ""

    def test_impute_full_datetime_unchanged(self) -> None:
        assert impute_partial_date("2022-03-30T14:30:00") == "2022-03-30T14:30:00"

    def test_impute_hhmm_unchanged(self) -> None:
        assert impute_partial_date("2022-03-30T14:30") == "2022-03-30T14:30"

    def test_impute_invalid_method_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid imputation method"):
            impute_partial_date("2022", method="invalid")


class TestImputePartialDateWithFlag:
    """Tests for impute_partial_date_with_flag."""

    def test_impute_with_flag_year_month(self) -> None:
        result = impute_partial_date_with_flag("2022-03", method="first")
        assert result == ("2022-03-01", "D", None)

    def test_impute_with_flag_year_only(self) -> None:
        result = impute_partial_date_with_flag("2022", method="first")
        assert result == ("2022-01-01", "M", None)

    def test_impute_with_flag_complete_date(self) -> None:
        result = impute_partial_date_with_flag("2022-03-30", method="first")
        assert result == ("2022-03-30", None, None)

    def test_impute_with_flag_empty(self) -> None:
        result = impute_partial_date_with_flag("")
        assert result == ("", None, None)

    def test_impute_with_flag_none(self) -> None:
        result = impute_partial_date_with_flag(None)
        assert result == ("", None, None)

    def test_impute_with_flag_hour_only(self) -> None:
        result = impute_partial_date_with_flag("2022-03-30T14", method="first")
        assert result == ("2022-03-30T14:00:00", None, "M")
