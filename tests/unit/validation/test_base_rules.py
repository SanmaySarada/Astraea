"""Tests for validation rule base models."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.models.mapping import DomainMappingSpec
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.validation.rules.base import (
    RuleCategory,
    RuleResult,
    RuleSeverity,
    ValidationRule,
)

# ---------------------------------------------------------------------------
# Concrete test rule (needed because ValidationRule is abstract)
# ---------------------------------------------------------------------------


class AlwaysFailRule(ValidationRule):
    """A test rule that always returns one ERROR result."""

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                message=f"Test failure in domain {domain}",
                affected_count=len(df),
            )
        ]


class AlwaysPassRule(ValidationRule):
    """A test rule that always returns no findings."""

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        return []


# ---------------------------------------------------------------------------
# RuleSeverity tests
# ---------------------------------------------------------------------------


class TestRuleSeverity:
    def test_enum_values(self) -> None:
        assert RuleSeverity.ERROR == "ERROR"
        assert RuleSeverity.WARNING == "WARNING"
        assert RuleSeverity.NOTICE == "NOTICE"

    def test_display_name(self) -> None:
        assert RuleSeverity.ERROR.display_name == "Error"
        assert RuleSeverity.WARNING.display_name == "Warning"
        assert RuleSeverity.NOTICE.display_name == "Notice"

    def test_all_values(self) -> None:
        assert len(RuleSeverity) == 3


# ---------------------------------------------------------------------------
# RuleCategory tests
# ---------------------------------------------------------------------------


class TestRuleCategory:
    def test_enum_values(self) -> None:
        assert RuleCategory.TERMINOLOGY == "TERMINOLOGY"
        assert RuleCategory.PRESENCE == "PRESENCE"
        assert RuleCategory.CONSISTENCY == "CONSISTENCY"
        assert RuleCategory.LIMIT == "LIMIT"
        assert RuleCategory.FORMAT == "FORMAT"
        assert RuleCategory.FDA_BUSINESS == "FDA_BUSINESS"
        assert RuleCategory.FDA_TRC == "FDA_TRC"

    def test_all_values(self) -> None:
        assert len(RuleCategory) == 7


# ---------------------------------------------------------------------------
# RuleResult tests
# ---------------------------------------------------------------------------


class TestRuleResult:
    def test_creation_all_fields(self) -> None:
        result = RuleResult(
            rule_id="VAL-01-001",
            rule_description="Check CT compliance",
            category=RuleCategory.TERMINOLOGY,
            severity=RuleSeverity.ERROR,
            domain="AE",
            variable="AESER",
            message="Value 'YES' not in codelist C66742",
            affected_count=15,
            fix_suggestion="Use 'Y' instead of 'YES'",
            p21_equivalent="CT0001",
        )
        assert result.rule_id == "VAL-01-001"
        assert result.domain == "AE"
        assert result.variable == "AESER"
        assert result.affected_count == 15
        assert result.fix_suggestion is not None
        assert result.p21_equivalent == "CT0001"

    def test_creation_minimal_fields(self) -> None:
        result = RuleResult(
            rule_id="VAL-02-001",
            rule_description="Check required vars",
            category=RuleCategory.PRESENCE,
            severity=RuleSeverity.WARNING,
            message="Variable STUDYID is missing",
        )
        assert result.domain is None
        assert result.variable is None
        assert result.affected_count == 0
        assert result.fix_suggestion is None
        assert result.p21_equivalent is None

    def test_severity_is_rule_severity(self) -> None:
        result = RuleResult(
            rule_id="X",
            rule_description="X",
            category=RuleCategory.FORMAT,
            severity=RuleSeverity.NOTICE,
            message="Info",
        )
        assert isinstance(result.severity, RuleSeverity)
        assert isinstance(result.category, RuleCategory)


# ---------------------------------------------------------------------------
# ValidationRule subclass tests
# ---------------------------------------------------------------------------


class TestValidationRule:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            ValidationRule(
                rule_id="X",
                description="X",
                category=RuleCategory.PRESENCE,
                severity=RuleSeverity.ERROR,
            )

    def test_concrete_subclass_creation(self) -> None:
        rule = AlwaysFailRule(
            rule_id="TEST-001",
            description="Always fails",
            category=RuleCategory.PRESENCE,
            severity=RuleSeverity.ERROR,
        )
        assert rule.rule_id == "TEST-001"
        assert rule.category == RuleCategory.PRESENCE

    def test_evaluate_returns_results(self) -> None:
        rule = AlwaysFailRule(
            rule_id="TEST-001",
            description="Always fails",
            category=RuleCategory.PRESENCE,
            severity=RuleSeverity.ERROR,
        )
        df = pd.DataFrame({"STUDYID": ["S1", "S2"], "DOMAIN": ["AE", "AE"]})
        # Create a minimal DomainMappingSpec
        spec = DomainMappingSpec(
            domain="AE",
            domain_label="Adverse Events",
            domain_class="Events",
            structure="One record per adverse event per subject",
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
        # We pass None for sdtm_ref and ct_ref since AlwaysFailRule doesn't use them
        results = rule.evaluate(
            domain="AE", df=df, spec=spec, sdtm_ref=None, ct_ref=None  # type: ignore[arg-type]
        )
        assert len(results) == 1
        assert results[0].domain == "AE"
        assert results[0].affected_count == 2

    def test_pass_rule_returns_empty(self) -> None:
        rule = AlwaysPassRule(
            rule_id="TEST-PASS",
            description="Always passes",
            category=RuleCategory.FORMAT,
            severity=RuleSeverity.NOTICE,
        )
        df = pd.DataFrame({"X": [1]})
        spec = DomainMappingSpec(
            domain="DM",
            domain_label="Demographics",
            domain_class="Special-Purpose",
            structure="One record per subject",
            study_id="TEST-001",
            total_variables=1,
            required_mapped=1,
            expected_mapped=0,
            high_confidence_count=1,
            medium_confidence_count=0,
            low_confidence_count=0,
            mapping_timestamp="2026-02-28T00:00:00",
            model_used="test",
        )
        results = rule.evaluate(
            domain="DM", df=df, spec=spec, sdtm_ref=None, ct_ref=None  # type: ignore[arg-type]
        )
        assert results == []
