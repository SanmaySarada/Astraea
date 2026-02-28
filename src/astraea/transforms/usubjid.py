"""USUBJID generation and cross-domain validation for SDTM.

USUBJID (Unique Subject Identifier) must uniquely identify a subject
across all studies for a sponsor. Format: STUDYID + delimiter + SITEID + delimiter + SUBJID.

All functions are deterministic -- no LLM, no guessing.
"""

from __future__ import annotations

import pandas as pd
from loguru import logger


def generate_usubjid(
    studyid: str,
    siteid: str,
    subjid: str,
    delimiter: str = "-",
) -> str:
    """Generate USUBJID from components.

    Per SDTM-IG: USUBJID must uniquely identify a subject across all
    studies for a sponsor. Standard format is STUDYID-SITEID-SUBJID.

    Args:
        studyid: Study identifier (e.g., "PHA022121-C301" or "301").
        siteid: Site identifier (e.g., "04401").
        subjid: Subject identifier within site (e.g., "01").
        delimiter: Separator between components. Default "-".

    Returns:
        Concatenated USUBJID string with whitespace stripped from components.

    Examples:
        >>> generate_usubjid("301", "04401", "01")
        '301-04401-01'
        >>> generate_usubjid(" 301 ", " 04401 ", " 01 ")
        '301-04401-01'
    """
    components = [str(studyid).strip(), str(siteid).strip(), str(subjid).strip()]
    names = ["studyid", "siteid", "subjid"]
    inputs = [studyid, siteid, subjid]
    for name, val, raw in zip(names, components, inputs, strict=True):
        if not val or val.lower() in ("nan", "none"):
            raise ValueError(
                f"USUBJID component '{name}' is empty or NaN (got '{val}' from input {raw!r})"
            )
    return delimiter.join(components)


def extract_usubjid_components(
    usubjid: str,
    delimiter: str = "-",
) -> dict[str, str]:
    """Parse a USUBJID back into its components.

    Assumes 3-part format: STUDYID + delimiter + SITEID + delimiter + SUBJID.
    Logs a warning if the USUBJID has more or fewer than 3 parts.

    Args:
        usubjid: Full USUBJID string.
        delimiter: Separator used in the USUBJID. Default "-".

    Returns:
        Dictionary with keys "studyid", "siteid", "subjid".
        If format doesn't match 3 parts, returns best-effort split:
        - 1 part: studyid=value, siteid="", subjid=""
        - 2 parts: studyid=first, siteid=second, subjid=""
        - 3+ parts: studyid=first, siteid=second, subjid=rest joined

    Examples:
        >>> extract_usubjid_components("301-04401-01")
        {'studyid': '301', 'siteid': '04401', 'subjid': '01'}
    """
    parts = str(usubjid).strip().split(delimiter)

    if len(parts) == 3:
        return {
            "studyid": parts[0],
            "siteid": parts[1],
            "subjid": parts[2],
        }

    if len(parts) < 3:
        logger.warning(
            "USUBJID '{}' has {} parts (expected 3 with delimiter '{}')",
            usubjid,
            len(parts),
            delimiter,
        )
        return {
            "studyid": parts[0] if len(parts) >= 1 else "",
            "siteid": parts[1] if len(parts) >= 2 else "",
            "subjid": "",
        }

    # More than 3 parts -- join the remainder as subjid
    logger.warning(
        "USUBJID '{}' has {} parts (expected 3 with delimiter '{}'); "
        "treating first as studyid, second as siteid, rest as subjid",
        usubjid,
        len(parts),
        delimiter,
    )
    return {
        "studyid": parts[0],
        "siteid": parts[1],
        "subjid": delimiter.join(parts[2:]),
    }


