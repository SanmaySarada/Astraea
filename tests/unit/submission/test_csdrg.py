"""Tests for cSDRG template generator and known false-positive support."""

from __future__ import annotations

from pathlib import Path

import pytest

from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)
from astraea.models.sdtm import CoreDesignation
from astraea.submission.csdrg import generate_csdrg
from astraea.validation.report import ValidationReport
from astraea.validation.rules.base import RuleCategory, RuleResult, RuleSeverity


def _make_spec(
    domain: str,
    label: str,
    domain_class: str = "Events",
    num_vars: int = 3,
) -> DomainMappingSpec:
    """Create a synthetic DomainMappingSpec for testing."""
    mappings = [
        VariableMapping(
            sdtm_variable=f"{domain}VAR{i}",
            sdtm_label=f"Test Variable {i}",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ if i == 1 else CoreDesignation.EXP,
            source_dataset=f"{domain.lower()}.sas7bdat",
            source_variable=f"SRC{i}",
            mapping_pattern=MappingPattern.DIRECT if i <= 2 else MappingPattern.ASSIGN,
            mapping_logic=f"Direct map for var {i}",
            confidence=0.9,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="High match",
            order=i,
            origin=VariableOrigin.CRF,
        )
        for i in range(1, num_vars + 1)
    ]
    return DomainMappingSpec(
        domain=domain,
        domain_label=label,
        domain_class=domain_class,
        structure="One record per subject per event",
        study_id="TEST-001",
        source_datasets=[f"{domain.lower()}.sas7bdat"],
        variable_mappings=mappings,
        total_variables=num_vars,
        required_mapped=1,
        expected_mapped=num_vars - 1,
        high_confidence_count=num_vars,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00Z",
        model_used="test-model",
        suppqual_candidates=["EXTRA_VAR"] if domain == "AE" else [],
        missing_required_variables=["AESEQ"] if domain == "AE" else [],
    )


def _make_validation_report(
    results: list[RuleResult] | None = None,
) -> ValidationReport:
    """Create a synthetic ValidationReport."""
    if results is None:
        results = [
            RuleResult(
                rule_id="VAL-01-001",
                rule_description="CT check",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="AE",
                variable="AETERM",
                message="Invalid CT value found",
                affected_count=5,
            ),
            RuleResult(
                rule_id="VAL-02-001",
                rule_description="Required var check",
                category=RuleCategory.PRESENCE,
                severity=RuleSeverity.WARNING,
                domain="DM",
                variable="AGE",
                message="Expected variable AGE has missing values",
                affected_count=2,
            ),
            RuleResult(
                rule_id="VAL-05-001",
                rule_description="Date format check",
                category=RuleCategory.FORMAT,
                severity=RuleSeverity.NOTICE,
                domain="AE",
                variable="AESTDTC",
                message="Partial date found",
                affected_count=1,
            ),
        ]
    return ValidationReport.from_results(
        study_id="TEST-001",
        results=results,
        domains=["AE", "DM"],
    )


