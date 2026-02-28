"""Tests for SQLite-backed session persistence."""

from __future__ import annotations

from pathlib import Path

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
    DomainReviewStatus,
    HumanCorrection,
    ReviewDecision,
    ReviewStatus,
    SessionStatus,
)
from astraea.review.session import SessionStore

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
        _make_variable_mapping("DOMAIN", assigned_value=domain),
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
        domain_label="Demographics" if domain == "DM" else f"{domain} Domain",
        domain_class="Special Purpose" if domain == "DM" else "Events",
        structure="One record per subject",
        study_id="PHA022121-C301",
        source_datasets=[domain.lower()],
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


@pytest.fixture()
def store(tmp_path: Path) -> SessionStore:
    """Create a SessionStore with a temporary database."""
    s = SessionStore(tmp_path / "test_sessions.db")
    yield s  # type: ignore[misc]
    s.close()


@pytest.fixture()
def dm_spec() -> DomainMappingSpec:
    return _make_domain_spec("DM")


@pytest.fixture()
def ae_spec() -> DomainMappingSpec:
    return _make_domain_spec("AE")


# ---------------------------------------------------------------------------
# create_session tests
# ---------------------------------------------------------------------------


class TestCreateSession:
    """Tests for SessionStore.create_session."""

    def test_returns_valid_session(self, store: SessionStore, dm_spec: DomainMappingSpec) -> None:
        session = store.create_session(
            study_id="PHA022121-C301",
            domains=["DM"],
            specs={"DM": dm_spec},
        )
        assert len(session.session_id) == 12
        assert all(c in "0123456789abcdef" for c in session.session_id)
        assert session.study_id == "PHA022121-C301"
        assert session.status == SessionStatus.IN_PROGRESS
        assert session.domains == ["DM"]
        assert session.current_domain_index == 0
        assert "DM" in session.domain_reviews

    def test_domain_reviews_initialized_pending(
        self, store: SessionStore, dm_spec: DomainMappingSpec
    ) -> None:
        session = store.create_session(
            study_id="PHA022121-C301",
            domains=["DM"],
            specs={"DM": dm_spec},
        )
        review = session.domain_reviews["DM"]
        assert review.status == DomainReviewStatus.PENDING
        assert review.decisions == {}
        assert review.corrections == []
        assert review.reviewed_spec is None

    def test_missing_spec_raises(self, store: SessionStore) -> None:
        with pytest.raises(ValueError, match="No spec provided for domain 'DM'"):
            store.create_session(
                study_id="PHA022121-C301",
                domains=["DM"],
                specs={},
            )


# ---------------------------------------------------------------------------
# save_session + load_session round-trip tests
# ---------------------------------------------------------------------------


class TestSaveLoadSession:
    """Tests for save_session and load_session round-trip."""

    def test_basic_roundtrip(self, store: SessionStore, dm_spec: DomainMappingSpec) -> None:
        session = store.create_session(
            study_id="PHA022121-C301",
            domains=["DM"],
            specs={"DM": dm_spec},
        )

        # Modify session state
        session.current_domain_index = 1
        session.status = SessionStatus.COMPLETED
        store.save_session(session)

        # Load and verify
        loaded = store.load_session(session.session_id)
        assert loaded.session_id == session.session_id
        assert loaded.study_id == "PHA022121-C301"
        assert loaded.status == SessionStatus.COMPLETED
        assert loaded.current_domain_index == 1
        assert loaded.domains == ["DM"]

    def test_domain_reviews_roundtrip(
        self,
        store: SessionStore,
        dm_spec: DomainMappingSpec,
        ae_spec: DomainMappingSpec,
    ) -> None:
        session = store.create_session(
            study_id="PHA022121-C301",
            domains=["DM", "AE"],
            specs={"DM": dm_spec, "AE": ae_spec},
        )

        loaded = store.load_session(session.session_id)
        assert "DM" in loaded.domain_reviews
        assert "AE" in loaded.domain_reviews
        assert loaded.domain_reviews["DM"].original_spec.domain == "DM"
        assert loaded.domain_reviews["AE"].original_spec.domain == "AE"
        assert len(loaded.domain_reviews["DM"].original_spec.variable_mappings) == 3

    def test_load_unknown_session_raises(self, store: SessionStore) -> None:
        with pytest.raises(ValueError, match="Session 'nonexistent' not found"):
            store.load_session("nonexistent")


# ---------------------------------------------------------------------------
# save_domain_review tests
# ---------------------------------------------------------------------------


class TestSaveDomainReview:
    """Tests for save_domain_review."""

    def test_updates_domain_review(self, store: SessionStore, dm_spec: DomainMappingSpec) -> None:
        session = store.create_session(
            study_id="PHA022121-C301",
            domains=["DM"],
            specs={"DM": dm_spec},
        )

        # Update domain review with a decision
        mapping = dm_spec.variable_mappings[0]
        decision = ReviewDecision(
            sdtm_variable="STUDYID",
            status=ReviewStatus.APPROVED,
            original_mapping=mapping,
            timestamp="2026-02-27T13:00:00+00:00",
        )
        review = session.domain_reviews["DM"]
        review.status = DomainReviewStatus.IN_PROGRESS
        review.decisions["STUDYID"] = decision

        store.save_domain_review(session.session_id, review)

        # Reload and verify
        loaded = store.load_session(session.session_id)
        loaded_review = loaded.domain_reviews["DM"]
        assert loaded_review.status == DomainReviewStatus.IN_PROGRESS
        assert "STUDYID" in loaded_review.decisions
        assert loaded_review.decisions["STUDYID"].status == ReviewStatus.APPROVED


