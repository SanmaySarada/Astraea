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

        required_vars = [v.name for v in domain_spec.variables if v.core == CoreDesignation.REQ]
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
                        message=(f"Required variable {var_name} is missing from {domain} dataset"),
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

        expected_vars = [v.name for v in domain_spec.variables if v.core == CoreDesignation.EXP]
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
                        message=(f"Expected variable {var_name} is missing from {domain} dataset"),
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
                    message=(f"USUBJID contains {null_count} null value(s) in {domain} dataset"),
                    affected_count=null_count,
                    fix_suggestion="Ensure USUBJID derivation populates all rows",
                )
            )

        return results


class SeqUniquenessRule(ValidationRule):
    """Check that --SEQ is unique per USUBJID within a domain.

    Each subject should have unique sequence numbers within a domain.
    Duplicate --SEQ values for the same USUBJID indicate a data
    integrity issue that will cause FDA findings.
    """

    rule_id: str = "ASTR-P005"
    description: str = "--SEQ must be unique per USUBJID within a domain"
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
        """Check --SEQ uniqueness per USUBJID."""
        prefix = domain[:2]
        seq_col = f"{prefix}SEQ"

        if seq_col not in df.columns or "USUBJID" not in df.columns:
            return []

        # Check for duplicate SEQ values within each USUBJID
        dup_subjects: list[str] = []
        for usubjid, group in df.groupby("USUBJID"):
            seq_values = group[seq_col].dropna()
            if seq_values.duplicated().any():
                dup_subjects.append(str(usubjid))

        if dup_subjects:
            return [
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain,
                    variable=seq_col,
                    message=(
                        f"{seq_col} has duplicate values within USUBJID for "
                        f"{len(dup_subjects)} subject(s)"
                    ),
                    affected_count=len(dup_subjects),
                    p21_equivalent="SD0007",
                    fix_suggestion=(
                        f"Ensure {seq_col} values are unique per USUBJID "
                        f"within the {domain} domain"
                    ),
                )
            ]

        return []


class DMOneRecordPerSubjectRule(ValidationRule):
    """Check that DM has exactly one record per subject.

    The Demographics domain must contain exactly one record per USUBJID.
    Duplicate DM records indicate a data processing error and will
    cause FDA rejection.
    """

    rule_id: str = "ASTR-P006"
    description: str = "DM must have exactly one record per subject"
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
        """Check for duplicate USUBJID in DM."""
        if domain != "DM":
            return []

        if "USUBJID" not in df.columns:
            return []

        duplicated_mask = df["USUBJID"].duplicated(keep=False)
        if duplicated_mask.any():
            dup_count = int(df.loc[duplicated_mask, "USUBJID"].nunique())
            return [
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain,
                    variable="USUBJID",
                    message=(
                        f"DM has duplicate records for {dup_count} subject(s). "
                        f"DM must have exactly one record per USUBJID."
                    ),
                    affected_count=dup_count,
                    fix_suggestion="Remove duplicate DM records to ensure one per USUBJID",
                )
            ]

        return []


class DMArmPresenceRule(ValidationRule):
    """Check that DM contains all four ARM variables.

    ARM, ARMCD, ACTARM, and ACTARMCD are Required per SDTM-IG v3.4
    for the DM domain. Missing treatment arm variables are a top FDA
    finding and will cause rejection.
    """

    rule_id: str = "ASTR-P010"
    description: str = "DM must contain ARM, ARMCD, ACTARM, and ACTARMCD"
    category: RuleCategory = RuleCategory.PRESENCE
    severity: RuleSeverity = RuleSeverity.ERROR

    _ARM_VARIABLES: tuple[str, ...] = ("ARM", "ARMCD", "ACTARM", "ACTARMCD")

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check for missing ARM variables in DM."""
        if domain != "DM":
            return []

        df_cols = {str(c).upper() for c in df.columns}
        missing = [v for v in self._ARM_VARIABLES if v not in df_cols]

        if missing:
            return [
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=RuleSeverity.ERROR,
                    domain=domain,
                    message=(
                        f"DM is missing required ARM variable(s): {', '.join(missing)}. "
                        f"These are Required per SDTM-IG v3.4 and a top FDA finding."
                    ),
                    affected_count=len(df),
                    fix_suggestion=(
                        "Add ARM, ARMCD, ACTARM, ACTARMCD to DM mapping specification. "
                        "These are Required per SDTM-IG v3.4."
                    ),
                )
            ]
        return []


class DMArmCopyPasteRule(ValidationRule):
    """Check that ACTARM/ACTARMCD are not blindly copied from ARM/ARMCD.

    ACTARM should reflect actual treatment received, which may differ
    from the planned arm. If ACTARM == ARM for every row, the values
    may have been copied rather than independently derived. This is a
    WARNING because values can legitimately be equal when all patients
    received their planned treatment.
    """

    rule_id: str = "ASTR-P011"
    description: str = "ACTARM/ACTARMCD should be independently derived, not copied from ARM/ARMCD"
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
        """Check for ACTARM == ARM copy-paste pattern."""
        if domain != "DM":
            return []

        results: list[RuleResult] = []
        df_cols = {str(c).upper() for c in df.columns}

        # Only check if all four columns exist
        if not {"ARM", "ARMCD", "ACTARM", "ACTARMCD"}.issubset(df_cols):
            return []

        if len(df) == 0:
            return []

        # Check ACTARM == ARM for all rows
        if (df["ACTARM"] == df["ARM"]).all():
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=RuleSeverity.WARNING,
                    domain=domain,
                    variable="ACTARM",
                    message=(
                        "ACTARM equals ARM for all rows. Verify that ACTARM was "
                        "independently derived from source data reflecting actual "
                        "treatment received, not copied from planned arm."
                    ),
                    affected_count=len(df),
                    fix_suggestion=(
                        "Review source data for actual treatment assignment. "
                        "If values are legitimately equal, document in cSDRG."
                    ),
                )
            )

        # Check ACTARMCD == ARMCD for all rows
        if (df["ACTARMCD"] == df["ARMCD"]).all():
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=RuleSeverity.WARNING,
                    domain=domain,
                    variable="ACTARMCD",
                    message=(
                        "ACTARMCD equals ARMCD for all rows. Verify that ACTARMCD was "
                        "independently derived from source data reflecting actual "
                        "treatment received, not copied from planned arm code."
                    ),
                    affected_count=len(df),
                    fix_suggestion=(
                        "Review source data for actual treatment assignment. "
                        "If values are legitimately equal, document in cSDRG."
                    ),
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
        SeqUniquenessRule(),
        DMOneRecordPerSubjectRule(),
        DMArmPresenceRule(),
        DMArmCopyPasteRule(),
    ]
