"""SDTM --DY (study day) calculation utility.

Implements the SDTM "no Day 0" convention:
- Day 1 = reference date (RFSTDTC)
- Day -1 = day before reference date
- No Day 0 exists

All functions are deterministic -- no LLM, no guessing.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from loguru import logger


def calculate_study_day(event_dtc: str | None, rfstdtc: str | None) -> int | None:
    """Calculate --DY (study day) from an event date and reference date.

    Uses the SDTM "no Day 0" convention:
    - If event_date >= ref_date: (event_date - ref_date).days + 1
    - If event_date < ref_date: (event_date - ref_date).days
    This means Day 1 = RFSTDTC, Day -1 = day before RFSTDTC, no Day 0.

    Args:
        event_dtc: ISO 8601 date/datetime string for the event (e.g., "2022-03-30"
            or "2022-03-30T14:30:00"). Only the first 10 characters (date portion)
            are used.
        rfstdtc: ISO 8601 date string for the reference start date (RFSTDTC).
            Only the first 10 characters (date portion) are used.

    Returns:
        Study day as integer, or None if either date is missing, empty, partial
        (< 10 chars), or invalid.

    Examples:
        >>> calculate_study_day("2022-03-30", "2022-03-30")
        1
        >>> calculate_study_day("2022-04-01", "2022-03-30")
        3
        >>> calculate_study_day("2022-03-29", "2022-03-30")
        -1
        >>> calculate_study_day("2022-03", "2022-03-30") is None
        True
    """
    if event_dtc is None or rfstdtc is None:
        return None

    event_str = str(event_dtc).strip()
    ref_str = str(rfstdtc).strip()

    # Need at least 10 chars for a full date (YYYY-MM-DD)
    if len(event_str) < 10 or len(ref_str) < 10:
        return None

    # Extract date portion (first 10 chars)
    event_date_str = event_str[:10]
    ref_date_str = ref_str[:10]

    try:
        event_date = date.fromisoformat(event_date_str)
        ref_date = date.fromisoformat(ref_date_str)
    except ValueError:
        logger.warning(
            "Invalid date(s) for --DY calculation: event='{}', ref='{}'",
            event_dtc,
            rfstdtc,
        )
        return None

    delta_days = (event_date - ref_date).days

    if delta_days >= 0:
        return delta_days + 1  # Day 1 = ref date, Day 2 = next day, etc.
    else:
        return delta_days  # Day -1 = day before ref date


def calculate_study_day_column(
    df: pd.DataFrame,
    date_col: str,
    rfstdtc_lookup: dict[str, str],
    usubjid_col: str = "USUBJID",
) -> pd.Series:
    """Calculate --DY for an entire DataFrame column.

    Vectorized version that looks up each subject's RFSTDTC from a dictionary
    and computes study day for each row.

    Args:
        df: Source DataFrame containing date and USUBJID columns.
        date_col: Column name containing ISO 8601 event dates.
        rfstdtc_lookup: Dictionary mapping USUBJID -> RFSTDTC string.
        usubjid_col: Column name for USUBJID. Default "USUBJID".

    Returns:
        pandas Series with Int64 dtype (nullable integer). NaN for rows where
        study day cannot be calculated (missing dates, unknown USUBJID, etc.).

    Raises:
        KeyError: If required columns are missing from the DataFrame.
    """
    missing = [c for c in [date_col, usubjid_col] if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    def _compute_row(row: pd.Series) -> int | None:
        usubjid = str(row[usubjid_col])
        rfstdtc = rfstdtc_lookup.get(usubjid)
        if rfstdtc is None:
            return None
        event_dtc = row[date_col]
        if pd.isna(event_dtc):
            return None
        return calculate_study_day(str(event_dtc), rfstdtc)

    result = df.apply(_compute_row, axis=1)
    return result.astype("Int64")
