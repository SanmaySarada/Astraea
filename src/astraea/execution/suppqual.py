"""Deterministic SUPPQUAL generator with referential integrity validation.

Produces supplemental qualifier datasets (SUPP--) from parent domain
DataFrames. All SUPPQUAL records are generated deterministically with
guaranteed referential integrity: every record points to an existing
parent record via RDOMAIN/USUBJID/IDVAR/IDVARVAL.

SUPPQUAL generation is a deterministic post-processing step, never
LLM-generated, per the architecture guidelines in PITFALLS.md (C4).
"""

from __future__ import annotations

import pandas as pd
from loguru import logger

from astraea.models.suppqual import SuppVariable


def generate_suppqual(
    parent_df: pd.DataFrame,
    domain: str,
    study_id: str,
    supp_variables: list[SuppVariable],
) -> pd.DataFrame:
    """Generate a SUPPQUAL DataFrame from parent domain data.

    For each row in the parent DataFrame, for each SuppVariable, if the
    source column value is non-null and non-empty, creates a SUPPQUAL
    record with proper referential integrity linkage.

    Args:
        parent_df: Finalized parent domain DataFrame (must have USUBJID
            and {domain}SEQ columns).
        domain: Parent domain code (e.g., "AE", "LB").
        study_id: Study identifier (e.g., "PHA022121-C301").
        supp_variables: List of supplemental variables to extract.

    Returns:
        DataFrame with columns: STUDYID, RDOMAIN, USUBJID, IDVAR,
        IDVARVAL, QNAM, QLABEL, QVAL, QORIG, QEVAL.
        Returns empty DataFrame with correct columns if no records.
    """
    supp_columns = [
        "STUDYID",
        "RDOMAIN",
        "USUBJID",
        "IDVAR",
        "IDVARVAL",
        "QNAM",
        "QLABEL",
        "QVAL",
        "QORIG",
        "QEVAL",
    ]

    domain_upper = domain.upper()
    seq_var = f"{domain_upper}SEQ"

    if parent_df.empty or not supp_variables:
        return pd.DataFrame(columns=supp_columns)

    # Validate required columns exist
    if "USUBJID" not in parent_df.columns:
        logger.error("Parent DataFrame missing USUBJID column")
        return pd.DataFrame(columns=supp_columns)

    if seq_var not in parent_df.columns:
        logger.error(
            "Parent DataFrame missing {} column", seq_var
        )
        return pd.DataFrame(columns=supp_columns)

    records: list[dict[str, str]] = []

    for _, row in parent_df.iterrows():
        usubjid = row.get("USUBJID")
        seq_val = row.get(seq_var)

        if pd.isna(usubjid) or pd.isna(seq_val):
            continue

        # Convert SEQ to string integer (no decimals)
        idvarval = str(int(seq_val))

        for sv in supp_variables:
            source_val = row.get(sv.source_col)

            # Skip null/empty values
            if pd.isna(source_val):
                continue
            str_val = str(source_val).strip()
            if not str_val:
                continue

            records.append(
                {
                    "STUDYID": study_id,
                    "RDOMAIN": domain_upper,
                    "USUBJID": str(usubjid),
                    "IDVAR": seq_var,
                    "IDVARVAL": idvarval,
                    "QNAM": sv.qnam[:8],
                    "QLABEL": sv.qlabel[:40],
                    "QVAL": str_val,
                    "QORIG": sv.qorig,
                    "QEVAL": sv.qeval,
                }
            )

    if not records:
        return pd.DataFrame(columns=supp_columns)

    result = pd.DataFrame(records, columns=supp_columns)

    logger.info(
        "Generated SUPP{}: {} records from {} parent rows, {} supp variables",
        domain_upper,
        len(result),
        len(parent_df),
        len(supp_variables),
    )

    return result


def validate_suppqual_integrity(
    supp_df: pd.DataFrame,
    parent_df: pd.DataFrame,
    domain: str,
) -> list[str]:
    """Validate referential integrity of SUPPQUAL against parent domain.

    Checks:
    1. RDOMAIN matches the expected domain code.
    2. IDVAR matches {domain}SEQ.
    3. Every IDVARVAL exists in the parent domain's SEQ column.
    4. No duplicate QNAM within the same (USUBJID, IDVARVAL).

    Args:
        supp_df: SUPPQUAL DataFrame to validate.
        parent_df: Parent domain DataFrame for reference.
        domain: Expected parent domain code (e.g., "AE").

    Returns:
        List of error messages. Empty list means valid.
    """
    errors: list[str] = []
    domain_upper = domain.upper()
    seq_var = f"{domain_upper}SEQ"

    if supp_df.empty:
        return errors

    # Check 1: RDOMAIN matches domain
    if "RDOMAIN" in supp_df.columns:
        wrong_rdomain = supp_df[supp_df["RDOMAIN"] != domain_upper]
        if not wrong_rdomain.empty:
            bad_values = wrong_rdomain["RDOMAIN"].unique().tolist()
            errors.append(
                f"RDOMAIN mismatch: expected '{domain_upper}', "
                f"found {bad_values}"
            )

    # Check 2: IDVAR matches {domain}SEQ
    if "IDVAR" in supp_df.columns:
        wrong_idvar = supp_df[supp_df["IDVAR"] != seq_var]
        if not wrong_idvar.empty:
            bad_values = wrong_idvar["IDVAR"].unique().tolist()
            errors.append(
                f"IDVAR mismatch: expected '{seq_var}', found {bad_values}"
            )

    # Check 3: Every IDVARVAL exists in parent SEQ
    if "IDVARVAL" in supp_df.columns and seq_var in parent_df.columns:
        parent_seqs = set(
            str(int(v))
            for v in parent_df[seq_var].dropna()
        )
        supp_idvarvals = set(supp_df["IDVARVAL"].dropna().unique())
        orphans = supp_idvarvals - parent_seqs
        for orphan in sorted(orphans):
            errors.append(
                f"Orphaned SUPPQUAL record: IDVARVAL='{orphan}' "
                f"not found in parent {seq_var}"
            )

    # Check 4: No duplicate QNAM within same (USUBJID, IDVARVAL)
    if all(c in supp_df.columns for c in ("USUBJID", "IDVARVAL", "QNAM")):
        dups = supp_df.groupby(
            ["USUBJID", "IDVARVAL", "QNAM"]
        ).size()
        dup_entries = dups[dups > 1]
        for (usubjid, idvarval, qnam), count in dup_entries.items():
            errors.append(
                f"Duplicate QNAM '{qnam}' for USUBJID='{usubjid}', "
                f"IDVARVAL='{idvarval}' ({count} occurrences)"
            )

    return errors
