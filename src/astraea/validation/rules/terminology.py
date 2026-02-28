"""Controlled Terminology validation rules (VAL-01).

Validates that CT values in generated SDTM DataFrames conform to
CDISC controlled terminology codelists, distinguishing between
extensible and non-extensible codelist types.
"""

from __future__ import annotations

import pandas as pd

from astraea.models.mapping import DomainMappingSpec
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.validation.rules.base import (
    RuleCategory,
    RuleResult,
    RuleSeverity,
    ValidationRule,
)


class CTValueRule(ValidationRule):
    """Validate CT codelist values in generated datasets.

    For each variable mapping with a codelist_code, checks all unique
    non-null values against the codelist terms. Uses ERROR severity
    for non-extensible codelists (exact match required) and WARNING
    for extensible codelists (unexpected values flagged).
    """

    rule_id: str = "ASTR-T001"
    description: str = "Controlled terminology values must match codelist terms"
    category: RuleCategory = RuleCategory.TERMINOLOGY
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check CT values for each mapped variable with a codelist."""
        results: list[RuleResult] = []

        for vm in spec.variable_mappings:
            if not vm.codelist_code:
                continue

            var_name = vm.sdtm_variable.upper()
            if var_name not in df.columns:
                continue

            cl = ct_ref.lookup_codelist(vm.codelist_code)
            if cl is None:
                # Codelist not found -- can't validate
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=RuleSeverity.WARNING,
                        domain=domain,
                        variable=var_name,
                        message=(
                            f"Codelist {vm.codelist_code} not found in CT reference; "
                            f"cannot validate values for {var_name}"
                        ),
                        affected_count=0,
                        fix_suggestion=(f"Add codelist {vm.codelist_code} to bundled CT data"),
                    )
                )
                continue

            # Get unique non-null values
            non_null = df[var_name].dropna()
            if non_null.empty:
                continue

            unique_values = non_null.astype(str).unique()
            invalid_values = [v for v in unique_values if v not in cl.terms]

            if not invalid_values:
                continue

            # Count affected rows
            affected = int(non_null.astype(str).isin(invalid_values).sum())

            # Determine severity based on extensibility
            if cl.extensible:
                severity = RuleSeverity.WARNING
                msg_prefix = "Non-standard"
            else:
                severity = RuleSeverity.ERROR
                msg_prefix = "Invalid"

            # Build fix suggestion for non-extensible codelists
            fix_suggestion: str | None = None
            if not cl.extensible:
                valid_terms = sorted(cl.terms.keys())[:5]
                fix_suggestion = (
                    f"Valid values for {cl.name} ({vm.codelist_code}): "
                    f"{', '.join(valid_terms)}"
                    + (f" ... ({len(cl.terms)} total)" if len(cl.terms) > 5 else "")
                )

            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=severity,
                    domain=domain,
                    variable=var_name,
                    message=(
                        f"{msg_prefix} CT value(s) in {var_name}: "
                        f"{', '.join(repr(v) for v in invalid_values[:5])}"
                        + (f" ... ({len(invalid_values)} total)" if len(invalid_values) > 5 else "")
                    ),
                    affected_count=affected,
                    fix_suggestion=fix_suggestion,
                    p21_equivalent="SD0065",
                )
            )

        return results


class DomainValueRule(ValidationRule):
    """Validate that DOMAIN column value matches the domain code.

    Every SDTM dataset must have a DOMAIN column containing the
    two-letter domain abbreviation matching the dataset name.
    """

    rule_id: str = "ASTR-T002"
    description: str = "DOMAIN column value must match the dataset domain code"
    category: RuleCategory = RuleCategory.TERMINOLOGY
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check that DOMAIN column equals the expected domain code."""
        results: list[RuleResult] = []

        if "DOMAIN" not in df.columns:
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=RuleSeverity.ERROR,
                    domain=domain,
                    variable="DOMAIN",
                    message="DOMAIN column is missing from the dataset",
                    affected_count=len(df),
                    fix_suggestion=f"Add DOMAIN column with value '{domain}'",
                )
            )
            return results

        non_null = df["DOMAIN"].dropna()
        wrong_values = non_null[non_null.astype(str) != domain]
        if not wrong_values.empty:
            unique_wrong = wrong_values.astype(str).unique().tolist()
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=RuleSeverity.ERROR,
                    domain=domain,
                    variable="DOMAIN",
                    message=(
                        f"DOMAIN column contains incorrect value(s): "
                        f"{', '.join(repr(v) for v in unique_wrong[:5])}; "
                        f"expected '{domain}'"
                    ),
                    affected_count=len(wrong_values),
                    fix_suggestion=f"Set all DOMAIN values to '{domain}'",
                )
            )

        return results


def get_terminology_rules() -> list[ValidationRule]:
    """Return all terminology validation rule instances."""
    return [
        CTValueRule(),
        DomainValueRule(),
    ]
