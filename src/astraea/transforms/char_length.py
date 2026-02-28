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

    logger.debug(
        "Optimized character lengths for {} column(s): {}",
        len(widths),
        widths,
    )
    return widths
