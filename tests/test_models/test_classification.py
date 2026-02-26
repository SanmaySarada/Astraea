"""Tests for domain classification models."""

import pytest
from pydantic import ValidationError

from astraea.models import (
    ClassificationResult,
    DomainClassification,
    DomainPlan,
    HeuristicScore,
)


class TestHeuristicScore:
    """Tests for HeuristicScore model."""

    def test_create_valid_score(self) -> None:
        score = HeuristicScore(
            domain="AE",
            score=0.95,
            signals=["filename exact match", "variable AETERM found"],
        )
        assert score.domain == "AE"
        assert score.score == 0.95
        assert len(score.signals) == 2

    def test_score_bounds_zero(self) -> None:
        score = HeuristicScore(domain="XX", score=0.0, signals=[])
        assert score.score == 0.0

    def test_score_bounds_one(self) -> None:
        score = HeuristicScore(domain="DM", score=1.0, signals=["perfect match"])
        assert score.score == 1.0

    def test_rejects_score_above_one(self) -> None:
        with pytest.raises(ValidationError):
            HeuristicScore(domain="AE", score=1.1, signals=[])

    def test_rejects_negative_score(self) -> None:
        with pytest.raises(ValidationError):
            HeuristicScore(domain="AE", score=-0.1, signals=[])


class TestDomainClassification:
    """Tests for DomainClassification model."""

    def test_create_valid_classification(self) -> None:
        cls = DomainClassification(
            raw_dataset="ae.sas7bdat",
            primary_domain="AE",
            secondary_domains=["SUPPAE"],
            confidence=0.95,
            reasoning="Filename matches AE domain, contains AETERM variable",
            merge_candidates=[],
        )
        assert cls.raw_dataset == "ae.sas7bdat"
        assert cls.primary_domain == "AE"
        assert cls.secondary_domains == ["SUPPAE"]
        assert cls.confidence == 0.95

    def test_unclassified_domain(self) -> None:
        cls = DomainClassification(
            raw_dataset="unknown.sas7bdat",
            primary_domain="UNCLASSIFIED",
            confidence=0.1,
            reasoning="No matching domain found",
        )
        assert cls.primary_domain == "UNCLASSIFIED"

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            DomainClassification(
                raw_dataset="test.sas7bdat",
                primary_domain="AE",
                confidence=1.5,
            )

    def test_confidence_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            DomainClassification(
                raw_dataset="test.sas7bdat",
                primary_domain="AE",
                confidence=-0.1,
            )

    def test_default_empty_lists(self) -> None:
        cls = DomainClassification(
            raw_dataset="ae.sas7bdat",
            primary_domain="AE",
            confidence=0.9,
        )
        assert cls.secondary_domains == []
        assert cls.merge_candidates == []
        assert cls.heuristic_scores == []
        assert cls.reasoning == ""

    def test_with_merge_candidates(self) -> None:
        cls = DomainClassification(
            raw_dataset="lb_biochem.sas7bdat",
            primary_domain="LB",
            confidence=0.85,
            merge_candidates=["lb_hem.sas7bdat", "lb_urin.sas7bdat"],
        )
        assert len(cls.merge_candidates) == 2

    def test_with_heuristic_scores(self) -> None:
        scores = [
            HeuristicScore(domain="AE", score=0.9, signals=["filename match"]),
            HeuristicScore(domain="MH", score=0.1, signals=["low overlap"]),
        ]
        cls = DomainClassification(
            raw_dataset="ae.sas7bdat",
            primary_domain="AE",
            confidence=0.95,
            heuristic_scores=scores,
        )
        assert len(cls.heuristic_scores) == 2
        assert cls.heuristic_scores[0].domain == "AE"


class TestDomainPlan:
    """Tests for DomainPlan model."""

    def test_create_direct_plan(self) -> None:
        plan = DomainPlan(
            domain="AE",
            source_datasets=["ae.sas7bdat"],
            mapping_pattern="direct",
            notes="Single source direct mapping",
        )
        assert plan.domain == "AE"
        assert plan.mapping_pattern == "direct"

    def test_create_merge_plan(self) -> None:
        plan = DomainPlan(
            domain="LB",
            source_datasets=[
                "lb_biochem.sas7bdat",
                "lb_hem.sas7bdat",
                "lb_urin.sas7bdat",
            ],
            mapping_pattern="merge",
        )
        assert plan.mapping_pattern == "merge"
        assert len(plan.source_datasets) == 3

    def test_create_transpose_plan(self) -> None:
        plan = DomainPlan(
            domain="VS",
            source_datasets=["vs.sas7bdat"],
            mapping_pattern="transpose",
        )
        assert plan.mapping_pattern == "transpose"

    def test_create_mixed_plan(self) -> None:
        plan = DomainPlan(
            domain="LB",
            source_datasets=["lb_biochem.sas7bdat", "lb_hem.sas7bdat"],
            mapping_pattern="mixed",
        )
        assert plan.mapping_pattern == "mixed"

    def test_rejects_invalid_mapping_pattern(self) -> None:
        with pytest.raises(ValidationError):
            DomainPlan(
                domain="AE",
                source_datasets=["ae.sas7bdat"],
                mapping_pattern="unknown",  # type: ignore[arg-type]
            )

    def test_notes_default_empty(self) -> None:
        plan = DomainPlan(
            domain="DM",
            source_datasets=["dm.sas7bdat"],
            mapping_pattern="direct",
        )
        assert plan.notes == ""


class TestClassificationResult:
    """Tests for ClassificationResult model."""

    def test_create_complete_result(self) -> None:
        cls = DomainClassification(
            raw_dataset="ae.sas7bdat",
            primary_domain="AE",
            confidence=0.95,
        )
        plan = DomainPlan(
            domain="AE",
            source_datasets=["ae.sas7bdat"],
            mapping_pattern="direct",
        )
        result = ClassificationResult(
            classifications=[cls],
            domain_plans=[plan],
            unclassified_datasets=[],
        )
        assert len(result.classifications) == 1
        assert len(result.domain_plans) == 1
        assert result.unclassified_datasets == []

    def test_with_unclassified_datasets(self) -> None:
        result = ClassificationResult(
            classifications=[],
            domain_plans=[],
            unclassified_datasets=["mystery.sas7bdat", "unknown.sas7bdat"],
        )
        assert len(result.unclassified_datasets) == 2

    def test_empty_result(self) -> None:
        result = ClassificationResult()
        assert result.classifications == []
        assert result.domain_plans == []
        assert result.unclassified_datasets == []
