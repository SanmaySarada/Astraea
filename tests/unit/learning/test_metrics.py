"""Tests for learning system accuracy metrics computation."""

from __future__ import annotations

import pytest

from astraea.learning.metrics import (
    compute_domain_accuracy,
    compute_improvement_report,
    format_improvement_summary,
)
from astraea.learning.models import StudyMetrics
from astraea.models.mapping import (
    ConfidenceLevel,
    CoreDesignation,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)
from astraea.review.models import (
    CorrectionType,
    DomainReview,
    DomainReviewStatus,
    ReviewDecision,
    ReviewStatus,
)


def _make_mapping(var_name: str) -> VariableMapping:
    """Create a minimal VariableMapping for testing."""
    return VariableMapping(
        sdtm_variable=var_name,
        sdtm_label=f"Label for {var_name}",
        sdtm_data_type="Char",
        core=CoreDesignation.REQ,
        mapping_pattern=MappingPattern.DIRECT,
        mapping_logic=f"Direct carry of {var_name}",
        source_variable=var_name.lower(),
        source_dataset="ae.sas7bdat",
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="High confidence direct mapping",
    )


def _make_spec(
    domain: str, variables: list[str], study_id: str = "STUDY-001"
) -> DomainMappingSpec:
    """Create a minimal DomainMappingSpec for testing."""
    mappings = [_make_mapping(v) for v in variables]
    return DomainMappingSpec(
        domain=domain,
        domain_label=f"{domain} Domain",
        domain_class="Events",
        structure="One record per event",
        study_id=study_id,
        variable_mappings=mappings,
        total_variables=len(mappings),
        required_mapped=len(mappings),
        expected_mapped=0,
        high_confidence_count=len(mappings),
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T10:00:00+00:00",
        model_used="test-model",
        unmapped_source_variables=[],
        suppqual_candidates=[],
    )


def _make_decision(
    var_name: str,
    status: ReviewStatus,
    correction_type: CorrectionType | None = None,
) -> ReviewDecision:
    """Create a ReviewDecision for testing."""
    original = _make_mapping(var_name)
    corrected = None
    if status == ReviewStatus.CORRECTED and correction_type != CorrectionType.REJECT:
        corrected = _make_mapping(var_name)
        corrected = corrected.model_copy(
            update={"mapping_logic": "Corrected logic"}
        )
    return ReviewDecision(
        sdtm_variable=var_name,
        status=status,
        correction_type=correction_type,
        original_mapping=original,
        corrected_mapping=corrected,
        reason="Test reason" if status == ReviewStatus.CORRECTED else "",
        timestamp="2026-02-28T10:00:00+00:00",
    )


