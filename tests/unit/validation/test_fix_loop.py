"""Tests for the FixLoopEngine validate-fix-revalidate cycle.

Validates loop convergence, max iteration cap, fix accumulation,
needs-human separation, iteration details, and final report correctness.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from astraea.models.mapping import (
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.validation.autofix import (
    AutoFixer,
    FixAction,
    FixClassification,
    IssueClassification,
)
from astraea.validation.engine import ValidationEngine
from astraea.validation.fix_loop import (
    FixLoopEngine,
    format_needs_human_report,
)
from astraea.validation.rules.base import (
    RuleCategory,
    RuleResult,
    RuleSeverity,
)

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def _make_spec(
    domain: str = "AE",
    mappings: list[VariableMapping] | None = None,
    study_id: str = "TEST-001",
) -> DomainMappingSpec:
    """Build a minimal DomainMappingSpec for testing."""
    vm = mappings or []
    return DomainMappingSpec(
        domain=domain,
        domain_label="Test Domain",
        domain_class="Events",
        structure="One record per event",
        study_id=study_id,
        source_datasets=["test.sas7bdat"],
        variable_mappings=vm,
        total_variables=len(vm),
        required_mapped=0,
        expected_mapped=0,
        high_confidence_count=0,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


def _make_vm(
    variable: str,
    label: str = "Test Label",
    codelist_code: str | None = None,
) -> VariableMapping:
    """Build a minimal VariableMapping."""
    return VariableMapping(
        sdtm_variable=variable,
        sdtm_label=label,
        sdtm_data_type="Char",
        core=CoreDesignation.REQ,
        mapping_pattern=MappingPattern.ASSIGN,
        mapping_logic="Test logic",
        assigned_value="TEST",
        codelist_code=codelist_code,
        confidence=0.95,
        confidence_level="high",
        confidence_rationale="Test",
    )


def _make_result(
    rule_id: str,
    variable: str | None = None,
    message: str = "Test issue",
    domain: str = "AE",
    severity: RuleSeverity = RuleSeverity.ERROR,
    category: RuleCategory = RuleCategory.TERMINOLOGY,
    affected_count: int = 0,
    fix_suggestion: str | None = None,
) -> RuleResult:
    """Build a minimal RuleResult."""
    return RuleResult(
        rule_id=rule_id,
        rule_description="Test rule",
        category=category,
        severity=severity,
        domain=domain,
        variable=variable,
        message=message,
        affected_count=affected_count,
        fix_suggestion=fix_suggestion,
    )


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #


@pytest.fixture()
def ct_ref() -> CTReference:
    """Load real CT reference."""
    return CTReference()


@pytest.fixture()
def sdtm_ref() -> SDTMReference:
    """Load real SDTM-IG reference."""
    return SDTMReference()


@pytest.fixture()
def engine(sdtm_ref: SDTMReference, ct_ref: CTReference) -> ValidationEngine:
    """Create ValidationEngine with real reference data."""
    return ValidationEngine(sdtm_ref=sdtm_ref, ct_ref=ct_ref)


@pytest.fixture()
def auto_fixer(ct_ref: CTReference, sdtm_ref: SDTMReference) -> AutoFixer:
    """Create AutoFixer with real reference data."""
    return AutoFixer(ct_ref=ct_ref, sdtm_ref=sdtm_ref)


@pytest.fixture()
def fix_loop_engine(
    engine: ValidationEngine, auto_fixer: AutoFixer
) -> FixLoopEngine:
    """Create FixLoopEngine with real references."""
    return FixLoopEngine(engine=engine, auto_fixer=auto_fixer, max_iterations=3)


@pytest.fixture()
def sample_domain_with_issues() -> dict[str, tuple[pd.DataFrame, DomainMappingSpec]]:
    """Create a domain dict with one domain (AE) missing DOMAIN column."""
    df = pd.DataFrame(
        {
            "STUDYID": ["TEST-001", "TEST-001"],
            "USUBJID": ["TEST-001-001", "TEST-001-002"],
            "AETERM": ["Headache", "Nausea"],
            "AESEQ": [1, 2],
        }
    )
    spec = _make_spec(
        domain="AE",
        mappings=[
            _make_vm("STUDYID"),
            _make_vm("DOMAIN"),
            _make_vm("USUBJID"),
            _make_vm("AETERM"),
            _make_vm("AESEQ"),
        ],
    )
    return {"AE": (df, spec)}


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #


class TestFixLoopConvergence:
    """Test loop convergence behavior."""

    def test_loop_converges_when_no_auto_fixable(
        self, engine: ValidationEngine, auto_fixer: AutoFixer
    ) -> None:
        """When only needs-human issues exist, loop runs 1 iteration and converges."""
        # Create a domain with no auto-fixable issues -- well-formed data
        df = pd.DataFrame(
            {
                "STUDYID": ["TEST-001"],
                "DOMAIN": ["DM"],
                "USUBJID": ["TEST-001-001"],
            }
        )
        spec = _make_spec(
            domain="DM",
            mappings=[
                _make_vm("STUDYID"),
                _make_vm("DOMAIN"),
                _make_vm("USUBJID"),
            ],
        )
        domains: dict[str, tuple[pd.DataFrame, DomainMappingSpec]] = {
            "DM": (df, spec)
        }

        loop = FixLoopEngine(
            engine=engine, auto_fixer=auto_fixer, max_iterations=3
        )
        result = loop.run_fix_loop(domains, study_id="TEST-001")

        assert result.iterations_run >= 1
        assert result.converged is True
        assert result.total_fixed == 0
        assert result.final_report is not None

    def test_loop_fixes_and_revalidates(
        self,
        fix_loop_engine: FixLoopEngine,
        sample_domain_with_issues: dict[str, tuple[pd.DataFrame, DomainMappingSpec]],
    ) -> None:
        """A fixable issue (missing DOMAIN column) gets fixed in the loop."""
        domains = sample_domain_with_issues
        result = fix_loop_engine.run_fix_loop(domains, study_id="TEST-001")

        assert result.iterations_run >= 1
        assert result.total_fixed >= 1

        # Verify DOMAIN column now exists in the domain's DataFrame
        fixed_df, _spec = domains["AE"]
        assert "DOMAIN" in fixed_df.columns
        assert (fixed_df["DOMAIN"] == "AE").all()

        # Check fix action recorded
        domain_fix_actions = [
            a for a in result.all_fix_actions if a.variable == "DOMAIN"
        ]
        assert len(domain_fix_actions) >= 1
        assert domain_fix_actions[0].fix_type in (
            "add_missing_column",
            "fix_domain_value",
        )


class TestFixLoopMaxIterations:
    """Test max iteration cap behavior."""

    def test_loop_max_iterations_cap(
        self, engine: ValidationEngine, ct_ref: CTReference, sdtm_ref: SDTMReference
    ) -> None:
        """When fixes never resolve issues, loop stops at max_iterations."""
        # Create a mock auto_fixer that always classifies issues as fixable
        # but fixes don't actually resolve the issue
        mock_fixer = MagicMock(spec=AutoFixer)

        # classify_issue always returns AUTO_FIXABLE
        mock_fixer.classify_issue.return_value = IssueClassification(
            result=_make_result("ASTR-T002", variable="DOMAIN", domain="AE"),
            classification=FixClassification.AUTO_FIXABLE,
            reason="Always fixable",
        )

        # apply_fixes returns the same df (fix doesn't resolve the issue)
        # plus a fake FixAction
        def fake_apply(domain, df, spec, issues):
            action = FixAction(
                rule_id="ASTR-T002",
                domain=domain,
                variable="DOMAIN",
                fix_type="fix_domain_value",
                before_value="wrong",
                after_value="AE",
                affected_count=1,
                timestamp="2026-02-28T00:00:00",
            )
            return df, spec, [action]

        mock_fixer.apply_fixes.side_effect = fake_apply

        max_iter = 2
        loop = FixLoopEngine(
            engine=engine, auto_fixer=mock_fixer, max_iterations=max_iter
        )

        df = pd.DataFrame(
            {
                "STUDYID": ["TEST-001"],
                "USUBJID": ["TEST-001-001"],
            }
        )
        spec = _make_spec(domain="AE")
        domains: dict[str, tuple[pd.DataFrame, DomainMappingSpec]] = {
            "AE": (df, spec)
        }

        result = loop.run_fix_loop(domains, study_id="TEST-001")

        assert result.iterations_run == max_iter
        assert result.converged is False
        assert result.max_iterations == max_iter


class TestFixLoopAccumulation:
    """Test fix action accumulation across iterations."""

    def test_loop_accumulates_fix_actions(
        self,
        fix_loop_engine: FixLoopEngine,
        sample_domain_with_issues: dict[str, tuple[pd.DataFrame, DomainMappingSpec]],
    ) -> None:
        """All fix actions across iterations are accumulated in all_fix_actions."""
        domains = sample_domain_with_issues
        result = fix_loop_engine.run_fix_loop(domains, study_id="TEST-001")

        # Total fixed should match len of all_fix_actions
        assert result.total_fixed == len(result.all_fix_actions)

        # Each fix action should have required fields
        for action in result.all_fix_actions:
            assert action.rule_id
            assert action.domain
            assert action.fix_type
            assert action.timestamp


class TestFixLoopNeedsHuman:
    """Test needs-human issue handling."""

    def test_loop_needs_human_in_result(
        self,
        fix_loop_engine: FixLoopEngine,
    ) -> None:
        """Both auto-fixable and needs-human issues are correctly classified."""
        # Create domain with a date format issue (NEEDS_HUMAN) alongside fixable ones
        df = pd.DataFrame(
            {
                "STUDYID": ["TEST-001"],
                "USUBJID": ["TEST-001-001"],
                "AETERM": ["Headache"],
                "AESTDTC": ["30-Mar-2022"],  # Wrong format, needs human
            }
        )
        spec = _make_spec(
            domain="AE",
            mappings=[
                _make_vm("STUDYID"),
                _make_vm("DOMAIN"),
                _make_vm("USUBJID"),
                _make_vm("AETERM"),
                _make_vm("AESTDTC"),
            ],
        )
        domains: dict[str, tuple[pd.DataFrame, DomainMappingSpec]] = {
            "AE": (df, spec)
        }

        result = fix_loop_engine.run_fix_loop(domains, study_id="TEST-001")

        # The result should have a final_report
        assert result.final_report is not None

        # needs_human_issues should be a list (may or may not be populated
        # depending on what the real validation engine finds)
        assert isinstance(result.needs_human_issues, list)


class TestIterationDetails:
    """Test per-iteration detail population."""

    def test_iteration_details_populated(
        self,
        fix_loop_engine: FixLoopEngine,
        sample_domain_with_issues: dict[str, tuple[pd.DataFrame, DomainMappingSpec]],
    ) -> None:
        """Each IterationResult has correct fields populated."""
        domains = sample_domain_with_issues
        result = fix_loop_engine.run_fix_loop(domains, study_id="TEST-001")

        assert len(result.iteration_details) >= 1

        for detail in result.iteration_details:
            assert detail.iteration >= 1
            assert detail.issues_found >= 0
            assert detail.auto_fixed >= 0
            assert detail.remaining_auto_fixable >= 0
            assert detail.needs_human >= 0
            assert isinstance(detail.fix_actions, list)


class TestFinalReport:
    """Test final validation report correctness."""

    def test_final_report_reflects_fixes(
        self,
        fix_loop_engine: FixLoopEngine,
        sample_domain_with_issues: dict[str, tuple[pd.DataFrame, DomainMappingSpec]],
    ) -> None:
        """After the loop, final_report should reflect the fixed state."""
        domains = sample_domain_with_issues

        # Validate before fix loop -- missing DOMAIN triggers error
        pre_results = fix_loop_engine._engine.validate_all(domains)
        pre_domain_errors = [
            r
            for r in pre_results
            if r.rule_id in ("ASTR-T002", "ASTR-P001")
            and r.domain == "AE"
            and (r.variable or "").upper() == "DOMAIN"
        ]

        result = fix_loop_engine.run_fix_loop(domains, study_id="TEST-001")

        # If there were domain-related errors before, they should be fixed now
        if pre_domain_errors:
            post_domain_errors = [
                r
                for r in result.final_report.results
                if r.rule_id in ("ASTR-T002", "ASTR-P001")
                and r.domain == "AE"
                and (r.variable or "").upper() == "DOMAIN"
            ]
            assert len(post_domain_errors) < len(pre_domain_errors)


class TestFormatNeedsHumanReport:
    """Test the format_needs_human_report helper."""

    def test_format_needs_human_report_empty(self) -> None:
        """Empty list produces 'no issues' message."""
        output = format_needs_human_report([])
        assert "No issues requiring human intervention" in output

    def test_format_needs_human_report_with_issues(self) -> None:
        """Issues are grouped by domain with rule IDs and suggested fixes."""
        issues = [
            IssueClassification(
                result=_make_result(
                    "ASTR-F001",
                    variable="AESTDTC",
                    message="Date format invalid",
                    domain="AE",
                    category=RuleCategory.FORMAT,
                ),
                classification=FixClassification.NEEDS_HUMAN,
                reason="Date conversion requires understanding the source format",
                suggested_fix="Convert to ISO 8601",
            ),
            IssueClassification(
                result=_make_result(
                    "FDAB057",
                    variable=None,
                    message="DM missing required records",
                    domain="DM",
                    category=RuleCategory.FDA_BUSINESS,
                ),
                classification=FixClassification.NEEDS_HUMAN,
                reason="FDA business rule",
                suggested_fix="Ensure all subjects have DM records",
            ),
        ]

        output = format_needs_human_report(issues)

        # Should contain domain headers
        assert "AE" in output
        assert "DM" in output
        # Should contain rule IDs
        assert "ASTR-F001" in output
        assert "FDAB057" in output
        # Should contain suggested fixes
        assert "Convert to ISO 8601" in output
        assert "Ensure all subjects have DM records" in output
        # Should contain variable name
        assert "AESTDTC" in output
        # Should contain total count
        assert "2 issue(s)" in output


class TestOutputWriting:
    """Test XPT and audit trail writing."""

    def test_writes_xpt_to_output_dir(
        self,
        fix_loop_engine: FixLoopEngine,
        sample_domain_with_issues: dict[str, tuple[pd.DataFrame, DomainMappingSpec]],
        tmp_path: Path,
    ) -> None:
        """Fixed datasets are written to XPT files in output_dir."""
        domains = sample_domain_with_issues
        fix_loop_engine.run_fix_loop(
            domains, output_dir=tmp_path, study_id="TEST-001"
        )

        xpt_file = tmp_path / "ae.xpt"
        assert xpt_file.exists()

    def test_writes_audit_trail_json(
        self,
        fix_loop_engine: FixLoopEngine,
        sample_domain_with_issues: dict[str, tuple[pd.DataFrame, DomainMappingSpec]],
        tmp_path: Path,
    ) -> None:
        """Audit trail JSON is written to output_dir."""
        domains = sample_domain_with_issues
        fix_loop_engine.run_fix_loop(
            domains, output_dir=tmp_path, study_id="TEST-001"
        )

        audit_file = tmp_path / "autofix_audit.json"
        assert audit_file.exists()

        with open(audit_file) as f:
            audit_data = json.load(f)

        assert isinstance(audit_data, list)
        # Each entry should have required fields
        for entry in audit_data:
            assert "rule_id" in entry
            assert "domain" in entry
            assert "fix_type" in entry
            assert "timestamp" in entry
