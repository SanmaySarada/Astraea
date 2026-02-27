"""Tests for review data models."""

from __future__ import annotations

import pytest

from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation
from astraea.review.models import (
    CorrectionType,
    DomainReview,
    DomainReviewStatus,
    HumanCorrection,
    ReviewDecision,
    ReviewSession,
    ReviewStatus,
    SessionStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_variable_mapping(
    variable: str = "STUDYID",
    pattern: MappingPattern = MappingPattern.ASSIGN,
    **overrides: object,
) -> VariableMapping:
    """Create a minimal valid VariableMapping for testing."""
    defaults: dict[str, object] = {
        "sdtm_variable": variable,
        "sdtm_label": f"Label for {variable}",
        "sdtm_data_type": "Char",
        "core": CoreDesignation.REQ,
        "mapping_pattern": pattern,
        "mapping_logic": f"Assign {variable}",
        "assigned_value": "PHA022121-C301" if pattern == MappingPattern.ASSIGN else None,
        "confidence": 0.95,
        "confidence_level": ConfidenceLevel.HIGH,
        "confidence_rationale": "Standard assignment",
    }
    defaults.update(overrides)
    return VariableMapping(**defaults)  # type: ignore[arg-type]


def _make_domain_spec(domain: str = "DM") -> DomainMappingSpec:
    """Create a minimal valid DomainMappingSpec for testing."""
    mappings = [
        _make_variable_mapping("STUDYID"),
        _make_variable_mapping("DOMAIN", assigned_value="DM"),
        _make_variable_mapping(
            "USUBJID",
            pattern=MappingPattern.DERIVATION,
            assigned_value=None,
            source_dataset="dm",
            source_variable="SUBJID",
            mapping_logic="STUDYID + SITEID + SUBJID",
            confidence=0.90,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Standard derivation",
        ),
    ]
    return DomainMappingSpec(
        domain=domain,
        domain_label="Demographics",
        domain_class="Special Purpose",
        structure="One record per subject",
        study_id="PHA022121-C301",
        source_datasets=["dm"],
        variable_mappings=mappings,
        total_variables=3,
        required_mapped=3,
        expected_mapped=0,
        high_confidence_count=3,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T12:00:00+00:00",
        model_used="claude-sonnet-4-20250514",
    )


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestCorrectionType:
    """Tests for CorrectionType enum."""

    def test_all_values(self) -> None:
        assert CorrectionType.SOURCE_CHANGE == "source_change"
        assert CorrectionType.LOGIC_CHANGE == "logic_change"
        assert CorrectionType.PATTERN_CHANGE == "pattern_change"
        assert CorrectionType.CT_CHANGE == "ct_change"
        assert CorrectionType.CONFIDENCE_OVERRIDE == "confidence_override"
        assert CorrectionType.REJECT == "reject"
        assert CorrectionType.ADD == "add"

    def test_count(self) -> None:
        assert len(CorrectionType) == 7


class TestReviewStatus:
    """Tests for ReviewStatus enum."""

    def test_all_values(self) -> None:
        assert ReviewStatus.PENDING == "pending"
        assert ReviewStatus.APPROVED == "approved"
        assert ReviewStatus.CORRECTED == "corrected"
        assert ReviewStatus.SKIPPED == "skipped"

    def test_count(self) -> None:
        assert len(ReviewStatus) == 4


class TestDomainReviewStatus:
    """Tests for DomainReviewStatus enum."""

    def test_all_values(self) -> None:
        assert DomainReviewStatus.PENDING == "pending"
        assert DomainReviewStatus.IN_PROGRESS == "in_progress"
        assert DomainReviewStatus.COMPLETED == "completed"
        assert DomainReviewStatus.SKIPPED == "skipped"


class TestSessionStatus:
    """Tests for SessionStatus enum."""

    def test_all_values(self) -> None:
        assert SessionStatus.IN_PROGRESS == "in_progress"
        assert SessionStatus.COMPLETED == "completed"
        assert SessionStatus.ABANDONED == "abandoned"


# ---------------------------------------------------------------------------
# ReviewDecision tests
# ---------------------------------------------------------------------------


class TestReviewDecision:
    """Tests for ReviewDecision model."""

    def test_approve_no_correction(self) -> None:
        mapping = _make_variable_mapping()
        decision = ReviewDecision(
            sdtm_variable="STUDYID",
            status=ReviewStatus.APPROVED,
            original_mapping=mapping,
            timestamp="2026-02-27T12:00:00+00:00",
        )
        assert decision.status == ReviewStatus.APPROVED
        assert decision.correction_type is None
        assert decision.corrected_mapping is None

    def test_corrected_with_all_fields(self) -> None:
        original = _make_variable_mapping(
            "USUBJID",
            pattern=MappingPattern.DERIVATION,
            assigned_value=None,
            source_dataset="dm",
            source_variable="SUBJID",
            mapping_logic="STUDYID + SUBJID",
            confidence=0.70,
            confidence_level=ConfidenceLevel.MEDIUM,
            confidence_rationale="Missing SITEID",
        )
        corrected = _make_variable_mapping(
            "USUBJID",
            pattern=MappingPattern.DERIVATION,
            assigned_value=None,
            source_dataset="dm",
            source_variable="SUBJID",
            mapping_logic="STUDYID + SITEID + SUBJID",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Corrected by reviewer",
        )
        decision = ReviewDecision(
            sdtm_variable="USUBJID",
            status=ReviewStatus.CORRECTED,
            correction_type=CorrectionType.LOGIC_CHANGE,
            original_mapping=original,
            corrected_mapping=corrected,
            reason="SITEID must be included per SDTM-IG",
            timestamp="2026-02-27T12:00:00+00:00",
        )
        assert decision.status == ReviewStatus.CORRECTED
        assert decision.correction_type == CorrectionType.LOGIC_CHANGE
        assert decision.corrected_mapping is not None

    def test_corrected_requires_corrected_mapping(self) -> None:
        mapping = _make_variable_mapping()
        with pytest.raises(ValueError, match="corrected_mapping is required"):
            ReviewDecision(
                sdtm_variable="STUDYID",
                status=ReviewStatus.CORRECTED,
                correction_type=CorrectionType.SOURCE_CHANGE,
                original_mapping=mapping,
                corrected_mapping=None,
                timestamp="2026-02-27T12:00:00+00:00",
            )

    def test_corrected_requires_correction_type(self) -> None:
        mapping = _make_variable_mapping()
        corrected = _make_variable_mapping(assigned_value="DIFFERENT")
        with pytest.raises(ValueError, match="correction_type is required"):
            ReviewDecision(
                sdtm_variable="STUDYID",
                status=ReviewStatus.CORRECTED,
                correction_type=None,
                original_mapping=mapping,
                corrected_mapping=corrected,
                timestamp="2026-02-27T12:00:00+00:00",
            )

    def test_skipped_no_correction_fields(self) -> None:
        mapping = _make_variable_mapping()
        decision = ReviewDecision(
            sdtm_variable="STUDYID",
            status=ReviewStatus.SKIPPED,
            original_mapping=mapping,
            timestamp="2026-02-27T12:00:00+00:00",
        )
        assert decision.status == ReviewStatus.SKIPPED
        assert decision.correction_type is None


# ---------------------------------------------------------------------------
# HumanCorrection tests
# ---------------------------------------------------------------------------


class TestHumanCorrection:
    """Tests for HumanCorrection model."""

    def test_roundtrip_serialization(self) -> None:
        original = _make_variable_mapping("AEDECOD", pattern=MappingPattern.DIRECT)
        corrected = _make_variable_mapping(
            "AEDECOD",
            pattern=MappingPattern.DERIVATION,
            source_dataset="ae",
            source_variable="AE_PTERM",
            mapping_logic="Use AE_PTERM for preferred term",
            confidence=0.90,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Reviewer correction",
            assigned_value=None,
        )
        correction = HumanCorrection(
            session_id="abc123def456",
            domain="AE",
            sdtm_variable="AEDECOD",
            correction_type=CorrectionType.SOURCE_CHANGE,
            original_mapping=original,
            corrected_mapping=corrected,
            reason="AEDECOD should come from AE_PTERM, not AETERM",
            reviewer="test_user",
            timestamp="2026-02-27T12:00:00+00:00",
        )

        json_str = correction.model_dump_json()
        restored = HumanCorrection.model_validate_json(json_str)

        assert restored.session_id == correction.session_id
        assert restored.domain == correction.domain
        assert restored.sdtm_variable == correction.sdtm_variable
        assert restored.correction_type == CorrectionType.SOURCE_CHANGE
        assert restored.original_mapping.sdtm_variable == "AEDECOD"
        assert restored.corrected_mapping is not None
        assert restored.corrected_mapping.source_variable == "AE_PTERM"
        assert restored.reason == correction.reason
        assert restored.reviewer == "test_user"

    def test_reject_no_corrected_mapping(self) -> None:
        original = _make_variable_mapping("AEGRPID")
        correction = HumanCorrection(
            session_id="abc123def456",
            domain="AE",
            sdtm_variable="AEGRPID",
            correction_type=CorrectionType.REJECT,
            original_mapping=original,
            corrected_mapping=None,
            reason="Not applicable for this study",
            timestamp="2026-02-27T12:00:00+00:00",
        )
        assert correction.corrected_mapping is None
        assert correction.correction_type == CorrectionType.REJECT


# ---------------------------------------------------------------------------
# DomainReview tests
# ---------------------------------------------------------------------------


class TestDomainReview:
    """Tests for DomainReview model."""

    def test_creation_with_spec(self) -> None:
        spec = _make_domain_spec()
        review = DomainReview(domain="DM", original_spec=spec)
        assert review.domain == "DM"
        assert review.status == DomainReviewStatus.PENDING
        assert review.decisions == {}
        assert review.corrections == []
        assert review.reviewed_spec is None
        assert review.reviewed_at is None

    def test_original_spec_preserved(self) -> None:
        spec = _make_domain_spec()
        review = DomainReview(domain="DM", original_spec=spec)
        assert len(review.original_spec.variable_mappings) == 3
        assert review.original_spec.domain == "DM"


# ---------------------------------------------------------------------------
# ReviewSession tests
# ---------------------------------------------------------------------------


class TestReviewSession:
    """Tests for ReviewSession model."""

    def test_creation_with_defaults(self) -> None:
        session = ReviewSession(
            session_id="abc123def456",
            study_id="PHA022121-C301",
            created_at="2026-02-27T12:00:00+00:00",
            updated_at="2026-02-27T12:00:00+00:00",
            domains=["DM", "AE", "LB"],
        )
        assert session.session_id == "abc123def456"
        assert session.study_id == "PHA022121-C301"
        assert session.status == SessionStatus.IN_PROGRESS
        assert session.current_domain_index == 0
        assert session.domain_reviews == {}
        assert len(session.domains) == 3

    def test_serialization_roundtrip(self) -> None:
        spec = _make_domain_spec()
        review = DomainReview(domain="DM", original_spec=spec)
        session = ReviewSession(
            session_id="abc123def456",
            study_id="PHA022121-C301",
            created_at="2026-02-27T12:00:00+00:00",
            updated_at="2026-02-27T12:00:00+00:00",
            domains=["DM"],
            domain_reviews={"DM": review},
        )

        json_str = session.model_dump_json()
        restored = ReviewSession.model_validate_json(json_str)

        assert restored.session_id == "abc123def456"
        assert "DM" in restored.domain_reviews
        assert restored.domain_reviews["DM"].original_spec.domain == "DM"
