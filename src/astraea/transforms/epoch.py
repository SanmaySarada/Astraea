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

    # Pre-group SE data by USUBJID for efficient lookup (vectorized)
    se_records = se_df.to_dict("records")
    se_grouped: dict[str, list[dict[str, str]]] = {}
    for rec in se_records:
        subj = str(rec[usubjid_col])
        element = {
            "sestdtc": str(rec["SESTDTC"]) if pd.notna(rec["SESTDTC"]) else "",
            "seendtc": str(rec.get("SEENDTC", "")) if pd.notna(rec.get("SEENDTC")) else "",
            "epoch": str(rec["EPOCH"]) if pd.notna(rec["EPOCH"]) else "",
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


def detect_epoch_overlaps(
    se_df: pd.DataFrame,
    usubjid_col: str = "USUBJID",
) -> list[dict]:
    """Detect overlapping SE epoch date ranges per subject.

    Groups SE data by USUBJID, sorts by SESTDTC, and checks for overlapping
    date ranges. Adjacent elements (SEENDTC == SESTDTC of next) are NOT
    considered overlaps -- uses strict less-than comparison.

    Args:
        se_df: Subject Elements (SE) domain DataFrame. Must contain columns:
            USUBJID, SESTDTC, SEENDTC, EPOCH.
        usubjid_col: Column name for USUBJID. Default "USUBJID".

    Returns:
        List of dicts with keys: usubjid, epoch_1, epoch_2, overlap_start,
        overlap_end. Empty list if no overlaps found.

    Notes:
        - Open-ended elements (missing SEENDTC) extend to infinity.
        - Uses string comparison for ISO 8601 dates.
    """
    if se_df.empty:
        return []

    required_cols = [usubjid_col, "SESTDTC", "EPOCH"]
    missing = [c for c in required_cols if c not in se_df.columns]
    if missing:
        raise KeyError(f"Missing required columns in se_df: {missing}")

    overlaps: list[dict] = []

    # Group by subject
    for subj, group in se_df.groupby(usubjid_col):
        # Sort by SESTDTC
        sorted_group = group.sort_values("SESTDTC").reset_index(drop=True)
        records = sorted_group.to_dict("records")

        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                rec_a = records[i]
                rec_b = records[j]

                # Get date strings (first 10 chars for date-only comparison)
                start_a = str(rec_a["SESTDTC"])[:10] if pd.notna(rec_a["SESTDTC"]) else ""
                end_a_raw = rec_a.get("SEENDTC")
                end_a = str(end_a_raw)[:10] if pd.notna(end_a_raw) and str(end_a_raw).strip() else ""
                start_b = str(rec_b["SESTDTC"])[:10] if pd.notna(rec_b["SESTDTC"]) else ""
                end_b_raw = rec_b.get("SEENDTC")
                end_b = str(end_b_raw)[:10] if pd.notna(end_b_raw) and str(end_b_raw).strip() else ""

                if not start_a or not start_b:
                    continue

                epoch_a = str(rec_a["EPOCH"]) if pd.notna(rec_a["EPOCH"]) else ""
                epoch_b = str(rec_b["EPOCH"]) if pd.notna(rec_b["EPOCH"]) else ""

                # Check overlap: start_B < end_A (strict less-than)
                # If end_A is open-ended (empty), it extends to infinity
                if end_a:
                    if start_b < end_a:  # strict less-than: adjacent is NOT overlap
                        overlap_start = max(start_a, start_b)
                        overlap_end = min(end_a, end_b) if end_b else end_a
                        overlaps.append({
                            "usubjid": str(subj),
                            "epoch_1": epoch_a,
                            "epoch_2": epoch_b,
                            "overlap_start": overlap_start,
                            "overlap_end": overlap_end,
                        })
                else:
                    # A is open-ended: any B that starts is within A
                    overlap_start = max(start_a, start_b)
                    overlap_end = end_b if end_b else ""
                    overlaps.append({
                        "usubjid": str(subj),
                        "epoch_1": epoch_a,
                        "epoch_2": epoch_b,
                        "overlap_start": overlap_start,
                        "overlap_end": overlap_end,
                    })

    return overlaps
