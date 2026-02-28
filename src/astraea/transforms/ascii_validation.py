"""ASCII validation and cleanup for XPT character data.

XPT v5 (SAS Transport) requires ASCII-only character data. This module
detects non-ASCII characters in DataFrame string columns and provides
auto-replacement for common non-ASCII characters found in clinical data
(curly quotes, en-dash, degree sign, etc.).
"""

from __future__ import annotations

import pandas as pd
from loguru import logger

# Common non-ASCII characters found in clinical data and their ASCII replacements.
_NON_ASCII_REPLACEMENTS: dict[str, str] = {
    "\u2018": "'",  # left single curly quote
    "\u2019": "'",  # right single curly quote
    "\u201c": '"',  # left double curly quote
    "\u201d": '"',  # right double curly quote
    "\u2013": "-",  # en-dash
    "\u2014": "-",  # em-dash
    "\u2026": "...",  # ellipsis
    "\u00b0": "deg",  # degree sign
    "\u00b5": "u",  # micro sign (mu)
    "\u00b1": "+-",  # plus-minus
    "\u2264": "<=",  # less-than-or-equal
    "\u2265": ">=",  # greater-than-or-equal
}

_MAX_ISSUES = 100


def validate_ascii(df: pd.DataFrame) -> list[dict[str, str | int]]:
    """Check all string columns for non-ASCII characters.

    Args:
        df: DataFrame to validate.

    Returns:
        List of dicts with keys: column, row, value, non_ascii_chars.
        Capped at 100 issues to avoid memory explosion.
    """
    issues: list[dict[str, str | int]] = []

    string_cols = df.select_dtypes(include=["object", "string"]).columns

    for col in string_cols:
        for row_idx, val in df[col].items():
            if len(issues) >= _MAX_ISSUES:
                break
            if pd.isna(val):
                continue
            str_val = str(val)
            if not str_val.isascii():
                non_ascii = "".join(c for c in str_val if ord(c) > 127)
                issues.append(
                    {
                        "column": col,
                        "row": row_idx,
                        "value": str_val,
                        "non_ascii_chars": non_ascii,
                    }
                )
        if len(issues) >= _MAX_ISSUES:
            break

    if issues:
        logger.warning(
            "Found {} non-ASCII issue(s) across string columns (capped at {})",
            len(issues),
            _MAX_ISSUES,
        )
    else:
        logger.debug("All string columns contain ASCII-only data")

    return issues


def fix_common_non_ascii(df: pd.DataFrame) -> pd.DataFrame:
    """Replace common non-ASCII characters with ASCII equivalents.

    Works on a copy of the DataFrame. Applies replacements from the
    ``_NON_ASCII_REPLACEMENTS`` map to all object/string columns.

    Args:
        df: DataFrame to fix.

    Returns:
        New DataFrame with common non-ASCII characters replaced.
    """
    result = df.copy()
    string_cols = result.select_dtypes(include=["object", "string"]).columns

    for col in string_cols:
        col_replacements = 0
        for old_char, new_char in _NON_ASCII_REPLACEMENTS.items():
            mask = result[col].astype(str).str.contains(old_char, na=False)
            count = mask.sum()
            if count > 0:
                result[col] = result[col].astype(str).str.replace(old_char, new_char, regex=False)
                col_replacements += count
        if col_replacements > 0:
            logger.info(
                "Column '{}': {} non-ASCII replacement(s) applied",
                col,
                col_replacements,
            )

    return result
