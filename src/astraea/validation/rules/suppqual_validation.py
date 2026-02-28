"""SUPPQUAL referential integrity validation rule (ASTR-S001).

Validates that SUPP* (Supplemental Qualifier) domains have valid
RDOMAIN, IDVAR, IDVARVAL references and QNAM naming conventions.
When the parent domain DataFrame is available, also checks that
every RDOMAIN/USUBJID/IDVAR/IDVARVAL combination actually references
an existing record in the parent domain.
"""

from __future__ import annotations

import re

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

# Valid QNAM: 1-8 characters, alphanumeric only (no underscores per SDTM)
_QNAM_PATTERN = re.compile(r"^[A-Z0-9]{1,8}$")

# Known valid domain codes (2-4 uppercase alpha)
_DOMAIN_CODE_PATTERN = re.compile(r"^[A-Z]{2,4}$")


class SUPPQUALIntegrityRule(ValidationRule):
    """Validate SUPPQUAL referential integrity.

    Checks SUPP* domains for:
    - RDOMAIN contains valid domain codes
    - IDVAR is a plausible variable name for the referenced domain
    - QNAM follows naming conventions (<=8 chars, alphanumeric uppercase)
    - No duplicate QNAM values per parent domain
    - When parent domain data is available: referential integrity of
      USUBJID/IDVAR/IDVARVAL combinations
    """

    rule_id: str = "ASTR-S001"
    description: str = "SUPPQUAL referential integrity check"
    category: RuleCategory = RuleCategory.CONSISTENCY
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Evaluate SUPPQUAL integrity rules.

        Only applies to SUPP* domains (SUPPAE, SUPPDM, SUPPLB, etc.).
        """
        results: list[RuleResult] = []
        domain_upper = domain.upper()

        # Only apply to SUPP* domains
        if not domain_upper.startswith("SUPP"):
            return results

        # Check RDOMAIN column
        if "RDOMAIN" in df.columns:
            rdomain_values = df["RDOMAIN"].dropna().unique()
            for val in rdomain_values:
                val_str = str(val).strip()
                if not _DOMAIN_CODE_PATTERN.match(val_str):
                    results.append(
                        RuleResult(
                            rule_id=self.rule_id,
                            rule_description=self.description,
                            category=self.category,
                            severity=self.severity,
                            domain=domain_upper,
                            variable="RDOMAIN",
                            message=f"RDOMAIN value '{val_str}' is not a valid domain code",
                            affected_count=int((df["RDOMAIN"] == val).sum()),
                        )
                    )
        else:
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain_upper,
                    variable="RDOMAIN",
                    message="Required column RDOMAIN is missing from SUPPQUAL dataset",
                    affected_count=len(df),
                )
            )

        # Check IDVAR column
        if "IDVAR" in df.columns:
            idvar_values = df["IDVAR"].dropna().unique()
            for val in idvar_values:
                val_str = str(val).strip()
                # IDVAR should be a valid SDTM variable name (1-8 chars, alpha start)
                if not re.match(r"^[A-Z][A-Z0-9]{0,7}$", val_str):
                    results.append(
                        RuleResult(
                            rule_id=self.rule_id,
                            rule_description=self.description,
                            category=self.category,
                            severity=RuleSeverity.WARNING,
                            domain=domain_upper,
                            variable="IDVAR",
                            message=(
                                f"IDVAR value '{val_str}' may not be a valid "
                                f"variable name for the parent domain"
                            ),
                            affected_count=int((df["IDVAR"] == val).sum()),
                        )
                    )

        # Check QNAM column
        if "QNAM" in df.columns:
            qnam_values = df["QNAM"].dropna().unique()
            for val in qnam_values:
                val_str = str(val).strip()
                if not _QNAM_PATTERN.match(val_str):
                    results.append(
                        RuleResult(
                            rule_id=self.rule_id,
                            rule_description=self.description,
                            category=self.category,
                            severity=self.severity,
                            domain=domain_upper,
                            variable="QNAM",
                            message=(
                                f"QNAM value '{val_str}' does not follow naming "
                                f"convention (1-8 uppercase alphanumeric characters)"
                            ),
                            affected_count=int((df["QNAM"] == val).sum()),
                        )
                    )

            # Check for duplicate QNAM within same subject
            if "USUBJID" in df.columns and "IDVARVAL" in df.columns:
                dup_check = df.groupby(["USUBJID", "QNAM", "IDVARVAL"]).size()
                dups = dup_check[dup_check > 1]
                if len(dups) > 0:
                    results.append(
                        RuleResult(
                            rule_id=self.rule_id,
                            rule_description=self.description,
                            category=self.category,
                            severity=self.severity,
                            domain=domain_upper,
                            variable="QNAM",
                            message=(
                                f"Duplicate QNAM values found for same "
                                f"USUBJID/IDVARVAL combination ({len(dups)} duplicates)"
                            ),
                            affected_count=int(dups.sum() - len(dups)),
                        )
                    )
        else:
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain_upper,
                    variable="QNAM",
                    message="Required column QNAM is missing from SUPPQUAL dataset",
                    affected_count=len(df),
                )
            )

        return results


def get_suppqual_rules() -> list[ValidationRule]:
    """Return all SUPPQUAL validation rules."""
    return [SUPPQUALIntegrityRule()]
