"""Validation engine orchestrator.

Discovers, registers, and runs validation rules against SDTM datasets.
The engine maintains a registry of ValidationRule instances and provides
methods to validate individual domains or entire studies.
"""

from __future__ import annotations

import pandas as pd
from loguru import logger

from astraea.models.mapping import DomainMappingSpec
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.validation.rules.base import (
    RuleCategory,
    RuleResult,
    RuleSeverity,
    ValidationRule,
)


class ValidationEngine:
    """Orchestrates validation rule execution across SDTM domains.

    The engine holds references to SDTM-IG and CT data, maintains a
    registry of validation rules, and runs them against domain datasets.
    """

    def __init__(
        self,
        *,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> None:
        """Initialize the validation engine.

        Args:
            sdtm_ref: SDTM-IG reference for domain/variable lookups.
            ct_ref: Controlled Terminology reference for codelist lookups.
        """
        self._sdtm_ref = sdtm_ref
        self._ct_ref = ct_ref
        self._rules: list[ValidationRule] = []
        self.register_defaults()

    @property
    def rules(self) -> list[ValidationRule]:
        """Return the list of registered validation rules."""
        return list(self._rules)

    def register(self, rule: ValidationRule) -> None:
        """Register a validation rule with the engine.

        Args:
            rule: A ValidationRule instance to add to the registry.
        """
        self._rules.append(rule)
        logger.debug("Registered validation rule: {}", rule.rule_id)

    def register_defaults(self) -> None:
        """Import and register all built-in validation rules.

        Uses try/except so the engine works even when rule modules
        are empty or not yet implemented. Rules are added by subsequent
        plans (07-02, 07-03, etc.).
        """
        # VAL-01: Terminology rules
        try:
            from astraea.validation.rules.terminology import get_terminology_rules

            for rule in get_terminology_rules():
                self.register(rule)
        except (ImportError, AttributeError):
            logger.debug("No terminology rules available yet")

        # VAL-02: Presence rules
        try:
            from astraea.validation.rules.presence import get_presence_rules

            for rule in get_presence_rules():
                self.register(rule)
        except (ImportError, AttributeError):
            logger.debug("No presence rules available yet")

        # VAL-03: Consistency rules
        try:
            from astraea.validation.rules.consistency import get_consistency_rules

            for rule in get_consistency_rules():
                self.register(rule)
        except (ImportError, AttributeError):
            logger.debug("No consistency rules available yet")

        # VAL-04: Limit rules
        try:
            from astraea.validation.rules.limits import get_limit_rules

            for rule in get_limit_rules():
                self.register(rule)
        except (ImportError, AttributeError):
            logger.debug("No limit rules available yet")

        # VAL-05: Format rules
        try:
            from astraea.validation.rules.format import get_format_rules

            for rule in get_format_rules():
                self.register(rule)
        except (ImportError, AttributeError):
            logger.debug("No format rules available yet")

        # FDA Business Rules
        try:
            from astraea.validation.rules.fda_business import get_fda_business_rules

            for rule in get_fda_business_rules():
                self.register(rule)
        except (ImportError, AttributeError):
            logger.debug("No FDA business rules available yet")

        # FDA TRC Rules
        try:
            from astraea.validation.rules.fda_trc import get_fda_trc_rules

            for rule in get_fda_trc_rules():
                self.register(rule)
        except (ImportError, AttributeError):
            logger.debug("No FDA TRC rules available yet")

    def validate_domain(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
    ) -> list[RuleResult]:
        """Run all registered rules against one domain.

        Args:
            domain: SDTM domain code (e.g., 'AE').
            df: The generated SDTM DataFrame for the domain.
            spec: The mapping specification for the domain.

        Returns:
            List of all RuleResult findings from all rules.
        """
        results: list[RuleResult] = []
        for rule in self._rules:
            try:
                rule_results = rule.evaluate(
                    domain=domain,
                    df=df,
                    spec=spec,
                    sdtm_ref=self._sdtm_ref,
                    ct_ref=self._ct_ref,
                )
                results.extend(rule_results)
            except Exception as exc:
                logger.error(
                    "Rule {} failed on domain {}: {}", rule.rule_id, domain, exc
                )
                results.append(
                    RuleResult(
                        rule_id=rule.rule_id,
                        rule_description=rule.description,
                        category=rule.category,
                        severity=RuleSeverity.WARNING,
                        domain=domain,
                        message=f"Rule execution failed: {exc}",
                    )
                )
        return results

    def validate_all(
        self,
        domains: dict[str, tuple[pd.DataFrame, DomainMappingSpec]],
    ) -> list[RuleResult]:
        """Run all registered rules across multiple domains.

        Args:
            domains: Mapping of domain code to (DataFrame, DomainMappingSpec) tuples.

        Returns:
            Combined list of all RuleResult findings across all domains.
        """
        all_results: list[RuleResult] = []
        for domain_code, (df, spec) in domains.items():
            logger.info(
                "Validating domain {} ({} rows, {} rules)",
                domain_code,
                len(df),
                len(self._rules),
            )
            domain_results = self.validate_domain(domain_code, df, spec)
            all_results.extend(domain_results)
        return all_results

    @staticmethod
    def filter_results(
        results: list[RuleResult],
        *,
        category: RuleCategory | None = None,
        severity: RuleSeverity | None = None,
        domain: str | None = None,
    ) -> list[RuleResult]:
        """Filter validation results by category, severity, and/or domain.

        Args:
            results: List of RuleResult to filter.
            category: Filter to this category only.
            severity: Filter to this severity only.
            domain: Filter to this domain only.

        Returns:
            Filtered list of RuleResult.
        """
        filtered = results
        if category is not None:
            filtered = [r for r in filtered if r.category == category]
        if severity is not None:
            filtered = [r for r in filtered if r.severity == severity]
        if domain is not None:
            filtered = [r for r in filtered if r.domain == domain]
        return filtered
