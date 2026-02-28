"""Tests for cSDRG auto-generated content -- Sections 2, 6, and 8."""

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
from astraea.submission.csdrg import (
    _build_suppqual_justifications,
    _generate_known_data_issues,
    _generate_study_description,
    generate_csdrg,
)
from astraea.validation.report import ValidationReport
from astraea.validation.rules.base import RuleCategory, RuleResult, RuleSeverity


def _make_spec(
    domain: str,
    label: str,
    domain_class: str = "Events",
    num_vars: int = 3,
    suppqual_candidates: list[str] | None = None,
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
        suppqual_candidates=suppqual_candidates or [],
        missing_required_variables=[],
    )


def _make_validation_report(
    results: list[RuleResult] | None = None,
) -> ValidationReport:
    """Create a synthetic ValidationReport."""
    if results is None:
        results = []
    return ValidationReport.from_results(
        study_id="TEST-001",
        results=results,
        domains=["AE", "DM"],
    )


# ---------------------------------------------------------------------------
# Section 2 -- Study Description
# ---------------------------------------------------------------------------


class TestStudyDescription:
    """Tests for cSDRG Section 2 auto-generation from TS params."""

    def test_generates_from_ts_params(self) -> None:
        """Study description includes all TS parameter values."""
        ts = {
            "TITLE": "A Phase 3 Study of Drug X",
            "TPHASE": "Phase 3",
            "INDIC": "Hereditary Angioedema",
            "TBLIND": "double-blind",
            "TCNTRL": "placebo-controlled",
            "NARMS": "3",
            "PLANSUB": "120",
            "OBJPRIM": "Evaluate efficacy of Drug X",
        }
        result = _generate_study_description(ts)

        assert "A Phase 3 Study of Drug X" in result
        assert "Phase 3" in result
        assert "double-blind" in result
        assert "placebo-controlled" in result
        assert "Hereditary Angioedema" in result
        assert "3 treatment arm(s)" in result
        assert "120 subjects" in result
        assert "Evaluate efficacy of Drug X" in result

    def test_uses_fallback_for_missing_params(self) -> None:
        """Missing TS parameters fall back to '[Not specified]'."""
        ts = {"TITLE": "My Study"}
        result = _generate_study_description(ts)

        assert "My Study" in result
        assert "[Not specified]" in result

    def test_all_missing_params(self) -> None:
        """All parameters missing uses fallback for each."""
        result = _generate_study_description({})
        # Should have multiple occurrences of fallback
        assert result.count("[Not specified]") >= 5

    def test_section2_in_csdrg_with_ts_params(self, tmp_path: Path) -> None:
        """Section 2 in generated cSDRG uses TS params when provided."""
        specs = [_make_spec("DM", "Demographics")]
        report = _make_validation_report()
        output = tmp_path / "csdrg.md"
        ts = {"TITLE": "Study ABC-123", "TPHASE": "Phase 2"}

        generate_csdrg(specs, report, "TEST-001", output, ts_params=ts)
        content = output.read_text()

        assert "Study ABC-123" in content
        assert "Phase 2" in content

    def test_section2_placeholder_without_ts_params(self, tmp_path: Path) -> None:
        """Section 2 shows placeholder when no TS params provided."""
        specs = [_make_spec("DM", "Demographics")]
        report = _make_validation_report()
        output = tmp_path / "csdrg.md"

        generate_csdrg(specs, report, "TEST-001", output)
        content = output.read_text()

        assert "[Placeholder:" in content


# ---------------------------------------------------------------------------
# Section 6 -- Known Data Issues
# ---------------------------------------------------------------------------


