"""Findings domain execution pipeline for LB, EG, and VS domains.

Provides FindingsExecutor, which orchestrates multi-source data merging,
column normalization, and delegation to DatasetExecutor for Findings-class
SDTM domains. Includes per-domain normalizers that handle both pre-SDTM
(already tall) and CRF-format source data.

Exports:
    FindingsExecutor: Orchestrator class for Findings domain assembly.
    normalize_lab_columns: Column normalization for lab sources.
    normalize_ecg_columns: Column normalization for ECG sources.
    normalize_vs_columns: Column normalization for vital signs sources.
    merge_findings_sources: Multi-source alignment and concatenation.
    derive_standardized_results: Derive STRESC/STRESN/STRESU from ORRES.
    derive_nrind: Derive NRIND from STRESN and reference ranges.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger

from astraea.execution.executor import CrossDomainContext, DatasetExecutor
from astraea.execution.preprocessing import align_multi_source_columns
from astraea.execution.suppqual import generate_suppqual
from astraea.models.mapping import DomainMappingSpec
from astraea.models.suppqual import SuppVariable
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference


def normalize_lab_columns(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Normalize column names for lab source DataFrames.

    Handles two main lab source patterns:
    - lab_results (pre-SDTM): Columns already SDTM-named, no changes needed.
    - llb (local lab): Renames LBTEST2->LBTEST and similar CRF-style columns.

    Ensures LBTESTCD exists (creates placeholder from LBTEST if missing)
    and adds LBCAT column if absent.

    Args:
        df: Raw lab source DataFrame.
        source_name: Source file identifier (e.g., "lab_results", "llb").

    Returns:
        Copy of DataFrame with normalized column names.
    """
    result = df.copy()

    # llb-style local lab data has different column names
    if "llb" in source_name.lower():
        rename_map: dict[str, str] = {}
        if "LBTEST2" in result.columns:
            rename_map["LBTEST2"] = "LBTEST"
        if "LBORNRLO" in result.columns and "LBSTNRLO" not in result.columns:
            rename_map["LBORNRLO"] = "LBSTNRLO"
        if "LBORNRHI" in result.columns and "LBSTNRHI" not in result.columns:
            rename_map["LBORNRHI"] = "LBSTNRHI"
        if rename_map:
            result = result.rename(columns=rename_map)

    # Ensure LBCAT exists
    if "LBCAT" not in result.columns:
        result["LBCAT"] = ""

    # Ensure LBTESTCD exists: derive from LBTEST if missing
    if "LBTESTCD" not in result.columns and "LBTEST" in result.columns:
        result["LBTESTCD"] = result["LBTEST"].astype(str).str[:8].str.upper().str.strip()
        logger.debug("Created LBTESTCD from LBTEST for source '{}'", source_name)

    return result


def normalize_ecg_columns(
    df: pd.DataFrame,
    source_name: str,
    time_point: str | None = None,
) -> pd.DataFrame:
    """Normalize column names for ECG source DataFrames.

    Handles two ECG source patterns:
    - ecg_results (pre-SDTM): Columns already SDTM-named, no changes.
    - eg_pre/eg_post/eg3 (CRF): Renames EGPERF3->EGPERF, EGDAT3->EGDTC,
      EGRS3->EGORRES, EGABS3/EGCS3 kept for SUPPEG candidates.

    If time_point is provided, sets EGTPT for all rows in this source.

    Args:
        df: Raw ECG source DataFrame.
        source_name: Source file identifier (e.g., "ecg_results", "eg_pre").
        time_point: Optional time point value (e.g., "Pre-dose") to set EGTPT.

    Returns:
        Copy of DataFrame with normalized column names.
    """
    result = df.copy()
    source_lower = source_name.lower()

    # CRF-style ECG sources (eg_pre, eg_post, eg3)
    if any(tag in source_lower for tag in ("eg_pre", "eg_post", "eg3")):
        rename_map: dict[str, str] = {}
        if "EGPERF3" in result.columns:
            rename_map["EGPERF3"] = "EGPERF"
        if "EGDAT3" in result.columns:
            rename_map["EGDAT3"] = "EGDTC"
        if "EGRS3" in result.columns:
            rename_map["EGRS3"] = "EGORRES"
        # EGTIM3: if present alongside a date, could be appended to EGDTC
        # For now keep as-is for potential SUPPEG
        if "EGABS3" in result.columns:
            rename_map["EGABS3"] = "EGABS"
        if "EGCS3" in result.columns:
            rename_map["EGCS3"] = "EGCLSIG"

        # Handle time point columns
        for tpt_col in ("EG_TPT_PRE", "EG_TPT_POST", "EG_TPT"):
            if tpt_col in result.columns:
                rename_map[tpt_col] = "EGTPT"
                break

        if rename_map:
            result = result.rename(columns=rename_map)

    # Set EGTPT from parameter if provided
    if time_point is not None:
        result["EGTPT"] = time_point

    return result


