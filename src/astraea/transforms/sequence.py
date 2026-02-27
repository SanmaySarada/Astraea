"""SDTM --SEQ (sequence number) generation utility.

Generates monotonic integer sequence numbers (1, 2, 3, ...) within each
USUBJID group, suitable for AESEQ, LBSEQ, VSSEQ, etc.

All functions are deterministic -- no LLM, no guessing.
"""

from __future__ import annotations

import pandas as pd
from loguru import logger


def generate_seq(
    df: pd.DataFrame,
    domain: str,
    sort_keys: list[str],
    usubjid_col: str = "USUBJID",
) -> pd.Series:
    """Generate --SEQ sequence numbers within each USUBJID group.

    Sorts the DataFrame by USUBJID and the specified sort keys, then assigns
    monotonically increasing integers (1, 2, 3, ...) within each USUBJID group.

    Args:
        df: Source DataFrame. Must contain the usubjid_col column.
        domain: SDTM domain code (e.g., "AE", "LB"). Used for logging only.
        sort_keys: List of column names to sort by within each USUBJID group.
            Columns not present in df are silently skipped.
        usubjid_col: Column name for USUBJID. Default "USUBJID".

    Returns:
        pandas Series with Int64 dtype containing sequence numbers (1-based).
        The series index matches the ORIGINAL DataFrame index, not the sorted order.

    Examples:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     "USUBJID": ["S001", "S001", "S002", "S001"],
        ...     "AESTDTC": ["2022-01-01", "2022-02-01", "2022-01-15", "2022-03-01"],
        ... })
        >>> generate_seq(df, "AE", ["AESTDTC"])
        0    1
        1    2
        2    1
        3    3
        dtype: Int64
    """
    if df.empty:
        return pd.Series(dtype="Int64")

    if usubjid_col not in df.columns:
        raise KeyError(f"Missing required column: '{usubjid_col}'")

    # Filter sort keys to only columns that exist in df
    valid_sort_keys = [k for k in sort_keys if k in df.columns and k != usubjid_col]
    skipped = [k for k in sort_keys if k not in df.columns and k != usubjid_col]
    if skipped:
        logger.debug(
            "{}SEQ: skipping sort keys not in DataFrame: {}",
            domain,
            skipped,
        )

    # Build full sort key list
    full_sort = [usubjid_col] + valid_sort_keys

    # Sort and compute cumcount within groups
    sorted_df = df.sort_values(full_sort, na_position="last")
    seq_sorted = sorted_df.groupby(usubjid_col, sort=False).cumcount() + 1

    # Reindex to match original DataFrame index
    result = seq_sorted.reindex(df.index)
    return result.astype("Int64")
