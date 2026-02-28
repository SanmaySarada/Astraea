"""RELREC (Related Records) stub generator.

Provides a minimal stub for the RELREC domain. Full cross-domain
relationship linking is deferred to Phase 7+ per PITFALLS.md m2.

Exports:
    generate_relrec_stub -- returns empty RELREC DataFrame with correct columns
"""

from __future__ import annotations

import pandas as pd
from loguru import logger

# Valid SDTM domain codes (common domains)
_VALID_DOMAINS = frozenset(
    {
        "AE", "CE", "CM", "DA", "DD", "DM", "DS", "DV", "EC", "EG",
        "EX", "FA", "FT", "HO", "IE", "IS", "LB", "MB", "MH", "MI",
        "MK", "MS", "NV", "OE", "PC", "PE", "PP", "PR", "QS", "RE",
        "RP", "RS", "SC", "SE", "SG", "SM", "SR", "SS", "SU", "SV",
        "TA", "TD", "TE", "TI", "TM", "TR", "TS", "TU", "TV", "UR",
        "VS",
    }
)

# RELREC column order per SDTM-IG
RELREC_COLUMNS: list[str] = [
    "STUDYID",
    "RDOMAIN",
    "USUBJID",
    "IDVAR",
    "IDVARVAL",
    "RELTYPE",
    "RELID",
]


def generate_relrec_stub(
    study_id: str,
    domains: list[str] | None = None,
) -> pd.DataFrame:
    """Generate an empty RELREC domain DataFrame with correct column structure.

    This is a stub implementation. Full cross-domain relationship linking
    requires significant analysis of record-level relationships between
    domains (e.g., linking AE records to CM records that treated them)
    and is deferred to Phase 7+.

    Args:
        study_id: Study identifier (used for documentation, not populated
            since the DataFrame is empty).
        domains: Optional list of domain codes to validate. If provided,
            each code is checked against known SDTM domain codes.

    Returns:
        Empty DataFrame with RELREC columns: STUDYID, RDOMAIN, USUBJID,
        IDVAR, IDVARVAL, RELTYPE, RELID.

    Raises:
        ValueError: If any domain in the domains list is not a valid
            SDTM domain code.
    """
    logger.warning(
        "RELREC generation is a stub. Full cross-domain relationship "
        "linking is deferred to Phase 7+. See PITFALLS.md m2."
    )

    # Validate domain codes if provided
    if domains is not None:
        for d in domains:
            if d.upper() not in _VALID_DOMAINS:
                msg = f"'{d}' is not a valid SDTM domain code"
                raise ValueError(msg)

    return pd.DataFrame(columns=RELREC_COLUMNS)
