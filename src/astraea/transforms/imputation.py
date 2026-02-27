"""Date and time imputation flag utilities for SDTM --DTF and --TMF variables.

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


def get_date_imputation_flag(
    original_dtc: str, imputed_dtc: str
) -> str | None:
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


def get_time_imputation_flag(
    original_dtc: str, imputed_dtc: str
) -> str | None:
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
