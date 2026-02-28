"""Variable ordering validation rule (ASTR-O001, P21 SD0066 equivalent).

Checks that variables in the generated DataFrame appear in the order
specified by the SDTM-IG domain specification. While variable ordering
does not affect data integrity, P21 flags out-of-order variables and
FDA reviewers expect standard ordering.
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


class VariableOrderingRule(ValidationRule):
    """Validate that DataFrame columns follow SDTM-IG variable order.

    Compares the order of SDTM variables in the DataFrame against the
    expected order from the SDTM-IG domain specification. Only checks
    variables that are present in both the DataFrame and the spec --
    extra columns (e.g., intermediate columns) are ignored.
    """

    rule_id: str = "ASTR-O001"
    description: str = "Variable order should match SDTM-IG specification"
    category: RuleCategory = RuleCategory.FORMAT
    severity: RuleSeverity = RuleSeverity.WARNING

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check variable ordering against SDTM-IG spec."""
        results: list[RuleResult] = []
        domain_upper = domain.upper()

        # Skip SUPP* domains -- they have a fixed structure not in domains.json
        if domain_upper.startswith("SUPP"):
            return results

        domain_spec = sdtm_ref.get_domain_spec(domain_upper)
        if domain_spec is None:
            return results

        # Build expected order from SDTM-IG variable list
        expected_order = [v.name for v in domain_spec.variables]

        # Get actual columns in the DataFrame (uppercase for comparison)
        actual_cols = [str(c).upper() for c in df.columns]

        # Filter to only variables that are in both expected and actual
        expected_present = [v for v in expected_order if v in actual_cols]
        actual_sdtm = [c for c in actual_cols if c in expected_order]

        if not expected_present or not actual_sdtm:
            return results

        # Compare ordering: extract the relative order of shared variables
        if actual_sdtm != expected_present:
            # Find the first out-of-order variable
            misorder_vars: list[str] = []
            for i, (actual, expected) in enumerate(
                zip(actual_sdtm, expected_present, strict=False)
            ):
                if actual != expected:
                    misorder_vars.append(f"{actual} (found at position {i + 1}, "
                                        f"expected {expected})")
                    if len(misorder_vars) >= 5:
                        break

            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain_upper,
                    variable=None,
                    message=(
                        f"Variable ordering does not match SDTM-IG specification. "
                        f"First mismatches: {'; '.join(misorder_vars)}"
                    ),
                    affected_count=len(misorder_vars),
                    p21_equivalent="SD0066",
                    fix_suggestion="Reorder DataFrame columns to match SDTM-IG variable order",
                )
            )

        return results


def get_ordering_rules() -> list[ValidationRule]:
    """Return all variable ordering validation rules."""
    return [VariableOrderingRule()]
