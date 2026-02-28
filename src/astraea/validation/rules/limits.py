"""Variable length limit validation rules (VAL-04).

Validates that variable names, labels, and character data conform to
XPT v5 format constraints. These limits are hard requirements --
exceeding them causes silent truncation by pyreadstat.
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


class VariableNameLengthRule(ValidationRule):
    """Check that all column names are <= 8 characters.

    XPT v5 format limits variable names to 8 characters. Names
    exceeding this will be silently truncated by pyreadstat.
    """

    rule_id: str = "ASTR-L001"
    description: str = "Variable names must not exceed 8 characters (XPT v5 limit)"
    category: RuleCategory = RuleCategory.LIMIT
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check column name lengths."""
        results: list[RuleResult] = []

        for col in df.columns:
            col_str = str(col)
            if len(col_str) > 8:
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=RuleSeverity.ERROR,
                        domain=domain,
                        variable=col_str,
                        message=(
                            f"Variable name '{col_str}' exceeds 8 characters ({len(col_str)} chars)"
                        ),
                        affected_count=len(df),
                        fix_suggestion=f"Rename '{col_str}' to 8 characters or fewer",
                        p21_equivalent="SD0006",
                    )
                )

        return results


class VariableLabelLengthRule(ValidationRule):
    """Check that all variable labels are <= 40 characters.

    XPT v5 format limits variable labels to 40 characters. Labels
    exceeding this will be silently truncated by pyreadstat.
    """

    rule_id: str = "ASTR-L002"
    description: str = "Variable labels must not exceed 40 characters (XPT v5 limit)"
    category: RuleCategory = RuleCategory.LIMIT
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check variable label lengths from the mapping spec."""
        results: list[RuleResult] = []

        for vm in spec.variable_mappings:
            label = vm.sdtm_label
            if len(label) > 40:
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=RuleSeverity.ERROR,
                        domain=domain,
                        variable=vm.sdtm_variable,
                        message=(
                            f"Label for {vm.sdtm_variable} exceeds 40 characters "
                            f"({len(label)} chars): '{label[:50]}...'"
                        ),
                        affected_count=0,
                        fix_suggestion=(f"Truncate label for {vm.sdtm_variable} to 40 characters"),
                    )
                )

        return results


class CharacterLengthRule(ValidationRule):
    """Check that character column values do not exceed 200 bytes.

    XPT v5 format limits character variable values to 200 bytes.
    Values exceeding this will be truncated or cause write failure.
    """

    rule_id: str = "ASTR-L003"
    description: str = "Character variable values must not exceed 200 bytes (XPT v5 limit)"
    category: RuleCategory = RuleCategory.LIMIT
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check character column value lengths."""
        results: list[RuleResult] = []

        for col in df.columns:
            if not pd.api.types.is_string_dtype(df[col]):
                continue

            non_null = df[col].dropna()
            if non_null.empty:
                continue

            byte_lengths = non_null.astype(str).apply(lambda x: len(x.encode("utf-8")))
            max_bytes = int(byte_lengths.max())
            if max_bytes > 200:
                over_count = int((byte_lengths > 200).sum())
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=RuleSeverity.ERROR,
                        domain=domain,
                        variable=str(col),
                        message=(
                            f"Column '{col}' has values exceeding 200 bytes "
                            f"(max: {max_bytes} bytes)"
                        ),
                        affected_count=over_count,
                        fix_suggestion=(
                            f"Truncate values in '{col}' to 200 bytes or move to SUPPQUAL"
                        ),
                    )
                )

        return results


class DatasetSizeRule(ValidationRule):
    """Estimate dataset size and warn if unusually large.

    Individual domain datasets over 100MB are suspicious; over 500MB
    may indicate a problem. The total submission limit is 5GB.
    """

    rule_id: str = "ASTR-L004"
    description: str = "Dataset size should be reasonable for a single SDTM domain"
    category: RuleCategory = RuleCategory.LIMIT
    severity: RuleSeverity = RuleSeverity.NOTICE

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Estimate dataset size and flag large datasets."""
        results: list[RuleResult] = []

        # Estimate size: memory_usage gives a reasonable proxy
        estimated_bytes = int(df.memory_usage(deep=True).sum())
        estimated_mb = estimated_bytes / (1024 * 1024)

        if estimated_mb > 500:
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=RuleSeverity.WARNING,
                    domain=domain,
                    message=(
                        f"{domain} dataset estimated at {estimated_mb:.1f} MB "
                        f"(>500 MB threshold). Check for data duplication."
                    ),
                    affected_count=len(df),
                    fix_suggestion=(
                        "Review dataset for duplicate records or unnecessary variables. "
                        "Total submission must be under 5 GB."
                    ),
                )
            )
        elif estimated_mb > 100:
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=RuleSeverity.NOTICE,
                    domain=domain,
                    message=(
                        f"{domain} dataset estimated at {estimated_mb:.1f} MB "
                        f"(>100 MB). Verify this is expected."
                    ),
                    affected_count=len(df),
                )
            )

        return results


def get_limit_rules() -> list[ValidationRule]:
    """Return all limit validation rule instances."""
    return [
        VariableNameLengthRule(),
        VariableLabelLengthRule(),
        CharacterLengthRule(),
        DatasetSizeRule(),
    ]
