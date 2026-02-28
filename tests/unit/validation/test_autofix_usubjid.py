"""Tests for USUBJID auto-fix classification as NEEDS_HUMAN."""

from __future__ import annotations

import pytest

from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.validation.autofix import AutoFixer, FixClassification
from astraea.validation.rules.base import RuleCategory, RuleResult, RuleSeverity


@pytest.fixture()
def fixer() -> AutoFixer:
    return AutoFixer(ct_ref=CTReference(), sdtm_ref=SDTMReference())


def _missing_var_result(variable: str) -> RuleResult:
    return RuleResult(
        rule_id="ASTR-P001",
        rule_name="Required Variable Present",
        rule_description="Checks that required variables are present",
        severity=RuleSeverity.ERROR,
        category=RuleCategory.PRESENCE,
        domain="DM",
        variable=variable,
        message=f"Required variable {variable} is missing from DM",
        affected_count=100,
    )


class TestUSUBJIDClassification:
    """USUBJID must be classified as NEEDS_HUMAN, not AUTO_FIXABLE."""

    def test_usubjid_needs_human(self, fixer: AutoFixer) -> None:
        result = _missing_var_result("USUBJID")
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.NEEDS_HUMAN

    def test_studyid_still_auto_fixable(self, fixer: AutoFixer) -> None:
        result = _missing_var_result("STUDYID")
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.AUTO_FIXABLE

    def test_domain_still_auto_fixable(self, fixer: AutoFixer) -> None:
        result = _missing_var_result("DOMAIN")
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.AUTO_FIXABLE