def normalize_vs_columns(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Normalize column names for vital signs source DataFrames.

    Handles common CRF patterns for VS data:
    - VSPERF -> VSSTAT (performed flag)
    - VSDAT -> VSDTC (date)
    - VSTIM -> appended to VSDTC if both exist
    - VSPOS -> VSPOS (position, kept as-is)
    - VSLOC -> VSLOC (location, kept as-is)
    - VSBLFL -> VSBLFL (baseline flag, kept as-is)

    Ensures VSTESTCD exists (creates placeholder from VSTEST if missing).

    Args:
        df: Raw VS source DataFrame.
        source_name: Source file identifier.

    Returns:
        Copy of DataFrame with normalized column names.
    """
    result = df.copy()

    # CRF-style column renames
    rename_map: dict[str, str] = {}
    if "VSPERF" in result.columns and "VSSTAT" not in result.columns:
        rename_map["VSPERF"] = "VSSTAT"
    if "VSDAT" in result.columns and "VSDTC" not in result.columns:
        rename_map["VSDAT"] = "VSDTC"

    if rename_map:
        result = result.rename(columns=rename_map)

    # Append VSTIM to VSDTC if both exist
    if "VSTIM" in result.columns and "VSDTC" in result.columns:
        # Combine date and time into ISO 8601 datetime
        mask = result["VSTIM"].notna() & (result["VSTIM"].astype(str).str.strip() != "")
        if mask.any():
            result.loc[mask, "VSDTC"] = (
                result.loc[mask, "VSDTC"].astype(str) + "T" + result.loc[mask, "VSTIM"].astype(str)
            )
        result = result.drop(columns=["VSTIM"])

    # Ensure VSTESTCD exists: derive from VSTEST if missing
    if "VSTESTCD" not in result.columns and "VSTEST" in result.columns:
        result["VSTESTCD"] = result["VSTEST"].astype(str).str[:8].str.upper().str.strip()
        logger.debug("Created VSTESTCD from VSTEST for source '{}'", source_name)

    return result


def merge_findings_sources(
    dfs: dict[str, pd.DataFrame],
    domain: str,
) -> tuple[pd.DataFrame, list[str]]:
    """Merge multiple normalized Findings source DataFrames.

    Aligns columns across sources and concatenates into a single DataFrame.
    Identifies supplemental candidate columns that are not standard SDTM
    variables for the given domain.

    Args:
        dfs: Dictionary of source_name -> normalized DataFrame.
        domain: SDTM domain code (e.g., "LB", "EG", "VS").

    Returns:
        Tuple of (merged_df, supplemental_candidate_columns).
        supplemental_candidate_columns are columns that exist in sources
        but are not standard SDTM domain variables.
    """
    if not dfs:
        return pd.DataFrame(), []

    if len(dfs) == 1:
        merged = next(iter(dfs.values())).copy()
    else:
        # Use align_multi_source_columns with empty rename maps (already normalized)
        aligned = align_multi_source_columns(dfs, {})
        merged = pd.concat(list(aligned.values()), ignore_index=True)

    # Identify supplemental candidates: columns not matching standard SDTM prefix
    domain_upper = domain.upper()
    # Standard SDTM Findings columns share the domain prefix or are common identifiers
    common_sdtm_cols = {
        "STUDYID",
        "DOMAIN",
        "USUBJID",
        "VISITNUM",
        "VISIT",
        "EPOCH",
        "Subject",
        "SiteNumber",
        "InstanceName",
    }
    supp_candidates = []
    for col in merged.columns:
        if col in common_sdtm_cols:
            continue
        if col.upper().startswith(domain_upper):
            continue
        # Columns that don't match the domain prefix are supplemental candidates
        supp_candidates.append(col)

    logger.debug(
        "Merged {} sources for {} domain: {} rows, {} supplemental candidates",
        len(dfs),
        domain,
        len(merged),
        len(supp_candidates),
    )

    return merged, supp_candidates


def derive_standardized_results(df: pd.DataFrame, domain_prefix: str) -> pd.DataFrame:
    """Derive standardized result variables (--STRESC, --STRESN, --STRESU) from original results.

    For v1, NO unit conversion is performed -- ORRESU is copied directly to STRESU.
    Unit standardization (e.g., lbs to kg, mg/dL to mmol/L) is deferred to a future version.

    Args:
        df: DataFrame containing at minimum ``{prefix}ORRES`` column.
        domain_prefix: Two-letter SDTM domain prefix (e.g., "LB", "EG", "VS").

    Returns:
        The DataFrame with STRESC, STRESN, and optionally STRESU columns added.
        If the ORRES column does not exist, returns the DataFrame unchanged.
    """
    orres_col = f"{domain_prefix}ORRES"
    if orres_col not in df.columns:
        return df

    stresc_col = f"{domain_prefix}STRESC"
    stresn_col = f"{domain_prefix}STRESN"
    stresu_col = f"{domain_prefix}STRESU"
    orresu_col = f"{domain_prefix}ORRESU"

    # STRESC: character copy of ORRES
    df[stresc_col] = df[orres_col]

    # STRESN: numeric parse -- NaN for non-numeric values
    df[stresn_col] = pd.to_numeric(df[orres_col], errors="coerce")

    # STRESU: copy of ORRESU if it exists
    if orresu_col in df.columns:
        df[stresu_col] = df[orresu_col]

    logger.debug(
        "Derived standardized results for {} domain: STRESC, STRESN{}",
        domain_prefix,
        ", STRESU" if orresu_col in df.columns else "",
    )
    return df


def derive_nrind(df: pd.DataFrame, domain_prefix: str) -> pd.DataFrame:
    """Derive normal range indicator (--NRIND) from standardized numeric result.

    Uses reference ranges (STNRLO/STNRHI) to classify results.

    Produces LOW, HIGH, NORMAL, or null based on comparison of STRESN to STNRLO/STNRHI.
    Handles partial ranges: if only one bound is available, derives the applicable
    indicator (LOW or HIGH) and leaves null where the missing bound would be needed.

    Args:
        df: DataFrame containing at minimum ``{prefix}STRESN`` column.
            Optionally ``{prefix}STNRLO`` and/or ``{prefix}STNRHI``.
        domain_prefix: Two-letter SDTM domain prefix (e.g., "LB", "EG", "VS").

    Returns:
        The DataFrame with NRIND column added.
        If the STRESN column does not exist, returns the DataFrame unchanged.
    """
    stresn_col = f"{domain_prefix}STRESN"
    if stresn_col not in df.columns:
        return df

    nrind_col = f"{domain_prefix}NRIND"
    stnrlo_col = f"{domain_prefix}STNRLO"
    stnrhi_col = f"{domain_prefix}STNRHI"

    stresn = pd.to_numeric(df[stresn_col], errors="coerce")
    has_lo = stnrlo_col in df.columns
    has_hi = stnrhi_col in df.columns

    if has_lo:
        stnrlo = pd.to_numeric(df[stnrlo_col], errors="coerce")
    if has_hi:
        stnrhi = pd.to_numeric(df[stnrhi_col], errors="coerce")

    # Build conditions and choices using np.select
    conditions: list[pd.Series] = []
    choices: list[str] = []

    if has_lo:
        conditions.append(stresn.notna() & stnrlo.notna() & (stresn < stnrlo))
        choices.append("LOW")

    if has_hi:
        conditions.append(stresn.notna() & stnrhi.notna() & (stresn > stnrhi))
        choices.append("HIGH")

    if has_lo and has_hi:
        conditions.append(
            stresn.notna()
            & stnrlo.notna()
            & stnrhi.notna()
            & (stresn >= stnrlo)
            & (stresn <= stnrhi)
        )
        choices.append("NORMAL")

    if conditions:
        result = np.select(conditions, choices, default=None)
        df[nrind_col] = pd.array(result, dtype=object)
        # Ensure None stays as None (np.select returns 0/None as string "0"/"None")
        valid_values = ["LOW", "HIGH", "NORMAL"]
        df[nrind_col] = df[nrind_col].where(
            df[nrind_col].isin(valid_values), other=None
        )
    else:
        # No range columns at all -- NRIND is all null
        df[nrind_col] = None

    logger.debug(
        "Derived NRIND for {} domain (lo={}, hi={})",
        domain_prefix,
        has_lo,
        has_hi,
    )
    return df


class FindingsExecutor:
    """Orchestrator for multi-source Findings domain execution.

    Wraps DatasetExecutor with domain-specific normalization and merging
    for LB, EG, and VS domains. Handles column alignment, multi-source
    concatenation, and optional SUPPQUAL generation.

    Args:
        sdtm_ref: SDTM-IG reference for domain specs.
        ct_ref: Controlled terminology reference for codelist lookups.
    """

    def __init__(
        self,
        *,
        sdtm_ref: SDTMReference | None = None,
        ct_ref: CTReference | None = None,
    ) -> None:
        self.sdtm_ref = sdtm_ref
        self.ct_ref = ct_ref
        self._executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)

    def _derive_findings_variables(self, df: pd.DataFrame, domain_prefix: str) -> pd.DataFrame:
        """Derive standardized results and normal range indicator for a Findings domain.

        Calls derive_standardized_results (STRESC/STRESN/STRESU) then derive_nrind (NRIND)
        in sequence. Should be called AFTER DatasetExecutor.execute() but BEFORE SUPPQUAL
        generation.

        Args:
            df: Executed Findings DataFrame.
            domain_prefix: Two-letter SDTM domain prefix (e.g., "LB", "EG", "VS").

        Returns:
            DataFrame with derived Findings variables added.
        """
        df = derive_standardized_results(df, domain_prefix)
        df = derive_nrind(df, domain_prefix)
        return df

    def execute_lb(
        self,
        spec: DomainMappingSpec,
        raw_dfs: dict[str, pd.DataFrame],
        cross_domain: CrossDomainContext | None = None,
        *,
        study_id: str | None = None,
        site_col: str = "SiteNumber",
        subject_col: str = "Subject",
        supp_variables: list[SuppVariable] | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        """Execute LB domain from multiple lab source DataFrames.

        Normalizes each source, merges into a single DataFrame, delegates
        to DatasetExecutor, and optionally generates SUPPLB.

        Args:
            spec: LB domain mapping specification.
            raw_dfs: Dict of source_name -> raw lab DataFrame.
            cross_domain: Cross-domain context for --DY, EPOCH, VISIT.
            study_id: Study identifier for USUBJID generation.
            site_col: Raw column name for site ID.
            subject_col: Raw column name for subject ID.
            supp_variables: Optional SUPPQUAL variables to extract.

        Returns:
            Tuple of (lb_df, supplb_df_or_none).
        """
        # Normalize each source
        normalized: dict[str, pd.DataFrame] = {}
        for name, df in raw_dfs.items():
            normalized[name] = normalize_lab_columns(df, name)

        # Merge sources
        merged, _supp_candidates = merge_findings_sources(normalized, "LB")

        # Execute via DatasetExecutor
        lb_df = self._executor.execute(
            spec,
            {"merged_lb": merged},
            cross_domain=cross_domain,
            study_id=study_id,
            site_col=site_col,
            subject_col=subject_col,
        )

        # Derive Findings-specific variables (STRESC, STRESN, STRESU, NRIND)
        lb_df = self._derive_findings_variables(lb_df, "LB")

        # Generate SUPPLB if requested
        supplb_df = None
        if supp_variables and not lb_df.empty:
            sid = study_id or spec.study_id
            supplb_df = generate_suppqual(lb_df, "LB", sid, supp_variables)
            if supplb_df.empty:
                supplb_df = None

        logger.info(
            "LB execution complete: {} rows from {} sources",
            len(lb_df),
            len(raw_dfs),
        )

        return lb_df, supplb_df

    def execute_eg(
        self,
        spec: DomainMappingSpec,
        raw_dfs: dict[str, pd.DataFrame],
        cross_domain: CrossDomainContext | None = None,
        *,
        study_id: str | None = None,
        site_col: str = "SiteNumber",
        subject_col: str = "Subject",
        supp_variables: list[SuppVariable] | None = None,
        time_points: dict[str, str] | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        """Execute EG domain from multiple ECG source DataFrames.

        Normalizes each source (with optional time point assignment),
        merges, delegates to DatasetExecutor, and optionally generates SUPPEG.

        Args:
            spec: EG domain mapping specification.
            raw_dfs: Dict of source_name -> raw ECG DataFrame.
            cross_domain: Cross-domain context for --DY, EPOCH, VISIT.
            study_id: Study identifier for USUBJID generation.
            site_col: Raw column name for site ID.
            subject_col: Raw column name for subject ID.
            supp_variables: Optional SUPPQUAL variables to extract.
            time_points: Optional mapping of source_name -> time point value
                (e.g., {"eg_pre": "Pre-dose", "eg_post": "Post-dose"}).

        Returns:
            Tuple of (eg_df, suppeg_df_or_none).
        """
        time_points = time_points or {}

        # Normalize each source
        normalized: dict[str, pd.DataFrame] = {}
        for name, df in raw_dfs.items():
            tp = time_points.get(name)
            normalized[name] = normalize_ecg_columns(df, name, time_point=tp)

        # Merge sources
        merged, _supp_candidates = merge_findings_sources(normalized, "EG")

        # Execute via DatasetExecutor
        eg_df = self._executor.execute(
            spec,
            {"merged_eg": merged},
            cross_domain=cross_domain,
            study_id=study_id,
            site_col=site_col,
            subject_col=subject_col,
        )

        # Derive Findings-specific variables (STRESC, STRESN, STRESU, NRIND)
        eg_df = self._derive_findings_variables(eg_df, "EG")

        # Generate SUPPEG if requested
        suppeg_df = None
        if supp_variables and not eg_df.empty:
            sid = study_id or spec.study_id
            suppeg_df = generate_suppqual(eg_df, "EG", sid, supp_variables)
            if suppeg_df.empty:
                suppeg_df = None

        logger.info(
            "EG execution complete: {} rows from {} sources",
            len(eg_df),
            len(raw_dfs),
        )

        return eg_df, suppeg_df

    def execute_vs(
        self,
        spec: DomainMappingSpec,
        raw_dfs: dict[str, pd.DataFrame],
        cross_domain: CrossDomainContext | None = None,
        *,
        study_id: str | None = None,
        site_col: str = "SiteNumber",
        subject_col: str = "Subject",
        supp_variables: list[SuppVariable] | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        """Execute VS domain from vital signs source DataFrames.

        Normalizes each source, merges if multiple, delegates to
        DatasetExecutor, and optionally generates SUPPVS.

        Args:
            spec: VS domain mapping specification.
            raw_dfs: Dict of source_name -> raw VS DataFrame.
            cross_domain: Cross-domain context for --DY, EPOCH, VISIT.
            study_id: Study identifier for USUBJID generation.
            site_col: Raw column name for site ID.
            subject_col: Raw column name for subject ID.
            supp_variables: Optional SUPPQUAL variables to extract.

        Returns:
            Tuple of (vs_df, suppvs_df_or_none).
        """
        # Normalize each source
        normalized: dict[str, pd.DataFrame] = {}
        for name, df in raw_dfs.items():
            normalized[name] = normalize_vs_columns(df, name)

        # Merge sources
        merged, _supp_candidates = merge_findings_sources(normalized, "VS")

        # Execute via DatasetExecutor
        vs_df = self._executor.execute(
            spec,
            {"merged_vs": merged},
            cross_domain=cross_domain,
            study_id=study_id,
            site_col=site_col,
            subject_col=subject_col,
        )

        # Derive Findings-specific variables (STRESC, STRESN, STRESU, NRIND)
        vs_df = self._derive_findings_variables(vs_df, "VS")

        # Generate SUPPVS if requested
        suppvs_df = None
        if supp_variables and not vs_df.empty:
            sid = study_id or spec.study_id
            suppvs_df = generate_suppqual(vs_df, "VS", sid, supp_variables)
            if suppvs_df.empty:
                suppvs_df = None

        logger.info(
            "VS execution complete: {} rows from {} sources",
            len(vs_df),
            len(raw_dfs),
        )

        return vs_df, suppvs_df