class TestComputeDomainAccuracy:
    """Tests for compute_domain_accuracy."""

    def test_all_approved(self) -> None:
        """All mappings approved unchanged -> 100% accuracy."""
        spec = _make_spec("AE", ["AETERM", "AEDECOD", "AESTDTC"])
        review = DomainReview(
            domain="AE",
            status=DomainReviewStatus.COMPLETED,
            original_spec=spec,
            decisions={
                "AETERM": _make_decision("AETERM", ReviewStatus.APPROVED),
                "AEDECOD": _make_decision("AEDECOD", ReviewStatus.APPROVED),
                "AESTDTC": _make_decision("AESTDTC", ReviewStatus.APPROVED),
            },
            reviewed_at="2026-02-28T10:00:00+00:00",
        )

        metrics = compute_domain_accuracy(review, "STUDY-001")

        assert metrics.total_proposed == 3
        assert metrics.approved_unchanged == 3
        assert metrics.corrected == 0
        assert metrics.rejected == 0
        assert metrics.added_by_reviewer == 0
        assert metrics.accuracy_rate == pytest.approx(1.0)
        assert metrics.correction_rate == pytest.approx(0.0)

    def test_mixed_decisions(self) -> None:
        """Mixed decisions: some approved, some corrected, some rejected."""
        spec = _make_spec(
            "AE", ["AETERM", "AEDECOD", "AESTDTC", "AEENDTC"]
        )
        review = DomainReview(
            domain="AE",
            status=DomainReviewStatus.COMPLETED,
            original_spec=spec,
            decisions={
                "AETERM": _make_decision("AETERM", ReviewStatus.APPROVED),
                "AEDECOD": _make_decision(
                    "AEDECOD",
                    ReviewStatus.CORRECTED,
                    CorrectionType.SOURCE_CHANGE,
                ),
                "AESTDTC": _make_decision(
                    "AESTDTC",
                    ReviewStatus.CORRECTED,
                    CorrectionType.REJECT,
                ),
                "AEENDTC": _make_decision("AEENDTC", ReviewStatus.APPROVED),
            },
            reviewed_at="2026-02-28T10:00:00+00:00",
        )

        metrics = compute_domain_accuracy(review, "STUDY-001")

        assert metrics.total_proposed == 4
        assert metrics.approved_unchanged == 2
        assert metrics.corrected == 1
        assert metrics.rejected == 1
        assert metrics.accuracy_rate == pytest.approx(0.5)
        assert metrics.correction_rate == pytest.approx(0.25)

    def test_zero_mappings(self) -> None:
        """Edge case: spec with zero mappings."""
        spec = _make_spec("AE", [])
        review = DomainReview(
            domain="AE",
            status=DomainReviewStatus.COMPLETED,
            original_spec=spec,
            decisions={},
            reviewed_at="2026-02-28T10:00:00+00:00",
        )

        metrics = compute_domain_accuracy(review, "STUDY-001")

        assert metrics.total_proposed == 0
        assert metrics.accuracy_rate == pytest.approx(0.0)
        assert metrics.correction_rate == pytest.approx(0.0)

    def test_add_correction_type(self) -> None:
        """ADD correction type is counted as added_by_reviewer."""
        spec = _make_spec("DM", ["STUDYID"])
        review = DomainReview(
            domain="DM",
            status=DomainReviewStatus.COMPLETED,
            original_spec=spec,
            decisions={
                "STUDYID": _make_decision("STUDYID", ReviewStatus.APPROVED),
                "BRTHDTC": _make_decision(
                    "BRTHDTC",
                    ReviewStatus.CORRECTED,
                    CorrectionType.ADD,
                ),
            },
            reviewed_at="2026-02-28T10:00:00+00:00",
        )

        metrics = compute_domain_accuracy(review, "STUDY-001")

        assert metrics.approved_unchanged == 1
        assert metrics.added_by_reviewer == 1
        assert metrics.corrected == 0

    def test_uses_reviewed_at_timestamp(self) -> None:
        """completed_at uses the domain_review.reviewed_at timestamp."""
        spec = _make_spec("DM", ["STUDYID"])
        review = DomainReview(
            domain="DM",
            status=DomainReviewStatus.COMPLETED,
            original_spec=spec,
            decisions={
                "STUDYID": _make_decision("STUDYID", ReviewStatus.APPROVED),
            },
            reviewed_at="2026-01-15T08:30:00+00:00",
        )

        metrics = compute_domain_accuracy(review, "STUDY-001")
        assert metrics.completed_at == "2026-01-15T08:30:00+00:00"


