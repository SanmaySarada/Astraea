"""Tests for Phase 14 date/time handling fixes.

Covers:
- ISO datetime passthrough (MED-20)
- HH:MM:SS seconds support (MED-19)
- ISO 8601 timezone offset validation (MED-03)
"""

from __future__ import annotations

import re

import pytest

from astraea.transforms.dates import parse_string_date_to_iso


class TestISODatetimePassthrough:
    """ISO datetime strings should pass through unchanged."""

    def test_iso_datetime_passthrough(self) -> None:
        assert parse_string_date_to_iso("2022-03-30T14:30:00") == "2022-03-30T14:30:00"

    def test_iso_datetime_passthrough_with_tz(self) -> None:
        assert parse_string_date_to_iso("2022-03-30T14:30:00Z") == "2022-03-30T14:30:00Z"

    def test_iso_datetime_passthrough_offset(self) -> None:
        assert (
            parse_string_date_to_iso("2022-03-30T14:30:00+05:30")
            == "2022-03-30T14:30:00+05:30"
        )

    def test_iso_datetime_passthrough_negative_offset(self) -> None:
        assert (
            parse_string_date_to_iso("2022-03-30T14:30:00-04:00")
            == "2022-03-30T14:30:00-04:00"
        )

    def test_iso_datetime_passthrough_hhmm_only(self) -> None:
        assert parse_string_date_to_iso("2022-03-30T14:30") == "2022-03-30T14:30"


class TestDDMonYYYYHHMMSS:
    """DD Mon YYYY HH:MM:SS format with seconds."""

    def test_dd_mon_yyyy_hhmmss(self) -> None:
        assert parse_string_date_to_iso("30 Mar 2022 14:30:45") == "2022-03-30T14:30:45"

    def test_dd_mon_yyyy_hhmm_still_works(self) -> None:
        assert parse_string_date_to_iso("30 Mar 2022 14:30") == "2022-03-30T14:30"

    def test_dd_mon_yyyy_hhmmss_midnight(self) -> None:
        assert parse_string_date_to_iso("01 Jan 2023 00:00:00") == "2023-01-01T00:00:00"

    def test_dd_mon_yyyy_hhmmss_end_of_day(self) -> None:
        assert parse_string_date_to_iso("31 Dec 2022 23:59:59") == "2022-12-31T23:59:59"


class TestISOTimezoneValidation:
    """Validation regex accepts timezone offsets."""

    @pytest.fixture()
    def iso_pattern(self) -> re.Pattern[str]:
        from astraea.validation.rules.format import _ISO_8601_PATTERN

        return _ISO_8601_PATTERN

    def test_iso_tz_z_passes(self, iso_pattern: re.Pattern[str]) -> None:
        assert iso_pattern.match("2022-03-30T14:30:00Z")

    def test_iso_tz_positive_offset_passes(self, iso_pattern: re.Pattern[str]) -> None:
        assert iso_pattern.match("2022-03-30T14:30:00+05:30")

    def test_iso_tz_negative_offset_passes(self, iso_pattern: re.Pattern[str]) -> None:
        assert iso_pattern.match("2022-03-30T14:30:00-04:00")

    def test_plain_date_passes(self, iso_pattern: re.Pattern[str]) -> None:
        assert iso_pattern.match("2022-03-30")

    def test_partial_yyyy_mm_passes(self, iso_pattern: re.Pattern[str]) -> None:
        assert iso_pattern.match("2022-03")

    def test_partial_yyyy_passes(self, iso_pattern: re.Pattern[str]) -> None:
        assert iso_pattern.match("2022")

    def test_tz_without_time_does_not_match(self, iso_pattern: re.Pattern[str]) -> None:
        """Timezone offset should only be valid with a time component."""
        assert not iso_pattern.match("2022-03-30Z")

    def test_hhmm_with_tz_passes(self, iso_pattern: re.Pattern[str]) -> None:
        assert iso_pattern.match("2022-03-30T14:30Z")


class TestExistingFormatsUnbroken:
    """Ensure no regression in existing date format handling."""

    def test_dd_mon_yyyy(self) -> None:
        assert parse_string_date_to_iso("30 Mar 2022") == "2022-03-30"

    def test_mon_yyyy(self) -> None:
        assert parse_string_date_to_iso("Mar 2022") == "2022-03"

    def test_yyyy(self) -> None:
        assert parse_string_date_to_iso("2022") == "2022"

    def test_yyyy_mm_dd(self) -> None:
        assert parse_string_date_to_iso("2022-03-30") == "2022-03-30"

    def test_un_unk_yyyy(self) -> None:
        assert parse_string_date_to_iso("un UNK 2022") == "2022"

    def test_un_mon_yyyy(self) -> None:
        assert parse_string_date_to_iso("un Mar 2022") == "2022-03"

    def test_empty_string(self) -> None:
        assert parse_string_date_to_iso("") == ""

    def test_none(self) -> None:
        assert parse_string_date_to_iso(None) == ""
