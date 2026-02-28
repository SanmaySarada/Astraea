"""Subject Visits (SV) domain builder.

Builds the SV domain DataFrame from EDC visit-level metadata present in
raw source DataFrames. SV tracks every subject's actual visit dates,
derived from InstanceName/FolderName/FolderSeq columns found across
all raw EDC files.

Exports:
    extract_visit_dates -- scans raw DataFrames for visit metadata
    build_sv_domain -- produces SV DataFrame from extracted visit data
"""

from __future__ import annotations

import pandas as pd
from loguru import logger


def extract_visit_dates(
    raw_dfs: dict[str, pd.DataFrame],
    date_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Extract visit-level date ranges from raw EDC DataFrames.

    Scans all raw DataFrames for visit metadata columns (InstanceName,
    FolderName, FolderSeq) and a subject identifier (Subject or USUBJID).
    For each unique (subject, visit) tuple, finds the earliest and latest
    date values from any date-like column.

    Args:
        raw_dfs: Dictionary of source dataset name -> DataFrame.
        date_cols: Explicit list of date column names to consider.
            If None, auto-detects columns ending in "DAT" or "DTC".

    Returns:
        DataFrame with columns: subject_id, visit_name, visit_folder,
        visit_seq, earliest_date, latest_date. Empty DataFrame with
        these columns if no visit metadata is found.
    """
    result_columns = [
        "subject_id",
        "visit_name",
        "visit_folder",
        "visit_seq",
        "earliest_date",
        "latest_date",
    ]

    visit_records: list[dict[str, object]] = []

    for ds_name, df in raw_dfs.items():
        # Check for required visit metadata columns
        if "InstanceName" not in df.columns or "FolderName" not in df.columns:
            logger.debug("Skipping {} -- no InstanceName/FolderName columns", ds_name)
            continue

        # Detect subject column
        subject_col: str | None = None
        for candidate in ("Subject", "USUBJID", "SUBJID"):
            if candidate in df.columns:
                subject_col = candidate
                break

        if subject_col is None:
            logger.debug("Skipping {} -- no subject identifier column", ds_name)
            continue

        # Detect date columns
        if date_cols is not None:
            det_date_cols = [c for c in date_cols if c in df.columns]
        else:
            det_date_cols = [
                c for c in df.columns if c.upper().endswith("DAT") or c.upper().endswith("DTC")
            ]

        # Determine FolderSeq column
        folder_seq_col = "FolderSeq" if "FolderSeq" in df.columns else None

        # Group by subject + visit
        group_cols = [subject_col, "InstanceName", "FolderName"]
        if folder_seq_col:
            group_cols.append(folder_seq_col)

        for group_key, group_df in df.groupby(group_cols, dropna=False):
            if folder_seq_col:
                subj, inst, folder, seq = group_key
            else:
                subj, inst, folder = group_key
                seq = None

            if pd.isna(subj) or pd.isna(inst):
                continue

            # Find earliest and latest dates
            earliest: str | None = None
            latest: str | None = None

            for dcol in det_date_cols:
                col_values = group_df[dcol].dropna()
                if col_values.empty:
                    continue

                col_strs = col_values.astype(str)
                col_min = col_strs.min()
                col_max = col_strs.max()

                if earliest is None or col_min < earliest:
                    earliest = col_min
                if latest is None or col_max > latest:
                    latest = col_max

            visit_records.append(
                {
                    "subject_id": str(subj),
                    "visit_name": str(inst),
                    "visit_folder": str(folder),
                    "visit_seq": float(seq) if seq is not None and not pd.isna(seq) else None,
                    "earliest_date": earliest,
                    "latest_date": latest,
                }
            )

    if not visit_records:
        logger.info("No visit metadata found in {} raw DataFrames", len(raw_dfs))
        return pd.DataFrame(columns=result_columns)

    result = pd.DataFrame(visit_records, columns=result_columns)

    # Deduplicate: keep the widest date range per subject+visit
    dedup_key = ["subject_id", "visit_name"]
    result = (
        result.sort_values(["subject_id", "visit_name", "earliest_date"])
        .drop_duplicates(subset=dedup_key, keep="first")
        .reset_index(drop=True)
    )

    logger.info(
        "Extracted {} visit records from {} sources",
        len(result),
        len(raw_dfs),
    )

    return result


def build_sv_domain(
    visit_data: pd.DataFrame,
    study_id: str,
    *,
    site_col: str = "SiteNumber",
    usubjid_lookup: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Build an SV (Subject Visits) domain DataFrame from extracted visit data.

    Takes the output of extract_visit_dates and produces an SDTM-compliant
    SV domain with required variables.

    Args:
        visit_data: DataFrame from extract_visit_dates with subject_id,
            visit_name, visit_folder, visit_seq, earliest_date, latest_date.
        study_id: Study identifier for STUDYID.
        site_col: Name of the site column (unused in SV but kept for API parity).
        usubjid_lookup: Optional mapping from subject_id -> USUBJID.
            If None, constructs USUBJID as study_id + "-" + subject_id.

    Returns:
        SV domain DataFrame with columns: STUDYID, DOMAIN, USUBJID,
        VISITNUM, VISIT, SVSTDTC, SVENDTC, SVUPDES, SVSEQ.
        Sorted by STUDYID, USUBJID, VISITNUM.
    """
    sv_columns = [
        "STUDYID",
        "DOMAIN",
        "USUBJID",
        "SVSEQ",
        "VISITNUM",
        "VISIT",
        "SVSTDTC",
        "SVENDTC",
        "SVUPDES",
    ]

    if visit_data.empty:
        logger.info("No visit data provided -- returning empty SV domain")
        return pd.DataFrame(columns=sv_columns)

    rows: list[dict[str, object]] = []

    for _, row in visit_data.iterrows():
        subj_id = str(row["subject_id"])

        if usubjid_lookup is not None:
            usubjid = usubjid_lookup.get(subj_id, f"{study_id}-{subj_id}")
        else:
            usubjid = f"{study_id}-{subj_id}"

        visitnum = row["visit_seq"] if pd.notna(row.get("visit_seq")) else None
        svstdtc = row["earliest_date"] if pd.notna(row.get("earliest_date")) else ""
        svendtc = row["latest_date"] if pd.notna(row.get("latest_date")) else ""

        rows.append(
            {
                "STUDYID": study_id,
                "DOMAIN": "SV",
                "USUBJID": usubjid,
                "VISITNUM": visitnum,
                "VISIT": str(row["visit_name"]) if pd.notna(row.get("visit_name")) else "",
                "SVSTDTC": svstdtc,
                "SVENDTC": svendtc,
                "SVUPDES": "",
            }
        )

    sv_df = pd.DataFrame(rows, columns=sv_columns[:-1])  # Without SVSEQ initially

    # Sort by STUDYID, USUBJID, VISITNUM
    sort_cols = ["STUDYID", "USUBJID"]
    if "VISITNUM" in sv_df.columns and sv_df["VISITNUM"].notna().any():
        sort_cols.append("VISITNUM")
    sv_df = sv_df.sort_values(sort_cols, na_position="last").reset_index(drop=True)

    # Generate SVSEQ per subject
    sv_df["SVSEQ"] = sv_df.groupby("USUBJID").cumcount() + 1

    # Enforce column order
    sv_df = sv_df[[c for c in sv_columns if c in sv_df.columns]]

    logger.info("Built SV domain: {} rows for study {}", len(sv_df), study_id)

    return sv_df
