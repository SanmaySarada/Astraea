"""Tests for the core reviewer logic."""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from rich.console import Console

from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation
from astraea.review.models import (
    CorrectionType,
    DomainReviewStatus,
    ReviewStatus,
)
from astraea.review.reviewer import DomainReviewer, ReviewInterrupted
from astraea.review.session import SessionStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_variable_mapping(
    variable: str = "STUDYID",
    pattern: MappingPattern = MappingPattern.ASSIGN,
    confidence: float = 0.95,
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH,
    core: CoreDesignation = CoreDesignation.REQ,
    **overrides: object,
) -> VariableMapping:
    """Create a minimal valid VariableMapping for testing."""
    defaults: dict[str, object] = {
        "sdtm_variable": variable,
        "sdtm_label": f"Label for {variable}",
        "sdtm_data_type": "Char",
        "core": core,
        "mapping_pattern": pattern,
        "mapping_logic": f"Assign {variable}",
        "assigned_value": "PHA022121-C301" if pattern == MappingPattern.ASSIGN else None,
        "confidence": confidence,
        "confidence_level": confidence_level,
        "confidence_rationale": "Standard assignment",
    }
    defaults.update(overrides)
    return VariableMapping(**defaults)  # type: ignore[arg-type]


def _make_mixed_spec() -> DomainMappingSpec:
    """Create a spec with 3 HIGH, 2 MEDIUM, 1 LOW variable mappings."""
    mappings = [
        # 3 HIGH confidence
        _make_variable_mapping("STUDYID", confidence=0.95, confidence_level=ConfidenceLevel.HIGH),
        _make_variable_mapping(
            "DOMAIN", confidence=0.95, confidence_level=ConfidenceLevel.HIGH,
            assigned_value="AE",
        ),
        _make_variable_mapping(
            "USUBJID",
            pattern=MappingPattern.DERIVATION,
            confidence=0.90,
            confidence_level=ConfidenceLevel.HIGH,
            assigned_value=None,
            source_dataset="ae",
            source_variable="SUBJID",
            mapping_logic="STUDYID + SITEID + SUBJID",
        ),
        # 2 MEDIUM confidence
        _make_variable_mapping(
            "AETERM",
            pattern=MappingPattern.DIRECT,
            confidence=0.70,
            confidence_level=ConfidenceLevel.MEDIUM,
            core=CoreDesignation.EXP,
            assigned_value=None,
            source_dataset="ae",
            source_variable="AETERM",
            mapping_logic="Direct carry",
        ),
        _make_variable_mapping(
            "AESTDTC",
            pattern=MappingPattern.REFORMAT,
            confidence=0.65,
            confidence_level=ConfidenceLevel.MEDIUM,
            core=CoreDesignation.EXP,
            assigned_value=None,
            source_dataset="ae",
            source_variable="AESTDT",
            mapping_logic="ISO 8601 conversion",
        ),
        # 1 LOW confidence
        _make_variable_mapping(
            "AEDECOD",
            pattern=MappingPattern.DERIVATION,
            confidence=0.40,
            confidence_level=ConfidenceLevel.LOW,
            core=CoreDesignation.PERM,
            assigned_value=None,
            source_dataset="ae",
            source_variable="AETERM",
            mapping_logic="MedDRA preferred term",
            codelist_code="C66729",
            codelist_name="MedDRA",
        ),
    ]
    return DomainMappingSpec(
        domain="AE",
        domain_label="Adverse Events",
        domain_class="Events",
        structure="One record per event",
        study_id="PHA022121-C301",
        source_datasets=["ae"],
        variable_mappings=mappings,
        total_variables=6,
        required_mapped=3,
        expected_mapped=2,
        high_confidence_count=3,
        medium_confidence_count=2,
        low_confidence_count=1,
        mapping_timestamp="2026-02-27T12:00:00+00:00",
        model_used="claude-sonnet-4-20250514",
    )


