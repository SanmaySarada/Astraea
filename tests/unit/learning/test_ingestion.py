"""Tests for the review-to-learning ingestion pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from astraea.learning.example_store import ExampleStore
from astraea.learning.ingestion import ingest_domain_review, ingest_session
from astraea.learning.vector_store import LearningVectorStore
from astraea.models.mapping import (
    ConfidenceLevel,
    CoreDesignation,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)
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


def _make_mapping(var_name: str, pattern: MappingPattern = MappingPattern.DIRECT) -> VariableMapping:
    """Create a minimal VariableMapping."""
    return VariableMapping(
        sdtm_variable=var_name,
        sdtm_label=f"Label for {var_name}",
        sdtm_data_type="Char",
        core=CoreDesignation.REQ,
        mapping_pattern=pattern,
        mapping_logic=f"Direct carry of {var_name}",
        source_variable=var_name.lower(),
        source_dataset="ae.sas7bdat",
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="High confidence",
    )


def _make_spec(
    domain: str, variables: list[str], study_id: str = "STUDY-001"
) -> DomainMappingSpec:
    """Create a minimal DomainMappingSpec."""
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
    """Create a ReviewDecision."""
    original = _make_mapping(var_name)
    corrected = None
    if status == ReviewStatus.CORRECTED and correction_type != CorrectionType.REJECT:
        corrected = _make_mapping(var_name, MappingPattern.RENAME)
        corrected = corrected.model_copy(
            update={"mapping_logic": "Corrected logic"}
        )
    return ReviewDecision(
        sdtm_variable=var_name,
        status=status,
        correction_type=correction_type,
        original_mapping=original,
        corrected_mapping=corrected,
        reason="Corrected for accuracy" if status == ReviewStatus.CORRECTED else "",
        timestamp="2026-02-28T10:00:00+00:00",
    )


def _make_correction(
    var_name: str,
    correction_type: CorrectionType = CorrectionType.SOURCE_CHANGE,
    session_id: str = "sess123",
) -> HumanCorrection:
    """Create a HumanCorrection."""
    original = _make_mapping(var_name)
    corrected = None
    if correction_type != CorrectionType.REJECT:
        corrected = _make_mapping(var_name, MappingPattern.RENAME)
        corrected = corrected.model_copy(
            update={"mapping_logic": "Corrected logic"}
        )
    return HumanCorrection(
        session_id=session_id,
        domain="AE",
        sdtm_variable=var_name,
        correction_type=correction_type,
        original_mapping=original,
        corrected_mapping=corrected,
        reason="Fixed source variable",
        reviewer="tester",
        timestamp="2026-02-28T10:00:00+00:00",
    )


@pytest.fixture()
def stores(tmp_path: Path) -> tuple[ExampleStore, LearningVectorStore]:
    """Create real SQLite and ChromaDB stores in tmp_path."""
    example_store = ExampleStore(tmp_path / "learning.db")
    vector_store = LearningVectorStore(tmp_path / "chromadb")
    yield example_store, vector_store
    example_store.close()
    vector_store.close()


class TestIngestDomainReview:
    """Tests for ingest_domain_review."""

    def test_approved_and_corrected_mappings(
        self, stores: tuple[ExampleStore, LearningVectorStore]
    ) -> None:
        """3 approved + 1 corrected -> 4 examples + 1 correction stored."""
        example_store, vector_store = stores
        variables = ["AETERM", "AEDECOD", "AESTDTC", "AEENDTC"]
        spec = _make_spec("AE", variables)

        review = DomainReview(
            domain="AE",
            status=DomainReviewStatus.COMPLETED,
            original_spec=spec,
            decisions={
                "AETERM": _make_decision("AETERM", ReviewStatus.APPROVED),
                "AEDECOD": _make_decision(
                    "AEDECOD", ReviewStatus.CORRECTED, CorrectionType.SOURCE_CHANGE
                ),
                "AESTDTC": _make_decision("AESTDTC", ReviewStatus.APPROVED),
                "AEENDTC": _make_decision("AEENDTC", ReviewStatus.APPROVED),
            },
            corrections=[
                _make_correction("AEDECOD", CorrectionType.SOURCE_CHANGE),
            ],
            reviewed_at="2026-02-28T10:00:00+00:00",
        )

        count = ingest_domain_review(
            review, "STUDY-001", example_store, vector_store, session_id="sess123"
        )

        assert count == 5  # 4 examples + 1 correction
        assert example_store.get_example_count() == 4
        assert example_store.get_correction_count() == 1

        # Verify vector store counts
        counts = vector_store.get_collection_counts()
        assert counts["approved_mappings"] == 4
        assert counts["corrections"] == 1

    def test_was_corrected_flag_set(
        self, stores: tuple[ExampleStore, LearningVectorStore]
    ) -> None:
        """was_corrected flag is True only for corrected variables."""
        example_store, vector_store = stores
        spec = _make_spec("AE", ["AETERM", "AEDECOD"])

        review = DomainReview(
            domain="AE",
            status=DomainReviewStatus.COMPLETED,
            original_spec=spec,
            decisions={
                "AETERM": _make_decision("AETERM", ReviewStatus.APPROVED),
                "AEDECOD": _make_decision(
                    "AEDECOD", ReviewStatus.CORRECTED, CorrectionType.LOGIC_CHANGE
                ),
            },
            corrections=[],
            reviewed_at="2026-02-28T10:00:00+00:00",
        )

        ingest_domain_review(
            review, "STUDY-001", example_store, vector_store
        )

        examples = example_store.get_examples_for_domain("AE")
        by_var = {e.sdtm_variable: e for e in examples}

        assert by_var["AETERM"].was_corrected is False
        assert by_var["AEDECOD"].was_corrected is True

    def test_idempotent_ingestion(
        self, stores: tuple[ExampleStore, LearningVectorStore]
    ) -> None:
        """Calling ingest twice does not create duplicates."""
        example_store, vector_store = stores
        spec = _make_spec("AE", ["AETERM", "AEDECOD"])

        review = DomainReview(
            domain="AE",
            status=DomainReviewStatus.COMPLETED,
            original_spec=spec,
            decisions={
                "AETERM": _make_decision("AETERM", ReviewStatus.APPROVED),
                "AEDECOD": _make_decision("AEDECOD", ReviewStatus.APPROVED),
            },
            corrections=[],
            reviewed_at="2026-02-28T10:00:00+00:00",
        )

        # Ingest twice
        ingest_domain_review(
            review, "STUDY-001", example_store, vector_store, session_id="sess123"
        )
        ingest_domain_review(
            review, "STUDY-001", example_store, vector_store, session_id="sess123"
        )

        # Should still have only 2 examples (not 4)
        assert example_store.get_example_count() == 2
        counts = vector_store.get_collection_counts()
        assert counts["approved_mappings"] == 2

    def test_all_approved_no_corrections(
        self, stores: tuple[ExampleStore, LearningVectorStore]
    ) -> None:
        """All approved, no corrections -> examples stored, zero corrections."""
        example_store, vector_store = stores
        spec = _make_spec("DM", ["STUDYID", "USUBJID"])

        review = DomainReview(
            domain="DM",
            status=DomainReviewStatus.COMPLETED,
            original_spec=spec,
            decisions={
                "STUDYID": _make_decision("STUDYID", ReviewStatus.APPROVED),
                "USUBJID": _make_decision("USUBJID", ReviewStatus.APPROVED),
            },
            corrections=[],
            reviewed_at="2026-02-28T10:00:00+00:00",
        )

        count = ingest_domain_review(
            review, "STUDY-001", example_store, vector_store
        )

        assert count == 2
        assert example_store.get_example_count() == 2
        assert example_store.get_correction_count() == 0


class TestIngestSession:
    """Tests for ingest_session."""

    def test_processes_multiple_domains(
        self, stores: tuple[ExampleStore, LearningVectorStore]
    ) -> None:
        """Session with two completed domains ingests both."""
        example_store, vector_store = stores

        ae_spec = _make_spec("AE", ["AETERM", "AEDECOD"])
        dm_spec = _make_spec("DM", ["STUDYID", "USUBJID"])

        session = ReviewSession(
            session_id="sess456",
            study_id="STUDY-001",
            created_at="2026-02-28T09:00:00+00:00",
            updated_at="2026-02-28T10:00:00+00:00",
            status=SessionStatus.COMPLETED,
            domains=["AE", "DM"],
            domain_reviews={
                "AE": DomainReview(
                    domain="AE",
                    status=DomainReviewStatus.COMPLETED,
                    original_spec=ae_spec,
                    decisions={
                        "AETERM": _make_decision("AETERM", ReviewStatus.APPROVED),
                        "AEDECOD": _make_decision("AEDECOD", ReviewStatus.APPROVED),
                    },
                    corrections=[],
                    reviewed_at="2026-02-28T10:00:00+00:00",
                ),
                "DM": DomainReview(
                    domain="DM",
                    status=DomainReviewStatus.COMPLETED,
                    original_spec=dm_spec,
                    decisions={
                        "STUDYID": _make_decision("STUDYID", ReviewStatus.APPROVED),
                        "USUBJID": _make_decision("USUBJID", ReviewStatus.APPROVED),
                    },
                    corrections=[],
                    reviewed_at="2026-02-28T10:00:00+00:00",
                ),
            },
        )

        result = ingest_session(session, example_store, vector_store)

        assert result["total_examples"] == 4
        assert result["total_corrections"] == 0
        assert sorted(result["domains_ingested"]) == ["AE", "DM"]

    def test_computes_and_stores_metrics(
        self, stores: tuple[ExampleStore, LearningVectorStore]
    ) -> None:
        """Session ingestion computes and saves StudyMetrics."""
        example_store, vector_store = stores

        spec = _make_spec("AE", ["AETERM", "AEDECOD", "AESTDTC"])

        session = ReviewSession(
            session_id="sess789",
            study_id="STUDY-001",
            created_at="2026-02-28T09:00:00+00:00",
            updated_at="2026-02-28T10:00:00+00:00",
            status=SessionStatus.COMPLETED,
            domains=["AE"],
            domain_reviews={
                "AE": DomainReview(
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
                        "AESTDTC": _make_decision("AESTDTC", ReviewStatus.APPROVED),
                    },
                    corrections=[
                        _make_correction("AEDECOD", session_id="sess789"),
                    ],
                    reviewed_at="2026-02-28T10:00:00+00:00",
                ),
            },
        )

        ingest_session(session, example_store, vector_store)

        # Verify metrics were saved
        metrics = example_store.get_study_metrics("STUDY-001")
        assert len(metrics) == 1
        assert metrics[0].domain == "AE"
        assert metrics[0].approved_unchanged == 2
        assert metrics[0].corrected == 1
        assert metrics[0].accuracy_rate == pytest.approx(2.0 / 3.0)

    def test_skips_non_completed_domains(
        self, stores: tuple[ExampleStore, LearningVectorStore]
    ) -> None:
        """Non-completed domains are skipped during ingestion."""
        example_store, vector_store = stores

        ae_spec = _make_spec("AE", ["AETERM"])
        dm_spec = _make_spec("DM", ["STUDYID"])

        session = ReviewSession(
            session_id="sess101",
            study_id="STUDY-001",
            created_at="2026-02-28T09:00:00+00:00",
            updated_at="2026-02-28T10:00:00+00:00",
            status=SessionStatus.IN_PROGRESS,
            domains=["AE", "DM"],
            domain_reviews={
                "AE": DomainReview(
                    domain="AE",
                    status=DomainReviewStatus.COMPLETED,
                    original_spec=ae_spec,
                    decisions={
                        "AETERM": _make_decision("AETERM", ReviewStatus.APPROVED),
                    },
                    corrections=[],
                    reviewed_at="2026-02-28T10:00:00+00:00",
                ),
                "DM": DomainReview(
                    domain="DM",
                    status=DomainReviewStatus.PENDING,
                    original_spec=dm_spec,
                ),
            },
        )

        result = ingest_session(session, example_store, vector_store)

        assert result["total_examples"] == 1
        assert result["domains_ingested"] == ["AE"]
