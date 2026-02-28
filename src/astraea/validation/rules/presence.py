"""Required variable and record presence validation rules (VAL-02).

Validates that generated SDTM datasets contain all required and
expected variables per the SDTM-IG domain specification, and that
critical identifiers like USUBJID are complete.
"""

from __future__ import annotations

import pandas as pd

from astraea.models.mapping import DomainMappingSpec
from astraea.models.sdtm import CoreDesignation
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.validation.rules.base import (
    RuleCategory,
    RuleResult,
    RuleSeverity,
    ValidationRule,
)


class RequiredVariableRule(ValidationRule):
    """Check that all Required (core==REQ) variables exist as columns.

    SDTM-IG designates certain variables as Required -- they must
    be present in every submitted dataset for the domain.
    """

    rule_id: str = "ASTR-P001"
    description: str = "Required SDTM-IG variables must be present in the dataset"
    category: RuleCategory = RuleCategory.PRESENCE
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check for missing Required variables."""
        results: list[RuleResult] = []

        domain_spec = sdtm_ref.get_domain_spec(domain)
        if domain_spec is None:
            return results

        required_vars = [
            v.name for v in domain_spec.variables if v.core == CoreDesignation.REQ
        ]
        df_cols = {str(c).upper() for c in df.columns}

        for var_name in required_vars:
            if var_name.upper() not in df_cols:
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=RuleSeverity.ERROR,
                        domain=domain,
                        variable=var_name,
                        message=(
                            f"Required variable {var_name} is missing "
                            f"from {domain} dataset"
                        ),
                        affected_count=len(df),
                        fix_suggestion=f"Add {var_name} column to the {domain} dataset",
                        p21_equivalent="SD0083",
                    )
                )

        return results


class ExpectedVariableRule(ValidationRule):
    """Check that Expected (core==EXP) variables exist as columns.

    Expected variables should be present in most datasets. Their
    absence is a warning, not an error.
    """

    rule_id: str = "ASTR-P002"
    description: str = "Expected SDTM-IG variables should be present in the dataset"
    category: RuleCategory = RuleCategory.PRESENCE
    severity: RuleSeverity = RuleSeverity.WARNING

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check for missing Expected variables."""
        results: list[RuleResult] = []

        domain_spec = sdtm_ref.get_domain_spec(domain)
        if domain_spec is None:
            return results

        expected_vars = [
            v.name for v in domain_spec.variables if v.core == CoreDesignation.EXP
        ]
        df_cols = {str(c).upper() for c in df.columns}

        for var_name in expected_vars:
            if var_name.upper() not in df_cols:
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=RuleSeverity.WARNING,
                        domain=domain,
                        variable=var_name,
                        message=(
                            f"Expected variable {var_name} is missing "
                            f"from {domain} dataset"
                        ),
                        affected_count=0,
                        fix_suggestion=(
                            f"Consider adding {var_name} to the {domain} dataset "
                            f"or document absence in cSDRG"
                        ),
                    )
                )

        return results


class NoRecordsRule(ValidationRule):
    """Check that the dataset contains at least one record.

    An empty domain file is suspicious and may indicate a
    processing error or missing source data.
    """

    rule_id: str = "ASTR-P003"
    description: str = "Domain dataset should contain at least one record"
    category: RuleCategory = RuleCategory.PRESENCE
    severity: RuleSeverity = RuleSeverity.WARNING

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check for empty dataset."""
        if len(df) == 0:
            return [
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=RuleSeverity.WARNING,
                    domain=domain,
                    message=f"{domain} dataset contains zero records",
                    affected_count=0,
                    fix_suggestion=(
                        "Verify source data and mapping specification. "
                        "Empty domains should be omitted from submission."
                    ),
                )
            ]
        return []


class USUBJIDPresentRule(ValidationRule):
    """Check that USUBJID column exists and has no null values.

    USUBJID is the universal subject identifier required in every
    subject-level SDTM domain. Missing or null USUBJIDs prevent
    cross-domain linkage and will cause FDA rejection.
    """

    rule_id: str = "ASTR-P004"
    description: str = "USUBJID must be present and complete (no nulls)"
    category: RuleCategory = RuleCategory.PRESENCE
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check USUBJID presence and completeness."""
        results: list[RuleResult] = []

        if "USUBJID" not in df.columns:
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=RuleSeverity.ERROR,
                    domain=domain,
                    variable="USUBJID",
                    message=f"USUBJID column is missing from {domain} dataset",
                    affected_count=len(df),
                    fix_suggestion="Add USUBJID column derived from STUDYID + SITEID + SUBJID",
                )
            )
            return results

        null_count = int(df["USUBJID"].isna().sum())
        if null_count > 0:
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=RuleSeverity.ERROR,
                    domain=domain,
                    variable="USUBJID",
                    message=(
                        f"USUBJID contains {null_count} null value(s) "
                        f"in {domain} dataset"
                    ),
                    affected_count=null_count,
                    fix_suggestion="Ensure USUBJID derivation populates all rows",
                )
            )

        return results


def get_presence_rules() -> list[ValidationRule]:
    """Return all presence validation rule instances."""
    return [
        RequiredVariableRule(),
        ExpectedVariableRule(),
        NoRecordsRule(),
        USUBJIDPresentRule(),
    ]
