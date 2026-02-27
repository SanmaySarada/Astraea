"""Pre-execution utilities for source DataFrame preparation.

Provides row filtering and multi-source column alignment functions
that run before the main execution pipeline transforms raw data
into SDTM-compliant datasets.
"""

from __future__ import annotations

import pandas as pd


def filter_rows(
    df: pd.DataFrame,
    *,
    column: str,
    keep_values: set[str] | None = None,
    exclude_values: set[str] | None = None,
) -> pd.DataFrame:
    """Filter source DataFrame rows before execution.

    Exactly one of keep_values or exclude_values must be provided.
    Comparison is case-insensitive string matching after str() conversion.

    Args:
        df: Source DataFrame to filter.
        column: Column name to filter on.
        keep_values: If provided, keep only rows where column value is in this set.
        exclude_values: If provided, remove rows where column value is in this set.

    Returns:
        Filtered DataFrame copy with reset index.

    Raises:
        ValueError: If neither or both of keep_values/exclude_values are provided.
        KeyError: If column not in df.
    """
    if (keep_values is None) == (exclude_values is None):
        msg = "Exactly one of keep_values or exclude_values must be provided."
        raise ValueError(msg)

    if column not in df.columns:
        msg = f"Column '{column}' not found in DataFrame. Available: {list(df.columns)}"
        raise KeyError(msg)

    # Normalize column values to uppercase strings for case-insensitive matching
    normalized = df[column].astype(str).str.strip().str.upper()

    if keep_values is not None:
        upper_values = {v.upper() for v in keep_values}
        mask = normalized.isin(upper_values)
    else:
        assert exclude_values is not None  # noqa: S101
        upper_values = {v.upper() for v in exclude_values}
        mask = ~normalized.isin(upper_values)

    return df.loc[mask].copy().reset_index(drop=True)


def align_multi_source_columns(
    dfs: dict[str, pd.DataFrame],
    rename_maps: dict[str, dict[str, str]],
) -> dict[str, pd.DataFrame]:
    """Rename columns in multiple source DataFrames to align before merge.

    Args:
        dfs: Dict of source_name -> DataFrame.
        rename_maps: Dict of source_name -> {old_col: new_col} rename mapping.
            Source names not in rename_maps are passed through unchanged.

    Returns:
        Dict of source_name -> DataFrame with columns renamed. DataFrames are copies.
    """
    result: dict[str, pd.DataFrame] = {}
    for source_name, df in dfs.items():
        if source_name in rename_maps:
            result[source_name] = df.rename(columns=rename_maps[source_name]).copy()
        else:
            result[source_name] = df.copy()
    return result
