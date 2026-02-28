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


# --- SEX recoding (C66731) ---

_SEX_MAP: dict[str, str] = {
    "male": "M",
    "m": "M",
    "1": "M",
    "female": "F",
    "f": "F",
    "2": "F",
    "unknown": "U",
    "u": "U",
    "undifferentiated": "UNDIFFERENTIATED",
}


def recode_sex(value: object) -> str | None:
    """Recode raw sex values to C66731 submission values (M/F/U/UNDIFFERENTIATED).

    Handles case-insensitive text, single-letter abbreviations, and numeric codes.

    Args:
        value: Raw value from source data.

    Returns:
        CDISC CT submission value, or None for missing/unrecognized values.
    """
    if value is None or pd.isna(value):
        return None
    key = str(value).strip().lower()
    return _SEX_MAP.get(key)


# --- RACE recoding (C74457) ---

_RACE_MAP: dict[str, str] = {
    "white": "WHITE",
    "caucasian": "WHITE",
    "1": "WHITE",
    "black": "BLACK OR AFRICAN AMERICAN",
    "black or african american": "BLACK OR AFRICAN AMERICAN",
    "african american": "BLACK OR AFRICAN AMERICAN",
    "2": "BLACK OR AFRICAN AMERICAN",
    "asian": "ASIAN",
    "3": "ASIAN",
    "american indian": "AMERICAN INDIAN OR ALASKA NATIVE",
    "american indian or alaska native": "AMERICAN INDIAN OR ALASKA NATIVE",
    "native american": "AMERICAN INDIAN OR ALASKA NATIVE",
    "alaska native": "AMERICAN INDIAN OR ALASKA NATIVE",
    "4": "AMERICAN INDIAN OR ALASKA NATIVE",
    "native hawaiian": "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
    "native hawaiian or other pacific islander": "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
    "pacific islander": "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
    "5": "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
    "other": "OTHER",
    "6": "OTHER",
    "multiple": "MULTIPLE",
    "mixed": "MULTIPLE",
    "7": "MULTIPLE",
}


def recode_race(value: object) -> str | None:
    """Recode raw race values to C74457 submission values.

    Handles case-insensitive text, common aliases, and numeric codes.

    Args:
        value: Raw value from source data.

    Returns:
        CDISC CT submission value, or None for missing/unrecognized values.
    """
    if value is None or pd.isna(value):
        return None
    key = str(value).strip().lower()
    return _RACE_MAP.get(key)


# --- ETHNIC recoding (C66790) ---

_ETHNIC_MAP: dict[str, str] = {
    "hispanic": "HISPANIC OR LATINO",
    "hispanic or latino": "HISPANIC OR LATINO",
    "latino": "HISPANIC OR LATINO",
    "1": "HISPANIC OR LATINO",
    "not hispanic": "NOT HISPANIC OR LATINO",
    "not hispanic or latino": "NOT HISPANIC OR LATINO",
    "2": "NOT HISPANIC OR LATINO",
    "unknown": "UNKNOWN",
    "u": "UNKNOWN",
    "3": "UNKNOWN",
    "not reported": "NOT REPORTED",
    "nr": "NOT REPORTED",
    "4": "NOT REPORTED",
}


def recode_ethnic(value: object) -> str | None:
    """Recode raw ethnicity values to C66790 submission values.

    Handles case-insensitive text, short forms, and numeric codes.

    Args:
        value: Raw value from source data.

    Returns:
        CDISC CT submission value, or None for missing/unrecognized values.
    """
    if value is None or pd.isna(value):
        return None
    key = str(value).strip().lower()
    return _ETHNIC_MAP.get(key)
