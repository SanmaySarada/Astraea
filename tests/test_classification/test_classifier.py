"""Tests for the LLM domain classifier with heuristic fusion.

All tests use mocks for the LLM client -- no ANTHROPIC_API_KEY required.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from astraea.classification.classifier import (
    _LLMClassificationOutput,
    _determine_mapping_pattern,
    classify_all,
    classify_dataset,
    load_classification,
    save_classification,
)
from astraea.models.classification import (
    ClassificationResult,
    DomainClassification,
    DomainPlan,
    HeuristicScore,
)
from astraea.models.profiling import DatasetProfile, VariableProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(
    filename: str,
    clinical_vars: list[str],
    row_count: int = 100,
) -> DatasetProfile:
    """Create a minimal DatasetProfile for testing."""
    variables = [
        VariableProfile(
            name=var,
            dtype="character",
            n_total=row_count,
            n_missing=0,
            n_unique=50,
            missing_pct=0.0,
            is_edc_column=False,
        )
        for var in clinical_vars
    ]
    return DatasetProfile(
        filename=filename,
        row_count=row_count,
        col_count=len(variables),
        variables=variables,
    )


def _make_mock_client(
    primary_domain: str = "AE",
    confidence: float = 0.9,
    reasoning: str = "Test reasoning",
    secondary_domains: list[str] | None = None,
    merge_candidates: list[str] | None = None,
) -> MagicMock:
    """Create a mock AstraeaLLMClient that returns a fixed classification."""
    client = MagicMock()
    client.parse.return_value = _LLMClassificationOutput(
        primary_domain=primary_domain,
        confidence=confidence,
        reasoning=reasoning,
        secondary_domains=secondary_domains or [],
        merge_candidates=merge_candidates or [],
    )
    return client


def _make_mock_ref() -> MagicMock:
    """Create a mock SDTMReference."""
    ref = MagicMock()
    ref.list_domains.return_value = ["AE", "CM", "DM", "DS", "EX", "LB", "MH", "VS"]
    ref.get_domain_class.return_value = None  # Default: not Findings
    return ref


# ---------------------------------------------------------------------------
# Tests: classify_dataset
# ---------------------------------------------------------------------------


class TestClassifyDataset:
    """Tests for classify_dataset()."""

    def test_basic_classification(self) -> None:
        """LLM classification should return a DomainClassification."""
        profile = _make_profile("ae.sas7bdat", ["AETERM", "AESTDTC"])
        heuristic_scores = [
            HeuristicScore(domain="AE", score=1.0, signals=["filename exact match"]),
        ]
        client = _make_mock_client(primary_domain="AE", confidence=0.95)
        ref = _make_mock_ref()

        result = classify_dataset(
            dataset_name="ae.sas7bdat",
            profile=profile,
            heuristic_scores=heuristic_scores,
            ecrf_form_name="Adverse Events",
            client=client,
            ref=ref,
        )

        assert isinstance(result, DomainClassification)
        assert result.raw_dataset == "ae.sas7bdat"
        assert result.primary_domain == "AE"
        assert result.confidence > 0.0
        assert result.reasoning == "Test reasoning"

    def test_heuristic_llm_agreement_boosts_confidence(self) -> None:
        """When heuristic >= 0.9 and LLM agrees, confidence should be max of both."""
        profile = _make_profile("ae.sas7bdat", ["AETERM"])
        heuristic_scores = [
            HeuristicScore(domain="AE", score=0.95, signals=["filename"]),
        ]
        client = _make_mock_client(primary_domain="AE", confidence=0.85)
        ref = _make_mock_ref()

        result = classify_dataset(
            dataset_name="ae.sas7bdat",
            profile=profile,
            heuristic_scores=heuristic_scores,
            ecrf_form_name=None,
            client=client,
            ref=ref,
        )

        # Should boost to max(0.95, 0.85) = 0.95
        assert result.confidence == pytest.approx(0.95)

    def test_heuristic_llm_disagreement_reduces_confidence(self) -> None:
        """When heuristic >= 0.8 but LLM disagrees, confidence should be reduced."""
        profile = _make_profile("ae.sas7bdat", ["AETERM"])
        heuristic_scores = [
            HeuristicScore(domain="AE", score=0.85, signals=["filename"]),
        ]
        # LLM says CM instead of AE
        client = _make_mock_client(primary_domain="CM", confidence=0.7)
        ref = _make_mock_ref()

        result = classify_dataset(
            dataset_name="ae.sas7bdat",
            profile=profile,
            heuristic_scores=heuristic_scores,
            ecrf_form_name=None,
            client=client,
            ref=ref,
        )

        # Should reduce: min(0.85, 0.7) * 0.7 = 0.49
        assert result.confidence == pytest.approx(0.49, abs=0.01)
        assert result.primary_domain == "CM"  # LLM decision stands

    def test_unclassified_heuristic_no_penalty(self) -> None:
        """UNCLASSIFIED heuristic should not trigger disagreement logic."""
        profile = _make_profile("unknown.sas7bdat", ["XVAR"])
        heuristic_scores = [
            HeuristicScore(domain="UNCLASSIFIED", score=0.0, signals=["no match"]),
        ]
        client = _make_mock_client(primary_domain="UNCLASSIFIED", confidence=0.3)
        ref = _make_mock_ref()

        result = classify_dataset(
            dataset_name="unknown.sas7bdat",
            profile=profile,
            heuristic_scores=heuristic_scores,
            ecrf_form_name=None,
            client=client,
            ref=ref,
        )

        assert result.primary_domain == "UNCLASSIFIED"
        assert result.confidence == pytest.approx(0.3)

    def test_ecrf_form_included_in_prompt(self) -> None:
        """eCRF form name should appear in the LLM call prompt."""
        profile = _make_profile("ae.sas7bdat", ["AETERM"])
        heuristic_scores = [
            HeuristicScore(domain="AE", score=1.0, signals=["filename"]),
        ]
        client = _make_mock_client(primary_domain="AE", confidence=0.9)
        ref = _make_mock_ref()

        classify_dataset(
            dataset_name="ae.sas7bdat",
            profile=profile,
            heuristic_scores=heuristic_scores,
            ecrf_form_name="Adverse Events",
            client=client,
            ref=ref,
        )

        # Check the prompt contains the eCRF form name
        call_args = client.parse.call_args
        messages = call_args.kwargs["messages"]
        assert "Adverse Events" in messages[0]["content"]

    def test_secondary_domains_and_merge_candidates(self) -> None:
        """Secondary domains and merge_candidates should be passed through."""
        profile = _make_profile("ae.sas7bdat", ["AETERM"])
        heuristic_scores = [
            HeuristicScore(domain="AE", score=1.0, signals=["filename"]),
        ]
        client = _make_mock_client(
            primary_domain="AE",
            confidence=0.9,
            secondary_domains=["SUPPAE"],
            merge_candidates=["ae_extra.sas7bdat"],
        )
        ref = _make_mock_ref()

        result = classify_dataset(
            dataset_name="ae.sas7bdat",
            profile=profile,
            heuristic_scores=heuristic_scores,
            ecrf_form_name=None,
            client=client,
            ref=ref,
        )

        assert result.secondary_domains == ["SUPPAE"]
        assert result.merge_candidates == ["ae_extra.sas7bdat"]


# ---------------------------------------------------------------------------
# Tests: classify_all
# ---------------------------------------------------------------------------


class TestClassifyAll:
    """Tests for classify_all() orchestrator."""

    @patch("astraea.classification.classifier.compute_heuristic_scores")
    @patch("astraea.classification.classifier.detect_merge_groups")
    def test_orchestrator_three_datasets(
        self, mock_merge: MagicMock, mock_heuristic: MagicMock
    ) -> None:
        """classify_all should process all datasets and build domain plans."""
        profiles = [
            _make_profile("ae.sas7bdat", ["AETERM"]),
            _make_profile("dm.sas7bdat", ["SEX", "RACE"]),
            _make_profile("unknown.sas7bdat", ["XVAR"]),
        ]

        mock_heuristic.side_effect = [
            [HeuristicScore(domain="AE", score=1.0, signals=["filename"])],
            [HeuristicScore(domain="DM", score=1.0, signals=["filename"])],
            [HeuristicScore(domain="UNCLASSIFIED", score=0.0, signals=["no match"])],
        ]
        mock_merge.return_value = {}

        # Create client that returns different results per call
        client = MagicMock()
        client.parse.side_effect = [
            _LLMClassificationOutput(
                primary_domain="AE",
                confidence=0.95,
                reasoning="AE variables",
                secondary_domains=[],
                merge_candidates=[],
            ),
            _LLMClassificationOutput(
                primary_domain="DM",
                confidence=0.9,
                reasoning="DM variables",
                secondary_domains=[],
                merge_candidates=[],
            ),
            _LLMClassificationOutput(
                primary_domain="UNCLASSIFIED",
                confidence=0.2,
                reasoning="No standard domain fits",
                secondary_domains=[],
                merge_candidates=[],
            ),
        ]
        ref = _make_mock_ref()

        result = classify_all(
            profiles=profiles,
            client=client,
            ref=ref,
        )

        assert isinstance(result, ClassificationResult)
        assert len(result.classifications) == 3
        assert len(result.unclassified_datasets) == 1
        assert "unknown.sas7bdat" in result.unclassified_datasets

        # Domain plans should exist for AE and DM (not UNCLASSIFIED)
        plan_domains = {p.domain for p in result.domain_plans}
        assert "AE" in plan_domains
        assert "DM" in plan_domains

    @patch("astraea.classification.classifier.compute_heuristic_scores")
    @patch("astraea.classification.classifier.detect_merge_groups")
    def test_merge_detection_in_domain_plan(
        self, mock_merge: MagicMock, mock_heuristic: MagicMock
    ) -> None:
        """Merge groups should result in 'merge' mapping pattern."""
        profiles = [
            _make_profile("lb_biochem.sas7bdat", ["LBTESTCD"]),
            _make_profile("lb_hem.sas7bdat", ["LBTESTCD"]),
        ]

        mock_heuristic.return_value = [
            HeuristicScore(domain="LB", score=0.7, signals=["filename"]),
        ]
        mock_merge.return_value = {
            "LB": ["lb_biochem.sas7bdat", "lb_hem.sas7bdat"],
        }

        client = MagicMock()
        client.parse.return_value = _LLMClassificationOutput(
            primary_domain="LB",
            confidence=0.85,
            reasoning="Lab data",
            secondary_domains=[],
            merge_candidates=[],
        )
        ref = _make_mock_ref()
        # Make LB a Findings domain
        from astraea.models.sdtm import DomainClass

        ref.get_domain_class.return_value = DomainClass.FINDINGS

        result = classify_all(profiles=profiles, client=client, ref=ref)

        lb_plans = [p for p in result.domain_plans if p.domain == "LB"]
        assert len(lb_plans) == 1
        assert lb_plans[0].mapping_pattern == "mixed"  # merge + findings
        assert len(lb_plans[0].source_datasets) == 2


# ---------------------------------------------------------------------------
# Tests: _determine_mapping_pattern
# ---------------------------------------------------------------------------


class TestDetermineMappingPattern:
    """Tests for mapping pattern determination."""

    def test_single_non_findings_is_direct(self) -> None:
        assert _determine_mapping_pattern("AE", 1, None) == "direct"

    def test_single_findings_is_transpose(self) -> None:
        assert _determine_mapping_pattern("LB", 1, None) == "transpose"

    def test_multi_non_findings_is_merge(self) -> None:
        assert _determine_mapping_pattern("AE", 2, None) == "merge"

    def test_multi_findings_is_mixed(self) -> None:
        assert _determine_mapping_pattern("VS", 3, None) == "mixed"


# ---------------------------------------------------------------------------
# Tests: save/load round-trip
# ---------------------------------------------------------------------------


class TestSaveLoad:
    """Tests for save_classification and load_classification."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """Save and load should produce identical ClassificationResult."""
        original = ClassificationResult(
            classifications=[
                DomainClassification(
                    raw_dataset="ae.sas7bdat",
                    primary_domain="AE",
                    confidence=0.95,
                    reasoning="AE variables present",
                    heuristic_scores=[
                        HeuristicScore(domain="AE", score=1.0, signals=["filename"]),
                    ],
                ),
            ],
            domain_plans=[
                DomainPlan(
                    domain="AE",
                    source_datasets=["ae.sas7bdat"],
                    mapping_pattern="direct",
                ),
            ],
            unclassified_datasets=["unknown.sas7bdat"],
        )

        output_path = tmp_path / "classification.json"
        save_classification(original, output_path)

        assert output_path.exists()

        loaded = load_classification(output_path)
        assert loaded.classifications[0].raw_dataset == "ae.sas7bdat"
        assert loaded.classifications[0].primary_domain == "AE"
        assert loaded.classifications[0].confidence == pytest.approx(0.95)
        assert len(loaded.domain_plans) == 1
        assert loaded.unclassified_datasets == ["unknown.sas7bdat"]

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Loading a missing file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_classification(tmp_path / "nonexistent.json")
