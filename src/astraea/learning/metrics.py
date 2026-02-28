"""Accuracy metrics computation from review decisions.

Computes per-domain per-study accuracy rates from completed reviews and
tracks improvement over time across studies. Provides the primary signal
for measuring whether the learning system is actually improving.
"""

from __future__ import annotations

from datetime import UTC, datetime

from astraea.learning.models import StudyMetrics
from astraea.review.models import (
    CorrectionType,
    DomainReview,
    ReviewStatus,
)


def compute_domain_accuracy(
    domain_review: DomainReview,
    study_id: str,
) -> StudyMetrics:
    """Compute accuracy metrics from a completed domain review.

    Counts decisions by status to determine how many mappings were
    approved unchanged vs corrected vs rejected. The accuracy_rate
    is the primary learning signal (approved_unchanged / total_proposed).

    Args:
        domain_review: Completed domain review with decisions.
        study_id: Study identifier for the metrics record.

    Returns:
        StudyMetrics with all fields populated from the review decisions.
    """
    total_proposed = len(domain_review.original_spec.variable_mappings)

    approved_unchanged = 0
    corrected = 0
    rejected = 0
    added_by_reviewer = 0

    for decision in domain_review.decisions.values():
        if decision.status == ReviewStatus.APPROVED:
            approved_unchanged += 1
        elif decision.status == ReviewStatus.CORRECTED:
            if decision.correction_type == CorrectionType.REJECT:
                rejected += 1
            elif decision.correction_type == CorrectionType.ADD:
                added_by_reviewer += 1
            else:
                corrected += 1

    accuracy_rate = (
        approved_unchanged / total_proposed if total_proposed > 0 else 0.0
    )
    correction_rate = (
        corrected / total_proposed if total_proposed > 0 else 0.0
    )

    completed_at = (
        domain_review.reviewed_at
        or datetime.now(tz=UTC).isoformat()
    )

    return StudyMetrics(
        study_id=study_id,
        domain=domain_review.domain,
        total_proposed=total_proposed,
        approved_unchanged=approved_unchanged,
        corrected=corrected,
        rejected=rejected,
        added_by_reviewer=added_by_reviewer,
        accuracy_rate=accuracy_rate,
        correction_rate=correction_rate,
        completed_at=completed_at,
    )


def compute_improvement_report(
    metrics_list: list[StudyMetrics],
) -> dict:
    """Compute an improvement report across studies and domains.

    Groups metrics by domain, sorts by completion time, and computes
    accuracy trends showing whether the system is improving.

    Args:
        metrics_list: List of StudyMetrics from multiple studies/domains.

    Returns:
        Dict with keys:
        - overall_accuracy: Mean of all accuracy_rates.
        - by_domain: Per-domain breakdown with first, latest, improvement, trend.
        - total_examples: Sum of total_proposed across all entries.
        - total_corrections: Sum of corrected across all entries.
    """
    if not metrics_list:
        return {
            "overall_accuracy": 0.0,
            "by_domain": {},
            "total_examples": 0,
            "total_corrections": 0,
        }

    # Group by domain
    by_domain: dict[str, list[StudyMetrics]] = {}
    for m in metrics_list:
        by_domain.setdefault(m.domain, []).append(m)

    # Sort each domain's entries by completed_at
    for domain_metrics in by_domain.values():
        domain_metrics.sort(key=lambda x: x.completed_at)

    # Build per-domain summary
    domain_summary: dict[str, dict] = {}
    for domain, entries in by_domain.items():
        trend = [e.accuracy_rate for e in entries]
        domain_summary[domain] = {
            "first": trend[0],
            "latest": trend[-1],
            "improvement": trend[-1] - trend[0],
            "studies": len(entries),
            "trend": trend,
        }

    overall_accuracy = (
        sum(m.accuracy_rate for m in metrics_list) / len(metrics_list)
    )
    total_examples = sum(m.total_proposed for m in metrics_list)
    total_corrections = sum(m.corrected for m in metrics_list)

    return {
        "overall_accuracy": overall_accuracy,
        "by_domain": domain_summary,
        "total_examples": total_examples,
        "total_corrections": total_corrections,
    }


def format_improvement_summary(report: dict) -> str:
    """Format an improvement report as a human-readable string.

    Shows per-domain accuracy trends and overall improvement for
    CLI display.

    Args:
        report: Output of compute_improvement_report().

    Returns:
        Multi-line formatted string summarizing learning progress.
    """
    lines: list[str] = []
    lines.append("Learning System Improvement Report")
    lines.append("=" * 40)
    lines.append("")
    lines.append(
        f"Overall Accuracy: {report['overall_accuracy']:.1%}"
    )
    lines.append(f"Total Examples:   {report['total_examples']}")
    lines.append(f"Total Corrections: {report['total_corrections']}")
    lines.append("")

    by_domain = report.get("by_domain", {})
    if by_domain:
        lines.append("Per-Domain Breakdown:")
        lines.append("-" * 40)
        for domain in sorted(by_domain):
            info = by_domain[domain]
            improvement = info["improvement"]
            arrow = "+" if improvement >= 0 else ""
            lines.append(
                f"  {domain:8s} | "
                f"First: {info['first']:.1%} | "
                f"Latest: {info['latest']:.1%} | "
                f"Change: {arrow}{improvement:.1%} | "
                f"Studies: {info['studies']}"
            )
    else:
        lines.append("No domain data available yet.")

    lines.append("")
    return "\n".join(lines)