# ---------------------------------------------------------------------------
# save_correction tests
# ---------------------------------------------------------------------------


class TestSaveCorrection:
    """Tests for save_correction."""

    def test_correction_persisted(self, store: SessionStore, dm_spec: DomainMappingSpec) -> None:
        session = store.create_session(
            study_id="PHA022121-C301",
            domains=["DM"],
            specs={"DM": dm_spec},
        )

        original = dm_spec.variable_mappings[2]  # USUBJID
        corrected = _make_variable_mapping(
            "USUBJID",
            pattern=MappingPattern.DERIVATION,
            assigned_value=None,
            source_dataset="dm",
            source_variable="SUBJID",
            mapping_logic="STUDYID + '-' + SITEID + '-' + SUBJID",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Corrected by reviewer",
        )

        correction = HumanCorrection(
            session_id=session.session_id,
            domain="DM",
            sdtm_variable="USUBJID",
            correction_type=CorrectionType.LOGIC_CHANGE,
            original_mapping=original,
            corrected_mapping=corrected,
            reason="Need hyphens as separator",
            reviewer="test_user",
            timestamp="2026-02-27T13:00:00+00:00",
        )
        store.save_correction(correction)

        # Also update domain review with correction
        review = session.domain_reviews["DM"]
        review.corrections.append(correction)
        store.save_domain_review(session.session_id, review)

        # Reload and verify correction is in domain review
        loaded = store.load_session(session.session_id)
        loaded_corrections = loaded.domain_reviews["DM"].corrections
        assert len(loaded_corrections) == 1
        assert loaded_corrections[0].sdtm_variable == "USUBJID"
        assert loaded_corrections[0].correction_type == CorrectionType.LOGIC_CHANGE
        assert loaded_corrections[0].reason == "Need hyphens as separator"

    def test_correction_in_corrections_table(
        self, store: SessionStore, dm_spec: DomainMappingSpec
    ) -> None:
        session = store.create_session(
            study_id="PHA022121-C301",
            domains=["DM"],
            specs={"DM": dm_spec},
        )

        correction = HumanCorrection(
            session_id=session.session_id,
            domain="DM",
            sdtm_variable="STUDYID",
            correction_type=CorrectionType.REJECT,
            original_mapping=dm_spec.variable_mappings[0],
            corrected_mapping=None,
            reason="Not needed",
            timestamp="2026-02-27T13:00:00+00:00",
        )
        store.save_correction(correction)

        # Verify in corrections table directly
        row = store._conn.execute(
            "SELECT * FROM corrections WHERE session_id = ?",
            (session.session_id,),
        ).fetchone()
        assert row is not None
        assert row["sdtm_variable"] == "STUDYID"
        assert row["correction_type"] == "reject"


# ---------------------------------------------------------------------------
# list_sessions tests
# ---------------------------------------------------------------------------


class TestListSessions:
    """Tests for list_sessions."""

    def test_returns_summaries(self, store: SessionStore, dm_spec: DomainMappingSpec) -> None:
        store.create_session(
            study_id="PHA022121-C301",
            domains=["DM"],
            specs={"DM": dm_spec},
        )
        sessions = store.list_sessions()
        assert len(sessions) == 1
        s = sessions[0]
        assert s["study_id"] == "PHA022121-C301"
        assert s["status"] == "in_progress"
        assert s["domain_count"] == 1
        assert "session_id" in s
        assert "created_at" in s
        assert "updated_at" in s

    def test_filter_by_study_id(
        self,
        store: SessionStore,
        dm_spec: DomainMappingSpec,
        ae_spec: DomainMappingSpec,
    ) -> None:
        store.create_session(
            study_id="STUDY-A",
            domains=["DM"],
            specs={"DM": dm_spec},
        )
        store.create_session(
            study_id="STUDY-B",
            domains=["AE"],
            specs={"AE": ae_spec},
        )

        all_sessions = store.list_sessions()
        assert len(all_sessions) == 2

        a_sessions = store.list_sessions(study_id="STUDY-A")
        assert len(a_sessions) == 1
        assert a_sessions[0]["study_id"] == "STUDY-A"

        b_sessions = store.list_sessions(study_id="STUDY-B")
        assert len(b_sessions) == 1
        assert b_sessions[0]["study_id"] == "STUDY-B"

    def test_empty_when_no_sessions(self, store: SessionStore) -> None:
        assert store.list_sessions() == []

    def test_multiple_sessions_same_study(
        self, store: SessionStore, dm_spec: DomainMappingSpec
    ) -> None:
        s1 = store.create_session(
            study_id="PHA022121-C301",
            domains=["DM"],
            specs={"DM": dm_spec},
        )
        s2 = store.create_session(
            study_id="PHA022121-C301",
            domains=["DM"],
            specs={"DM": dm_spec},
        )

        sessions = store.list_sessions(study_id="PHA022121-C301")
        assert len(sessions) == 2
        session_ids = {s["session_id"] for s in sessions}
        assert s1.session_id in session_ids
        assert s2.session_id in session_ids
