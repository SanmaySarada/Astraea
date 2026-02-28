"""Tests for submission package assembly and size validation."""

from __future__ import annotations

from pathlib import Path

from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)
from astraea.models.sdtm import CoreDesignation
from astraea.submission.package import (
    assemble_package_manifest,
    check_submission_size,
    validate_file_naming,
)
from astraea.validation.report import ValidationReport
from astraea.validation.rules.base import RuleCategory, RuleResult, RuleSeverity


def _make_spec(domain: str, label: str) -> DomainMappingSpec:
    """Create a minimal DomainMappingSpec for testing."""
    return DomainMappingSpec(
        domain=domain,
        domain_label=label,
        domain_class="Events",
        structure="One record per subject",
        study_id="TEST-001",
        source_datasets=[f"{domain.lower()}.sas7bdat"],
        variable_mappings=[
            VariableMapping(
                sdtm_variable="STUDYID",
                sdtm_label="Study Identifier",
                sdtm_data_type="Char",
                core=CoreDesignation.REQ,
                mapping_pattern=MappingPattern.ASSIGN,
                mapping_logic="Constant",
                confidence=1.0,
                confidence_level=ConfidenceLevel.HIGH,
                confidence_rationale="Assigned",
                origin=VariableOrigin.ASSIGNED,
            ),
        ],
        total_variables=1,
        required_mapped=1,
        expected_mapped=0,
        high_confidence_count=1,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00Z",
        model_used="test",
    )


class TestCheckSubmissionSize:
    """Tests for check_submission_size."""

    def test_small_dir_returns_notice(self, tmp_path: Path) -> None:
        """Under-limit submission returns NOTICE only."""
        (tmp_path / "dm.xpt").write_bytes(b"x" * 100)
        (tmp_path / "ae.xpt").write_bytes(b"x" * 200)

        results = check_submission_size(tmp_path)

        severities = {r.severity for r in results}
        assert RuleSeverity.ERROR not in severities
        assert RuleSeverity.WARNING not in severities
        assert RuleSeverity.NOTICE in severities

    def test_over_limit_returns_error(self, tmp_path: Path) -> None:
        """Total size over limit returns ERROR."""
        # Create a file that when combined exceeds limit
        # Use a tiny limit for testing
        (tmp_path / "big.xpt").write_bytes(b"x" * 1000)

        results = check_submission_size(tmp_path, limit_gb=0.0000001)

        error_results = [r for r in results if r.severity == RuleSeverity.ERROR]
        assert len(error_results) >= 1
        assert "exceeds" in error_results[0].message.lower()

    def test_lb_over_1gb_returns_split_guidance(self, tmp_path: Path) -> None:
        """lb.xpt > 1GB returns WARNING with LB-specific split guidance."""
        # Create a file just over 1GB -- use sparse file trick
        lb_path = tmp_path / "lb.xpt"
        with open(lb_path, "wb") as f:
            f.seek(1024**3 + 1)
            f.write(b"\0")

        results = check_submission_size(tmp_path)

        warnings = [r for r in results if r.severity == RuleSeverity.WARNING]
        assert len(warnings) >= 1
        assert warnings[0].fix_suggestion is not None
        assert "Split LB by LBCAT" in warnings[0].fix_suggestion

    def test_unknown_domain_over_1gb_returns_generic_guidance(self, tmp_path: Path) -> None:
        """Unknown domain > 1GB returns WARNING with generic split guidance."""
        big_path = tmp_path / "zz.xpt"
        with open(big_path, "wb") as f:
            f.seek(1024**3 + 1)
            f.write(b"\0")

        results = check_submission_size(tmp_path)

        warnings = [r for r in results if r.severity == RuleSeverity.WARNING]
        assert len(warnings) >= 1
        assert warnings[0].fix_suggestion is not None
        assert "categorical variable" in warnings[0].fix_suggestion

    def test_nonexistent_dir_returns_error(self, tmp_path: Path) -> None:
        """Nonexistent directory returns ERROR."""
        results = check_submission_size(tmp_path / "nope")

        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR


