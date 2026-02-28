"""Tests for ISO 8601 date conversion utilities.

Covers SAS DATE, SAS DATETIME, string parsing, partial dates,
and format detection -- all critical path for SDTM compliance.
"""

from __future__ import annotations

from astraea.transforms.dates import (
    SAS_EPOCH,
    detect_date_format,
    format_partial_iso8601,
    parse_string_date_to_iso,
    sas_date_to_iso,
    sas_datetime_to_iso,
)

# ---------------------------------------------------------------------------
# sas_date_to_iso (DAYS since 1960-01-01)
# ---------------------------------------------------------------------------


class TestSasDateToIso:
    """SAS date values are integer days since 1960-01-01."""

    def test_known_value(self):
        # 22734 days after 1960-01-01 = 2022-03-30
        assert sas_date_to_iso(22734.0) == "2022-03-30"

    def test_epoch(self):
        assert sas_date_to_iso(0.0) == "1960-01-01"

    def test_day_one(self):
        assert sas_date_to_iso(1.0) == "1960-01-02"

    def test_negative_days(self):
        # Before SAS epoch
        assert sas_date_to_iso(-1.0) == "1959-12-31"

    def test_leap_year(self):
        # 2020-02-29 is a leap day. Days from 1960-01-01 to 2020-02-29:
        from datetime import date

        days = (date(2020, 2, 29) - SAS_EPOCH).days
        assert sas_date_to_iso(float(days)) == "2020-02-29"

    def test_none_returns_empty(self):
        assert sas_date_to_iso(None) == ""

    def test_nan_returns_empty(self):
        assert sas_date_to_iso(float("nan")) == ""

    def test_integer_input(self):
        assert sas_date_to_iso(0) == "1960-01-01"

    def test_fractional_rounds_up(self):
        """22738.9999 should round to 22739 = 2022-04-04, not truncate to 22738."""
        assert sas_date_to_iso(22738.9999) == "2022-04-04"

    def test_fractional_rounds_down(self):
        """22738.4 should round to 22738 = 2022-04-03."""
        assert sas_date_to_iso(22738.4) == "2022-04-03"

    def test_exact_integer_unchanged(self):
        """22739.0 stays at 22739 = 2022-04-04."""
        assert sas_date_to_iso(22739.0) == "2022-04-04"


# ---------------------------------------------------------------------------
# sas_datetime_to_iso (SECONDS since 1960-01-01 00:00:00)
# ---------------------------------------------------------------------------


class TestSasDatetimeToIso:
    """SAS datetime values are seconds since 1960-01-01 00:00:00.

    CRITICAL: Sample data uses DATETIME (seconds), not DATE (days).
    Applying the wrong conversion gives dates in year 5000+.
    """

    def test_critical_sample_data_value(self):
        """1964217600 seconds from 1960-01-01 should be ~2022, NOT year 5000+."""
        result = sas_datetime_to_iso(1964217600.0)
        # Must be in 2022 range
        assert result.startswith("2022-"), f"Expected 2022 date, got: {result}"
        assert result == "2022-03-30T00:00:00"

    def test_epoch(self):
        assert sas_datetime_to_iso(0.0) == "1960-01-01T00:00:00"

    def test_one_second(self):
        assert sas_datetime_to_iso(1.0) == "1960-01-01T00:00:01"

    def test_one_day_in_seconds(self):
        assert sas_datetime_to_iso(86400.0) == "1960-01-02T00:00:00"

    def test_noon(self):
        # 12 hours = 43200 seconds
        assert sas_datetime_to_iso(43200.0) == "1960-01-01T12:00:00"

    def test_none_returns_empty(self):
        assert sas_datetime_to_iso(None) == ""

    def test_nan_returns_empty(self):
        assert sas_datetime_to_iso(float("nan")) == ""

    def test_fractional_rounds(self):
        """1964217600.7 rounds to 1964217601 seconds = 2022-03-30T00:00:01."""
        assert sas_datetime_to_iso(1964217600.7) == "2022-03-30T00:00:01"

    def test_exact_unchanged(self):
        """1964217600.0 stays exact = 2022-03-30T00:00:00."""
        assert sas_datetime_to_iso(1964217600.0) == "2022-03-30T00:00:00"

    def test_not_confused_with_date(self):
        """Ensure DATETIME (seconds) is not confused with DATE (days).

        If we mistakenly treat 1964217600 as days, we get:
        1960-01-01 + 1964217600 days = year ~5,380,000. WRONG.
        """
        result = sas_datetime_to_iso(1964217600.0)
        year = int(result[:4])
        assert year < 2100, f"Year {year} suggests DATE/DATETIME confusion!"
        assert year > 2000, f"Year {year} is too early for this value"


# ---------------------------------------------------------------------------
# parse_string_date_to_iso
# ---------------------------------------------------------------------------