def _make_input_callback(responses: list[str]) -> tuple[list[str], object]:
    """Create an input_callback that returns responses in order.

    Returns:
        Tuple of (responses list for tracking, callback function).
    """
    it: Iterator[str] = iter(responses)

    def callback(message: str, choices: list[str], default: str) -> str:
        try:
            return next(it)
        except StopIteration:
            return default

    return responses, callback


@pytest.fixture()
def store(tmp_path: Path) -> SessionStore:
    """Create a SessionStore with a temporary database."""
    s = SessionStore(tmp_path / "test_review.db")
    yield s  # type: ignore[misc]
    s.close()


@pytest.fixture()
def console() -> Console:
    """Console that captures output to StringIO."""
    return Console(file=io.StringIO(), force_terminal=True, width=120)


@pytest.fixture()
def mixed_spec() -> DomainMappingSpec:
    return _make_mixed_spec()


@pytest.fixture()
def session_with_ae(
    store: SessionStore, mixed_spec: DomainMappingSpec
) -> str:
    """Create a session with AE domain and return session_id."""
    session = store.create_session(
        study_id="PHA022121-C301",
        domains=["AE"],
        specs={"AE": mixed_spec},
    )
    return session.session_id


# ---------------------------------------------------------------------------
# Approve-all tests
# ---------------------------------------------------------------------------


