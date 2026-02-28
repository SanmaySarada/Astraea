"""Validation report model.

Aggregates validation results into a structured report with severity
counts, domain breakdowns, category breakdowns, pass rates, and
submission readiness assessment. Supports known false-positive flagging
via JSON whitelist and Markdown export for pre-submission reporting.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from astraea.validation.rules.base import RuleCategory, RuleResult, RuleSeverity

_DEFAULT_WHITELIST_PATH = Path(__file__).parent / "known_false_positives.json"


class ValidationReport(BaseModel):
    """Aggregated validation report for an SDTM study.

    Summarizes all validation findings with severity counts, pass rates,
    and domain/category breakdowns. The submission_ready flag indicates
    whether the study has zero effective errors and is ready for submission.
    """

    study_id: str = Field(..., description="Study identifier")
    domains_validated: list[str] = Field(
        default_factory=list, description="List of domain codes validated"
    )
    results: list[RuleResult] = Field(default_factory=list, description="All validation findings")
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
        description="True if effective_error_count is zero -- study can be submitted",
    )
    generated_at: str = Field(default="", description="ISO 8601 timestamp of report generation")
    summary_by_domain: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Domain -> {errors, warnings, notices} counts",
    )
    summary_by_category: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Category -> {errors, warnings, notices} counts",
    )

    @property
    def effective_error_count(self) -> int:
        """Error count excluding known false positives."""
        return sum(
            1
            for r in self.results
            if r.severity == RuleSeverity.ERROR and not r.known_false_positive
        )

    @property
    def effective_warning_count(self) -> int:
        """Warning count excluding known false positives."""
        return sum(
            1
            for r in self.results
            if r.severity == RuleSeverity.WARNING and not r.known_false_positive
        )

    @property
    def known_false_positive_results(self) -> list[RuleResult]:
        """Return all results flagged as known false positives."""
        return [r for r in self.results if r.known_false_positive]

    def flag_known_false_positives(self, whitelist_path: Path | None = None) -> None:
        """Flag matching RuleResults as known false positives.

        Loads the whitelist from JSON and marks matching results. A result
        matches if: rule_id matches AND (entry domain is null OR domain
        matches) AND (entry variable is null OR variable matches).

        After flagging, recalculates submission_ready based on effective counts.

        Args:
            whitelist_path: Path to known_false_positives.json. Defaults
                to the bundled file next to this module.
        """
        path = whitelist_path or _DEFAULT_WHITELIST_PATH
        if not path.exists():
            return

        with open(path) as f:
            data = json.load(f)

        entries = data.get("entries", [])
        if not entries:
            return

        for result in self.results:
            for entry in entries:
                if result.rule_id != entry["rule_id"]:
                    continue
                entry_domain = entry.get("domain")
                entry_variable = entry.get("variable")
                if entry_domain is not None and result.domain != entry_domain:
                    continue
                if entry_variable is not None and result.variable != entry_variable:
                    continue
                result.known_false_positive = True
                result.known_false_positive_reason = entry.get("reason", "")
                break

        # Recalculate submission readiness based on effective counts
        self.submission_ready = self.effective_error_count == 0

    @classmethod
    def from_results(
        cls,
        study_id: str,
        results: list[RuleResult],
        domains: list[str],
        *,
        whitelist_path: Path | None = None,
    ) -> ValidationReport:
        """Create a ValidationReport by computing summaries from raw results.

        Args:
            study_id: Study identifier.
            results: All RuleResult findings from validation.
            domains: List of domain codes that were validated.
            whitelist_path: Optional path to known_false_positives.json.
                If provided, matching results are flagged automatically.

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
                "errors": sum(1 for r in domain_results if r.severity == RuleSeverity.ERROR),
                "warnings": sum(1 for r in domain_results if r.severity == RuleSeverity.WARNING),
                "notices": sum(1 for r in domain_results if r.severity == RuleSeverity.NOTICE),
            }

        # Category-level breakdown
        summary_by_category: dict[str, dict[str, int]] = {}
        for cat in RuleCategory:
            cat_results = [r for r in results if r.category == cat]
            if cat_results:
                summary_by_category[cat.value] = {
                    "errors": sum(1 for r in cat_results if r.severity == RuleSeverity.ERROR),
                    "warnings": sum(1 for r in cat_results if r.severity == RuleSeverity.WARNING),
                    "notices": sum(1 for r in cat_results if r.severity == RuleSeverity.NOTICE),
                }

        # Pass rate: % of domains with zero errors
        if domains:
            domains_with_errors = sum(
                1 for d in domains if summary_by_domain.get(d, {}).get("errors", 0) > 0
            )
            pass_rate = (len(domains) - domains_with_errors) / len(domains)
        else:
            pass_rate = 1.0

        report = cls(
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

        # Apply known false-positive flagging if requested
        if whitelist_path is not None:
            report.flag_known_false_positives(whitelist_path)
        else:
            # Always try the default whitelist
            report.flag_known_false_positives()

        return report

    def to_markdown(self) -> str:
        """Render the validation report as a Markdown document.

        Returns:
            A formatted Markdown string with summary, per-domain breakdown,
            per-category breakdown, top issues, known false positives, and
            submission readiness assessment.
        """
        lines: list[str] = []

        # Header
        lines.append(f"# Validation Report: {self.study_id}")
        lines.append("")
        lines.append(f"**Generated:** {self.generated_at}")
        lines.append("")

        # Summary table
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Domains Validated | {len(self.domains_validated)} |")
        lines.append(f"| Total Findings | {self.total_rules_run} |")
        lines.append(f"| Errors | {self.effective_error_count} |")
        lines.append(f"| Warnings | {self.effective_warning_count} |")
        lines.append(f"| Notices | {self.notice_count} |")
        fp_count = len(self.known_false_positive_results)
        if fp_count > 0:
            lines.append(f"| Known False Positives | {fp_count} |")
        lines.append(f"| Pass Rate | {self.pass_rate:.0%} |")
        ready_str = "READY" if self.submission_ready else "NOT READY"
        lines.append(f"| Submission Status | {ready_str} |")
        lines.append("")

        # Per-domain breakdown
        if self.summary_by_domain:
            lines.append("## Per-Domain Breakdown")
            lines.append("")
            lines.append("| Domain | Errors | Warnings | Notices |")
            lines.append("|--------|--------|----------|---------|")
            for domain in sorted(self.summary_by_domain):
                counts = self.summary_by_domain[domain]
                lines.append(
                    f"| {domain} | {counts['errors']} | "
                    f"{counts['warnings']} | {counts['notices']} |"
                )
            lines.append("")

        # Per-category breakdown
        if self.summary_by_category:
            lines.append("## Per-Category Breakdown")
            lines.append("")
            lines.append("| Category | Errors | Warnings | Notices |")
            lines.append("|----------|--------|----------|---------|")
            for cat in sorted(self.summary_by_category):
                counts = self.summary_by_category[cat]
                lines.append(
                    f"| {cat} | {counts['errors']} | {counts['warnings']} | {counts['notices']} |"
                )
            lines.append("")

        # Top 10 issues
        sorted_results = sorted(
            self.results,
            key=lambda r: (
                0
                if r.severity == RuleSeverity.ERROR
                else (1 if r.severity == RuleSeverity.WARNING else 2),
                -r.affected_count,
            ),
        )
        top_issues = [r for r in sorted_results if not r.known_false_positive][:10]
        if top_issues:
            lines.append("## Top Issues")
            lines.append("")
            lines.append("| # | Severity | Rule | Domain | Variable | Message |")
            lines.append("|---|----------|------|--------|----------|---------|")
            for i, r in enumerate(top_issues, 1):
                domain_str = r.domain or "-"
                var_str = r.variable or "-"
                msg = r.message[:80] + "..." if len(r.message) > 80 else r.message
                lines.append(
                    f"| {i} | {r.severity.display_name} | {r.rule_id} | "
                    f"{domain_str} | {var_str} | {msg} |"
                )
            lines.append("")

        # Known false positives section
        fp_results = self.known_false_positive_results
        if fp_results:
            lines.append("## Known False Positives")
            lines.append("")
            lines.append(
                "The following findings match known false-positive patterns and are "
                "excluded from the effective error/warning counts."
            )
            lines.append("")
            lines.append("| Rule | Domain | Variable | Reason |")
            lines.append("|------|--------|----------|--------|")
            for r in fp_results:
                domain_str = r.domain or "-"
                var_str = r.variable or "-"
                reason = r.known_false_positive_reason or "-"
                lines.append(f"| {r.rule_id} | {domain_str} | {var_str} | {reason} |")
            lines.append("")

        # Submission readiness assessment
        lines.append("## Submission Readiness")
        lines.append("")
        if self.submission_ready:
            lines.append(
                "**READY** -- No blocking errors found. Study datasets are ready for submission."
            )
        else:
            blocking = [
                r
                for r in self.results
                if r.severity == RuleSeverity.ERROR and not r.known_false_positive
            ]
            lines.append(f"**NOT READY** -- {len(blocking)} blocking error(s) must be resolved:")
            lines.append("")
            for r in blocking:
                domain_str = f" [{r.domain}]" if r.domain else ""
                lines.append(f"- **{r.rule_id}**{domain_str}: {r.message}")
        lines.append("")

        return "\n".join(lines)