class TestGenerateCsdrg:
    """Tests for cSDRG template generation."""

    def test_generate_csdrg_creates_file(self, tmp_path: Path) -> None:
        """cSDRG generates a file at the output path."""
        specs = [_make_spec("AE", "Adverse Events"), _make_spec("DM", "Demographics")]
        report = _make_validation_report()
        output = tmp_path / "csdrg.md"

        result = generate_csdrg(specs, report, "TEST-001", output)

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    def test_generate_csdrg_valid_markdown(self, tmp_path: Path) -> None:
        """cSDRG output is valid Markdown with expected content."""
        specs = [_make_spec("AE", "Adverse Events"), _make_spec("DM", "Demographics")]
        report = _make_validation_report()
        output = tmp_path / "csdrg.md"

        generate_csdrg(specs, report, "TEST-001", output)
        content = output.read_text()

        # Must have Markdown headers
        assert "# " in content
        assert "## " in content

    def test_generate_csdrg_all_8_sections(self, tmp_path: Path) -> None:
        """cSDRG contains all 8 required sections."""
        specs = [_make_spec("AE", "Adverse Events"), _make_spec("DM", "Demographics")]
        report = _make_validation_report()
        output = tmp_path / "csdrg.md"

        generate_csdrg(specs, report, "TEST-001", output)
        content = output.read_text()

        assert "## 1. Introduction" in content
        assert "## 2. Study Description" in content
        assert "## 3. Data Standards" in content
        assert "## 4. Dataset Overview" in content
        assert "## 5. Domain-Specific Information" in content
        assert "## 6. Data Issues" in content
        assert "## 7. Validation Results" in content
        assert "## 8. Non-Standard Variables" in content

    def test_generate_csdrg_domain_overview_count(self, tmp_path: Path) -> None:
        """Domain overview table has correct number of domain rows."""
        specs = [_make_spec("AE", "Adverse Events"), _make_spec("DM", "Demographics")]
        report = _make_validation_report()
        output = tmp_path / "csdrg.md"

        generate_csdrg(specs, report, "TEST-001", output)
        content = output.read_text()

        # Find the overview table -- count rows with domain codes
        assert "| AE |" in content
        assert "| DM |" in content

    def test_generate_csdrg_validation_summary(self, tmp_path: Path) -> None:
        """Validation summary includes error/warning counts."""
        specs = [_make_spec("AE", "Adverse Events")]
        report = _make_validation_report()
        output = tmp_path / "csdrg.md"

        generate_csdrg(specs, report, "TEST-001", output)
        content = output.read_text()

        # Should include the counts from the report
        assert "Errors" in content
        assert "Warnings" in content
        assert "Notices" in content

    def test_generate_csdrg_creates_parent_dirs(self, tmp_path: Path) -> None:
        """cSDRG creates parent directories if they don't exist."""
        specs = [_make_spec("AE", "Adverse Events")]
        report = _make_validation_report()
        output = tmp_path / "nested" / "dir" / "csdrg.md"

        result = generate_csdrg(specs, report, "TEST-001", output)

        assert result == output
        assert output.exists()

    def test_generate_csdrg_suppqual_candidates_in_section_8(
        self, tmp_path: Path
    ) -> None:
        """Section 8 lists SUPPQUAL candidates from specs."""
        specs = [_make_spec("AE", "Adverse Events")]  # has suppqual_candidates
        report = _make_validation_report()
        output = tmp_path / "csdrg.md"

        generate_csdrg(specs, report, "TEST-001", output)
        content = output.read_text()

        assert "EXTRA_VAR" in content


