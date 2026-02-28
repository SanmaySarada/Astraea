"""Tests for ISO 8601 partial date edge cases and DDMonYYYY format."""

from __future__ import annotations

from astraea.transforms.dates import (
    detect_date_format,
    format_partial_iso8601,
    parse_string_date_to_iso,
)


class TestPartialISO8601HourWithoutMinute:
    """Hour without minute should truncate time component entirely."""

    def test_hour_without_minute_returns_date_only(self) -> None:
        result = format_partial_iso8601(2023, 3, 15, 10, None, None)
        assert result == "2023-03-15"

    def test_hour_with_minute_returns_time(self) -> None:
        result = format_partial_iso8601(2023, 3, 15, 10, 30, None)
        assert result == "2023-03-15T10:30"

    def test_full_datetime(self) -> None:
        result = format_partial_iso8601(2023, 3, 15, 10, 30, 45)
        assert result == "2023-03-15T10:30:45"

    def test_hour_and_minute_zero(self) -> None:
        result = format_partial_iso8601(2023, 3, 15, 0, 0, None)
        assert result == "2023-03-15T00:00"


class TestDDMonYYYYFormat:
    """DDMonYYYY format (no spaces) should parse correctly."""

    def test_ddmonyyyy_uppercase(self) -> None:
        assert parse_string_date_to_iso("30MAR2022") == "2022-03-30"

    def test_ddmonyyyy_lowercase(self) -> None:
        assert parse_string_date_to_iso("15jan2023") == "2023-01-15"

    def test_ddmonyyyy_single_digit_day(self) -> None:
        assert parse_string_date_to_iso("5FEB2021") == "2021-02-05"

    def test_ddmonyyyy_mixed_case(self) -> None:
        assert parse_string_date_to_iso("12Dec2020") == "2020-12-12"

    def test_ddmonyyyy_with_whitespace(self) -> None:
        assert parse_string_date_to_iso("  30MAR2022  ") == "2022-03-30"


class TestDetectDDMonYYYYFormat:
    """detect_date_format should recognize DDMonYYYY."""

    def test_detect_ddmonyyyy(self) -> None:
        result = detect_date_format(["30MAR2022", "15JAN2023"])
        assert result == "DDMonYYYY"

    def test_detect_mixed_prefers_majority(self) -> None:
        # 2 DDMonYYYY vs 1 DD Mon YYYY
        result = detect_date_format(["30MAR2022", "15JAN2023", "10 Feb 2021"])
        assert result == "DDMonYYYY"
