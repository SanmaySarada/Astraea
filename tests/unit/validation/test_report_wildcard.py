"""Tests for wildcard matching in known_false_positives flagging."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from astraea.validation.report import ValidationReport
from astraea.validation.rules.base import RuleCategory, RuleResult, RuleSeverity


def _make_result(
    rule_id: str = "ASTR-T001",
    domain: str = "DM",
    variable: str = "SEX",
    severity: RuleSeverity = RuleSeverity.WARNING,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_name="Test Rule",
        rule_description="Test rule description",
        severity=severity,
        category=RuleCategory.TERMINOLOGY,
        domain=domain,
        variable=variable,
        message="Test finding",
        affected_count=1,
    )


def _write_whitelist(entries: list[dict], tmp_path: Path) -> Path:
    path = tmp_path / "whitelist.json"
    path.write_text(json.dumps({"entries": entries}))
    return path


class TestWildcardDomainMatching:
    """Wildcard '*' in domain field should match all domains."""

    def test_wildcard_domain_matches_dm(self, tmp_path: Path) -> None:
        whitelist_path = _write_whitelist(
            [{"rule_id": "ASTR-T001", "domain": "*", "reason": "Known issue"}],
            tmp_path,
        )
        report = ValidationReport(study_id="TEST", results=[_make_result(domain="DM")])
        report.flag_known_false_positives(whitelist_path)
        assert report.results[0].known_false_positive is True

    def test_wildcard_domain_matches_ae(self, tmp_path: Path) -> None:
        whitelist_path = _write_whitelist(
            [{"rule_id": "ASTR-T001", "domain": "*", "reason": "Known issue"}],
            tmp_path,
        )
        report = ValidationReport(study_id="TEST", results=[_make_result(domain="AE")])
        report.flag_known_false_positives(whitelist_path)
        assert report.results[0].known_false_positive is True

    def test_wildcard_domain_matches_lb(self, tmp_path: Path) -> None:
        whitelist_path = _write_whitelist(
            [{"rule_id": "ASTR-T001", "domain": "*", "reason": "Known issue"}],
            tmp_path,
        )
        report = ValidationReport(study_id="TEST", results=[_make_result(domain="LB")])
        report.flag_known_false_positives(whitelist_path)
        assert report.results[0].known_false_positive is True


class TestWildcardVariableMatching:
    """Wildcard '*' in variable field should match all variables."""

    def test_wildcard_variable_matches_any(self, tmp_path: Path) -> None:
        whitelist_path = _write_whitelist(
            [{"rule_id": "ASTR-T001", "domain": "DM", "variable": "*", "reason": "Known"}],
            tmp_path,
        )
        report = ValidationReport(
            study_id="TEST",
            results=[_make_result(variable="RACE")],
        )
        report.flag_known_false_positives(whitelist_path)
        assert report.results[0].known_false_positive is True

    def test_wildcard_both_domain_and_variable(self, tmp_path: Path) -> None:
        whitelist_path = _write_whitelist(
            [{"rule_id": "ASTR-T001", "domain": "*", "variable": "*", "reason": "All"}],
            tmp_path,
        )
        results = [
            _make_result(domain="DM", variable="SEX"),
            _make_result(domain="AE", variable="AETERM"),
        ]
        report = ValidationReport(study_id="TEST", results=results)
        report.flag_known_false_positives(whitelist_path)
        assert all(r.known_false_positive for r in report.results)


class TestNullDomainPreserved:
    """Null domain/variable in whitelist entry still means match-all (existing behavior)."""

    def test_null_domain_matches_all(self, tmp_path: Path) -> None:
        whitelist_path = _write_whitelist(
            [{"rule_id": "ASTR-T001", "reason": "No domain specified"}],
            tmp_path,
        )
        results = [
            _make_result(domain="DM"),
            _make_result(domain="AE"),
        ]
        report = ValidationReport(study_id="TEST", results=results)
        report.flag_known_false_positives(whitelist_path)
        assert all(r.known_false_positive for r in report.results)

    def test_null_variable_matches_all(self, tmp_path: Path) -> None:
        whitelist_path = _write_whitelist(
            [{"rule_id": "ASTR-T001", "domain": "DM", "reason": "No variable"}],
            tmp_path,
        )
        results = [
            _make_result(domain="DM", variable="SEX"),
            _make_result(domain="DM", variable="RACE"),
        ]
        report = ValidationReport(study_id="TEST", results=results)
        report.flag_known_false_positives(whitelist_path)
        assert all(r.known_false_positive for r in report.results)

    def test_specific_domain_does_not_match_other(self, tmp_path: Path) -> None:
        """Non-wildcard domain should still filter correctly."""
        whitelist_path = _write_whitelist(
            [{"rule_id": "ASTR-T001", "domain": "DM", "reason": "DM only"}],
            tmp_path,
        )
        results = [
            _make_result(domain="DM"),
            _make_result(domain="AE"),
        ]
        report = ValidationReport(study_id="TEST", results=results)
        report.flag_known_false_positives(whitelist_path)
        assert report.results[0].known_false_positive is True
        assert report.results[1].known_false_positive is False
