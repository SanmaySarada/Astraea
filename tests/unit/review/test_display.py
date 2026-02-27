"""Tests for review display functions."""

from __future__ import annotations

import io
import re

from rich.console import Console

from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation
from astraea.review.display import (
    display_review_summary,
    display_review_table,
    display_session_list,
    display_variable_detail,
)
from astraea.review.models import (
    CorrectionType,
    DomainReview,
    DomainReviewStatus,
    HumanCorrection,
    ReviewDecision,
    ReviewStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _capture_console() -> tuple[Console, io.StringIO]:
    """Create a Console that captures output to StringIO."""
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    return console, buf


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


def _make_spec_with_mixed_confidence() -> DomainMappingSpec:
    """Create a DomainMappingSpec with HIGH, MEDIUM, and LOW variables."""
    mappings = [
        _make_variable_mapping(
            "STUDYID",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
        ),
        _make_variable_mapping(
            "DOMAIN",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            assigned_value="AE",
        ),
        _make_variable_mapping(
            "AETERM",
            pattern=MappingPattern.DIRECT,
            confidence=0.70,
            confidence_level=ConfidenceLevel.MEDIUM,
            core=CoreDesignation.EXP,
            assigned_value=None,
            source_dataset="ae",
            source_variable="AETERM",
            mapping_logic="Direct carry from source",
        ),
        _make_variable_mapping(
            "AEDECOD",
            pattern=MappingPattern.DERIVATION,
            confidence=0.45,
            confidence_level=ConfidenceLevel.LOW,
            core=CoreDesignation.PERM,
            assigned_value=None,
            source_dataset="ae",
            source_variable="AETERM",
            mapping_logic="MedDRA preferred term lookup",
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
        total_variables=4,
        required_mapped=2,
        expected_mapped=1,
        high_confidence_count=2,
        medium_confidence_count=1,
        low_confidence_count=1,
        mapping_timestamp="2026-02-27T12:00:00+00:00",
        model_used="claude-sonnet-4-20250514",
    )


# ---------------------------------------------------------------------------
# display_review_table tests
# ---------------------------------------------------------------------------


class TestDisplayReviewTable:
    """Tests for display_review_table."""

    def test_renders_all_variable_names(self) -> None:
        console, buf = _capture_console()
        spec = _make_spec_with_mixed_confidence()
        display_review_table(spec, {}, console)
        text = _strip_ansi(buf.getvalue())
        assert "STUDYID" in text
        assert "DOMAIN" in text
        assert "AETERM" in text
        assert "AEDECOD" in text

    def test_renders_header_panel(self) -> None:
        console, buf = _capture_console()
        spec = _make_spec_with_mixed_confidence()
        display_review_table(spec, {}, console)
        text = _strip_ansi(buf.getvalue())
        assert "AE" in text
        assert "Adverse Events" in text
        assert "PHA022121-C301" in text

    def test_pending_status_when_no_decisions(self) -> None:
        console, buf = _capture_console()
        spec = _make_spec_with_mixed_confidence()
        display_review_table(spec, {}, console)
        text = _strip_ansi(buf.getvalue())
        assert "..." in text
        assert "4 pending" in text

    def test_approved_status_shown(self) -> None:
        console, buf = _capture_console()
        spec = _make_spec_with_mixed_confidence()
        decisions = {
            "STUDYID": ReviewDecision(
                sdtm_variable="STUDYID",
                status=ReviewStatus.APPROVED,
                original_mapping=spec.variable_mappings[0],
                timestamp="2026-02-27T13:00:00+00:00",
            ),
        }
        display_review_table(spec, decisions, console)
        text = _strip_ansi(buf.getvalue())
        assert "OK" in text
        assert "1 approved" in text

    def test_corrected_status_shown(self) -> None:
        console, buf = _capture_console()
        spec = _make_spec_with_mixed_confidence()
        corrected_mapping = _make_variable_mapping(
            "AETERM",
            pattern=MappingPattern.DIRECT,
            source_variable="AE_PTERM",
            source_dataset="ae",
            assigned_value=None,
        )
        decisions = {
            "AETERM": ReviewDecision(
                sdtm_variable="AETERM",
                status=ReviewStatus.CORRECTED,
                correction_type=CorrectionType.SOURCE_CHANGE,
                original_mapping=spec.variable_mappings[2],
                corrected_mapping=corrected_mapping,
                reason="Wrong source",
                timestamp="2026-02-27T13:00:00+00:00",
            ),
        }
        display_review_table(spec, decisions, console)
        text = _strip_ansi(buf.getvalue())
        assert "FIX" in text
        assert "1 corrected" in text

    def test_assign_source_shows_value(self) -> None:
        console, buf = _capture_console()
        spec = _make_spec_with_mixed_confidence()
        display_review_table(spec, {}, console)
        text = _strip_ansi(buf.getvalue())
        # STUDYID has assign pattern with value
        assert '="PHA022121-C301"' in text

    def test_pattern_column_shown(self) -> None:
        console, buf = _capture_console()
        spec = _make_spec_with_mixed_confidence()
        display_review_table(spec, {}, console)
        text = _strip_ansi(buf.getvalue())
        assert "assign" in text
        assert "direct" in text
        assert "derivation" in text


# ---------------------------------------------------------------------------
# display_variable_detail tests
# ---------------------------------------------------------------------------


class TestDisplayVariableDetail:
    """Tests for display_variable_detail."""

    def test_shows_basic_info(self) -> None:
        console, buf = _capture_console()
        mapping = _make_variable_mapping(
            "AETERM",
            pattern=MappingPattern.DIRECT,
            assigned_value=None,
            source_dataset="ae",
            source_variable="AETERM",
            mapping_logic="Direct carry from source",
        )
        display_variable_detail(mapping, console)
        text = _strip_ansi(buf.getvalue())
        assert "AETERM" in text
        assert "Label for AETERM" in text
        assert "direct" in text
        assert "ae.AETERM" in text

    def test_shows_assign_source(self) -> None:
        console, buf = _capture_console()
        mapping = _make_variable_mapping("STUDYID")
        display_variable_detail(mapping, console)
        text = _strip_ansi(buf.getvalue())
        assert 'Assigned: "PHA022121-C301"' in text

    def test_shows_confidence(self) -> None:
        console, buf = _capture_console()
        mapping = _make_variable_mapping("STUDYID", confidence=0.70)
        display_variable_detail(mapping, console)
        text = _strip_ansi(buf.getvalue())
        assert "0.70" in text

    def test_shows_codelist(self) -> None:
        console, buf = _capture_console()
        mapping = _make_variable_mapping(
            "AEDECOD",
            pattern=MappingPattern.LOOKUP_RECODE,
            assigned_value=None,
            codelist_code="C66729",
            codelist_name="MedDRA",
        )
        display_variable_detail(mapping, console)
        text = _strip_ansi(buf.getvalue())
        assert "C66729" in text
        assert "MedDRA" in text

    def test_shows_derivation_rule(self) -> None:
        console, buf = _capture_console()
        mapping = _make_variable_mapping(
            "USUBJID",
            pattern=MappingPattern.DERIVATION,
            assigned_value=None,
            source_dataset="dm",
            source_variable="SUBJID",
            derivation_rule="concat(STUDYID, '-', SITEID, '-', SUBJID)",
        )
        display_variable_detail(mapping, console)
        text = _strip_ansi(buf.getvalue())
        assert "concat(STUDYID" in text

    def test_shows_rationale(self) -> None:
        console, buf = _capture_console()
        mapping = _make_variable_mapping(
            "STUDYID", confidence_rationale="Standard assignment pattern"
        )
        display_variable_detail(mapping, console)
        text = _strip_ansi(buf.getvalue())
        assert "Standard assignment pattern" in text


# ---------------------------------------------------------------------------
# display_review_summary tests
# ---------------------------------------------------------------------------


class TestDisplayReviewSummary:
    """Tests for display_review_summary."""

    def test_shows_counts(self) -> None:
        console, buf = _capture_console()
        spec = _make_spec_with_mixed_confidence()
        review = DomainReview(
            domain="AE",
            status=DomainReviewStatus.IN_PROGRESS,
            original_spec=spec,
            decisions={
                "STUDYID": ReviewDecision(
                    sdtm_variable="STUDYID",
                    status=ReviewStatus.APPROVED,
                    original_mapping=spec.variable_mappings[0],
                    timestamp="2026-02-27T13:00:00+00:00",
                ),
                "DOMAIN": ReviewDecision(
                    sdtm_variable="DOMAIN",
                    status=ReviewStatus.APPROVED,
                    original_mapping=spec.variable_mappings[1],
                    timestamp="2026-02-27T13:00:00+00:00",
                ),
                "AETERM": ReviewDecision(
                    sdtm_variable="AETERM",
                    status=ReviewStatus.SKIPPED,
                    original_mapping=spec.variable_mappings[2],
                    timestamp="2026-02-27T13:00:00+00:00",
                ),
            },
        )
        display_review_summary(review, console)
        text = _strip_ansi(buf.getvalue())
        assert "Approved:" in text and "2" in text
        assert "Skipped:" in text and "1" in text
        assert "Pending:" in text and "1" in text

    def test_shows_corrections_list(self) -> None:
        console, buf = _capture_console()
        spec = _make_spec_with_mixed_confidence()
        corrected_mapping = _make_variable_mapping(
            "AETERM",
            pattern=MappingPattern.DIRECT,
            source_variable="AE_PTERM",
            source_dataset="ae",
            assigned_value=None,
        )
        correction = HumanCorrection(
            session_id="abc123",
            domain="AE",
            sdtm_variable="AETERM",
            correction_type=CorrectionType.SOURCE_CHANGE,
            original_mapping=spec.variable_mappings[2],
            corrected_mapping=corrected_mapping,
            reason="Wrong source variable",
            timestamp="2026-02-27T13:00:00+00:00",
        )
        review = DomainReview(
            domain="AE",
            status=DomainReviewStatus.COMPLETED,
            original_spec=spec,
            decisions={
                "AETERM": ReviewDecision(
                    sdtm_variable="AETERM",
                    status=ReviewStatus.CORRECTED,
                    correction_type=CorrectionType.SOURCE_CHANGE,
                    original_mapping=spec.variable_mappings[2],
                    corrected_mapping=corrected_mapping,
                    reason="Wrong source variable",
                    timestamp="2026-02-27T13:00:00+00:00",
                ),
            },
            corrections=[correction],
        )
        display_review_summary(review, console)
        text = _strip_ansi(buf.getvalue())
        assert "Corrections:" in text
        assert "AETERM" in text
        assert "source_change" in text
        assert "Wrong source variable" in text

    def test_no_corrections_section_when_empty(self) -> None:
        console, buf = _capture_console()
        spec = _make_spec_with_mixed_confidence()
        review = DomainReview(
            domain="AE",
            status=DomainReviewStatus.PENDING,
            original_spec=spec,
        )
        display_review_summary(review, console)
        text = _strip_ansi(buf.getvalue())
        assert "Corrections:" not in text


# ---------------------------------------------------------------------------
# display_session_list tests
# ---------------------------------------------------------------------------


class TestDisplaySessionList:
    """Tests for display_session_list."""

    def test_renders_session_table(self) -> None:
        console, buf = _capture_console()
        sessions = [
            {
                "session_id": "abc123def456",
                "study_id": "PHA022121-C301",
                "status": "in_progress",
                "created_at": "2026-02-27T12:00:00+00:00",
                "updated_at": "2026-02-27T13:00:00+00:00",
                "domain_count": 3,
            },
        ]
        display_session_list(sessions, console)
        text = _strip_ansi(buf.getvalue())
        assert "abc123def456" in text
        assert "PHA022121-C301" in text
        assert "in_progress" in text
        assert "3" in text

    def test_multiple_sessions(self) -> None:
        console, buf = _capture_console()
        sessions = [
            {
                "session_id": "aaa111",
                "study_id": "STUDY-A",
                "status": "completed",
                "created_at": "2026-02-27T10:00:00+00:00",
                "updated_at": "2026-02-27T11:00:00+00:00",
                "domain_count": 2,
            },
            {
                "session_id": "bbb222",
                "study_id": "STUDY-B",
                "status": "abandoned",
                "created_at": "2026-02-27T09:00:00+00:00",
                "updated_at": "2026-02-27T09:30:00+00:00",
                "domain_count": 1,
            },
        ]
        display_session_list(sessions, console)
        text = _strip_ansi(buf.getvalue())
        assert "aaa111" in text
        assert "bbb222" in text
        assert "completed" in text
        assert "abandoned" in text

    def test_empty_sessions(self) -> None:
        console, buf = _capture_console()
        display_session_list([], console)
        text = _strip_ansi(buf.getvalue())
        assert "No review sessions found" in text
