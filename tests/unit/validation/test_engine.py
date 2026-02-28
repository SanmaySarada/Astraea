"""Tests for the ValidationEngine orchestrator and ValidationReport."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from astraea.models.mapping import DomainMappingSpec
from astraea.validation.engine import ValidationEngine
from astraea.validation.report import ValidationReport
from astraea.validation.rules.base import (
    RuleCategory,
    RuleResult,
    RuleSeverity,
    ValidationRule,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class CountingRule(ValidationRule):
    """Rule that returns one result per row in the DataFrame."""

    def evaluate(self, domain, df, spec, sdtm_ref, ct_ref) -> list[RuleResult]:
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                message=f"Row {i} checked",
                affected_count=1,
            )
            for i in range(len(df))
        ]


class ErrorRule(ValidationRule):
    """Rule that always returns one error."""

    def evaluate(self, domain, df, spec, sdtm_ref, ct_ref) -> list[RuleResult]:
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=RuleSeverity.ERROR,
                domain=domain,
                message="Error found",
            )
        ]


class WarningRule(ValidationRule):
    """Rule that always returns one warning."""

    def evaluate(self, domain, df, spec, sdtm_ref, ct_ref) -> list[RuleResult]:
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=RuleSeverity.WARNING,
                domain=domain,
                message="Warning found",
            )
        ]


class ExplodingRule(ValidationRule):
    """Rule that raises an exception during evaluate."""

    def evaluate(self, domain, df, spec, sdtm_ref, ct_ref) -> list[RuleResult]:
        msg = "Something went wrong"
        raise RuntimeError(msg)


def _make_spec(domain: str = "AE") -> DomainMappingSpec:
    return DomainMappingSpec(
        domain=domain,
        domain_label=f"{domain} Domain",
        domain_class="Events",
        structure="One record per event per subject",
        study_id="TEST-001",
        total_variables=2,
        required_mapped=2,
        expected_mapped=0,
        high_confidence_count=2,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


@pytest.fixture
def mock_sdtm_ref() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_ct_ref() -> MagicMock:
    return MagicMock()


@pytest.fixture
def engine(mock_sdtm_ref: MagicMock, mock_ct_ref: MagicMock) -> ValidationEngine:
    return ValidationEngine(sdtm_ref=mock_sdtm_ref, ct_ref=mock_ct_ref)


@pytest.fixture
def small_df() -> pd.DataFrame:
    return pd.DataFrame({"STUDYID": ["S1", "S2"], "DOMAIN": ["AE", "AE"]})


# ---------------------------------------------------------------------------
# ValidationEngine tests
# ---------------------------------------------------------------------------


class TestValidationEngine:
    def test_creation_with_mocks(self, engine: ValidationEngine) -> None:
        assert engine is not None

    def test_default_rules_loaded(self, engine: ValidationEngine) -> None:
        # Default rules are auto-registered from terminology, presence,
        # limits, format, FDA business rule modules
        assert len(engine.rules) > 0

    def test_register_adds_rule(self, engine: ValidationEngine) -> None:
        initial_count = len(engine.rules)
        rule = CountingRule(
            rule_id="T-001",
            description="Count rows",
            category=RuleCategory.PRESENCE,
            severity=RuleSeverity.NOTICE,
        )
        engine.register(rule)
        assert len(engine.rules) == initial_count + 1
        assert engine.rules[-1].rule_id == "T-001"

    def test_validate_domain_runs_rules(
        self, engine: ValidationEngine, small_df: pd.DataFrame
    ) -> None:
        rule = CountingRule(
            rule_id="T-001",
            description="Count",
            category=RuleCategory.PRESENCE,
            severity=RuleSeverity.NOTICE,
        )
        engine.register(rule)
        results = engine.validate_domain("AE", small_df, _make_spec("AE"))
        # Should include results from CountingRule (one per row) plus default rules
        counting_results = [r for r in results if r.rule_id == "T-001"]
        assert len(counting_results) == 2  # one per row
        assert all(r.domain == "AE" for r in counting_results)

    def test_validate_domain_returns_default_rule_results(
        self, engine: ValidationEngine, small_df: pd.DataFrame
    ) -> None:
        # Default rules produce results (may be empty for clean data)
        results = engine.validate_domain("AE", small_df, _make_spec("AE"))
        # All results should have domain set to AE
        assert all(r.domain == "AE" for r in results if r.domain is not None)

    def test_validate_all_runs_across_domains(self, engine: ValidationEngine) -> None:
        rule = ErrorRule(
            rule_id="E-001",
            description="Error",
            category=RuleCategory.TERMINOLOGY,
            severity=RuleSeverity.ERROR,
        )
        engine.register(rule)

        ae_df = pd.DataFrame({"X": [1]})
        dm_df = pd.DataFrame({"X": [1, 2]})
        domains = {
            "AE": (ae_df, _make_spec("AE")),
            "DM": (dm_df, _make_spec("DM")),
        }
        results = engine.validate_all(domains)
        # Should include at least one error per domain from ErrorRule
        error_results = [r for r in results if r.rule_id == "E-001"]
        assert len(error_results) == 2  # one error per domain
        domains_found = {r.domain for r in error_results}
        assert domains_found == {"AE", "DM"}

    def test_validate_domain_handles_rule_exception(
        self, engine: ValidationEngine, small_df: pd.DataFrame
    ) -> None:
        rule = ExplodingRule(
            rule_id="BOOM",
            description="Explodes",
            category=RuleCategory.FORMAT,
            severity=RuleSeverity.ERROR,
        )
        engine.register(rule)
        results = engine.validate_domain("AE", small_df, _make_spec("AE"))
        boom_results = [r for r in results if r.rule_id == "BOOM"]
        assert len(boom_results) == 1
        assert "Rule execution failed" in boom_results[0].message
        assert boom_results[0].severity == RuleSeverity.WARNING

    def test_filter_by_category(self, engine: ValidationEngine) -> None:
        results = [
            RuleResult(
                rule_id="A",
                rule_description="A",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                message="term error",
            ),
            RuleResult(
                rule_id="B",
                rule_description="B",
                category=RuleCategory.PRESENCE,
                severity=RuleSeverity.ERROR,
                message="presence error",
            ),
        ]
        filtered = engine.filter_results(results, category=RuleCategory.TERMINOLOGY)
        assert len(filtered) == 1
        assert filtered[0].rule_id == "A"

    def test_filter_by_severity(self, engine: ValidationEngine) -> None:
        results = [
            RuleResult(
                rule_id="A",
                rule_description="A",
                category=RuleCategory.FORMAT,
                severity=RuleSeverity.ERROR,
                message="error",
            ),
            RuleResult(
                rule_id="B",
                rule_description="B",
                category=RuleCategory.FORMAT,
                severity=RuleSeverity.WARNING,
                message="warning",
            ),
        ]
        filtered = engine.filter_results(results, severity=RuleSeverity.WARNING)
        assert len(filtered) == 1
        assert filtered[0].rule_id == "B"

    def test_filter_by_domain(self, engine: ValidationEngine) -> None:
        results = [
            RuleResult(
                rule_id="A",
                rule_description="A",
                category=RuleCategory.LIMIT,
                severity=RuleSeverity.NOTICE,
                domain="AE",
                message="ae notice",
            ),
            RuleResult(
                rule_id="B",
                rule_description="B",
                category=RuleCategory.LIMIT,
                severity=RuleSeverity.NOTICE,
                domain="DM",
                message="dm notice",
            ),
        ]
        filtered = engine.filter_results(results, domain="DM")
        assert len(filtered) == 1
        assert filtered[0].domain == "DM"

    def test_filter_combined(self, engine: ValidationEngine) -> None:
        results = [
            RuleResult(
                rule_id="A",
                rule_description="A",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="AE",
                message="ae term error",
            ),
            RuleResult(
                rule_id="B",
                rule_description="B",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.WARNING,
                domain="AE",
                message="ae term warning",
            ),
            RuleResult(
                rule_id="C",
                rule_description="C",
                category=RuleCategory.PRESENCE,
                severity=RuleSeverity.ERROR,
                domain="DM",
                message="dm presence error",
            ),
        ]
        filtered = engine.filter_results(
            results,
            category=RuleCategory.TERMINOLOGY,
            severity=RuleSeverity.ERROR,
            domain="AE",
        )
        assert len(filtered) == 1
        assert filtered[0].rule_id == "A"


# ---------------------------------------------------------------------------
# ValidationReport tests
# ---------------------------------------------------------------------------


class TestValidationReport:
    def test_from_results_no_findings(self) -> None:
        report = ValidationReport.from_results(
            study_id="TEST-001",
            results=[],
            domains=["AE", "DM"],
        )
        assert report.study_id == "TEST-001"
        assert report.error_count == 0
        assert report.warning_count == 0
        assert report.notice_count == 0
        assert report.pass_rate == 1.0
        assert report.submission_ready is True
        assert len(report.domains_validated) == 2

    def test_from_results_with_errors(self) -> None:
        results = [
            RuleResult(
                rule_id="E1",
                rule_description="Error rule",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="AE",
                message="CT mismatch",
            ),
            RuleResult(
                rule_id="W1",
                rule_description="Warning rule",
                category=RuleCategory.PRESENCE,
                severity=RuleSeverity.WARNING,
                domain="AE",
                message="Missing expected var",
            ),
            RuleResult(
                rule_id="N1",
                rule_description="Notice rule",
                category=RuleCategory.FORMAT,
                severity=RuleSeverity.NOTICE,
                domain="DM",
                message="Best practice",
            ),
        ]
        report = ValidationReport.from_results(
            study_id="TEST-001",
            results=results,
            domains=["AE", "DM"],
        )
        assert report.error_count == 1
        assert report.warning_count == 1
        assert report.notice_count == 1
        assert report.submission_ready is False
        # AE has errors, DM does not -> 50% pass rate
        assert report.pass_rate == 0.5

    def test_summary_by_domain(self) -> None:
        results = [
            RuleResult(
                rule_id="E1",
                rule_description="E",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="AE",
                message="err",
            ),
            RuleResult(
                rule_id="E2",
                rule_description="E",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="AE",
                message="err2",
            ),
            RuleResult(
                rule_id="W1",
                rule_description="W",
                category=RuleCategory.PRESENCE,
                severity=RuleSeverity.WARNING,
                domain="DM",
                message="warn",
            ),
        ]
        report = ValidationReport.from_results("S1", results, ["AE", "DM"])
        assert report.summary_by_domain["AE"]["errors"] == 2
        assert report.summary_by_domain["AE"]["warnings"] == 0
        assert report.summary_by_domain["DM"]["errors"] == 0
        assert report.summary_by_domain["DM"]["warnings"] == 1

    def test_summary_by_category(self) -> None:
        results = [
            RuleResult(
                rule_id="T1",
                rule_description="T",
                category=RuleCategory.TERMINOLOGY,
                severity=RuleSeverity.ERROR,
                domain="AE",
                message="term",
            ),
            RuleResult(
                rule_id="P1",
                rule_description="P",
                category=RuleCategory.PRESENCE,
                severity=RuleSeverity.WARNING,
                domain="DM",
                message="pres",
            ),
        ]
        report = ValidationReport.from_results("S1", results, ["AE", "DM"])
        assert "TERMINOLOGY" in report.summary_by_category
        assert report.summary_by_category["TERMINOLOGY"]["errors"] == 1
        assert "PRESENCE" in report.summary_by_category
        assert report.summary_by_category["PRESENCE"]["warnings"] == 1
        # Categories with no results should not appear
        assert "FORMAT" not in report.summary_by_category

    def test_generated_at_is_iso(self) -> None:
        report = ValidationReport.from_results("S1", [], ["AE"])
        assert "T" in report.generated_at  # ISO 8601 format has T separator

    def test_pass_rate_all_domains_have_errors(self) -> None:
        results = [
            RuleResult(
                rule_id="E1",
                rule_description="E",
                category=RuleCategory.LIMIT,
                severity=RuleSeverity.ERROR,
                domain="AE",
                message="err",
            ),
            RuleResult(
                rule_id="E2",
                rule_description="E",
                category=RuleCategory.LIMIT,
                severity=RuleSeverity.ERROR,
                domain="DM",
                message="err",
            ),
        ]
        report = ValidationReport.from_results("S1", results, ["AE", "DM"])
        assert report.pass_rate == 0.0

    def test_empty_domains_list(self) -> None:
        report = ValidationReport.from_results("S1", [], [])
        assert report.pass_rate == 1.0
        assert report.submission_ready is True
        assert report.domains_validated == []

    def test_total_rules_run(self) -> None:
        results = [
            RuleResult(
                rule_id=f"R{i}",
                rule_description="R",
                category=RuleCategory.FORMAT,
                severity=RuleSeverity.NOTICE,
                message="info",
            )
            for i in range(5)
        ]
        report = ValidationReport.from_results("S1", results, ["AE"])
        assert report.total_rules_run == 5
