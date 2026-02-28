"""Predict-and-prevent validation for mapping specifications.

Lightweight spec-level checks that run BEFORE dataset generation,
catching issues early so they can be fixed during human review.
No generated data needed -- operates purely on DomainMappingSpec.

Rule IDs: ASTR-PP001 through ASTR-PP007.
"""

from __future__ import annotations

from astraea.models.mapping import DomainMappingSpec, MappingPattern
from astraea.models.sdtm import CoreDesignation, DomainSpec
from astraea.reference.controlled_terms import CTReference
from astraea.validation.rules.base import RuleCategory, RuleResult, RuleSeverity


def predict_and_prevent(
    spec: DomainMappingSpec,
    domain_spec: DomainSpec,
    ct_ref: CTReference,
) -> list[RuleResult]:
    """Run all spec-level predict-and-prevent checks.

    Args:
        spec: The domain mapping specification to validate.
        domain_spec: SDTM-IG domain specification for the target domain.
        ct_ref: Controlled Terminology reference for codelist validation.

    Returns:
        List of RuleResult findings. Empty list means all checks passed.
    """
    results: list[RuleResult] = []
    results.extend(_check_required_variables(spec, domain_spec))
    results.extend(_check_duplicate_mappings(spec))
    results.extend(_check_codelist_exists(spec, ct_ref))
    results.extend(_check_assign_ct_values(spec, ct_ref))
    results.extend(_check_variable_names_in_ig(spec, domain_spec))
    results.extend(_check_origin_populated(spec))
    results.extend(_check_computational_method(spec))
    return results


def results_to_issue_dicts(results: list[RuleResult]) -> list[dict]:
    """Convert RuleResult objects to plain dicts for DomainMappingSpec storage.

    Maps RuleResult fields to a simplified dict format suitable for
    storing on DomainMappingSpec.predict_prevent_issues without creating
    a circular import from models -> validation.

    Args:
        results: List of RuleResult objects from predict_and_prevent.

    Returns:
        List of dicts with keys: rule_id, severity, domain, variable,
        message, fix_suggestion.
    """
    return [
        {
            "rule_id": r.rule_id,
            "severity": r.severity.value,
            "domain": r.domain,
            "variable": r.variable,
            "message": r.message,
            "fix_suggestion": r.fix_suggestion,
        }
        for r in results
    ]


def _check_required_variables(
    spec: DomainMappingSpec,
    domain_spec: DomainSpec,
) -> list[RuleResult]:
    """ASTR-PP001: All Required variables must have mappings."""
    mapped_names = {m.sdtm_variable.upper() for m in spec.variable_mappings}
    required_vars = [
        v.name for v in domain_spec.variables if v.core == CoreDesignation.REQ
    ]

    results: list[RuleResult] = []
    for var_name in required_vars:
        if var_name not in mapped_names:
            results.append(
                RuleResult(
                    rule_id="ASTR-PP001",
                    rule_description="Required variable must have a mapping",
                    category=RuleCategory.PRESENCE,
                    severity=RuleSeverity.ERROR,
                    domain=spec.domain,
                    variable=var_name,
                    message=(
                        f"Required variable {var_name} has no "
                        f"mapping in {spec.domain} specification"
                    ),
                    fix_suggestion=f"Add a mapping for {var_name} (core=Req in SDTM-IG)",
                )
            )
    return results


def _check_duplicate_mappings(spec: DomainMappingSpec) -> list[RuleResult]:
    """ASTR-PP002: No two mappings should target the same SDTM variable."""
    seen: dict[str, int] = {}
    results: list[RuleResult] = []

    for m in spec.variable_mappings:
        var_upper = m.sdtm_variable.upper()
        if var_upper in seen:
            seen[var_upper] += 1
        else:
            seen[var_upper] = 1

    for var_name, count in seen.items():
        if count > 1:
            results.append(
                RuleResult(
                    rule_id="ASTR-PP002",
                    rule_description="No duplicate variable mappings allowed",
                    category=RuleCategory.CONSISTENCY,
                    severity=RuleSeverity.ERROR,
                    domain=spec.domain,
                    variable=var_name,
                    message=(
                        f"Variable {var_name} has {count} "
                        f"mappings in {spec.domain} (expected 1)"
                    ),
                    fix_suggestion=f"Remove duplicate mapping(s) for {var_name}",
                )
            )
    return results