class TestApproveAll:
    """Tests for the approve-all flow."""

    def test_all_variables_approved(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        _, callback = _make_input_callback(["approve-all"])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        result = reviewer.review_domain(session_with_ae, "AE")

        assert result.status == DomainReviewStatus.COMPLETED
        assert len(result.decisions) == 6
        for decision in result.decisions.values():
            assert decision.status == ReviewStatus.APPROVED

    def test_state_persisted_after_approve_all(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        _, callback = _make_input_callback(["approve-all"])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        reviewer.review_domain(session_with_ae, "AE")

        # Reload from store
        loaded = store.load_session(session_with_ae)
        review = loaded.domain_reviews["AE"]
        assert review.status == DomainReviewStatus.COMPLETED
        assert len(review.decisions) == 6


# ---------------------------------------------------------------------------
# Two-tier review tests
# ---------------------------------------------------------------------------


class TestTwoTierReview:
    """Tests for the two-tier review flow."""

    def test_batch_approve_high_then_individual(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        # Action: review -> batch approve HIGH (y) -> approve each remaining (a, a, a)
        _, callback = _make_input_callback([
            "review",  # main action
            "y",       # batch approve HIGH
            "a",       # approve AETERM
            "a",       # approve AESTDTC
            "a",       # approve AEDECOD
        ])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        result = reviewer.review_domain(session_with_ae, "AE")

        assert result.status == DomainReviewStatus.COMPLETED
        assert len(result.decisions) == 6
        # All HIGH should be approved
        assert result.decisions["STUDYID"].status == ReviewStatus.APPROVED
        assert result.decisions["DOMAIN"].status == ReviewStatus.APPROVED
        assert result.decisions["USUBJID"].status == ReviewStatus.APPROVED
        # MEDIUM/LOW individually approved
        assert result.decisions["AETERM"].status == ReviewStatus.APPROVED
        assert result.decisions["AESTDTC"].status == ReviewStatus.APPROVED
        assert result.decisions["AEDECOD"].status == ReviewStatus.APPROVED

    def test_decline_batch_reviews_all_individually(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        # Decline batch, then approve all 6 individually
        _, callback = _make_input_callback([
            "review",  # main action
            "n",       # decline batch
            "a", "a", "a",  # HIGH variables
            "a", "a", "a",  # MEDIUM/LOW variables
        ])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        result = reviewer.review_domain(session_with_ae, "AE")

        assert result.status == DomainReviewStatus.COMPLETED
        assert len(result.decisions) == 6
        for decision in result.decisions.values():
            assert decision.status == ReviewStatus.APPROVED


# ---------------------------------------------------------------------------
# Correction tests
# ---------------------------------------------------------------------------


class TestCorrection:
    """Tests for the correction flow."""

    def test_source_change_correction(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        _, callback = _make_input_callback([
            "review",       # main action
            "y",            # batch approve HIGH
            "c",            # correct AETERM
            "s",            # source change
            "AE_PTERM",     # new source
            "Wrong source", # reason
            "a",            # approve AESTDTC
            "a",            # approve AEDECOD
        ])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        result = reviewer.review_domain(session_with_ae, "AE")

        assert result.status == DomainReviewStatus.COMPLETED
        assert result.decisions["AETERM"].status == ReviewStatus.CORRECTED
        assert result.decisions["AETERM"].correction_type == CorrectionType.SOURCE_CHANGE
        assert result.decisions["AETERM"].corrected_mapping is not None
        assert result.decisions["AETERM"].corrected_mapping.source_variable == "AE_PTERM"
        assert result.decisions["AETERM"].corrected_mapping.confidence == 1.0
        assert result.decisions["AETERM"].corrected_mapping.confidence_level == ConfidenceLevel.HIGH
        assert result.decisions["AETERM"].reason == "Wrong source"

    def test_correction_saved_to_corrections_list(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        _, callback = _make_input_callback([
            "review",
            "y",
            "c", "s", "AE_PTERM", "Wrong source",
            "a", "a",
        ])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        result = reviewer.review_domain(session_with_ae, "AE")

        assert len(result.corrections) == 1
        assert result.corrections[0].sdtm_variable == "AETERM"
        assert result.corrections[0].correction_type == CorrectionType.SOURCE_CHANGE

    def test_correction_persisted_in_store(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        _, callback = _make_input_callback([
            "review",
            "y",
            "c", "s", "AE_PTERM", "Wrong source",
            "a", "a",
        ])
        reviewer = DomainReviewer(store, console, input_callback=callback)
        reviewer.review_domain(session_with_ae, "AE")

        # Reload from store
        loaded = store.load_session(session_with_ae)
        review = loaded.domain_reviews["AE"]
        assert len(review.corrections) == 1
        assert review.corrections[0].sdtm_variable == "AETERM"


# ---------------------------------------------------------------------------
# Reject tests
# ---------------------------------------------------------------------------


class TestReject:
    """Tests for the reject flow."""

    def test_reject_creates_correction_with_no_mapping(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        _, callback = _make_input_callback([
            "review",
            "y",           # batch approve HIGH
            "c",           # correct AETERM
            "r",           # reject
            "Not needed",  # reason
            "a", "a",      # approve rest
        ])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        result = reviewer.review_domain(session_with_ae, "AE")

        decision = result.decisions["AETERM"]
        assert decision.status == ReviewStatus.CORRECTED
        assert decision.correction_type == CorrectionType.REJECT
        assert decision.corrected_mapping is None
        assert decision.reason == "Not needed"


# ---------------------------------------------------------------------------
# Skip tests
# ---------------------------------------------------------------------------


class TestSkip:
    """Tests for skip flows."""

    def test_skip_domain(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        _, callback = _make_input_callback(["skip"])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        result = reviewer.review_domain(session_with_ae, "AE")

        assert result.status == DomainReviewStatus.SKIPPED
        assert len(result.decisions) == 0

    def test_skip_individual_variable(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        _, callback = _make_input_callback([
            "review",
            "y",   # batch approve HIGH
            "s",   # skip AETERM
            "a",   # approve AESTDTC
            "a",   # approve AEDECOD
        ])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        result = reviewer.review_domain(session_with_ae, "AE")

        assert result.decisions["AETERM"].status == ReviewStatus.SKIPPED
        assert result.decisions["AESTDTC"].status == ReviewStatus.APPROVED


# ---------------------------------------------------------------------------
# Quit tests
# ---------------------------------------------------------------------------


class TestQuit:
    """Tests for quit/interrupt flow."""

    def test_quit_raises_review_interrupted(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        _, callback = _make_input_callback(["quit"])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        with pytest.raises(ReviewInterrupted) as exc_info:
            reviewer.review_domain(session_with_ae, "AE")

        assert exc_info.value.session_id == session_with_ae

    def test_quit_saves_state(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        _, callback = _make_input_callback(["quit"])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        with pytest.raises(ReviewInterrupted):
            reviewer.review_domain(session_with_ae, "AE")

        # State should be saved
        loaded = store.load_session(session_with_ae)
        review = loaded.domain_reviews["AE"]
        assert review.status == DomainReviewStatus.IN_PROGRESS

    def test_quit_mid_review_saves_partial_progress(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        _, callback = _make_input_callback([
            "review",
            "y",   # batch approve HIGH
            "a",   # approve AETERM
            "q",   # quit on AESTDTC
        ])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        with pytest.raises(ReviewInterrupted):
            reviewer.review_domain(session_with_ae, "AE")

        # Reload and check partial progress
        loaded = store.load_session(session_with_ae)
        review = loaded.domain_reviews["AE"]
        # 3 HIGH + 1 AETERM = 4 decided
        assert len(review.decisions) == 4
        assert "STUDYID" in review.decisions
        assert "AETERM" in review.decisions
        assert "AESTDTC" not in review.decisions


# ---------------------------------------------------------------------------
# Resume tests
# ---------------------------------------------------------------------------


class TestResume:
    """Tests for resume after interruption."""

    def test_resume_skips_already_reviewed(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        # First pass: approve HIGH, approve AETERM, quit
        _, callback1 = _make_input_callback([
            "review",
            "y",   # batch HIGH
            "a",   # approve AETERM
            "q",   # quit
        ])
        reviewer1 = DomainReviewer(store, console, input_callback=callback1)
        with pytest.raises(ReviewInterrupted):
            reviewer1.review_domain(session_with_ae, "AE")

        # Second pass: should only see AESTDTC and AEDECOD
        _, callback2 = _make_input_callback([
            "review",
            # No batch prompt (no HIGH pending)
            "a",   # approve AESTDTC
            "a",   # approve AEDECOD
        ])
        console2 = Console(file=io.StringIO(), force_terminal=True, width=120)
        reviewer2 = DomainReviewer(store, console2, input_callback=callback2)
        result = reviewer2.review_domain(session_with_ae, "AE")

        assert result.status == DomainReviewStatus.COMPLETED
        assert len(result.decisions) == 6

    def test_resume_already_completed_domain(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        # Complete the domain
        _, callback1 = _make_input_callback(["approve-all"])
        reviewer1 = DomainReviewer(store, console, input_callback=callback1)
        reviewer1.review_domain(session_with_ae, "AE")

        # Resume should immediately return completed
        console2 = Console(file=io.StringIO(), force_terminal=True, width=120)
        # No input needed - should short-circuit
        _, callback2 = _make_input_callback([])
        reviewer2 = DomainReviewer(store, console2, input_callback=callback2)
        result = reviewer2.review_domain(session_with_ae, "AE")

        assert result.status == DomainReviewStatus.COMPLETED
        assert len(result.decisions) == 6


# ---------------------------------------------------------------------------
# Logic change correction test
# ---------------------------------------------------------------------------


class TestLogicChange:
    """Tests for the logic change correction flow."""

    def test_logic_change_keeps_original_mapping(
        self,
        store: SessionStore,
        console: Console,
        session_with_ae: str,
    ) -> None:
        _, callback = _make_input_callback([
            "review",
            "y",                    # batch approve HIGH
            "c",                    # correct AETERM
            "o",                    # other/logic change
            "Need partial dates",   # reason
            "a", "a",              # approve rest
        ])
        reviewer = DomainReviewer(store, console, input_callback=callback)

        result = reviewer.review_domain(session_with_ae, "AE")

        decision = result.decisions["AETERM"]
        assert decision.status == ReviewStatus.CORRECTED
        assert decision.correction_type == CorrectionType.LOGIC_CHANGE
        # Logic change returns original mapping unchanged
        assert decision.corrected_mapping is not None
        assert decision.corrected_mapping.source_variable == "AETERM"
        assert decision.reason == "Need partial dates"