class TestKnownDataIssues:
    """Tests for cSDRG Section 6 auto-generation from validation findings."""

    def test_no_issues_clean_message(self) -> None:
        """Shows 'no issues' message when there are no errors."""
        report = _make_validation_report(results=[])
        result = _generate_known_data_issues(report)

        assert "No unresolved data quality issues were identified" in result

    def test_errors_grouped_by_domain(self) -> None:
        """ERROR findings are grouped by domain in Section 6."""
        results = [
            RuleResult(
                rule_id="VAL-01",
                rule_description="check",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="AE",
                variable="AETERM",
                message="Invalid CT value",
                affected_count=5,
            ),
            RuleResult(
                rule_id="VAL-02",
                rule_description="check",
                category=RuleCategory.PRESENCE,
                severity=RuleSeverity.ERROR,
                domain="DM",
                variable="AGE",
                message="Missing required values",
                affected_count=3,
            ),
        ]
        report = _make_validation_report(results=results)
        result = _generate_known_data_issues(report)

        assert "**AE:**" in result
        assert "**DM:**" in result
        assert "VAL-01" in result
        assert "VAL-02" in result
        assert "5 record(s)" in result

    def test_excludes_false_positives(self, tmp_path: Path) -> None:
        """Known false positives are excluded from Section 6."""
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
        ]
        report = ValidationReport.from_results(
            study_id="TEST-001",
            results=results,
            domains=["LB"],
            whitelist_path=whitelist_path,
        )
        result = _generate_known_data_issues(report)

        assert "No unresolved data quality issues were identified" in result

    def test_excludes_warnings_and_notices(self) -> None:
        """Only ERROR-level findings appear in Section 6."""
        results = [
            RuleResult(
                rule_id="VAL-W1",
                rule_description="warn",
                category=RuleCategory.FORMAT,
                severity=RuleSeverity.WARNING,
                domain="AE",
                message="Minor warning",
            ),
            RuleResult(
                rule_id="VAL-N1",
                rule_description="notice",
                category=RuleCategory.FORMAT,
                severity=RuleSeverity.NOTICE,
                domain="AE",
                message="Info notice",
            ),
        ]
        report = _make_validation_report(results=results)
        result = _generate_known_data_issues(report)

        assert "No unresolved data quality issues were identified" in result

    def test_section6_in_csdrg(self, tmp_path: Path) -> None:
        """Section 6 in generated cSDRG populates from validation findings."""
        results = [
            RuleResult(
                rule_id="VAL-E1",
                rule_description="check",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="AE",
                variable="AETERM",
                message="Invalid controlled terminology value",
                affected_count=2,
            ),
        ]
        specs = [_make_spec("AE", "Adverse Events")]
        report = _make_validation_report(results=results)
        output = tmp_path / "csdrg.md"

        generate_csdrg(specs, report, "TEST-001", output)
        content = output.read_text()

        assert "VAL-E1" in content
        assert "Invalid controlled terminology value" in content


# ---------------------------------------------------------------------------
# Section 8 -- Non-Standard Variables (per-variable SUPPQUAL justification)
# ---------------------------------------------------------------------------


class TestSuppqualJustification:
    """Tests for cSDRG Section 8 per-variable SUPPQUAL justification."""

    def test_per_variable_justification_text(self) -> None:
        """Each SUPPQUAL candidate gets a justification string."""
        specs = [_make_spec("AE", "Adverse Events", suppqual_candidates=["EXTRA1"])]
        entries = _build_suppqual_justifications(specs, "3.4")

        assert len(entries) == 1
        entry = entries[0]
        assert entry["domain"] == "AE"
        assert entry["variable"] == "EXTRA1"
        assert "SDTM-IG v3.4" in entry["justification"]
        assert "SUPPAE" in entry["justification"]
        assert entry["origin"] in ("CRF", "Derived", "Assigned")

    def test_multiple_candidates_across_domains(self) -> None:
        """Justifications generated for candidates across multiple domains."""
        specs = [
            _make_spec("AE", "Adverse Events", suppqual_candidates=["EXTRA_AE"]),
            _make_spec("CM", "Concomitant Meds", suppqual_candidates=["EXTRA_CM1", "EXTRA_CM2"]),
        ]
        entries = _build_suppqual_justifications(specs, "3.4")

        assert len(entries) == 3
        domains = [e["domain"] for e in entries]
        assert domains.count("AE") == 1
        assert domains.count("CM") == 2

    def test_no_candidates_empty_list(self) -> None:
        """No SUPPQUAL candidates produces empty list."""
        specs = [_make_spec("DM", "Demographics", suppqual_candidates=[])]
        entries = _build_suppqual_justifications(specs, "3.4")
        assert entries == []

    def test_section8_in_csdrg_has_justification(self, tmp_path: Path) -> None:
        """Section 8 in generated cSDRG includes per-variable justification."""
        specs = [_make_spec("AE", "Adverse Events", suppqual_candidates=["EXTRA_VAR"])]
        report = _make_validation_report()
        output = tmp_path / "csdrg.md"

        generate_csdrg(specs, report, "TEST-001", output)
        content = output.read_text()

        assert "EXTRA_VAR" in content
        assert "SDTM-IG v3.4" in content
        assert "SUPPAE" in content
        assert "Justification" in content

    def test_section8_no_candidates_message(self, tmp_path: Path) -> None:
        """Section 8 shows 'no non-standard variables' when none exist."""
        specs = [_make_spec("DM", "Demographics", suppqual_candidates=[])]
        report = _make_validation_report()
        output = tmp_path / "csdrg.md"

        generate_csdrg(specs, report, "TEST-001", output)
        content = output.read_text()

        assert "No non-standard variables requiring SUPPQUAL placement" in content