class TestParseStringDateToIso:
    """String date parsing for various formats found in clinical data."""

    # DD Mon YYYY -- primary format in Fakedata _RAW columns
    def test_dd_mon_yyyy(self):
        assert parse_string_date_to_iso("30 Mar 2022") == "2022-03-30"

    def test_dd_mon_yyyy_single_digit_day(self):
        assert parse_string_date_to_iso("1 Jan 2023") == "2023-01-01"

    def test_dd_mon_yyyy_case_insensitive(self):
        assert parse_string_date_to_iso("15 DEC 2021") == "2021-12-15"

    def test_dd_mon_yyyy_mixed_case(self):
        assert parse_string_date_to_iso("5 Feb 2020") == "2020-02-05"

    # YYYY-MM-DD passthrough
    def test_yyyy_mm_dd(self):
        assert parse_string_date_to_iso("2022-03-30") == "2022-03-30"

    # DD/MM/YYYY
    def test_dd_mm_yyyy(self):
        assert parse_string_date_to_iso("30/03/2022") == "2022-03-30"

    def test_dd_mm_yyyy_day_greater_than_12(self):
        """Day > 12 unambiguously identifies DD/MM/YYYY."""
        assert parse_string_date_to_iso("25/01/2022") == "2022-01-25"

    # MM/DD/YYYY
    def test_mm_dd_yyyy(self):
        """Month first when second field > 12."""
        assert parse_string_date_to_iso("01/25/2022") == "2022-01-25"

    # Ambiguous slash dates default to DD/MM/YYYY
    def test_ambiguous_slash_defaults_dd_mm(self):
        # 05/06/2022 -> DD/MM/YYYY -> June 5, 2022
        assert parse_string_date_to_iso("05/06/2022") == "2022-06-05"

    # Partial dates
    def test_mon_yyyy_partial(self):
        assert parse_string_date_to_iso("Mar 2022") == "2022-03"

    def test_yyyy_partial(self):
        assert parse_string_date_to_iso("2022") == "2022"

    def test_yyyy_mm_partial(self):
        assert parse_string_date_to_iso("2023-03") == "2023-03"

    # Edge cases
    def test_none_returns_empty(self):
        assert parse_string_date_to_iso(None) == ""

    def test_empty_string_returns_empty(self):
        assert parse_string_date_to_iso("") == ""

    def test_whitespace_returns_empty(self):
        assert parse_string_date_to_iso("   ") == ""

    def test_unparseable_returns_empty(self):
        assert parse_string_date_to_iso("not a date") == ""

    def test_leading_trailing_whitespace(self):
        assert parse_string_date_to_iso("  30 Mar 2022  ") == "2022-03-30"

    # --- Date validation tests ---

    def test_invalid_feb_30_returns_empty(self):
        assert parse_string_date_to_iso("30 Feb 2022") == ""

    def test_invalid_day_32_returns_empty(self):
        assert parse_string_date_to_iso("32 Mar 2022") == ""

    def test_valid_feb_29_leap_year(self):
        assert parse_string_date_to_iso("29 Feb 2024") == "2024-02-29"

    def test_invalid_feb_29_non_leap(self):
        assert parse_string_date_to_iso("29 Feb 2023") == ""

    def test_valid_jan_31(self):
        assert parse_string_date_to_iso("31 Jan 2022") == "2022-01-31"

    def test_invalid_apr_31(self):
        assert parse_string_date_to_iso("31 Apr 2022") == ""

    def test_slash_date_invalid_rejected(self):
        assert parse_string_date_to_iso("30/02/2022") == ""

    # --- UN UNK partial date patterns ---

    def test_un_unk_yyyy(self):
        assert parse_string_date_to_iso("UN UNK 2004") == "2004"

    def test_unk_unk_yyyy(self):
        assert parse_string_date_to_iso("UNK UNK 2004") == "2004"

    def test_un_unk_yyyy_lowercase(self):
        assert parse_string_date_to_iso("un unk 2004") == "2004"

    def test_un_mon_yyyy(self):
        assert parse_string_date_to_iso("UN Mar 2022") == "2022-03"

    def test_unk_mon_yyyy(self):
        assert parse_string_date_to_iso("UNK Mar 2022") == "2022-03"

    # --- Datetime string pattern ---

    def test_dd_mon_yyyy_hhmm(self):
        assert parse_string_date_to_iso("16 MAY 2022 21:30") == "2022-05-16T21:30"

    def test_dd_mon_yyyy_hhmm_lowercase(self):
        assert parse_string_date_to_iso("16 may 2022 21:30") == "2022-05-16T21:30"

    def test_dd_mon_yyyy_hhmm_single_digit_hour(self):
        assert parse_string_date_to_iso("5 Jun 2022 9:15") == "2022-06-05T09:15"

    def test_dd_mon_yyyy_hhmm_midnight(self):
        assert parse_string_date_to_iso("1 Jan 2023 0:00") == "2023-01-01T00:00"


