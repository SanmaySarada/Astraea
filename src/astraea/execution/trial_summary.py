"""Trial Summary (TS) domain builder.

Builds the TS domain DataFrame from a TSConfig model. The TS domain is
a key-value dataset (one row per parameter) that contains study-level
metadata required by the FDA for submission acceptance. Missing TS is
an automatic rejection trigger.

Exports:
    TSConfig (re-export from models)
    build_ts_domain -- builds TS DataFrame from config
    validate_ts_completeness -- checks FDA-mandatory parameters
    FDA_REQUIRED_PARAMS -- frozenset of mandatory TSPARMCD codes
"""

from __future__ import annotations

import pandas as pd
from loguru import logger

from astraea.models.trial_design import TSConfig, TSParameter

# FDA-mandatory TS parameters (missing any = submission risk)
FDA_REQUIRED_PARAMS: frozenset[str] = frozenset(
    {
        "SSTDTC",
        "SPONSOR",
        "INDIC",
        "TRT",
        "STYPE",
        "SDTMVER",
        "TPHASE",
    }
)


def build_ts_domain(
    config: TSConfig,
    dm_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build a Trial Summary (TS) domain DataFrame from configuration.

    Produces a key-value dataset with one row per trial summary parameter.
    Always includes the 8 core parameters (TITLE, SPONSOR, INDIC, TRT,
    PCLAS, STYPE, SDTMVER, TPHASE). Conditionally includes optional
    parameters when provided in config. If a DM DataFrame with RFSTDTC
    is supplied, derives SSTDTC (study start date) and optionally SENDTC
    (study end date).

    Args:
        config: Trial summary configuration with study metadata.
        dm_df: Optional DM domain DataFrame for date derivation.

    Returns:
        TS domain DataFrame with columns:
        STUDYID, DOMAIN, TSSEQ, TSPARMCD, TSPARM, TSVAL.
    """
    params: list[TSParameter] = []

    # -- Always-included parameters (8 core) --
    _add = params.append
    _add(
        TSParameter(
            tsparmcd="TITLE",
            tsparm="Trial Title",
            tsval=config.study_title,
        )
    )
    _add(
        TSParameter(
            tsparmcd="SPONSOR",
            tsparm="Clinical Study Sponsor",
            tsval=config.sponsor,
        )
    )
    _add(
        TSParameter(
            tsparmcd="INDIC",
            tsparm="Trial Disease/Condition Indication",
            tsval=config.indication,
        )
    )
    _add(
        TSParameter(
            tsparmcd="TRT",
            tsparm="Investigational Therapy or Treatment",
            tsval=config.treatment,
        )
    )
    _add(
        TSParameter(
            tsparmcd="PCLAS",
            tsparm="Pharmacological Class of Inv. Therapy",
            tsval=config.pharmacological_class,
        )
    )
    _add(
        TSParameter(
            tsparmcd="STYPE",
            tsparm="Study Type",
            tsval=config.study_type,
        )
    )
    _add(
        TSParameter(
            tsparmcd="SDTMVER",
            tsparm="SDTM Version",
            tsval=config.sdtm_version,
        )
    )
    _add(
        TSParameter(
            tsparmcd="TPHASE",
            tsparm="Trial Phase",
            tsval=config.trial_phase,
        )
    )

    # -- Conditionally-included parameters --
    if config.planned_enrollment is not None:
        params.append(
            TSParameter(
                tsparmcd="PLESSION",
                tsparm="Planned Number of Subjects",
                tsval=str(config.planned_enrollment),
            )
        )

    if config.number_of_arms is not None:
        params.append(
            TSParameter(
                tsparmcd="NARMS",
                tsparm="Planned Number of Arms",
                tsval=str(config.number_of_arms),
            )
        )

    if config.accession_number is not None:
        params.append(
            TSParameter(
                tsparmcd="ACESSION",
                tsparm="Accession Number",
                tsval=config.accession_number,
            )
        )

    if config.addon is not None:
        params.append(
            TSParameter(
                tsparmcd="ADDON",
                tsparm="Added on to Existing Treatments",
                tsval=config.addon,
            )
        )

    # -- Derive dates from DM if available --
    if dm_df is not None and "RFSTDTC" in dm_df.columns:
        rfstdtc_values = dm_df["RFSTDTC"].dropna()
        if not rfstdtc_values.empty:
            # SSTDTC = earliest reference start date
            sstdtc = str(rfstdtc_values.min())
            params.append(
                TSParameter(
                    tsparmcd="SSTDTC",
                    tsparm="Study Start Date",
                    tsval=sstdtc,
                )
            )
            logger.debug("Derived SSTDTC from DM: {}", sstdtc)

        # SENDTC = latest reference end date (if RFENDTC exists)
        if "RFENDTC" in dm_df.columns:
            rfendtc_values = dm_df["RFENDTC"].dropna()
            if not rfendtc_values.empty:
                sendtc = str(rfendtc_values.max())
                params.append(
                    TSParameter(
                        tsparmcd="SENDTC",
                        tsparm="Study End Date",
                        tsval=sendtc,
                    )
                )
                logger.debug("Derived SENDTC from DM: {}", sendtc)

    # -- Append any additional custom parameters --
    params.extend(config.additional_params)

    # -- Build DataFrame --
    rows = []
    for seq, param in enumerate(params, start=1):
        rows.append(
            {
                "STUDYID": config.study_id,
                "DOMAIN": "TS",
                "TSSEQ": seq,
                "TSPARMCD": param.tsparmcd,
                "TSPARM": param.tsparm,
                "TSVAL": param.tsval,
            }
        )

    ts_df = pd.DataFrame(rows)

    logger.info(
        "Built TS domain: {} parameters for study {}",
        len(ts_df),
        config.study_id,
    )

    return ts_df


def validate_ts_completeness(ts_df: pd.DataFrame) -> list[str]:
    """Validate that a TS DataFrame contains all FDA-mandatory parameters.

    Checks that every code in FDA_REQUIRED_PARAMS is present in TSPARMCD
    and that none of the required parameters have empty/null TSVAL.

    Args:
        ts_df: TS domain DataFrame with TSPARMCD and TSVAL columns.

    Returns:
        List of validation error/warning messages. Empty list = valid.
    """
    issues: list[str] = []

    if ts_df.empty:
        issues.append("TS domain is empty -- no parameters present")
        return issues

    if "TSPARMCD" not in ts_df.columns:
        issues.append("TS domain missing TSPARMCD column")
        return issues

    present_codes = set(ts_df["TSPARMCD"].dropna().unique())

    # Check for missing mandatory parameters
    for code in sorted(FDA_REQUIRED_PARAMS):
        if code not in present_codes:
            issues.append(f"FDA-mandatory parameter {code} is missing from TS domain")

    # Check for empty TSVAL on required parameters
    if "TSVAL" in ts_df.columns:
        for code in sorted(FDA_REQUIRED_PARAMS):
            if code in present_codes:
                rows = ts_df[ts_df["TSPARMCD"] == code]
                tsval = rows["TSVAL"].iloc[0] if not rows.empty else None
                if tsval is None or (isinstance(tsval, str) and tsval.strip() == ""):
                    issues.append(f"FDA-mandatory parameter {code} has empty TSVAL")

    return issues
