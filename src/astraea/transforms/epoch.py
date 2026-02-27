"""SDTM EPOCH derivation utility.

Assigns EPOCH values to observations by matching their dates against
Subject Element (SE) domain date ranges.

All functions are deterministic -- no LLM, no guessing.
"""

from __future__ import annotations

import pandas as pd


def assign_epoch(
    df: pd.DataFrame,
    se_df: pd.DataFrame,
    date_col: str,
    usubjid_col: str = "USUBJID",
) -> pd.Series:
    """Assign EPOCH to each row by matching observation dates to SE domain ranges.

    For each row in df, finds the SE element where SESTDTC <= obs_date <= SEENDTC
    for the same USUBJID, and returns the corresponding EPOCH value.

    Args:
        df: Source DataFrame containing observation dates and USUBJIDs.
        se_df: Subject Elements (SE) domain DataFrame. Must contain columns:
            USUBJID, SESTDTC, SEENDTC, EPOCH.
        date_col: Column name in df containing ISO 8601 date strings.
        usubjid_col: Column name for USUBJID. Default "USUBJID".

    Returns:
        pandas Series with object dtype containing EPOCH strings.
        NaN for rows where epoch cannot be determined (missing date,
        partial date, no matching SE element, etc.).

    Notes:
        - Uses string comparison for ISO 8601 dates (lexicographic order
          works correctly for YYYY-MM-DD format).
        - Partial dates (< 10 chars) are treated as unmatchable.
        - If SEENDTC is missing/NaN, the SE element is treated as open-ended
          (only checks >= SESTDTC).
    """
    required_df_cols = [date_col, usubjid_col]
    missing_df = [c for c in required_df_cols if c not in df.columns]
    if missing_df:
        raise KeyError(f"Missing required columns in df: {missing_df}")

    required_se_cols = [usubjid_col, "SESTDTC", "EPOCH"]
    missing_se = [c for c in required_se_cols if c not in se_df.columns]
    if missing_se:
        raise KeyError(f"Missing required columns in se_df: {missing_se}")

    # Pre-group SE data by USUBJID for efficient lookup
    se_grouped: dict[str, list[dict[str, str]]] = {}
    for _, se_row in se_df.iterrows():
        subj = str(se_row[usubjid_col])
        element = {
            "sestdtc": str(se_row["SESTDTC"]) if pd.notna(se_row["SESTDTC"]) else "",
            "seendtc": str(se_row.get("SEENDTC", "")) if pd.notna(se_row.get("SEENDTC")) else "",
            "epoch": str(se_row["EPOCH"]) if pd.notna(se_row["EPOCH"]) else "",
        }
        se_grouped.setdefault(subj, []).append(element)

    def _find_epoch(row: pd.Series) -> str | float:
        obs_date_raw = row[date_col]
        if pd.isna(obs_date_raw):
            return float("nan")

        obs_str = str(obs_date_raw).strip()
        if len(obs_str) < 10:
            return float("nan")

        obs_date = obs_str[:10]
        subj = str(row[usubjid_col])
        elements = se_grouped.get(subj, [])

        for elem in elements:
            sestdtc = elem["sestdtc"][:10] if len(elem["sestdtc"]) >= 10 else ""
            seendtc = elem["seendtc"][:10] if len(elem["seendtc"]) >= 10 else ""

            if not sestdtc:
                continue

            # Check if obs_date >= SESTDTC
            if obs_date < sestdtc:
                continue

            # Check if obs_date <= SEENDTC (or open-ended)
            if seendtc and obs_date > seendtc:
                continue

            # Match found
            return elem["epoch"] if elem["epoch"] else float("nan")

        return float("nan")

    result = df.apply(_find_epoch, axis=1)
    return result