# ---------------------------------------------------------------------------
# format_partial_iso8601
# ---------------------------------------------------------------------------


class TestFormatPartialIso8601:
    """SDTM-IG requires truncated ISO 8601 for partial dates.

    Gaps are NOT allowed: "2023---15" is INVALID.
    """

    def test_year_only(self):
        assert format_partial_iso8601(2023) == "2023"

    def test_year_month(self):
        assert format_partial_iso8601(2023, 3) == "2023-03"

    def test_full_date(self):
        assert format_partial_iso8601(2023, 3, 15) == "2023-03-15"

    def test_full_datetime(self):
        assert format_partial_iso8601(2023, 3, 15, 10, 30, 0) == "2023-03-15T10:30:00"

    def test_date_with_hour(self):
        assert format_partial_iso8601(2023, 3, 15, 10) == "2023-03-15T10"

    def test_date_with_hour_minute(self):
        assert format_partial_iso8601(2023, 3, 15, 10, 30) == "2023-03-15T10:30"

    def test_none_year_returns_empty(self):
        assert format_partial_iso8601(None) == ""

    def test_gap_truncates_at_first_none(self):
        """Year + gap + day should truncate at the gap (month=None)."""
        assert format_partial_iso8601(2023, None, 15) == "2023"

    def test_gap_in_time(self):
        """Date + hour + gap + second should truncate at minute=None."""
        assert format_partial_iso8601(2023, 3, 15, 10, None, 30) == "2023-03-15T10"

    def test_midnight(self):
        assert format_partial_iso8601(2023, 1, 1, 0, 0, 0) == "2023-01-01T00:00:00"

    def test_single_digit_month_padded(self):
        assert format_partial_iso8601(2023, 1) == "2023-01"

    def test_all_none(self):
        assert format_partial_iso8601() == ""

    def test_invalid_month_13_returns_empty(self):
        assert format_partial_iso8601(2022, 13, 1) == ""

    def test_invalid_day_for_month_returns_empty(self):
        """Feb 30 is invalid regardless of year."""
        assert format_partial_iso8601(2022, 2, 30) == ""


# ---------------------------------------------------------------------------
# detect_date_format
# ---------------------------------------------------------------------------


class TestDocstringExamples:
    """Verify that docstring examples match actual function output."""

    def test_sas_date_to_iso_docstring_example_1(self):
        """sas_date_to_iso(22734.0) should return '2022-03-30' per docstring."""
        assert sas_date_to_iso(22734.0) == "2022-03-30"

    def test_sas_date_to_iso_docstring_example_2(self):
        """sas_date_to_iso(0.0) should return '1960-01-01' per docstring."""
        assert sas_date_to_iso(0.0) == "1960-01-01"

    def test_sas_datetime_to_iso_docstring_example_1(self):
        """sas_datetime_to_iso(1964217600.0) should return '2022-03-30T00:00:00'."""
        assert sas_datetime_to_iso(1964217600.0) == "2022-03-30T00:00:00"

    def test_sas_datetime_to_iso_docstring_example_2(self):
        """sas_datetime_to_iso(0.0) should return '1960-01-01T00:00:00'."""
        assert sas_datetime_to_iso(0.0) == "1960-01-01T00:00:00"


class TestDetectDateFormat:
    """Format detection for profiler column annotation."""

    def test_dd_mon_yyyy(self):
        samples = ["30 Mar 2022", "15 Jan 2023", "1 Dec 2021"]
        assert detect_date_format(samples) == "DD Mon YYYY"

    def test_yyyy_mm_dd(self):
        samples = ["2022-03-30", "2023-01-15", "2021-12-01"]
        assert detect_date_format(samples) == "YYYY-MM-DD"

    def test_dd_mm_yyyy_unambiguous(self):
        samples = ["25/03/2022", "30/01/2023", "15/12/2021"]
        assert detect_date_format(samples) == "DD/MM/YYYY"

    def test_mm_dd_yyyy_unambiguous(self):
        samples = ["03/25/2022", "01/30/2023", "12/15/2021"]
        assert detect_date_format(samples) == "MM/DD/YYYY"

    def test_empty_list(self):
        assert detect_date_format([]) is None

    def test_no_dates(self):
        assert detect_date_format(["abc", "def", ""]) is None

    def test_mixed_with_empty(self):
        samples = ["30 Mar 2022", "", "15 Jan 2023"]
        assert detect_date_format(samples) == "DD Mon YYYY"

    def test_majority_wins(self):
        samples = ["30 Mar 2022", "15 Jan 2023", "2022-03-30"]
        assert detect_date_format(samples) == "DD Mon YYYY"
