"""SDTM VISITNUM/VISIT assignment utility.

Maps raw visit identifiers (e.g., EDC InstanceName values) to standardized
SDTM VISITNUM (numeric) and VISIT (character) values.

All functions are deterministic -- no LLM, no guessing.
"""

from __future__ import annotations

import pandas as pd
from loguru import logger


def assign_visit(
    df: pd.DataFrame,
    visit_mapping: dict[str, tuple[float, str]],
    raw_visit_col: str = "InstanceName",
) -> tuple[pd.Series, pd.Series]:
    """Assign VISITNUM and VISIT from raw visit identifiers.

    Maps each row's raw visit value through the provided mapping dictionary
    to produce standardized VISITNUM (numeric) and VISIT (character) values.

    Args:
        df: Source DataFrame containing the raw visit column.
        visit_mapping: Dictionary mapping raw visit identifier strings to
            (VISITNUM, VISIT) tuples. VISITNUM is float to allow decimal
            values for unplanned visits (e.g., 2.1).
            Example: {"Screening": (1.0, "SCREENING"),
                       "Week 1": (2.0, "WEEK 1"),
                       "Unplanned 1": (2.1, "UNPLANNED")}
        raw_visit_col: Column name in df containing raw visit identifiers.
            Default "InstanceName".

    Returns:
        Tuple of (visitnum_series, visit_series) where:
        - visitnum_series: Float64 dtype, NaN for unmatched visits
        - visit_series: object dtype, NaN for unmatched visits

    Notes:
        Logs a warning listing any unmatched raw visit values.
    """
    if raw_visit_col not in df.columns:
        raise KeyError(f"Missing required column: '{raw_visit_col}'")

    visitnum_values: list[float | None] = []
    visit_values: list[str | None] = []
    unmatched: set[str] = set()

    for _, row in df.iterrows():
        raw_val = row[raw_visit_col]
        if pd.isna(raw_val):
            visitnum_values.append(None)
            visit_values.append(None)
            continue

        raw_str = str(raw_val).strip()
        mapping = visit_mapping.get(raw_str)

        if mapping is not None:
            visitnum_values.append(mapping[0])
            visit_values.append(mapping[1])
        else:
            visitnum_values.append(None)
            visit_values.append(None)
            if raw_str:
                unmatched.add(raw_str)

    if unmatched:
        logger.warning(
            "Unmatched raw visit values ({}): {}",
            len(unmatched),
            sorted(unmatched)[:10],
        )

    visitnum_series = pd.array(visitnum_values, dtype="Float64")
    visit_series = pd.array(visit_values, dtype="object")

    return (
        pd.Series(visitnum_series, index=df.index, dtype="Float64"),
        pd.Series(visit_series, index=df.index, dtype="object"),
    )