class TestKnownFalsePositives:
    """Tests for known false-positive flagging."""

    def test_flag_known_false_positive_matches(self, tmp_path: Path) -> None:
        """RuleResult matching a whitelist entry gets flagged."""
        # Create a whitelist
        whitelist_path = tmp_path / "kfp.json"
        whitelist_path.write_text(
            '{"entries": [{"rule_id": "SD1076", "domain": "LB", '
            '"variable": "LBSTRESC", "reason": "P21 known issue"}]}'
        )

        results = [
            RuleResult(
                rule_id="SD1076",
                rule_description="CT check",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="LB",
                variable="LBSTRESC",
                message="Value not in codelist",
                affected_count=10,
            ),
            RuleResult(
                rule_id="VAL-01-001",
                rule_description="Other check",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="AE",
                variable="AETERM",
                message="Invalid term",
            ),
        ]

        report = ValidationReport.from_results(
            study_id="TEST-001",
            results=results,
            domains=["LB", "AE"],
            whitelist_path=whitelist_path,
        )

        # The SD1076 result should be flagged
        flagged = [r for r in report.results if r.known_false_positive]
        assert len(flagged) == 1
        assert flagged[0].rule_id == "SD1076"
        assert flagged[0].known_false_positive_reason == "P21 known issue"

    def test_effective_counts_exclude_false_positives(self, tmp_path: Path) -> None:
        """Effective error/warning counts exclude known false positives."""
        whitelist_path = tmp_path / "kfp.json"
        whitelist_path.write_text(
            '{"entries": [{"rule_id": "SD1076", "domain": "LB", '
            '"variable": "LBSTRESC", "reason": "P21 known issue"}]}'
        )

        results = [
            RuleResult(
                rule_id="SD1076",
                rule_description="CT check",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="LB",
                variable="LBSTRESC",
                message="Value not in codelist",
            ),
            RuleResult(
                rule_id="VAL-01-002",
                rule_description="Other check",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="AE",
                variable="AETERM",
                message="Invalid term",
            ),
        ]

        report = ValidationReport.from_results(
            study_id="TEST-001",
            results=results,
            domains=["LB", "AE"],
            whitelist_path=whitelist_path,
        )

        # Total error_count includes all, effective excludes flagged
        assert report.error_count == 2
        assert report.effective_error_count == 1

    def test_submission_ready_uses_effective_count(self, tmp_path: Path) -> None:
        """submission_ready uses effective error count after false-positive flagging."""
        whitelist_path = tmp_path / "kfp.json"
        whitelist_path.write_text(
            '{"entries": [{"rule_id": "SD1076", "domain": null, '
            '"variable": null, "reason": "Known issue"}]}'
        )

        results = [
            RuleResult(
                rule_id="SD1076",
                rule_description="CT check",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="LB",
                variable="LBSTRESC",
                message="Value not in codelist",
            ),
        ]

        report = ValidationReport.from_results(
            study_id="TEST-001",
            results=results,
            domains=["LB"],
            whitelist_path=whitelist_path,
        )

        # Only error is a known false positive, so submission should be ready
        assert report.error_count == 1
        assert report.effective_error_count == 0
        assert report.submission_ready is True

    def test_csdrg_section_7_known_false_positives(self, tmp_path: Path) -> None:
        """cSDRG Section 7 includes Known False Positives subsection."""
        whitelist_path = tmp_path / "kfp.json"
        whitelist_path.write_text(
            '{"entries": [{"rule_id": "SD1076", "domain": "LB", '
            '"variable": "LBSTRESC", "reason": "P21 v2405.2 known issue"}]}'
        )

        results = [
            RuleResult(
                rule_id="SD1076",
                rule_description="CT check",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="LB",
                variable="LBSTRESC",
                message="Value not in codelist",
            ),
        ]

        report = ValidationReport.from_results(
            study_id="TEST-001",
            results=results,
            domains=["LB"],
            whitelist_path=whitelist_path,
        )

        specs = [_make_spec("LB", "Laboratory Test Results", "Findings")]
        output = tmp_path / "csdrg.md"

        generate_csdrg(specs, report, "TEST-001", output)
        content = output.read_text()

        assert "Known False Positives" in content
        assert "SD1076" in content
        assert "LBSTRESC" in content
        assert "P21 v2405.2 known issue" in content

    def test_whitelist_null_domain_matches_any(self, tmp_path: Path) -> None:
        """Whitelist entry with null domain matches any domain."""
        whitelist_path = tmp_path / "kfp.json"
        whitelist_path.write_text(
            '{"entries": [{"rule_id": "SD1076", "domain": null, '
            '"variable": null, "reason": "Known everywhere"}]}'
        )

        results = [
            RuleResult(
                rule_id="SD1076",
                rule_description="CT check",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.WARNING,
                domain="AE",
                variable="AETERM",
                message="Something",
            ),
        ]

        report = ValidationReport.from_results(
            study_id="TEST-001",
            results=results,
            domains=["AE"],
            whitelist_path=whitelist_path,
        )

        assert report.results[0].known_false_positive is True