def _check_codelist_exists(
    spec: DomainMappingSpec,
    ct_ref: CTReference,
) -> list[RuleResult]:
    """ASTR-PP003: Codelist codes referenced in mappings must exist in CT."""
    results: list[RuleResult] = []
    checked: set[str] = set()

    for m in spec.variable_mappings:
        if m.codelist_code and m.codelist_code not in checked:
            checked.add(m.codelist_code)
            cl = ct_ref.lookup_codelist(m.codelist_code)
            if cl is None:
                results.append(
                    RuleResult(
                        rule_id="ASTR-PP003",
                        rule_description="Referenced codelist must exist in CT",
                        category=RuleCategory.TERMINOLOGY,
                        severity=RuleSeverity.WARNING,
                        domain=spec.domain,
                        variable=m.sdtm_variable,
                        message=(
                            f"Codelist {m.codelist_code} referenced by "
                            f"{m.sdtm_variable} not found in CT reference"
                        ),
                        fix_suggestion=(
                            f"Verify codelist code {m.codelist_code} "
                            f"or remove codelist_code from mapping"
                        ),
                    )
                )
    return results


def _check_assign_ct_values(
    spec: DomainMappingSpec,
    ct_ref: CTReference,
) -> list[RuleResult]:
    """ASTR-PP004: ASSIGN values must be valid in non-extensible codelists."""
    results: list[RuleResult] = []

    for m in spec.variable_mappings:
        if (
            m.mapping_pattern == MappingPattern.ASSIGN
            and m.codelist_code
            and m.assigned_value
        ):
            cl = ct_ref.lookup_codelist(m.codelist_code)
            if cl is not None and not cl.extensible and m.assigned_value not in cl.terms:
                results.append(
                    RuleResult(
                        rule_id="ASTR-PP004",
                        rule_description=(
                            "ASSIGN value must be valid in "
                            "non-extensible codelist"
                        ),
                        category=RuleCategory.TERMINOLOGY,
                        severity=RuleSeverity.ERROR,
                        domain=spec.domain,
                        variable=m.sdtm_variable,
                        message=(
                            f"Assigned value '{m.assigned_value}' "
                            f"for {m.sdtm_variable} is not a valid "
                            f"term in non-extensible codelist "
                            f"{m.codelist_code}"
                        ),
                        fix_suggestion=(
                            f"Use a valid term from codelist "
                            f"{m.codelist_code}: "
                            f"{', '.join(list(cl.terms.keys())[:5])}"
                            + ("..." if len(cl.terms) > 5 else "")
                        ),
                    )
                )
    return results


def _check_variable_names_in_ig(
    spec: DomainMappingSpec,
    domain_spec: DomainSpec,
) -> list[RuleResult]:
    """ASTR-PP005: All mapped variable names should exist in SDTM-IG."""
    ig_var_names = {v.name.upper() for v in domain_spec.variables}
    results: list[RuleResult] = []

    for m in spec.variable_mappings:
        if m.sdtm_variable.upper() not in ig_var_names:
            results.append(
                RuleResult(
                    rule_id="ASTR-PP005",
                    rule_description="Mapped variable should exist in SDTM-IG domain spec",
                    category=RuleCategory.PRESENCE,
                    severity=RuleSeverity.WARNING,
                    domain=spec.domain,
                    variable=m.sdtm_variable,
                    message=(
                        f"Variable {m.sdtm_variable} not found in SDTM-IG "
                        f"specification for domain {spec.domain}"
                    ),
                    fix_suggestion="Check if this is a SUPPQUAL candidate or a typo",
                )
            )
    return results


def _check_origin_populated(spec: DomainMappingSpec) -> list[RuleResult]:
    """ASTR-PP006: All mappings should have origin set for define.xml."""
    results: list[RuleResult] = []

    for m in spec.variable_mappings:
        if m.origin is None:
            results.append(
                RuleResult(
                    rule_id="ASTR-PP006",
                    rule_description="Variable origin should be populated for define.xml",
                    category=RuleCategory.FORMAT,
                    severity=RuleSeverity.NOTICE,
                    domain=spec.domain,
                    variable=m.sdtm_variable,
                    message=(
                        f"Variable {m.sdtm_variable} has no origin set "
                        f"(needed for define.xml Origin element)"
                    ),
                    fix_suggestion="Set origin to CRF, Derived, Assigned, Protocol, or eDT",
                )
            )
    return results


def _check_computational_method(spec: DomainMappingSpec) -> list[RuleResult]:
    """ASTR-PP007: Derived variables should have computational_method."""
    results: list[RuleResult] = []

    for m in spec.variable_mappings:
        if m.mapping_pattern == MappingPattern.DERIVATION and not m.computational_method:
            results.append(
                RuleResult(
                    rule_id="ASTR-PP007",
                    rule_description=(
                        "Derived variable should have "
                        "computational method for define.xml"
                    ),
                    category=RuleCategory.FORMAT,
                    severity=RuleSeverity.NOTICE,
                    domain=spec.domain,
                    variable=m.sdtm_variable,
                    message=(
                        f"Derived variable {m.sdtm_variable} has no "
                        f"computational_method (needed for define.xml MethodDef)"
                    ),
                    fix_suggestion="Add computational_method describing the derivation algorithm",
                )
            )
    return results
