"""Date format, ASCII, and naming convention validation rules (VAL-05).

Validates ISO 8601 date format compliance, ASCII-only character data,
and domain file naming conventions.
"""

from __future__ import annotations

import re

import pandas as pd

from astraea.models.mapping import DomainMappingSpec
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.transforms.ascii_validation import validate_ascii
from astraea.validation.rules.base import (
    RuleCategory,
    RuleResult,
    RuleSeverity,
    ValidationRule,
)

# ISO 8601 patterns valid for SDTM --DTC variables:
# YYYY, YYYY-MM, YYYY-MM-DD, YYYY-MM-DDTHH, YYYY-MM-DDTHH:MM,
# YYYY-MM-DDTHH:MM:SS
_ISO_8601_PATTERN = re.compile(r"^\d{4}(-\d{2}(-\d{2}(T\d{2}(:\d{2}(:\d{2})?)?)?)?)?$")

# Valid domain code pattern: 2-8 lowercase alpha characters
_DOMAIN_NAME_PATTERN = re.compile(r"^[a-zA-Z]{2,8}$")


class DateFormatRule(ValidationRule):
    """Validate ISO 8601 date format in --DTC columns.

    All date/time variables in SDTM (ending in DTC) must use
    ISO 8601 format with proper truncation for partial dates.
    """

    rule_id: str = "ASTR-F001"
    description: str = "Date/time variables (--DTC) must use ISO 8601 format"
    category: RuleCategory = RuleCategory.FORMAT
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check --DTC columns for ISO 8601 compliance."""
        results: list[RuleResult] = []

        dtc_cols = [c for c in df.columns if str(c).upper().endswith("DTC")]

        for col in dtc_cols:
            col_str = str(col)
            non_null = df[col].dropna()
            if non_null.empty:
                continue

            str_values = non_null.astype(str)
            invalid_mask = ~str_values.str.match(_ISO_8601_PATTERN)
            invalid_count = int(invalid_mask.sum())

            if invalid_count > 0:
                invalid_examples = str_values[invalid_mask].unique()[:5].tolist()
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=RuleSeverity.ERROR,
                        domain=domain,
                        variable=col_str.upper(),
                        message=(
                            f"{col_str} contains {invalid_count} non-ISO 8601 "
                            f"value(s): {', '.join(repr(v) for v in invalid_examples)}"
                        ),
                        affected_count=invalid_count,
                        fix_suggestion=(
                            "Convert dates to ISO 8601 format: YYYY-MM-DD or "
                            "YYYY-MM-DDTHH:MM:SS. Use truncation for partial dates."
                        ),
                        p21_equivalent="SD0020",
                    )
                )

        return results


class ASCIIRule(ValidationRule):
    """Check all character columns for non-ASCII characters.

    XPT v5 format requires ASCII-only character data. Non-ASCII
    characters must be replaced before writing to XPT.
    """

    rule_id: str = "ASTR-F002"
    description: str = "Character variables must contain ASCII-only data"
    category: RuleCategory = RuleCategory.FORMAT
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check for non-ASCII characters using ascii_validation module."""
        results: list[RuleResult] = []

        issues = validate_ascii(df)
        if not issues:
            return results

        # Group by column for reporting
        cols_affected: dict[str, int] = {}
        for issue in issues:
            col = str(issue["column"])
            cols_affected[col] = cols_affected.get(col, 0) + 1

        for col, count in cols_affected.items():
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=RuleSeverity.ERROR,
                    domain=domain,
                    variable=col,
                    message=(f"Column '{col}' contains {count} non-ASCII value(s)"),
                    affected_count=count,
                    fix_suggestion=("Run fix_common_non_ascii() before XPT write"),
                )
            )

        return results


class FileNamingRule(ValidationRule):
    """Validate that the domain code is valid for XPT file naming.

    SDTM XPT files must be named as lowercase domain code (e.g.,
    ae.xpt, dm.xpt). The domain code itself must be 2-8 alphabetic
    characters.
    """

    rule_id: str = "ASTR-F003"
    description: str = "Domain code must be valid for XPT file naming (2-8 alpha chars)"
    category: RuleCategory = RuleCategory.FORMAT
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Check domain code validity for file naming."""
        results: list[RuleResult] = []

        if not _DOMAIN_NAME_PATTERN.match(domain):
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=RuleSeverity.ERROR,
                    domain=domain,
                    message=(
                        f"Domain code '{domain}' is not valid for XPT file naming. "
                        f"Must be 2-8 alphabetic characters."
                    ),
                    affected_count=0,
                    fix_suggestion=(
                        f"Use a valid domain code (2-8 alpha chars). "
                        f"XPT file would be '{domain.lower()}.xpt'."
                    ),
                )
            )

        return results


def get_format_rules() -> list[ValidationRule]:
    """Return all format validation rule instances."""
    return [
        DateFormatRule(),
        ASCIIRule(),
        FileNamingRule(),
    ]
