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

    # Vectorized: map raw visit values through the mapping dict
    raw_vals = df[raw_visit_col].astype(str).str.strip()
    # Mark NaN entries
    is_na = df[raw_visit_col].isna()

    visitnum_mapped = raw_vals.map(
        lambda v: visit_mapping[v][0] if v in visit_mapping else None
    )
    visit_mapped = raw_vals.map(
        lambda v: visit_mapping[v][1] if v in visit_mapping else None
    )

    # Restore NaN for originally-null values
    visitnum_mapped = visitnum_mapped.where(~is_na, other=None)
    visit_mapped = visit_mapped.where(~is_na, other=None)

    # Log unmatched values
    non_na_raw = raw_vals[~is_na]
    matched = non_na_raw.isin(visit_mapping.keys())
    unmatched_vals = set(non_na_raw[~matched].unique())
    # Filter out empty strings
    unmatched_vals.discard("")
    if unmatched_vals:
        logger.warning(
            "Unmatched raw visit values ({}): {}",
            len(unmatched_vals),
            sorted(unmatched_vals)[:10],
        )

    visitnum_series = pd.Series(
        pd.array(visitnum_mapped.tolist(), dtype="Float64"),
        index=df.index,
        dtype="Float64",
    )
    visit_series = pd.Series(
        pd.array(visit_mapped.tolist(), dtype="object"),
        index=df.index,
        dtype="object",
    )

    return visitnum_series, visit_series


def build_visit_mapping_from_tv(
    tv_df: pd.DataFrame,
    armcd: str | None = None,
) -> dict[str, tuple[float, str]]:
    """Build a visit mapping dict from a TV (Trial Visits) domain DataFrame.

    Reads TV domain data and produces a mapping from VISIT name to
    (VISITNUM, VISIT) tuple suitable for use with ``assign_visit()``.

    Args:
        tv_df: Trial Visits (TV) domain DataFrame. Expected columns:
            VISITNUM, VISIT, and optionally ARMCD.
        armcd: If provided, filter TV rows to this ARMCD value. If None
            and TV has ARMCD column, uses the first arm found.

    Returns:
        Dict mapping VISIT name -> (VISITNUM, VISIT). Empty dict if
        required columns are missing or TV is empty.
    """
    if tv_df.empty:
        return {}

    required_cols = ["VISITNUM", "VISIT"]
    missing = [c for c in required_cols if c not in tv_df.columns]
    if missing:
        logger.warning(
            "TV DataFrame missing required columns {}, returning empty mapping",
            missing,
        )
        return {}

    working = tv_df.copy()

    # Filter by ARMCD if applicable
    if "ARMCD" in working.columns:
        if armcd is not None:
            working = working[working["ARMCD"] == armcd]
        else:
            # Use the first arm
            first_arm = working["ARMCD"].iloc[0]
            working = working[working["ARMCD"] == first_arm]

    if working.empty:
        return {}

    # Build mapping: VISIT -> (VISITNUM, VISIT)
    # Drop duplicates on VISIT to avoid overwriting
    deduped = working.drop_duplicates(subset=["VISIT"], keep="first")
    mapping: dict[str, tuple[float, str]] = {}
    for rec in deduped.to_dict("records"):
        visit_name = str(rec["VISIT"]).strip()
        try:
            visitnum = float(rec["VISITNUM"])
        except (ValueError, TypeError):
            continue
        if visit_name:
            mapping[visit_name] = (visitnum, visit_name)

    logger.debug(
        "Built visit mapping from TV with {} entries",
        len(mapping),
    )
    return mapping
