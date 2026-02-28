"""Base models for SDTM validation rules.

Defines the core abstractions: RuleSeverity, RuleCategory, RuleResult,
and ValidationRule. All concrete validation rules subclass ValidationRule
and implement the evaluate() method.
"""

from __future__ import annotations

from abc import abstractmethod
from enum import StrEnum

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from astraea.models.mapping import DomainMappingSpec
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference


class RuleSeverity(StrEnum):
    """Severity classification for validation findings.

    ERROR: Must fix before submission -- will cause FDA rejection.
    WARNING: Should fix, or explain in cSDRG if not fixed.
    NOTICE: Informational best-practice recommendation.
    INFORMATIONAL: Non-actionable metadata for documentation purposes.
    """

    ERROR = "ERROR"
    WARNING = "WARNING"
    NOTICE = "NOTICE"
    INFORMATIONAL = "INFORMATIONAL"

    @property
    def display_name(self) -> str:
        """Human-friendly display name."""
        return self.value.capitalize()


class RuleCategory(StrEnum):
    """Validation rule category matching the VAL-XX classification.

    TERMINOLOGY: VAL-01 -- CT codelist validation.
    PRESENCE: VAL-02 -- Required variable/record checks.
    CONSISTENCY: VAL-03 -- Cross-domain consistency.
    LIMIT: VAL-04 -- Variable length limits.
    FORMAT: VAL-05 -- Date format, naming conventions.
    FDA_BUSINESS: FDA Business Rules (FDAB*).
    FDA_TRC: FDA Technical Rejection Criteria.
    """

    TERMINOLOGY = "TERMINOLOGY"
    PRESENCE = "PRESENCE"
    CONSISTENCY = "CONSISTENCY"
    LIMIT = "LIMIT"
    FORMAT = "FORMAT"
    FDA_BUSINESS = "FDA_BUSINESS"
    FDA_TRC = "FDA_TRC"


class RuleResult(BaseModel):
    """Structured result from evaluating a single validation rule.

    Each RuleResult represents one finding -- a specific issue found
    (or the absence of issues) when a rule is evaluated against a domain.
    """

    rule_id: str = Field(..., description="Unique rule identifier (e.g., 'VAL-01-001')")
    rule_description: str = Field(..., description="Human-readable rule description")
    category: RuleCategory = Field(..., description="Rule category")
    severity: RuleSeverity = Field(..., description="Finding severity")
    domain: str | None = Field(default=None, description="Domain code if domain-specific")
    variable: str | None = Field(default=None, description="Variable name if variable-specific")
    message: str = Field(..., description="Detailed finding message")
    affected_count: int = Field(default=0, description="Number of affected records/rows")
    fix_suggestion: str | None = Field(default=None, description="Suggested remediation action")
    p21_equivalent: str | None = Field(
        default=None,
        description="Equivalent Pinnacle 21 rule ID if applicable",
    )
    known_false_positive: bool = Field(
        default=False,
        description="True if this result matches a known false-positive whitelist entry",
    )
    known_false_positive_reason: str | None = Field(
        default=None,
        description="Reason from the whitelist explaining why this is a known false positive",
    )


class ValidationRule(BaseModel):
    """Abstract base class for all SDTM validation rules.

    Subclasses must implement evaluate() which checks a domain's DataFrame
    and mapping specification against SDTM-IG and CT requirements.

    Uses model_config to allow arbitrary types (pd.DataFrame) in evaluate().
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    rule_id: str = Field(..., description="Unique rule identifier")
    description: str = Field(..., description="Human-readable rule description")
    category: RuleCategory = Field(..., description="Rule category")
    severity: RuleSeverity = Field(..., description="Default severity for findings")

    @abstractmethod
    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        """Evaluate this rule against a domain dataset.

        Args:
            domain: SDTM domain code (e.g., 'AE', 'DM').
            df: The generated SDTM DataFrame for the domain.
            spec: The mapping specification used to generate the dataset.
            sdtm_ref: SDTM-IG reference data for domain/variable lookups.
            ct_ref: Controlled Terminology reference for codelist lookups.

        Returns:
            List of RuleResult findings. Empty list means rule passed.
        """
        ...
