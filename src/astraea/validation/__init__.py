"""Deterministic P21-style validation rules.

Provides a rule-based validation engine for checking SDTM conformance.
Rules are organized by category (terminology, presence, consistency,
limits, format) and produce structured results with severity levels.
"""

from astraea.validation.engine import ValidationEngine
from astraea.validation.rules.base import (
    RuleCategory,
    RuleResult,
    RuleSeverity,
    ValidationRule,
)

__all__ = [
    "RuleCategory",
    "RuleResult",
    "RuleSeverity",
    "ValidationEngine",
    "ValidationRule",
]