class TestComputeImprovementReport:
    """Tests for compute_improvement_report."""

    def test_single_study(self) -> None:
        """Single study -> no improvement to measure (first == latest)."""
        metrics = [
            StudyMetrics(
                study_id="STUDY-001",
                domain="AE",
                total_proposed=10,
                approved_unchanged=8,
                corrected=2,
                rejected=0,
                added_by_reviewer=0,
                accuracy_rate=0.8,
                correction_rate=0.2,
                completed_at="2026-01-01T00:00:00+00:00",
            )
        ]

        report = compute_improvement_report(metrics)

        assert report["overall_accuracy"] == pytest.approx(0.8)
        assert report["by_domain"]["AE"]["first"] == pytest.approx(0.8)
        assert report["by_domain"]["AE"]["latest"] == pytest.approx(0.8)
        assert report["by_domain"]["AE"]["improvement"] == pytest.approx(0.0)
        assert report["by_domain"]["AE"]["studies"] == 1
        assert report["total_examples"] == 10
        assert report["total_corrections"] == 2

    def test_multiple_studies_showing_improvement(self) -> None:
        """Multiple studies for same domain -> improvement tracked."""
        metrics = [
            StudyMetrics(
                study_id="STUDY-001",
                domain="AE",
                total_proposed=10,
                approved_unchanged=6,
                corrected=4,
                rejected=0,
                added_by_reviewer=0,
                accuracy_rate=0.6,
                correction_rate=0.4,
                completed_at="2026-01-01T00:00:00+00:00",
            ),
            StudyMetrics(
                study_id="STUDY-002",
                domain="AE",
                total_proposed=10,
                approved_unchanged=9,
                corrected=1,
                rejected=0,
                added_by_reviewer=0,
                accuracy_rate=0.9,
                correction_rate=0.1,
                completed_at="2026-02-01T00:00:00+00:00",
            ),
        ]

        report = compute_improvement_report(metrics)

        assert report["overall_accuracy"] == pytest.approx(0.75)
        assert report["by_domain"]["AE"]["first"] == pytest.approx(0.6)
        assert report["by_domain"]["AE"]["latest"] == pytest.approx(0.9)
        assert report["by_domain"]["AE"]["improvement"] == pytest.approx(0.3)
        assert report["by_domain"]["AE"]["trend"] == pytest.approx([0.6, 0.9])
        assert report["total_examples"] == 20
        assert report["total_corrections"] == 5

    def test_groups_by_domain(self) -> None:
        """Multiple domains are tracked separately."""
        metrics = [
            StudyMetrics(
                study_id="STUDY-001",
                domain="AE",
                total_proposed=10,
                approved_unchanged=8,
                corrected=2,
                rejected=0,
                added_by_reviewer=0,
                accuracy_rate=0.8,
                correction_rate=0.2,
                completed_at="2026-01-01T00:00:00+00:00",
            ),
            StudyMetrics(
                study_id="STUDY-001",
                domain="DM",
                total_proposed=5,
                approved_unchanged=5,
                corrected=0,
                rejected=0,
                added_by_reviewer=0,
                accuracy_rate=1.0,
                correction_rate=0.0,
                completed_at="2026-01-01T00:00:00+00:00",
            ),
        ]

        report = compute_improvement_report(metrics)

        assert "AE" in report["by_domain"]
        assert "DM" in report["by_domain"]
        assert report["by_domain"]["AE"]["studies"] == 1
        assert report["by_domain"]["DM"]["studies"] == 1
        assert report["overall_accuracy"] == pytest.approx(0.9)

    def test_empty_metrics_list(self) -> None:
        """Empty list returns zeroed report."""
        report = compute_improvement_report([])

        assert report["overall_accuracy"] == 0.0
        assert report["by_domain"] == {}
        assert report["total_examples"] == 0
        assert report["total_corrections"] == 0


class TestFormatImprovementSummary:
    """Tests for format_improvement_summary."""

    def test_produces_nonempty_string(self) -> None:
        """Format produces a non-empty human-readable string."""
        report = {
            "overall_accuracy": 0.85,
            "by_domain": {
                "AE": {
                    "first": 0.7,
                    "latest": 0.9,
                    "improvement": 0.2,
                    "studies": 2,
                    "trend": [0.7, 0.9],
                }
            },
            "total_examples": 20,
            "total_corrections": 3,
        }

        result = format_improvement_summary(report)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "85.0%" in result
        assert "AE" in result
        assert "20" in result

    def test_empty_report(self) -> None:
        """Format handles empty domain data gracefully."""
        report = {
            "overall_accuracy": 0.0,
            "by_domain": {},
            "total_examples": 0,
            "total_corrections": 0,
        }

        result = format_improvement_summary(report)

        assert "No domain data available" in result
