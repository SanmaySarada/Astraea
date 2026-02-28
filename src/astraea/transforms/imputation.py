"""Date and time imputation flag and imputation utilities for SDTM.

Provides:
- Imputation flag detection (--DTF, --TMF) for tracking what was imputed
- Partial date imputation (impute_partial_date) for filling missing components

When partial dates/times are imputed to full ISO 8601 values, SDTM requires
corresponding imputation flag variables (e.g., AESTDTF, LBDTTMF) to indicate
which components were imputed.

Date imputation flags (--DTF):
    D = day was imputed
    M = month (and day) was imputed
    Y = year (and month and day) was imputed

Time imputation flags (--TMF):
    H = hour was imputed
    M = minute (and second) was imputed
    S = second was imputed
"""

from __future__ import annotations

import calendar
import re


def get_date_imputation_flag(original_dtc: str, imputed_dtc: str) -> str | None:
    """Determine the date imputation flag (--DTF) by comparing original and imputed DTC.

    Compares the date portion of the original partial DTC against a full date
    to determine what level of imputation occurred.

    Args:
        original_dtc: The original (possibly partial) ISO 8601 date/time string.
        imputed_dtc: The imputed (full) ISO 8601 date/time string.

    Returns:
        None if no date imputation, "D" if day imputed, "M" if month imputed,
        "Y" if year imputed. Returns None if either input is missing/empty.
    """
    if not original_dtc or not imputed_dtc:
        return None

    # Extract date portion (before T if present)
    date_part = original_dtc.split("T")[0]
    date_len = len(date_part)

    if date_len >= 10:  # YYYY-MM-DD
        return None
    if date_len >= 7:  # YYYY-MM
        return "D"
    if date_len >= 4:  # YYYY
        return "M"
    return "Y"


def get_time_imputation_flag(original_dtc: str, imputed_dtc: str) -> str | None:
    """Determine the time imputation flag (--TMF) by comparing original and imputed DTC.

    Compares the time portion of the original partial DTC against a full datetime
    to determine what level of time imputation occurred.

    Args:
        original_dtc: The original (possibly partial) ISO 8601 date/time string.
        imputed_dtc: The imputed (full) ISO 8601 date/time string.

    Returns:
        None if no time imputation, "H" if hour imputed, "M" if minute imputed,
        "S" if second imputed. Returns None if either input is missing/empty.
    """
    if not original_dtc or not imputed_dtc:
        return None

    has_original_time = "T" in original_dtc
    has_imputed_time = "T" in imputed_dtc

    # If imputed has time but original doesn't, entire time was imputed
    if not has_original_time and has_imputed_time:
        return "H"

    # If neither has time, no time imputation
    if not has_original_time and not has_imputed_time:
        return None

    # If original has time, check how complete it is
    # Extract time portion (after T), strip colons for length check
    time_part = original_dtc.split("T")[1] if has_original_time else ""
    time_digits = time_part.replace(":", "")
    time_len = len(time_digits)

    if time_len >= 6:  # HHMMSS
        return None
    if time_len >= 4:  # HHMM
        return "S"
    if time_len >= 2:  # HH
        return "M"
    return "H"


# Regex patterns for partial ISO 8601 date parsing
_RE_YYYY = re.compile(r"^(\d{4})$")
_RE_YYYY_MM = re.compile(r"^(\d{4})-(\d{2})$")
_RE_YYYY_MM_DD = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_RE_YYYY_MM_DD_THH = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2})$")
_RE_YYYY_MM_DD_THHMM = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$")
_RE_FULL_DATETIME = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})$"
)

_VALID_METHODS = {"first", "last", "mid"}


def impute_partial_date(
    partial_dtc: str | None,
    method: str = "first",
) -> str:
    """Impute missing components of a partial ISO 8601 date.

    Args:
        partial_dtc: Partial ISO 8601 date (e.g., "2022", "2022-03", "2022-03-30T14")
        method: Imputation method - "first" (Jan 1 / 00:00:00), "last" (Dec 31 / 23:59:59),
                "mid" (Jun 15 / 12:00:00)

    Returns:
        Imputed ISO 8601 date string. Returns input unchanged if already complete.
        Returns empty string for empty/null input.

    Raises:
        ValueError: If method is not one of "first", "last", "mid".
    """
    if method not in _VALID_METHODS:
        msg = f"Invalid imputation method '{method}'. Must be one of: {', '.join(sorted(_VALID_METHODS))}"
        raise ValueError(msg)

    if partial_dtc is None or not str(partial_dtc).strip():
        return ""

    s = str(partial_dtc).strip()

    # Already a full datetime -- return as-is
    if _RE_FULL_DATETIME.match(s):
        return s

    # YYYY-MM-DDTHH:MM -- only seconds missing
    m = _RE_YYYY_MM_DD_THHMM.match(s)
    if m:
        return s  # date is complete, time has HH:MM -- no imputation needed

    # YYYY-MM-DDTHH -- minutes and seconds missing
    m = _RE_YYYY_MM_DD_THH.match(s)
    if m:
        year, month, day, hour = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        if method == "first":
            return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:00:00"
        elif method == "last":
            return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:59:59"
        else:  # mid
            return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:30:00"

    # YYYY-MM-DD -- complete date, return as-is
    if _RE_YYYY_MM_DD.match(s):
        return s

    # YYYY-MM -- day missing
    m = _RE_YYYY_MM.match(s)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if method == "first":
            return f"{year:04d}-{month:02d}-01"
        elif method == "last":
            last_day = calendar.monthrange(year, month)[1]
            return f"{year:04d}-{month:02d}-{last_day:02d}"
        else:  # mid
            return f"{year:04d}-{month:02d}-15"

    # YYYY -- month and day missing
    m = _RE_YYYY.match(s)
    if m:
        year = int(m.group(1))
        if method == "first":
            return f"{year:04d}-01-01"
        elif method == "last":
            return f"{year:04d}-12-31"
        else:  # mid
            return f"{year:04d}-06-15"

    # Unrecognized format -- return as-is
    return s


def impute_partial_date_with_flag(
    partial_dtc: str | None,
    method: str = "first",
) -> tuple[str, str | None, str | None]:
    """Impute partial date and return (imputed_date, dtf_flag, tmf_flag).

    Combines impute_partial_date with get_date_imputation_flag/get_time_imputation_flag.

    Args:
        partial_dtc: Partial ISO 8601 date string.
        method: Imputation method ("first", "last", "mid").

    Returns:
        Tuple of (imputed_date, date_imputation_flag, time_imputation_flag).
    """
    if partial_dtc is None or not str(partial_dtc).strip():
        return ("", None, None)

    original = str(partial_dtc).strip()
    imputed = impute_partial_date(original, method=method)

    dtf = get_date_imputation_flag(original, imputed)
    tmf = get_time_imputation_flag(original, imputed)

    return (imputed, dtf, tmf)
