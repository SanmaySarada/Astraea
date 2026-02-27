"""Dataset execution pipeline for transforming mapping specs into SDTM DataFrames.

Provides DatasetExecutor, the core class that takes a DomainMappingSpec and
raw DataFrames and produces a fully-formed SDTM DataFrame with correct
variable order, derived fields (--DY, --SEQ, EPOCH, VISIT), and only
mapped columns retained.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from astraea.execution.pattern_handlers import PATTERN_HANDLERS
from astraea.models.mapping import DomainMappingSpec, MappingPattern, VariableMapping
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.transforms.epoch import assign_epoch
from astraea.transforms.sequence import generate_seq
from astraea.transforms.study_day import calculate_study_day_column
from astraea.transforms.visit import assign_visit


class ExecutionError(Exception):
    """Raised when a critical mapping execution step fails."""


class CrossDomainContext(BaseModel):
    """Cross-domain data needed for derived variables like --DY, EPOCH, VISITNUM.

    Carries data from other domains (e.g., DM for RFSTDTC, SE for EPOCH)
    that is needed during execution of any single domain.
    """

    rfstdtc_lookup: dict[str, str] = Field(
        default_factory=dict,
        description="USUBJID -> RFSTDTC mapping for --DY calculation",
    )
    se_data: Any = Field(
        default=None,
        description="SE domain DataFrame for EPOCH derivation",
    )
    tv_data: Any = Field(
        default=None,
        description="TV domain DataFrame for VISITNUM derivation",
    )
    visit_mapping: dict[str, tuple[float, str]] = Field(
        default_factory=dict,
        description="Raw visit identifier -> (VISITNUM, VISIT) mapping",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


# Critical SDTM variables -- if these fail, execution should abort
_CRITICAL_VARIABLES = frozenset({"STUDYID", "DOMAIN", "USUBJID"})

# Pattern execution priority order
_PATTERN_ORDER: list[set[MappingPattern]] = [
    {MappingPattern.ASSIGN},
    {MappingPattern.DIRECT, MappingPattern.RENAME},
    {MappingPattern.REFORMAT},
    {MappingPattern.LOOKUP_RECODE},
    {MappingPattern.DERIVATION, MappingPattern.COMBINE},
    {MappingPattern.SPLIT, MappingPattern.TRANSPOSE},
]


class DatasetExecutor:
    """Transforms a DomainMappingSpec + raw DataFrames into an SDTM DataFrame.

    Applies variable mappings via pattern handlers in priority order, then
    derives cross-domain fields (--DY, --SEQ, EPOCH, VISIT), enforces
    column order, and drops unmapped columns.
    """

    def __init__(
        self,
        *,
        sdtm_ref: SDTMReference | None = None,
        ct_ref: CTReference | None = None,
    ) -> None:
        self.sdtm_ref = sdtm_ref
        self.ct_ref = ct_ref

    def execute(
        self,
        spec: DomainMappingSpec,
        raw_dfs: dict[str, pd.DataFrame],
        cross_domain: CrossDomainContext | None = None,
        *,
        study_id: str | None = None,
        site_col: str = "SiteNumber",
        subject_col: str = "Subject",
    ) -> pd.DataFrame:
        """Execute a mapping specification against raw data.

        Args:
            spec: Domain mapping specification to execute.
            raw_dfs: Dictionary of source dataset name -> DataFrame.
            cross_domain: Optional cross-domain context for --DY, EPOCH, VISIT.
            study_id: Study identifier for USUBJID generation.
            site_col: Raw column name for site ID (default "SiteNumber").
            subject_col: Raw column name for subject ID (default "Subject").

        Returns:
            SDTM-compliant DataFrame with mapped variables in spec order.

        Raises:
            ExecutionError: If a critical variable (STUDYID, DOMAIN, USUBJID)
                fails to map.
        """
        # Step a: Merge raw DataFrames
        merged_df = self._merge_raw(raw_dfs)

        # Step b: Apply mappings by pattern priority order
        result_df = pd.DataFrame(index=merged_df.index)
        mapped_vars = set()

        handler_kwargs = {
            "ct_reference": self.ct_ref,
            "study_id": study_id or spec.study_id,
            "site_col": site_col,
            "subject_col": subject_col,
        }

        for pattern_group in _PATTERN_ORDER:
            group_mappings = [
                m for m in spec.variable_mappings if m.mapping_pattern in pattern_group
            ]
            for mapping in group_mappings:
                self._apply_mapping(
                    mapping, merged_df, result_df, mapped_vars, handler_kwargs
                )

        # Step c: Derive --DY variables
        if cross_domain and cross_domain.rfstdtc_lookup:
            self._derive_dy(result_df, spec, cross_domain)

        # Step d: Assign EPOCH
        if cross_domain and cross_domain.se_data is not None:
            self._assign_epoch(result_df, spec, cross_domain)

        # Step e: Assign VISITNUM/VISIT
        if cross_domain and cross_domain.visit_mapping:
            self._assign_visit(result_df, merged_df, cross_domain)

        # Step f: Generate --SEQ (not for DM)
        if spec.domain.upper() != "DM":
            self._generate_seq(result_df, spec)

        # Step g + h: Enforce variable column order and drop unmapped
        result_df = self._enforce_column_order(result_df, spec)

        # Step i: Sort rows by domain key variables
        result_df = self._sort_rows(result_df, spec)

        logger.info(
            "Executed {} domain: {} rows x {} columns",
            spec.domain,
            len(result_df),
            len(result_df.columns),
        )

        return result_df

    def _merge_raw(self, raw_dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Merge multiple source DataFrames into one, working on copies."""
        if not raw_dfs:
            return pd.DataFrame()

        dfs = list(raw_dfs.values())
        if len(dfs) == 1:
            return dfs[0].copy()

        return pd.concat(dfs, ignore_index=True)

    def _apply_mapping(
        self,
        mapping: VariableMapping,
        source_df: pd.DataFrame,
        result_df: pd.DataFrame,
        mapped_vars: set[str],
        handler_kwargs: dict[str, object],
    ) -> None:
        """Apply a single mapping, handling errors gracefully."""
        handler = PATTERN_HANDLERS.get(mapping.mapping_pattern)
        if handler is None:
            logger.error(
                "No handler for pattern {} on {}",
                mapping.mapping_pattern,
                mapping.sdtm_variable,
            )
            return

        try:
            series = handler(source_df, mapping, **handler_kwargs)
            result_df[mapping.sdtm_variable] = series
            mapped_vars.add(mapping.sdtm_variable)
        except Exception as exc:
            if mapping.sdtm_variable in _CRITICAL_VARIABLES:
                msg = (
                    f"Critical variable {mapping.sdtm_variable} failed: {exc}"
                )
                raise ExecutionError(msg) from exc

            logger.warning(
                "Non-critical mapping failed for {}: {}",
                mapping.sdtm_variable,
                exc,
            )
            result_df[mapping.sdtm_variable] = pd.Series(
                None, index=source_df.index, dtype="object"
            )

    def _derive_dy(
        self,
        result_df: pd.DataFrame,
        spec: DomainMappingSpec,
        cross_domain: CrossDomainContext,
    ) -> None:
        """Derive --DY columns from --DTC columns using cross-domain RFSTDTC."""
        # Get the set of --DY variables defined in the spec
        dy_vars = {
            m.sdtm_variable
            for m in spec.variable_mappings
            if m.sdtm_variable.endswith("DY")
        }

        if not dy_vars:
            return

        # Find matching --DTC columns
        for col in list(result_df.columns):
            if col.endswith("DTC"):
                dy_name = col.replace("DTC", "DY")
                if dy_name in dy_vars and "USUBJID" in result_df.columns:
                    try:
                        result_df[dy_name] = calculate_study_day_column(
                            result_df,
                            date_col=col,
                            rfstdtc_lookup=cross_domain.rfstdtc_lookup,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Failed to derive {}: {}", dy_name, exc
                        )

    def _assign_epoch(
        self,
        result_df: pd.DataFrame,
        spec: DomainMappingSpec,
        cross_domain: CrossDomainContext,
    ) -> None:
        """Assign EPOCH from SE domain data."""
        # Check if EPOCH is in the spec
        has_epoch = any(
            m.sdtm_variable == "EPOCH" for m in spec.variable_mappings
        )
        if not has_epoch:
            return

        # Determine date column based on domain class
        domain = spec.domain.upper()
        domain_class = spec.domain_class.lower()

        date_col = f"{domain}DTC" if domain_class == "findings" else f"{domain}STDTC"

        if date_col not in result_df.columns or "USUBJID" not in result_df.columns:
            return

        try:
            se_df = cross_domain.se_data
            result_df["EPOCH"] = assign_epoch(result_df, se_df, date_col)
        except Exception as exc:
            logger.warning("Failed to assign EPOCH: {}", exc)

    def _assign_visit(
        self,
        result_df: pd.DataFrame,
        source_df: pd.DataFrame,
        cross_domain: CrossDomainContext,
    ) -> None:
        """Assign VISITNUM and VISIT from visit mapping."""
        # Look for raw visit column in source data
        raw_visit_col = "InstanceName"
        if raw_visit_col not in source_df.columns:
            return

        try:
            visitnum, visit = assign_visit(
                source_df,
                cross_domain.visit_mapping,
                raw_visit_col=raw_visit_col,
            )
            if "VISITNUM" not in result_df.columns:
                result_df["VISITNUM"] = visitnum
            if "VISIT" not in result_df.columns:
                result_df["VISIT"] = visit
        except Exception as exc:
            logger.warning("Failed to assign VISIT: {}", exc)

    def _generate_seq(
        self,
        result_df: pd.DataFrame,
        spec: DomainMappingSpec,
    ) -> None:
        """Generate --SEQ for the domain."""
        domain = spec.domain.upper()
        seq_var = f"{domain}SEQ"

        # Check if SEQ is in the spec
        has_seq = any(
            m.sdtm_variable == seq_var for m in spec.variable_mappings
        )
        if not has_seq:
            return

        if "USUBJID" not in result_df.columns:
            return

        # Get sort keys from SDTM reference or spec
        sort_keys: list[str] = []
        if self.sdtm_ref:
            domain_spec = self.sdtm_ref.get_domain_spec(domain)
            if domain_spec and domain_spec.key_variables:
                sort_keys = [
                    k for k in domain_spec.key_variables
                    if k != "STUDYID" and k != "USUBJID" and k != seq_var
                ]

        # Fallback: use date columns as sort keys
        if not sort_keys:
            sort_keys = [
                c for c in result_df.columns
                if c.endswith("DTC") or c.endswith("STDTC")
            ]

        try:
            result_df[seq_var] = generate_seq(
                result_df, domain, sort_keys
            )
        except Exception as exc:
            logger.warning("Failed to generate {}: {}", seq_var, exc)

    def _enforce_column_order(
        self,
        result_df: pd.DataFrame,
        spec: DomainMappingSpec,
    ) -> pd.DataFrame:
        """Sort columns by mapping order and drop unmapped columns."""
        # Build order map from spec
        order_map: dict[str, int] = {}
        for m in spec.variable_mappings:
            order_map[m.sdtm_variable] = m.order

        # Only keep columns that appear in variable_mappings
        mapped_names = {m.sdtm_variable for m in spec.variable_mappings}
        keep_cols = [c for c in result_df.columns if c in mapped_names]

        # Sort by order value
        keep_cols.sort(key=lambda c: order_map.get(c, 9999))

        return result_df[keep_cols]

    def _sort_rows(
        self,
        result_df: pd.DataFrame,
        spec: DomainMappingSpec,
    ) -> pd.DataFrame:
        """Sort rows by domain key variables."""
        if result_df.empty:
            return result_df

        sort_cols: list[str] = []

        if self.sdtm_ref:
            domain_spec = self.sdtm_ref.get_domain_spec(spec.domain.upper())
            if domain_spec and domain_spec.key_variables:
                sort_cols = [
                    k for k in domain_spec.key_variables
                    if k in result_df.columns
                ]

        if not sort_cols:
            # Fallback: sort by STUDYID, USUBJID if available
            for col in ["STUDYID", "USUBJID"]:
                if col in result_df.columns:
                    sort_cols.append(col)

        if sort_cols:
            return result_df.sort_values(sort_cols, na_position="last").reset_index(
                drop=True
            )

        return result_df
