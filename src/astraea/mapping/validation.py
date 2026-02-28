"""Post-proposal validation and enrichment for SDTM mapping.

Validates LLM-proposed variable mappings against SDTM-IG domain specs
and CT codelists, enriches proposals with reference data (labels, core
designations, codelist names), and adjusts confidence scores based on
validation outcomes.
"""

from __future__ import annotations

from loguru import logger

from astraea.models.mapping import (
    DomainMappingProposal,
    VariableMapping,
    VariableMappingProposal,
    confidence_level_from_score,
)
from astraea.models.sdtm import CoreDesignation, DomainSpec
from astraea.reference.controlled_terms import CTReference


def validate_and_enrich(
    proposal: DomainMappingProposal,
    domain_spec: DomainSpec,
    ct_ref: CTReference,
) -> tuple[list[VariableMapping], list[str]]:
    """Validate and enrich LLM-proposed variable mappings.

    For each proposal:
    1. Look up the SDTM variable in domain_spec
    2. If not found: flag issue, set confidence to 0.3
    3. If found: enrich with label, data_type, core from VariableSpec
    4. Validate CT codelist if specified
    5. Adjust confidence based on validation results
    6. Compute confidence_level from adjusted score

    Args:
        proposal: Raw LLM output containing variable mapping proposals.
        domain_spec: SDTM-IG domain specification for the target domain.
        ct_ref: Controlled terminology reference for CT validation.

    Returns:
        Tuple of (enriched_mappings, validation_issues).
        enriched_mappings: List of fully populated VariableMapping objects.
        validation_issues: List of human-readable validation issue strings.
    """
    enriched: list[VariableMapping] = []
    issues: list[str] = []

    for vp in proposal.variable_proposals:
        mapping, var_issues = _validate_single_proposal(vp, domain_spec, ct_ref)
        enriched.append(mapping)
        issues.extend(var_issues)

    return enriched, issues


def _validate_single_proposal(
    vp: VariableMappingProposal,
    domain_spec: DomainSpec,
    ct_ref: CTReference,
) -> tuple[VariableMapping, list[str]]:
    """Validate and enrich a single variable mapping proposal.

    Returns:
        Tuple of (enriched VariableMapping, list of issues for this variable).
    """
    issues: list[str] = []
    confidence = vp.confidence

    # Step 1: Look up variable in SDTM-IG domain spec
    var_spec = None
    for v in domain_spec.variables:
        if v.name == vp.sdtm_variable.upper():
            var_spec = v
            break

    if var_spec is None:
        issues.append(f"Variable {vp.sdtm_variable} not in SDTM-IG for domain {domain_spec.domain}")
        # Use defaults for unknown variables
        sdtm_label = vp.sdtm_variable
        sdtm_data_type = "Char"
        core = CoreDesignation.PERM
        confidence = min(confidence, 0.3)
        logger.warning(
            "Variable {var} not found in SDTM-IG for {domain}, confidence capped at 0.3",
            var=vp.sdtm_variable,
            domain=domain_spec.domain,
        )
    else:
        sdtm_label = var_spec.label
        sdtm_data_type = var_spec.data_type
        core = var_spec.core

    # Step 2: Validate CT codelist
    codelist_name: str | None = None
    if vp.codelist_code:
        cl = ct_ref.lookup_codelist(vp.codelist_code)
        if cl is None:
            issues.append(
                f"{vp.sdtm_variable}: codelist {vp.codelist_code} not found in CT reference"
            )
            # Don't penalize ASSIGN patterns with trivially correct values
            # (e.g., DOMAIN="DM", STUDYID=constant) — missing codelist is a
            # reference gap, not a mapping quality issue
            if vp.mapping_pattern != "assign":
                confidence = min(confidence, 0.4)
        else:
            codelist_name = cl.name

            # For non-extensible codelists with an assigned value, validate term
            if vp.assigned_value and not cl.extensible and vp.assigned_value not in cl.terms:
                issues.append(
                    f"{vp.sdtm_variable}: value '{vp.assigned_value}' "
                    f"not in non-extensible codelist {vp.codelist_code} "
                    f"({cl.name})"
                )
                confidence = min(confidence, 0.4)

            # For LOOKUP_RECODE with non-extensible codelists, warn that runtime
            # values must be validated against CT (cannot check at spec time)
            if (
                vp.mapping_pattern == "lookup_recode"
                and not cl.extensible
                and not vp.assigned_value
            ):
                issues.append(
                    f"{vp.sdtm_variable}: non-extensible codelist "
                    f"{vp.codelist_code} ({cl.name}) used with "
                    f"lookup_recode -- runtime values MUST be validated "
                    f"against CT during execution"
                )
                logger.warning(
                    "Non-extensible codelist {cl} on {var} with lookup_recode "
                    "pattern -- cannot validate at spec time, must validate "
                    "at execution time",
                    cl=vp.codelist_code,
                    var=vp.sdtm_variable,
                )

            # Confidence boost for successful CT validation on lookup_recode
            if vp.mapping_pattern == "lookup_recode" and cl is not None:
                confidence = min(confidence + 0.05, 1.0)

    # Step 3: Compute confidence level
    confidence_level = confidence_level_from_score(confidence)

    # Build enriched mapping
    mapping = VariableMapping(
        sdtm_variable=vp.sdtm_variable.upper(),
        sdtm_label=sdtm_label,
        sdtm_data_type=sdtm_data_type,
        core=core,
        source_dataset=vp.source_dataset,
        source_variable=vp.source_variable,
        source_label=None,  # Populated later from profile if available
        mapping_pattern=vp.mapping_pattern,
        mapping_logic=vp.mapping_logic,
        derivation_rule=vp.derivation_rule,
        assigned_value=vp.assigned_value,
        codelist_code=vp.codelist_code,
        codelist_name=codelist_name,
        confidence=confidence,
        confidence_level=confidence_level,
        confidence_rationale=vp.rationale,
        notes="",
        order=var_spec.order if var_spec is not None else 0,
    )

    return mapping, issues


def check_required_coverage(
    mappings: list[VariableMapping],
    domain_spec: DomainSpec,
) -> list[str]:
    """Check that all Required variables in the domain spec have mappings.

    Args:
        mappings: List of enriched variable mappings.
        domain_spec: SDTM-IG domain specification.

    Returns:
        List of missing required variable names. Empty if all covered.
    """
    mapped_names = {m.sdtm_variable.upper() for m in mappings}
    required_vars = [v.name for v in domain_spec.variables if v.core == CoreDesignation.REQ]

    missing = [name for name in required_vars if name not in mapped_names]

    if missing:
        logger.warning(
            "Missing required variables for {domain}: {vars}",
            domain=domain_spec.domain,
            vars=", ".join(missing),
        )

    return missing
