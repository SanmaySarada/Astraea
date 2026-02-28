"""Trial design domain builders (TA, TE, TV, TI).

Config-driven builders that produce valid SDTM DataFrames for the
four trial design domains from a TrialDesignConfig model.

Exports:
    build_ta_domain -- Trial Arms
    build_te_domain -- Trial Elements
    build_tv_domain -- Trial Visits
    build_ti_domain -- Trial Inclusion/Exclusion
    TrialDesignConfig (re-export)
"""

from __future__ import annotations

import pandas as pd
from loguru import logger

from astraea.models.trial_design import TrialDesignConfig


def build_ta_domain(
    config: TrialDesignConfig,
    study_id: str,
) -> pd.DataFrame:
    """Build a Trial Arms (TA) domain DataFrame.

    Produces one row per element per arm, describing the sequence
    of trial elements each arm goes through.

    Args:
        config: Trial design configuration with arm definitions.
        study_id: Study identifier for STUDYID.

    Returns:
        TA domain DataFrame with columns: STUDYID, DOMAIN, ARMCD,
        ARM, TAETORD, ETCD, ELEMENT, TABRSESS, EPOCH.
    """
    rows: list[dict[str, object]] = []

    # Build element lookup for descriptions
    element_lookup: dict[str, str] = {e.etcd: e.element for e in config.elements}

    # Group arms by ARMCD to get unique arm names
    arm_names: dict[str, str] = {}
    for arm_def in config.arms:
        arm_names[arm_def.armcd] = arm_def.arm

    # Track session number per arm (TABRSESS)
    arm_session_counter: dict[str, int] = {}

    for arm_def in config.arms:
        arm_session_counter.setdefault(arm_def.armcd, 0)
        arm_session_counter[arm_def.armcd] += 1

        rows.append(
            {
                "STUDYID": study_id,
                "DOMAIN": "TA",
                "ARMCD": arm_def.armcd,
                "ARM": arm_def.arm,
                "TAETORD": arm_def.taetord,
                "ETCD": arm_def.etcd,
                "ELEMENT": element_lookup.get(arm_def.etcd, arm_def.etcd),
                "TABRSESS": arm_session_counter[arm_def.armcd],
                "EPOCH": element_lookup.get(arm_def.etcd, ""),
            }
        )

    ta_df = pd.DataFrame(rows)

    logger.info(
        "Built TA domain: {} rows ({} arms) for study {}",
        len(ta_df),
        len(arm_names),
        study_id,
    )

    return ta_df


def build_te_domain(
    config: TrialDesignConfig,
    study_id: str,
) -> pd.DataFrame:
    """Build a Trial Elements (TE) domain DataFrame.

    Produces one row per trial element, describing start/end rules
    and planned duration.

    Args:
        config: Trial design configuration with element definitions.
        study_id: Study identifier for STUDYID.

    Returns:
        TE domain DataFrame with columns: STUDYID, DOMAIN, ETCD,
        ELEMENT, TESTRL, TEENRL, TEDUR.
    """
    rows: list[dict[str, object]] = []

    for elem in config.elements:
        rows.append(
            {
                "STUDYID": study_id,
                "DOMAIN": "TE",
                "ETCD": elem.etcd,
                "ELEMENT": elem.element,
                "TESTRL": elem.testrl,
                "TEENRL": elem.teenrl,
                "TEDUR": elem.tedur,
            }
        )

    te_df = pd.DataFrame(rows)

    logger.info(
        "Built TE domain: {} elements for study {}",
        len(te_df),
        study_id,
    )

    return te_df


def build_tv_domain(
    config: TrialDesignConfig,
    study_id: str,
) -> pd.DataFrame:
    """Build a Trial Visits (TV) domain DataFrame.

    Produces one row per visit per arm, describing the planned
    visit schedule with window rules.

    Args:
        config: Trial design configuration with visit definitions.
        study_id: Study identifier for STUDYID.

    Returns:
        TV domain DataFrame with columns: STUDYID, DOMAIN, VISITNUM,
        VISIT, VISITDY, ARMCD, TVSTRL, TVENRL.
    """
    rows: list[dict[str, object]] = []

    for visit in config.visits:
        rows.append(
            {
                "STUDYID": study_id,
                "DOMAIN": "TV",
                "VISITNUM": visit.visitnum,
                "VISIT": visit.visit,
                "VISITDY": visit.visitdy,
                "ARMCD": visit.armcd,
                "TVSTRL": visit.tvstrl,
                "TVENRL": visit.tvenrl,
            }
        )

    tv_df = pd.DataFrame(rows)

    logger.info(
        "Built TV domain: {} visit-arm rows for study {}",
        len(tv_df),
        study_id,
    )

    return tv_df


def build_ti_domain(
    config: TrialDesignConfig,
    study_id: str,
) -> pd.DataFrame:
    """Build a Trial Inclusion/Exclusion (TI) domain DataFrame.

    Produces one row per I/E criterion. If config.inclusion_exclusion
    is None, returns an empty DataFrame with correct columns.

    NOTE: TI is the trial-level template. IE (from Phase 5) is the
    subject-level data capturing each subject's actual I/E results.

    Args:
        config: Trial design configuration with I/E criteria.
        study_id: Study identifier for STUDYID.

    Returns:
        TI domain DataFrame with columns: STUDYID, DOMAIN, IETESTCD,
        IETEST, IECAT, TIRL.
    """
    ti_columns = ["STUDYID", "DOMAIN", "IETESTCD", "IETEST", "IECAT", "TIRL"]

    if config.inclusion_exclusion is None:
        logger.info("No I/E criteria in config -- returning empty TI domain")
        return pd.DataFrame(columns=ti_columns)

    rows: list[dict[str, object]] = []

    for criterion in config.inclusion_exclusion:
        rows.append(
            {
                "STUDYID": study_id,
                "DOMAIN": "TI",
                "IETESTCD": criterion.ietestcd,
                "IETEST": criterion.ietest,
                "IECAT": criterion.iecat,
                "TIRL": criterion.tirl,
            }
        )

    ti_df = pd.DataFrame(rows, columns=ti_columns)

    logger.info(
        "Built TI domain: {} criteria for study {}",
        len(ti_df),
        study_id,
    )

    return ti_df
