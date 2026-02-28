"""Validation report model.

Aggregates validation results into a structured report with severity
counts, domain breakdowns, category breakdowns, pass rates, and
submission readiness assessment.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from astraea.validation.rules.base import RuleCategory, RuleResult, RuleSeverity


class ValidationReport(BaseModel):
    """Aggregated validation report for an SDTM study.

    Summarizes all validation findings with severity counts, pass rates,
    and domain/category breakdowns. The submission_ready flag indicates
    whether the study has zero errors and is ready for submission.
    """

    study_id: str = Field(..., description="Study identifier")
    domains_validated: list[str] = Field(
        default_factory=list, description="List of domain codes validated"
    )
    results: list[RuleResult] = Field(
        default_factory=list, description="All validation findings"
    )
    total_rules_run: int = Field(
        default=0, description="Total number of rule evaluations performed"
    )
    error_count: int = Field(default=0, description="Number of ERROR findings")
    warning_count: int = Field(default=0, description="Number of WARNING findings")
    notice_count: int = Field(default=0, description="Number of NOTICE findings")
    pass_rate: float = Field(
        default=1.0,
        description="Percentage of domains with zero errors (0.0 to 1.0)",
    )
    submission_ready: bool = Field(
        default=True,
        description="True if error_count is zero -- study can be submitted",
    )
    generated_at: str = Field(
        default="", description="ISO 8601 timestamp of report generation"
    )
    summary_by_domain: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Domain -> {errors, warnings, notices} counts",
    )
    summary_by_category: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Category -> {errors, warnings, notices} counts",
    )

    @classmethod
    def from_results(
        cls,
        study_id: str,
        results: list[RuleResult],
        domains: list[str],
    ) -> ValidationReport:
        """Create a ValidationReport by computing summaries from raw results.

        Args:
            study_id: Study identifier.
            results: All RuleResult findings from validation.
            domains: List of domain codes that were validated.

        Returns:
            A fully populated ValidationReport.
        """
        error_count = sum(1 for r in results if r.severity == RuleSeverity.ERROR)
        warning_count = sum(1 for r in results if r.severity == RuleSeverity.WARNING)
        notice_count = sum(1 for r in results if r.severity == RuleSeverity.NOTICE)

        # Domain-level breakdown
        summary_by_domain: dict[str, dict[str, int]] = {}
        for d in domains:
            domain_results = [r for r in results if r.domain == d]
            summary_by_domain[d] = {
                "errors": sum(
                    1 for r in domain_results if r.severity == RuleSeverity.ERROR
                ),
                "warnings": sum(
                    1 for r in domain_results if r.severity == RuleSeverity.WARNING
                ),
                "notices": sum(
                    1 for r in domain_results if r.severity == RuleSeverity.NOTICE
                ),
            }

        # Category-level breakdown
        summary_by_category: dict[str, dict[str, int]] = {}
        for cat in RuleCategory:
            cat_results = [r for r in results if r.category == cat]
            if cat_results:
                summary_by_category[cat.value] = {
                    "errors": sum(
                        1 for r in cat_results if r.severity == RuleSeverity.ERROR
                    ),
                    "warnings": sum(
                        1 for r in cat_results if r.severity == RuleSeverity.WARNING
                    ),
                    "notices": sum(
                        1 for r in cat_results if r.severity == RuleSeverity.NOTICE
                    ),
                }

        # Pass rate: % of domains with zero errors
        if domains:
            domains_with_errors = sum(
                1
                for d in domains
                if summary_by_domain.get(d, {}).get("errors", 0) > 0
            )
            pass_rate = (len(domains) - domains_with_errors) / len(domains)
        else:
            pass_rate = 1.0

        return cls(
            study_id=study_id,
            domains_validated=domains,
            results=results,
            total_rules_run=len(results),
            error_count=error_count,
            warning_count=warning_count,
            notice_count=notice_count,
            pass_rate=pass_rate,
            submission_ready=error_count == 0,
            generated_at=datetime.now(tz=UTC).isoformat(),
            summary_by_domain=summary_by_domain,
            summary_by_category=summary_by_category,
        )