def generate_usubjid_column(
    df: pd.DataFrame,
    studyid_col: str = "STUDYID",
    siteid_col: str = "SITEID",
    subjid_col: str = "SUBJID",
    studyid_value: str | None = None,
    delimiter: str = "-",
) -> pd.Series:
    """Generate USUBJID for an entire DataFrame.

    Args:
        df: Source DataFrame containing site and subject columns.
        studyid_col: Column name for study ID (used if studyid_value is None).
        siteid_col: Column name for site ID.
        subjid_col: Column name for subject ID.
        studyid_value: Constant study ID to use for all rows.
            If provided, overrides studyid_col. Common in clinical data
            where STUDYID is the same for every row.
        delimiter: Separator between components. Default "-".

    Returns:
        pandas Series of USUBJID strings.

    Raises:
        KeyError: If required columns are missing from the DataFrame.
    """
    # Validate required columns exist
    required_cols = [siteid_col, subjid_col]
    if studyid_value is None:
        required_cols.append(studyid_col)

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    if studyid_value is not None:
        studyid_series = pd.Series(studyid_value, index=df.index)
    else:
        studyid_series = df[studyid_col].astype(str).str.strip()

    siteid_series = df[siteid_col].astype(str).str.strip()
    subjid_series = df[subjid_col].astype(str).str.strip()

    # Detect NaN-contaminated components (astype(str) converts NaN to "nan")
    _invalid = {"nan", "none", ""}
    for col_label, series in [
        (studyid_col if studyid_value is None else "studyid_value", studyid_series),
        (siteid_col, siteid_series),
        (subjid_col, subjid_series),
    ]:
        nan_mask = series.str.lower().isin(_invalid)
        if nan_mask.any():
            n_bad = int(nan_mask.sum())
            logger.warning(
                "Found {} NaN/empty values in {} -- these will produce invalid USUBJIDs",
                n_bad,
                col_label,
            )

    result = studyid_series + delimiter + siteid_series + delimiter + subjid_series

    # Mark rows with NaN-contaminated components as pd.NA
    nan_mask = (
        studyid_series.str.lower().isin(_invalid)
        | siteid_series.str.lower().isin(_invalid)
        | subjid_series.str.lower().isin(_invalid)
    )
    result[nan_mask] = pd.NA

    return result


def validate_usubjid_consistency(
    datasets: dict[str, pd.DataFrame],
    usubjid_col: str = "USUBJID",
) -> list[str]:
    """Validate USUBJID consistency across SDTM domains.

    Checks:
    1. All USUBJIDs in non-DM domains exist in DM (orphan check).
    2. No duplicate USUBJIDs within DM.
    3. USUBJID format is consistent (same delimiter, same component count).

    Args:
        datasets: Dictionary mapping domain name to DataFrame.
            Expected to include "DM" as the reference domain.
        usubjid_col: Column name for USUBJID. Default "USUBJID".

    Returns:
        List of error messages. Empty list means all checks passed.
    """
    errors: list[str] = []

    # Check DM exists
    if "DM" not in datasets:
        errors.append("DM domain not found in datasets -- cannot validate USUBJID consistency")
        return errors

    dm_df = datasets["DM"]

    if usubjid_col not in dm_df.columns:
        errors.append(f"DM domain missing '{usubjid_col}' column")
        return errors

    dm_usubjids = set(dm_df[usubjid_col].dropna().astype(str))

    # Check for duplicates in DM
    dm_values = dm_df[usubjid_col].dropna().astype(str)
    duplicates = dm_values[dm_values.duplicated()]
    if not duplicates.empty:
        dup_list = sorted(duplicates.unique().tolist())
        errors.append(
            f"Duplicate USUBJIDs in DM: {dup_list[:10]}"
            + (f" (and {len(dup_list) - 10} more)" if len(dup_list) > 10 else "")
        )

    # Check format consistency in DM
    if dm_usubjids:
        delimiter_counts: dict[int, int] = {}
        for uid in dm_usubjids:
            n_delimiters = uid.count("-")
            delimiter_counts[n_delimiters] = delimiter_counts.get(n_delimiters, 0) + 1

        if len(delimiter_counts) > 1:
            errors.append(
                f"Inconsistent USUBJID formats in DM: delimiter counts {dict(delimiter_counts)}"
            )

    # Check all non-DM USUBJIDs exist in DM
    for domain_name, domain_df in datasets.items():
        if domain_name == "DM":
            continue

        if usubjid_col not in domain_df.columns:
            continue

        domain_usubjids = set(domain_df[usubjid_col].dropna().astype(str))
        orphans = domain_usubjids - dm_usubjids

        if orphans:
            orphan_list = sorted(orphans)
            errors.append(
                f"Orphan USUBJIDs in {domain_name} (not in DM): "
                f"{orphan_list[:5]}"
                + (f" (and {len(orphan_list) - 5} more)" if len(orphan_list) > 5 else "")
            )

    return errors
