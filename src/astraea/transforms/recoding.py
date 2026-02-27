"""Recoding transforms for SDTM value conversions.

Provides functions that recode raw clinical data values into
CDISC Controlled Terminology-compliant values (e.g., numeric
checkbox 0/1 to Y/N per C66742).
"""

from __future__ import annotations

import pandas as pd


def numeric_to_yn(value: object) -> str | None:
    """Convert numeric 0/1 or checkbox values to Y/N for C66742 codelist.

    Handles float64 (0.0/1.0), int (0/1), and string ("0"/"1") inputs.
    Returns None for NaN/missing values.

    Args:
        value: Raw value from source data. Can be int, float, str, or missing.

    Returns:
        "Y" for truthy (1), "N" for falsy (0), or None for missing/unexpected.
    """
    # Handle missing values first
    if value is None or pd.isna(value):
        return None

    # Numeric path (int or float)
    if isinstance(value, (int, float)):
        if value == 1:
            return "Y"
        if value == 0:
            return "N"
        return None

    # String fallback
    stripped = str(value).strip()
    if stripped in ("1", "1.0"):
        return "Y"
    if stripped in ("0", "0.0"):
        return "N"

    return None
