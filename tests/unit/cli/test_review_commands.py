"""Tests for CLI review commands (review-domain, resume, sessions).

Tests error handling, sessions listing, and non-interactive paths.
Interactive review flow is tested in the checkpoint task via manual
terminal interaction.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from astraea.cli.app import app
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation
from astraea.review.session import SessionStore

runner = CliRunner()


def _make_spec() -> DomainMappingSpec:
    """Create a minimal valid DomainMappingSpec for testing."""
    mappings = [
        VariableMapping(
            sdtm_variable="STUDYID",
            sdtm_label="Study Identifier",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            mapping_pattern=MappingPattern.ASSIGN,
            mapping_logic="Assign constant study ID",
            assigned_value="TEST-001",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Standard assignment",
        ),
        VariableMapping(
            sdtm_variable="DOMAIN",
            sdtm_label="Domain Abbreviation",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            mapping_pattern=MappingPattern.ASSIGN,
            mapping_logic="Assign 'DM'",
            assigned_value="DM",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Standard assignment",
        ),
        VariableMapping(
            sdtm_variable="SEX",
            sdtm_label="Sex",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            source_dataset="dm.sas7bdat",
            source_variable="SEX",
            mapping_pattern=MappingPattern.LOOKUP_RECODE,
            mapping_logic="Map via CT codelist",
            confidence=0.50,
            confidence_level=ConfidenceLevel.LOW,
            confidence_rationale="CT lookup needed",
        ),
    ]

    return DomainMappingSpec(
        domain="DM",
        domain_label="Demographics",
        domain_class="Special Purpose",
        structure="One record per subject",
        study_id="TEST-001",
        source_datasets=["dm.sas7bdat"],
        cross_domain_sources=[],
        variable_mappings=mappings,
        total_variables=3,
        required_mapped=3,
        expected_mapped=0,
        high_confidence_count=2,
        medium_confidence_count=0,
        low_confidence_count=1,
        mapping_timestamp="2026-02-27T12:00:00Z",
        model_used="claude-sonnet-4-20250514",
        unmapped_source_variables=[],
        suppqual_candidates=[],
    )


class TestReviewDomainCmd:
    """Tests for the review-domain CLI command."""

    def test_nonexistent_spec_file(self, tmp_path: Path) -> None:
        """review-domain with non-existent spec file returns error."""
        result = runner.invoke(
            app,
            [
                "review-domain",
                str(tmp_path / "nonexistent.json"),
                "--db",
                str(tmp_path / "sessions.db"),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_invalid_json_spec(self, tmp_path: Path) -> None:
        """review-domain with invalid JSON returns error."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")
        result = runner.invoke(
            app,
            [
                "review-domain",
                str(bad_file),
                "--db",
                str(tmp_path / "sessions.db"),
            ],
        )
        assert result.exit_code == 1
        assert "error" in result.output.lower()

    def test_invalid_session_id(self, tmp_path: Path) -> None:
        """review-domain with non-existent --session returns error."""
        spec = _make_spec()
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(spec.model_dump_json(indent=2))

        result = runner.invoke(
            app,
            [
                "review-domain",
                str(spec_file),
                "--session",
                "nonexistent123",
                "--db",
                str(tmp_path / "sessions.db"),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestSessionsCmd:
    """Tests for the sessions CLI command."""

    def test_no_database(self, tmp_path: Path) -> None:
        """sessions with no database shows 'no sessions found'."""
        result = runner.invoke(
            app,
            ["sessions", "--db", str(tmp_path / "nonexistent.db")],
        )
        assert result.exit_code == 0
        assert "no review sessions found" in result.output.lower()

    def test_empty_database(self, tmp_path: Path) -> None:
        """sessions with empty database shows 'no sessions found'."""
        db_path = tmp_path / "empty.db"
        store = SessionStore(db_path)
        store.close()

        result = runner.invoke(
            app,
            ["sessions", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "no review sessions found" in result.output.lower()

    def test_populated_database(self, tmp_path: Path) -> None:
        """sessions with data shows session table with header."""
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        spec = _make_spec()
        store.create_session(
            study_id="TEST-001",
            domains=["DM"],
            specs={"DM": spec},
        )
        store.close()

        result = runner.invoke(
            app,
            ["sessions", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        # Rich renders a table; verify table title and no "No review sessions" msg
        assert "Review Sessions" in result.output
        assert "no review sessions found" not in result.output.lower()

    def test_study_filter(self, tmp_path: Path) -> None:
        """sessions --study filters by study ID."""
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        spec = _make_spec()
        store.create_session(
            study_id="TEST-001",
            domains=["DM"],
            specs={"DM": spec},
        )
        store.close()

        # Filter for non-existent study
        result = runner.invoke(
            app,
            ["sessions", "--db", str(db_path), "--study", "NONEXISTENT"],
        )
        assert result.exit_code == 0
        assert "no review sessions found" in result.output.lower()


class TestResumeCmd:
    """Tests for the resume CLI command."""

    def test_no_database(self, tmp_path: Path) -> None:
        """resume with no database shows error."""
        result = runner.invoke(
            app,
            ["resume", "--db", str(tmp_path / "nonexistent.db")],
        )
        assert result.exit_code == 1
        assert "no session database" in result.output.lower()

    def test_no_in_progress_sessions(self, tmp_path: Path) -> None:
        """resume with no in-progress sessions shows message."""
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        store.close()

        result = runner.invoke(
            app,
            ["resume", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert "no in-progress sessions" in result.output.lower()

    def test_nonexistent_session_id(self, tmp_path: Path) -> None:
        """resume with unknown session ID shows error."""
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        store.close()

        result = runner.invoke(
            app,
            ["resume", "nonexistent123", "--db", str(db_path)],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestApplyCorrections:
    """Tests for the _apply_corrections helper."""

    def test_no_decisions_keeps_original(self) -> None:
        """With no decisions, all mappings are kept."""
        from astraea.cli.app import _apply_corrections

        spec = _make_spec()
        result = _apply_corrections(spec, {})
        assert len(result.variable_mappings) == 3
        assert result.total_variables == 3

    def test_reject_removes_variable(self) -> None:
        """A REJECT decision removes the variable from reviewed spec."""
        from astraea.cli.app import _apply_corrections
        from astraea.review.models import (
            CorrectionType,
            ReviewDecision,
            ReviewStatus,
        )

        spec = _make_spec()
        decisions = {
            "SEX": ReviewDecision(
                sdtm_variable="SEX",
                status=ReviewStatus.CORRECTED,
                correction_type=CorrectionType.REJECT,
                original_mapping=spec.variable_mappings[2],
                corrected_mapping=None,
                reason="Not needed",
                timestamp="2026-02-27T12:00:00Z",
            ),
        }
        result = _apply_corrections(spec, decisions)
        assert len(result.variable_mappings) == 2
        var_names = [m.sdtm_variable for m in result.variable_mappings]
        assert "SEX" not in var_names

    def test_source_correction_applied(self) -> None:
        """A SOURCE_CHANGE correction replaces the mapping."""
        from astraea.cli.app import _apply_corrections
        from astraea.review.models import (
            CorrectionType,
            ReviewDecision,
            ReviewStatus,
        )

        spec = _make_spec()
        original = spec.variable_mappings[2]  # SEX
        corrected = VariableMapping(
            sdtm_variable="SEX",
            sdtm_label="Sex",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            source_dataset="dm.sas7bdat",
            source_variable="GENDER",
            mapping_pattern=MappingPattern.LOOKUP_RECODE,
            mapping_logic="Corrected: source changed from SEX to GENDER",
            confidence=1.0,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Human-verified correction",
        )
        decisions = {
            "SEX": ReviewDecision(
                sdtm_variable="SEX",
                status=ReviewStatus.CORRECTED,
                correction_type=CorrectionType.SOURCE_CHANGE,
                original_mapping=original,
                corrected_mapping=corrected,
                reason="Wrong source",
                timestamp="2026-02-27T12:00:00Z",
            ),
        }
        result = _apply_corrections(spec, decisions)
        assert len(result.variable_mappings) == 3
        sex_mapping = [m for m in result.variable_mappings if m.sdtm_variable == "SEX"][0]
        assert sex_mapping.source_variable == "GENDER"