class TestValidateFileNaming:
    """Tests for validate_file_naming."""

    def test_correct_files_no_errors(self, tmp_path: Path) -> None:
        """Correct file names produce no errors."""
        (tmp_path / "ae.xpt").write_bytes(b"x")
        (tmp_path / "dm.xpt").write_bytes(b"x")
        (tmp_path / "define.xml").write_text("<define/>")

        results = validate_file_naming(tmp_path, ["AE", "DM"])

        errors = [r for r in results if r.severity == RuleSeverity.ERROR]
        assert len(errors) == 0

    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        """Missing expected domain file returns ERROR."""
        (tmp_path / "ae.xpt").write_bytes(b"x")
        (tmp_path / "define.xml").write_text("<define/>")

        results = validate_file_naming(tmp_path, ["AE", "DM"])

        errors = [r for r in results if r.severity == RuleSeverity.ERROR]
        assert any("dm.xpt" in r.message for r in errors)

    def test_missing_define_xml_returns_error(self, tmp_path: Path) -> None:
        """Missing define.xml returns ERROR."""
        (tmp_path / "ae.xpt").write_bytes(b"x")

        results = validate_file_naming(tmp_path, ["AE"])

        errors = [r for r in results if r.severity == RuleSeverity.ERROR]
        assert any("define.xml" in r.message for r in errors)

    def test_unexpected_file_returns_warning(self, tmp_path: Path) -> None:
        """Extra XPT file returns WARNING."""
        (tmp_path / "ae.xpt").write_bytes(b"x")
        (tmp_path / "extra.xpt").write_bytes(b"x")
        (tmp_path / "define.xml").write_text("<define/>")

        results = validate_file_naming(tmp_path, ["AE"])

        warnings = [r for r in results if r.severity == RuleSeverity.WARNING]
        assert any("extra.xpt" in r.message for r in warnings)


class TestAssemblePackageManifest:
    """Tests for assemble_package_manifest."""

    def test_manifest_returns_correct_inventory(self, tmp_path: Path) -> None:
        """Manifest includes correct file count and sizes."""
        (tmp_path / "ae.xpt").write_bytes(b"x" * 100)
        (tmp_path / "dm.xpt").write_bytes(b"x" * 200)
        (tmp_path / "define.xml").write_text("<define/>")

        specs = [_make_spec("AE", "Adverse Events"), _make_spec("DM", "Demographics")]
        manifest = assemble_package_manifest(tmp_path, specs)

        assert manifest["domain_count"] == 2
        assert manifest["has_define_xml"] is True
        assert len(manifest["files"]) == 3  # 2 xpt + define.xml
        assert manifest["total_size"] > 0


class TestValidationReportToMarkdown:
    """Tests for ValidationReport.to_markdown()."""

    def test_to_markdown_produces_valid_output(self) -> None:
        """to_markdown() produces Markdown with all expected sections."""
        results = [
            RuleResult(
                rule_id="VAL-01-001",
                rule_description="CT check",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="AE",
                variable="AETERM",
                message="Invalid CT value",
                affected_count=3,
            ),
            RuleResult(
                rule_id="VAL-02-001",
                rule_description="Presence check",
                category=RuleCategory.PRESENCE,
                severity=RuleSeverity.WARNING,
                domain="DM",
                message="Expected variable missing",
            ),
        ]

        report = ValidationReport.from_results(
            study_id="TEST-001",
            results=results,
            domains=["AE", "DM"],
        )

        md = report.to_markdown()

        assert "# Validation Report: TEST-001" in md
        assert "## Summary" in md
        assert "## Per-Domain Breakdown" in md
        assert "## Per-Category Breakdown" in md
        assert "## Top Issues" in md
        assert "## Submission Readiness" in md
        assert "NOT READY" in md
        assert "VAL-01-001" in md
