"""ISO 8601 date conversion utilities for SDTM.

Deterministic converters for:
- SAS DATE values (days since 1960-01-01) -> ISO 8601
- SAS DATETIME values (seconds since 1960-01-01 00:00:00) -> ISO 8601
- String dates in various formats -> ISO 8601
- Partial dates -> truncated ISO 8601 per SDTM-IG rules

All functions are pure -- no LLM, no guessing, no side effects.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, date, datetime, timedelta

from loguru import logger


def _validate_date_components(
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
) -> bool:
    """Validate that date components form a real calendar date.

    Args:
        year: 4-digit year (1800-2100 range).
        month: Month (1-12).
        day: Day (1-31, validated against month/year).

    Returns:
        True if all provided components are valid, False otherwise.
    """
    if year is not None and (year < 1800 or year > 2100):
        return False
    if month is not None and (month < 1 or month > 12):
        return False
    if day is not None:
        if day < 1 or day > 31:
            return False
        # If we have all three components, validate via datetime.date
        if year is not None and month is not None:
            try:
                date(year, month, day)
            except ValueError:
                return False
    return True


# SAS epoch: 1960-01-01
SAS_EPOCH = date(1960, 1, 1)
SAS_EPOCH_DATETIME = datetime(1960, 1, 1, tzinfo=UTC)

# Month abbreviation -> number mapping (case-insensitive)
_MONTH_ABBREV: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# Regex patterns for date format detection

# Partial date patterns with UN/UNK for unknown components
_PATTERN_UN_UNK_YYYY = re.compile(
    r"^\s*(?:un|unk)\s+(?:un|unk)\s+(\d{4})\s*$",
    re.IGNORECASE,
)
_PATTERN_UN_MON_YYYY = re.compile(
    r"^\s*(?:un|unk)\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{4})\s*$",
    re.IGNORECASE,
)

# Datetime string pattern: "DD MON YYYY HH:MM"
_PATTERN_DD_MON_YYYY_HHMM = re.compile(
    r"^\s*(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*$",
    re.IGNORECASE,
)

_PATTERN_DD_MON_YYYY = re.compile(
    r"^\s*(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{4})\s*$",
    re.IGNORECASE,
)
_PATTERN_MON_YYYY = re.compile(
    r"^\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{4})\s*$",
    re.IGNORECASE,
)
_PATTERN_YYYY_MM_DD = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$")
_PATTERN_YYYY_MM = re.compile(r"^\s*(\d{4})-(\d{2})\s*$")
_PATTERN_YYYY = re.compile(r"^\s*(\d{4})\s*$")
_PATTERN_DDMONYYYY = re.compile(
    r"^\s*(\d{1,2})(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{4})\s*$",
    re.IGNORECASE,
)
_PATTERN_SLASH_DMY_OR_MDY = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")


def _is_nan(value: object) -> bool:
    """Check if a value is NaN (works for float and numpy types)."""
    if value is None:
        return True
    try:
        return math.isnan(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def sas_date_to_iso(sas_numeric: float | None) -> str:
    """Convert SAS date value (DAYS since 1960-01-01) to ISO 8601.

    Args:
        sas_numeric: Number of days since SAS epoch (1960-01-01).
            None or NaN returns empty string.

    Returns:
        ISO 8601 date string "YYYY-MM-DD", or "" for missing values.

    Examples:
        >>> sas_date_to_iso(22734.0)
        '2022-03-30'
        >>> sas_date_to_iso(0.0)
        '1960-01-01'
        >>> sas_date_to_iso(None)
        ''
    """
    if _is_nan(sas_numeric):
        return ""

    days = round(sas_numeric)  # type: ignore[arg-type]
    result_date = SAS_EPOCH + timedelta(days=days)
    return result_date.isoformat()


def sas_datetime_to_iso(sas_numeric: float | None) -> str:
    """Convert SAS datetime value (SECONDS since 1960-01-01 00:00:00) to ISO 8601.

    CRITICAL: Sample data uses DATETIME format (seconds since epoch),
    NOT DATE format (days since epoch). Using the wrong conversion gives
    dates in year 5000+.

    Args:
        sas_numeric: Number of seconds since SAS epoch (1960-01-01 00:00:00).
            None or NaN returns empty string.

    Returns:
        ISO 8601 datetime string "YYYY-MM-DDTHH:MM:SS", or "" for missing values.

    Examples:
        >>> sas_datetime_to_iso(1964217600.0)
        '2022-03-30T00:00:00'
        >>> sas_datetime_to_iso(0.0)
        '1960-01-01T00:00:00'
        >>> sas_datetime_to_iso(None)
        ''
    """
    if _is_nan(sas_numeric):
        return ""

    seconds = round(sas_numeric)  # type: ignore[arg-type]
    result_dt = SAS_EPOCH_DATETIME + timedelta(seconds=seconds)
    # Format without timezone info (SDTM dates are typically timezone-naive)
    return result_dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_string_date_to_iso(date_str: str | None) -> str:
    """Parse various string date formats to ISO 8601.

    Supported formats (detected via regex):
        - "DD Mon YYYY" (e.g., "30 Mar 2022") -> "2022-03-30"
        - "YYYY-MM-DD" -> pass through
        - "DD/MM/YYYY" -> "YYYY-MM-DD"
        - "MM/DD/YYYY" -> "YYYY-MM-DD" (if first field <= 12 and second > 12)
        - "Mon YYYY" (partial) -> "YYYY-MM"
        - "YYYY" (partial) -> "YYYY"

    For ambiguous slash-separated dates (both fields <= 12), assumes DD/MM/YYYY.

    Args:
        date_str: Date string in any supported format. None or empty returns "".

    Returns:
        ISO 8601 date string, or "" for missing/unparseable input.

    Examples:
        >>> parse_string_date_to_iso("30 Mar 2022")
        '2022-03-30'
        >>> parse_string_date_to_iso("Mar 2022")
        '2022-03'
        >>> parse_string_date_to_iso("2022")
        '2022'
    """
    if date_str is None or not str(date_str).strip():
        return ""

    s = str(date_str).strip()

    # "UN UNK YYYY" or "UNK UNK YYYY" -- unknown day and month
    m = _PATTERN_UN_UNK_YYYY.match(s)
    if m:
        year = int(m.group(1))
        if not _validate_date_components(year=year):
            logger.warning("Invalid year in date string: '{}'", s)
            return ""
        return f"{year:04d}"

    # "UN Mon YYYY" or "UNK Mon YYYY" -- unknown day only
    m = _PATTERN_UN_MON_YYYY.match(s)
    if m:
        month = _MONTH_ABBREV[m.group(1).lower()]
        year = int(m.group(2))
        if not _validate_date_components(year=year, month=month):
            logger.warning("Invalid date components in: '{}'", s)
            return ""
        return f"{year:04d}-{month:02d}"

    # "DD MON YYYY HH:MM" -- datetime string (must be before DD Mon YYYY)
    m = _PATTERN_DD_MON_YYYY_HHMM.match(s)
    if m:
        day = int(m.group(1))
        month = _MONTH_ABBREV[m.group(2).lower()]
        year = int(m.group(3))
        hour = int(m.group(4))
        minute = int(m.group(5))
        if not _validate_date_components(year=year, month=month, day=day):
            logger.warning("Invalid date in datetime string: '{}'", s)
            return ""
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            logger.warning("Invalid time in datetime string: '{}'", s)
            return ""
        return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}"

    # "DD Mon YYYY" -- primary format in Fakedata _RAW columns
    m = _PATTERN_DD_MON_YYYY.match(s)
    if m:
        day = int(m.group(1))
        month = _MONTH_ABBREV[m.group(2).lower()]
        year = int(m.group(3))
        if not _validate_date_components(year=year, month=month, day=day):
            logger.warning("Invalid date: '{}'", s)
            return ""
        return f"{year:04d}-{month:02d}-{day:02d}"

    # "DDMonYYYY" -- no spaces (e.g., "30MAR2022")
    m = _PATTERN_DDMONYYYY.match(s)
    if m:
        day = int(m.group(1))
        month = _MONTH_ABBREV[m.group(2).lower()]
        year = int(m.group(3))
        if not _validate_date_components(year=year, month=month, day=day):
            logger.warning("Invalid date: '{}'", s)
            return ""
        return f"{year:04d}-{month:02d}-{day:02d}"

    # "YYYY-MM-DD" -- pass through (with validation)
    m = _PATTERN_YYYY_MM_DD.match(s)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        day = int(m.group(3))
        if not _validate_date_components(year=year, month=month, day=day):
            logger.warning("Invalid date: '{}'", s)
            return ""
        return s.strip()

    # "Mon YYYY" -- partial date
    m = _PATTERN_MON_YYYY.match(s)
    if m:
        month = _MONTH_ABBREV[m.group(1).lower()]
        year = int(m.group(2))
        if not _validate_date_components(year=year, month=month):
            logger.warning("Invalid date: '{}'", s)
            return ""
        return f"{year:04d}-{month:02d}"

    # "YYYY-MM" -- partial, pass through
    m = _PATTERN_YYYY_MM.match(s)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        if not _validate_date_components(year=year, month=month):
            logger.warning("Invalid date: '{}'", s)
            return ""
        return s.strip()

    # Slash-separated: DD/MM/YYYY or MM/DD/YYYY
    m = _PATTERN_SLASH_DMY_OR_MDY.match(s)
    if m:
        first = int(m.group(1))
        second = int(m.group(2))
        year = int(m.group(3))

        if first > 12:
            # Must be DD/MM/YYYY (day > 12 can't be month)
            day, month = first, second
        elif second > 12:
            # Must be MM/DD/YYYY (second > 12 can't be month)
            month, day = first, second
        else:
            # Ambiguous -- default to DD/MM/YYYY
            day, month = first, second
            logger.debug(
                "Ambiguous date '{}': assuming DD/MM/YYYY -> day={}, month={}",
                s,
                day,
                month,
            )

        if not _validate_date_components(year=year, month=month, day=day):
            logger.warning("Invalid date: '{}'", s)
            return ""
        return f"{year:04d}-{month:02d}-{day:02d}"

    # "YYYY" -- partial year only
    m = _PATTERN_YYYY.match(s)
    if m:
        year = int(m.group(1))
        if not _validate_date_components(year=year):
            logger.warning("Invalid year: '{}'", s)
            return ""
        return s.strip()

    logger.warning("Could not parse date string: '{}'", s)
    return ""


def format_partial_iso8601(
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    hour: int | None = None,
    minute: int | None = None,
    second: int | None = None,
) -> str:
    """Build ISO 8601 string, truncating from the right at first None.

    Per SDTM-IG: gaps are NOT allowed in ISO 8601 dates.
    "2023---15" is INVALID. Components must be contiguous from the left.

    Args:
        year: 4-digit year (required for non-empty output).
        month: Month (1-12).
        day: Day (1-31).
        hour: Hour (0-23).
        minute: Minute (0-59).
        second: Second (0-59).

    Returns:
        Truncated ISO 8601 string, or "" if year is None.

    Examples:
        >>> format_partial_iso8601(2023)
        '2023'
        >>> format_partial_iso8601(2023, 3)
        '2023-03'
        >>> format_partial_iso8601(2023, 3, 15)
        '2023-03-15'
        >>> format_partial_iso8601(2023, 3, 15, 10, 30, 0)
        '2023-03-15T10:30:00'
        >>> format_partial_iso8601(2023, None, 15)
        '2023'
    """
    if year is None:
        return ""

    if not _validate_date_components(year=year, month=month, day=day):
        logger.warning(
            "Invalid date components: year={}, month={}, day={}",
            year,
            month,
            day,
        )
        return ""

    result = f"{year:04d}"

    if month is None:
        return result
    result += f"-{month:02d}"

    if day is None:
        return result
    result += f"-{day:02d}"

    if hour is None or minute is None:
        return result
    result += f"T{hour:02d}:{minute:02d}"

    if second is None:
        return result
    result += f":{second:02d}"

    return result


def detect_date_format(samples: list[str]) -> str | None:
    """Examine sample string values and determine the date format.

    Examines non-empty sample values and returns the most common detected format.

    Args:
        samples: List of sample date strings from a column.

    Returns:
        Format name: "DD Mon YYYY", "YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY",
        or None if no format detected.
    """
    if not samples:
        return None

    format_counts: dict[str, int] = {}

    for s in samples:
        if not s or not str(s).strip():
            continue

        s = str(s).strip()

        if _PATTERN_DD_MON_YYYY.match(s):
            format_counts["DD Mon YYYY"] = format_counts.get("DD Mon YYYY", 0) + 1
        elif _PATTERN_DDMONYYYY.match(s):
            format_counts["DDMonYYYY"] = format_counts.get("DDMonYYYY", 0) + 1
        elif _PATTERN_YYYY_MM_DD.match(s):
            format_counts["YYYY-MM-DD"] = format_counts.get("YYYY-MM-DD", 0) + 1
        elif _PATTERN_SLASH_DMY_OR_MDY.match(s):
            m = _PATTERN_SLASH_DMY_OR_MDY.match(s)
            assert m is not None
            first = int(m.group(1))
            second = int(m.group(2))

            if first > 12:
                format_counts["DD/MM/YYYY"] = format_counts.get("DD/MM/YYYY", 0) + 1
            elif second > 12:
                format_counts["MM/DD/YYYY"] = format_counts.get("MM/DD/YYYY", 0) + 1
            else:
                # Ambiguous -- count as DD/MM/YYYY by default
                format_counts["DD/MM/YYYY"] = format_counts.get("DD/MM/YYYY", 0) + 1

    if not format_counts:
        return None

    # Return the most common format
    return max(format_counts, key=format_counts.get)  # type: ignore[arg-type]
