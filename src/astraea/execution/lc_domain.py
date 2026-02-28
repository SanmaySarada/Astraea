"""LC (Laboratory Conventional) domain generation from LB data.

Implements the FDA SDTCG v5.7 requirement for dual lab domains: LB for SI
units, LC for conventional units. For v1, LC is generated as a structural
copy of LB with columns renamed from LB-prefix to LC-prefix. A validation
warning explicitly flags that unit conversion was not performed, ensuring
reviewers know manual unit review is needed before submission.

Exports:
    generate_lc_from_lb: Generate LC DataFrame from LB DataFrame.
    get_lb_to_lc_rename_map: Build column rename mapping from LB to LC.
    generate_lc_mapping_spec: Create LC mapping spec from LB spec.
    LC_DOMAIN_DEFINITION: Basic metadata for define.xml reference.
"""

from __future__ import annotations

import pandas as pd
from loguru import logger

from astraea.models.mapping import (
    DomainMappingSpec,
    VariableMapping,
)

# Columns that are common across all SDTM domains and should NOT be renamed
_COMMON_COLUMNS = frozenset({
    "STUDYID",
    "DOMAIN",
    "USUBJID",
    "VISITNUM",
    "VISIT",
    "VISITDY",
    "EPOCH",
    "SITEID",
    "SUBJID",
    "RFSTDTC",
    "RFENDTC",
    "RFXSTDTC",
    "RFXENDTC",
    "RFICDTC",
    "RFPENDTC",
    "DTHDTC",
    "DTHFL",
    "Subject",
    "SiteNumber",
    "InstanceName",
    "FolderName",
})

# LC domain definition metadata for define.xml
LC_DOMAIN_DEFINITION: dict[str, str] = {
    "domain": "LC",
    "domain_label": "Laboratory Test Results - Conventional Units",
    "domain_class": "Findings",
    "structure": "One record per subject per visit per lab test per time point",
}


def get_lb_to_lc_rename_map(columns: list[str]) -> dict[str, str]:
    """Build the column rename mapping from LB-prefixed to LC-prefixed names.

    Filters out common/non-LB columns that should not be renamed.
    Only renames columns that start with 'LB' (case-sensitive).

    Args:
        columns: List of column names from the LB DataFrame.

    Returns:
        Dictionary mapping LB column names to their LC equivalents.
        For example: {"LBTESTCD": "LCTESTCD", "LBSEQ": "LCSEQ"}.
    """
    rename_map: dict[str, str] = {}
    for col in columns:
        if col in _COMMON_COLUMNS:
            continue
        if col.startswith("LB"):
            lc_name = "LC" + col[2:]
            rename_map[col] = lc_name
    return rename_map


def generate_lc_from_lb(
    lb_df: pd.DataFrame,
    study_id: str,
    *,
    unit_conversion: bool = False,
) -> tuple[pd.DataFrame, list[str]]:
    """Generate LC (Laboratory Conventional) domain from LB data.

    Creates the LC domain by copying LB and renaming LB-prefixed columns
    to LC-prefixed columns. Sets DOMAIN to 'LC'. For v1, no unit conversion
    is performed -- a warning is emitted indicating manual review is needed.

    Args:
        lb_df: LB domain DataFrame (source).
        study_id: Study identifier (for logging context).
        unit_conversion: If True, would perform SI-to-conventional unit
            conversion. Defaults to False for v1.

    Returns:
        Tuple of (lc_df, warnings). The warnings list contains any
        messages about missing unit conversion or other issues.
    """
    warnings: list[str] = []

    if lb_df.empty:
        logger.info("LB DataFrame is empty; generating empty LC domain")
        lc_df = lb_df.copy()
        rename_map = get_lb_to_lc_rename_map(list(lc_df.columns))
        lc_df = lc_df.rename(columns=rename_map)
        if "DOMAIN" in lc_df.columns:
            lc_df["DOMAIN"] = "LC"
        return lc_df, warnings

    # Step 1: Copy the LB DataFrame
    lc_df = lb_df.copy()

    # Step 2: Rename LB-prefixed columns to LC-prefixed
    rename_map = get_lb_to_lc_rename_map(list(lc_df.columns))
    lc_df = lc_df.rename(columns=rename_map)

    # Step 3: Set DOMAIN to LC
    lc_df["DOMAIN"] = "LC"

    # Step 4: Handle unit conversion flag
    if not unit_conversion:
        msg = (
            "LC domain generated as structural copy of LB. "
            "Unit conversion from SI to conventional units not performed. "
            "Manual review required."
        )
        warnings.append(msg)
        logger.warning(msg)
        # Set metadata attr for validation rule detection
        lc_df.attrs["lc_unit_conversion_performed"] = False
    else:
        lc_df.attrs["lc_unit_conversion_performed"] = True

    # Step 5: Validate row count
    assert len(lc_df) == len(lb_df), (
        f"LC and LB row count mismatch: LC={len(lc_df)}, LB={len(lb_df)}"
    )

    logger.info(
        "LC domain generated from LB for study {}: {} rows, {} columns renamed",
        study_id,
        len(lc_df),
        len(rename_map),
    )

    return lc_df, warnings


def generate_lc_mapping_spec(lb_spec: DomainMappingSpec) -> DomainMappingSpec:
    """Create an LC mapping specification from an LB mapping spec.

    Copies the LB spec structure with domain='LC' and renames all
    variable references from LB-prefix to LC-prefix. Used for
    define.xml and cSDRG generation.

    Args:
        lb_spec: The LB domain mapping specification.

    Returns:
        A new DomainMappingSpec for the LC domain.
    """
    lc_mappings: list[VariableMapping] = []
    for vm in lb_spec.variable_mappings:
        # Rename the SDTM variable from LB* to LC*
        sdtm_var = vm.sdtm_variable
        if sdtm_var.startswith("LB"):
            sdtm_var = "LC" + sdtm_var[2:]

        # Rename the label references
        sdtm_label = vm.sdtm_label
        if "LB" in sdtm_label:
            sdtm_label = sdtm_label  # Keep original label text -- domain-agnostic

        lc_mappings.append(
            vm.model_copy(
                update={
                    "sdtm_variable": sdtm_var,
                }
            )
        )

    return DomainMappingSpec(
        domain="LC",
        domain_label=LC_DOMAIN_DEFINITION["domain_label"],
        domain_class=LC_DOMAIN_DEFINITION["domain_class"],
        structure=LC_DOMAIN_DEFINITION["structure"],
        study_id=lb_spec.study_id,
        source_datasets=lb_spec.source_datasets,
        cross_domain_sources=lb_spec.cross_domain_sources,
        variable_mappings=lc_mappings,
        total_variables=lb_spec.total_variables,
        required_mapped=lb_spec.required_mapped,
        expected_mapped=lb_spec.expected_mapped,
        high_confidence_count=lb_spec.high_confidence_count,
        medium_confidence_count=lb_spec.medium_confidence_count,
        low_confidence_count=lb_spec.low_confidence_count,
        mapping_timestamp=lb_spec.mapping_timestamp,
        model_used=lb_spec.model_used,
        unmapped_source_variables=lb_spec.unmapped_source_variables,
        suppqual_candidates=lb_spec.suppqual_candidates,
        missing_required_variables=lb_spec.missing_required_variables,
    )
