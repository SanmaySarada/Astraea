"""Character variable length optimization for XPT files.

XPT v5 character variables default to 200 bytes if no explicit width is set.
This module computes the optimal (minimum necessary) byte width for each
character column, preventing bloated XPT files and potential P21 warnings.
"""

from __future__ import annotations

import pandas as pd
from loguru import logger


def optimize_char_lengths(df: pd.DataFrame) -> dict[str, int]:
    """Compute optimal byte width for each character column.

    For each object/string column, determines the maximum byte length
    of non-null values (using ASCII encoding with replacement for any
    remaining non-ASCII bytes). Minimum width is always 1.

    Args:
        df: DataFrame to analyze.

    Returns:
        Dict mapping column name to optimal byte width.
        Only includes object/string columns.
    """
    widths: dict[str, int] = {}
    string_cols = df.select_dtypes(include=["object", "string"]).columns

    for col in string_cols:
        non_null = df[col].dropna()
        if len(non_null) == 0:
            widths[col] = 1
        else:
            max_len = non_null.astype(str).str.encode("ascii", errors="replace").str.len().max()
            widths[col] = max(1, int(max_len))

    # Cap at XPT v5 max of 200 bytes
    for col in widths:
        if widths[col] > 200:
            logger.warning(
                "Column '{}' width {} exceeds 200-byte XPT max, capping to 200",
                col,
                widths[col],
            )
            widths[col] = 200

    logger.debug(
        "Optimized character lengths for {} column(s): {}",
        len(widths),
        widths,
    )
    return widths


def validate_char_max_length(
    df: pd.DataFrame, max_bytes: int = 200
) -> dict[str, list[int]]:
    """Validate that character column values do not exceed max byte length.

    Iterates over string/object columns, encodes non-null values to ASCII
    (with replacement for non-ASCII bytes), and checks byte length against
    the limit.

    Args:
        df: DataFrame to validate.
        max_bytes: Maximum allowed byte length per value. Default 200
            (XPT v5 character variable limit).

    Returns:
        Dict mapping column name to list of row indices where values
        exceed max_bytes. Empty dict if no violations found.
    """
    violations: dict[str, list[int]] = {}
    string_cols = df.select_dtypes(include=["object", "string"]).columns

    for col in string_cols:
        col_violations: list[int] = []
        for idx in df.index:
            val = df.at[idx, col]
            if pd.isna(val):
                continue
            byte_len = len(str(val).encode("ascii", errors="replace"))
            if byte_len > max_bytes:
                col_violations.append(idx)
        if col_violations:
            violations[col] = col_violations

    if violations:
        logger.warning(
            "Character length violations in {} column(s): {}",
            len(violations),
            {k: len(v) for k, v in violations.items()},
        )

    return violations
