"""Tests for the AutoFixer issue classification and fix functions.

Validates that each validation rule ID is correctly classified as
auto-fixable or needs-human, and that fix functions produce correct
results with complete audit trails.
"""

from __future__ import annotations

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
    FixClassification,
)
from astraea.validation.rules.base import (
    RuleCategory,
    RuleResult,
    RuleSeverity,
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
def fixer(ct_ref: CTReference, sdtm_ref: SDTMReference) -> AutoFixer:
    """Create AutoFixer instance."""
    return AutoFixer(ct_ref=ct_ref, sdtm_ref=sdtm_ref)


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


# ================================================================== #
# Classification tests
# ================================================================== #


class TestClassifyIssues:
    """Test classify_issue() for all known rule IDs."""

    def test_classify_ct_case_mismatch_as_auto_fixable(self, fixer: AutoFixer) -> None:
        """ASTR-T001 with case-mismatch values should be AUTO_FIXABLE."""
        # SEX codelist C66731 has 'M' and 'F' as submission values
        result = _make_result(
            rule_id="ASTR-T001",
            variable="SEX",
            message="Invalid CT value(s) in SEX: 'm', 'f'",
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.AUTO_FIXABLE

    def test_classify_ct_wrong_value_as_needs_human(self, fixer: AutoFixer) -> None:
        """ASTR-T001 with genuinely wrong value should be NEEDS_HUMAN."""
        result = _make_result(
            rule_id="ASTR-T001",
            variable="SEX",
            message="Invalid CT value(s) in SEX: 'UNKNOWN_VALUE'",
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.NEEDS_HUMAN

    def test_classify_domain_missing_as_auto_fixable(self, fixer: AutoFixer) -> None:
        """ASTR-T002 should always be AUTO_FIXABLE."""
        result = _make_result(
            rule_id="ASTR-T002",
            variable="DOMAIN",
            message="DOMAIN column is missing from the dataset",
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.AUTO_FIXABLE

    def test_classify_required_studyid_as_auto_fixable(self, fixer: AutoFixer) -> None:
        """ASTR-P001 for STUDYID should be AUTO_FIXABLE."""
        result = _make_result(
            rule_id="ASTR-P001",
            variable="STUDYID",
            message="Required variable STUDYID is missing",
            category=RuleCategory.PRESENCE,
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.AUTO_FIXABLE

    def test_classify_required_domain_as_auto_fixable(self, fixer: AutoFixer) -> None:
        """ASTR-P001 for DOMAIN should be AUTO_FIXABLE."""
        result = _make_result(
            rule_id="ASTR-P001",
            variable="DOMAIN",
            message="Required variable DOMAIN is missing",
            category=RuleCategory.PRESENCE,
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.AUTO_FIXABLE

    def test_classify_required_other_as_needs_human(self, fixer: AutoFixer) -> None:
        """ASTR-P001 for AETERM should be NEEDS_HUMAN."""
        result = _make_result(
            rule_id="ASTR-P001",
            variable="AETERM",
            message="Required variable AETERM is missing",
            category=RuleCategory.PRESENCE,
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.NEEDS_HUMAN

    def test_classify_name_length_as_auto_fixable(self, fixer: AutoFixer) -> None:
        """ASTR-L001 should be AUTO_FIXABLE."""
        result = _make_result(
            rule_id="ASTR-L001",
            variable="LONGVARNAME",
            message="Variable name 'LONGVARNAME' exceeds 8 characters",
            category=RuleCategory.LIMIT,
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.AUTO_FIXABLE

    def test_classify_label_length_as_auto_fixable(self, fixer: AutoFixer) -> None:
        """ASTR-L002 should be AUTO_FIXABLE."""
        result = _make_result(
            rule_id="ASTR-L002",
            variable="AETERM",
            message="Label for AETERM exceeds 40 characters",
            category=RuleCategory.LIMIT,
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.AUTO_FIXABLE

    def test_classify_char_length_as_needs_human(self, fixer: AutoFixer) -> None:
        """ASTR-L003 should be NEEDS_HUMAN."""
        result = _make_result(
            rule_id="ASTR-L003",
            variable="AETERM",
            message="Column 'AETERM' has values exceeding 200 bytes",
            category=RuleCategory.LIMIT,
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.NEEDS_HUMAN

    def test_classify_ascii_as_auto_fixable(self, fixer: AutoFixer) -> None:
        """ASTR-F002 should be AUTO_FIXABLE."""
        result = _make_result(
            rule_id="ASTR-F002",
            variable="AETERM",
            message="Column 'AETERM' contains 3 non-ASCII value(s)",
            category=RuleCategory.FORMAT,
            severity=RuleSeverity.WARNING,
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.AUTO_FIXABLE

    def test_classify_date_format_as_needs_human(self, fixer: AutoFixer) -> None:
        """ASTR-F001 should be NEEDS_HUMAN."""
        result = _make_result(
            rule_id="ASTR-F001",
            variable="AESTDTC",
            message="AESTDTC contains non-ISO 8601 value(s)",
            category=RuleCategory.FORMAT,
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.NEEDS_HUMAN

    def test_classify_fda_business_as_needs_human(self, fixer: AutoFixer) -> None:
        """FDAB057 should be NEEDS_HUMAN."""
        result = _make_result(
            rule_id="FDAB057",
            message="FDA Business Rule FDAB057 violation",
            category=RuleCategory.FDA_BUSINESS,
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.NEEDS_HUMAN

    def test_classify_cross_domain_as_needs_human(self, fixer: AutoFixer) -> None:
        """ASTR-C001 should be NEEDS_HUMAN."""
        result = _make_result(
            rule_id="ASTR-C001",
            message="Cross-domain consistency issue",
            category=RuleCategory.CONSISTENCY,
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.NEEDS_HUMAN

    def test_classify_file_naming_as_auto_fixable(self, fixer: AutoFixer) -> None:
        """ASTR-F003 should be AUTO_FIXABLE."""
        result = _make_result(
            rule_id="ASTR-F003",
            message="Domain code invalid for file naming",
            category=RuleCategory.FORMAT,
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.AUTO_FIXABLE

    def test_classify_unknown_rule_as_needs_human(self, fixer: AutoFixer) -> None:
        """Unknown rule IDs should be NEEDS_HUMAN."""
        result = _make_result(
            rule_id="CUSTOM-999",
            message="Some custom rule",
        )
        classification = fixer.classify_issue(result)
        assert classification.classification == FixClassification.NEEDS_HUMAN


# ================================================================== #
# Fix function tests
# ================================================================== #


class TestFixCTCaseNormalization:
    """Test CT case normalization fix."""

    def test_fix_ct_case_normalization(self, fixer: AutoFixer, ct_ref: CTReference) -> None:
        """Fix case-mismatched CT values to correct case."""
        # SEX codelist C66731 has 'M' and 'F' as submission values
        df = pd.DataFrame(
            {
                "SEX": ["m", "F", "f", "M"],
                "USUBJID": ["S1", "S2", "S3", "S4"],
            }
        )
        spec = _make_spec(
            domain="DM",
            mappings=[_make_vm("SEX", codelist_code="C66731")],
        )
        result = _make_result(
            rule_id="ASTR-T001",
            variable="SEX",
            domain="DM",
            message="Invalid CT value(s) in SEX: 'm', 'f'",
        )

        fixed_df, actions = fixer._fix_ct_case("DM", df, result, spec)

        # m -> M, f -> F, already-correct values unchanged
        assert list(fixed_df["SEX"]) == ["M", "F", "F", "M"]
        assert len(actions) == 1
        assert actions[0].fix_type == "ct_case_normalize"
        assert actions[0].affected_count == 2
        assert actions[0].domain == "DM"
        assert actions[0].variable == "SEX"


class TestFixDomainColumn:
    """Test DOMAIN column fix."""

    def test_fix_domain_column_missing(self, fixer: AutoFixer) -> None:
        """Add DOMAIN column when missing."""
        df = pd.DataFrame({"USUBJID": ["S1", "S2"]})
        result = _make_result(
            rule_id="ASTR-T002",
            variable="DOMAIN",
            message="DOMAIN column is missing from the dataset",
        )

        fixed_df, actions = fixer._fix_domain_column("AE", df, result)

        assert "DOMAIN" in fixed_df.columns
        assert list(fixed_df["DOMAIN"]) == ["AE", "AE"]
        assert len(actions) == 1
        assert actions[0].fix_type == "add_missing_column"
        assert actions[0].affected_count == 2

    def test_fix_domain_column_wrong_value(self, fixer: AutoFixer) -> None:
        """Correct wrong DOMAIN column values."""
        df = pd.DataFrame(
            {
                "DOMAIN": ["XX", "XX", "AE"],
                "USUBJID": ["S1", "S2", "S3"],
            }
        )
        result = _make_result(
            rule_id="ASTR-T002",
            variable="DOMAIN",
            message="DOMAIN column contains incorrect value(s): 'XX'",
        )

        fixed_df, actions = fixer._fix_domain_column("AE", df, result)

        assert list(fixed_df["DOMAIN"]) == ["AE", "AE", "AE"]
        assert len(actions) == 1
        assert actions[0].fix_type == "fix_domain_value"
        assert actions[0].affected_count == 2


class TestFixMissingStudyid:
    """Test STUDYID column fix."""

    def test_fix_missing_studyid(self, fixer: AutoFixer) -> None:
        """Add STUDYID column with value from spec."""
        df = pd.DataFrame({"USUBJID": ["S1", "S2", "S3"]})
        spec = _make_spec(domain="AE", study_id="PHA022121-C301")

        fixed_df, actions = fixer._fix_missing_studyid("AE", df, spec)

        assert "STUDYID" in fixed_df.columns
        assert list(fixed_df["STUDYID"]) == ["PHA022121-C301"] * 3
        assert len(actions) == 1
        assert actions[0].fix_type == "add_missing_column"
        assert actions[0].variable == "STUDYID"
        assert actions[0].affected_count == 3


class TestFixVariableNameTruncation:
    """Test variable name truncation fix."""

    def test_fix_variable_name_truncation(self, fixer: AutoFixer) -> None:
        """Truncate long variable names to 8 characters."""
        df = pd.DataFrame({"LONGVARNAME": [1, 2, 3]})
        result = _make_result(
            rule_id="ASTR-L001",
            variable="LONGVARNAME",
            message="Variable name 'LONGVARNAME' exceeds 8 characters",
            category=RuleCategory.LIMIT,
        )

        fixed_df, actions = fixer._fix_variable_name_length("AE", df, result)

        assert "LONGVARNAME" not in fixed_df.columns
        assert "LONGVARN" in fixed_df.columns
        assert len(actions) == 1
        assert actions[0].fix_type == "truncate_name"
        assert "LONGVARNAME" in actions[0].before_value
        assert "LONGVARN" in actions[0].after_value

    def test_fix_variable_name_collision(self, fixer: AutoFixer) -> None:
        """Handle collision when truncated name already exists."""
        df = pd.DataFrame(
            {
                "LONGVARN": [1, 2],
                "LONGVARNAME": [3, 4],
            }
        )
        result = _make_result(
            rule_id="ASTR-L001",
            variable="LONGVARNAME",
            message="Variable name 'LONGVARNAME' exceeds 8 characters",
            category=RuleCategory.LIMIT,
        )

        fixed_df, actions = fixer._fix_variable_name_length("AE", df, result)

        assert "LONGVARNAME" not in fixed_df.columns
        assert "LONGVARN" in fixed_df.columns  # original
        assert "LONGVAR1" in fixed_df.columns  # collision-resolved
        assert len(actions) == 1


class TestFixVariableLabelTruncation:
    """Test variable label truncation fix."""

    def test_fix_variable_label_truncation(self, fixer: AutoFixer) -> None:
        """Truncate long labels to 40 characters."""
        long_label = "This is a very long label that exceeds the 40 character limit for XPT"
        spec = _make_spec(
            domain="AE",
            mappings=[_make_vm("AETERM", label=long_label)],
        )
        result = _make_result(
            rule_id="ASTR-L002",
            variable="AETERM",
            message=f"Label for AETERM exceeds 40 characters ({len(long_label)} chars)",
            category=RuleCategory.LIMIT,
        )

        fixed_spec, actions = fixer._fix_variable_label_length("AE", spec, result)

        assert len(fixed_spec.variable_mappings[0].sdtm_label) == 40
        assert len(actions) == 1
        assert actions[0].fix_type == "truncate_label"
        assert actions[0].variable == "AETERM"


class TestFixAscii:
    """Test ASCII fix."""

    def test_fix_ascii_characters(self, fixer: AutoFixer) -> None:
        """Replace non-ASCII characters with ASCII equivalents."""
        df = pd.DataFrame(
            {
                "AETERM": ["Headache", "Nausea\u2019s", "Fever"],
            }
        )
        result = _make_result(
            rule_id="ASTR-F002",
            variable="AETERM",
            message="Column 'AETERM' contains 1 non-ASCII value(s)",
            category=RuleCategory.FORMAT,
            severity=RuleSeverity.WARNING,
            affected_count=1,
        )

        fixed_df, actions = fixer._fix_ascii("AE", df, result)

        # Right curly quote should be replaced with straight quote
        assert fixed_df["AETERM"].iloc[1] == "Nausea's"
        assert len(actions) == 1
        assert actions[0].fix_type == "fix_ascii"


# ================================================================== #
# Integration tests for apply_fixes
# ================================================================== #


class TestApplyFixes:
    """Test the apply_fixes orchestrator method."""

    def test_apply_fixes_returns_copy(self, fixer: AutoFixer) -> None:
        """Verify original DataFrame is not modified."""
        original_df = pd.DataFrame({"USUBJID": ["S1", "S2"]})
        spec = _make_spec(domain="AE")
        issues = [
            _make_result(
                rule_id="ASTR-T002",
                variable="DOMAIN",
                message="DOMAIN column is missing from the dataset",
            )
        ]

        fixed_df, _, actions = fixer.apply_fixes("AE", original_df, spec, issues)

        # Original should not have DOMAIN column
        assert "DOMAIN" not in original_df.columns
        # Fixed copy should have it
        assert "DOMAIN" in fixed_df.columns
        assert len(actions) == 1

    def test_apply_fixes_skips_needs_human(self, fixer: AutoFixer) -> None:
        """Only auto-fixable issues get fix actions."""
        df = pd.DataFrame({"USUBJID": ["S1"]})
        spec = _make_spec(domain="AE")
        issues = [
            # Auto-fixable
            _make_result(
                rule_id="ASTR-T002",
                variable="DOMAIN",
                message="DOMAIN column is missing",
            ),
            # Needs human
            _make_result(
                rule_id="ASTR-L003",
                variable="AETERM",
                message="Column 'AETERM' has values exceeding 200 bytes",
                category=RuleCategory.LIMIT,
            ),
            # Needs human
            _make_result(
                rule_id="FDAB057",
                message="FDA Business Rule",
                category=RuleCategory.FDA_BUSINESS,
            ),
        ]

        _, _, actions = fixer.apply_fixes("AE", df, spec, issues)

        # Only the DOMAIN fix should produce an action
        assert len(actions) == 1
        assert actions[0].fix_type == "add_missing_column"

    def test_apply_fixes_multiple_fixes(self, fixer: AutoFixer) -> None:
        """Multiple auto-fixable issues produce multiple fix actions."""
        df = pd.DataFrame(
            {
                "USUBJID": ["S1", "S2"],
                "AETERM": ["Headache\u2019s", "Nausea"],
            }
        )
        spec = _make_spec(domain="AE")
        issues = [
            _make_result(
                rule_id="ASTR-T002",
                variable="DOMAIN",
                message="DOMAIN column is missing",
            ),
            _make_result(
                rule_id="ASTR-F002",
                variable="AETERM",
                message="Column 'AETERM' contains 1 non-ASCII value(s)",
                category=RuleCategory.FORMAT,
                severity=RuleSeverity.WARNING,
                affected_count=1,
            ),
        ]

        fixed_df, _, actions = fixer.apply_fixes("AE", df, spec, issues)

        assert len(actions) == 2
        fix_types = {a.fix_type for a in actions}
        assert "add_missing_column" in fix_types
        assert "fix_ascii" in fix_types
        assert "DOMAIN" in fixed_df.columns

    def test_audit_trail_completeness(self, fixer: AutoFixer) -> None:
        """Verify FixAction has all required fields populated."""
        df = pd.DataFrame({"USUBJID": ["S1"]})
        spec = _make_spec(domain="AE")
        issues = [
            _make_result(
                rule_id="ASTR-T002",
                variable="DOMAIN",
                message="DOMAIN column is missing",
            )
        ]

        _, _, actions = fixer.apply_fixes("AE", df, spec, issues)

        assert len(actions) == 1
        action = actions[0]
        assert action.rule_id == "ASTR-T002"
        assert action.domain == "AE"
        assert action.variable == "DOMAIN"
        assert action.fix_type == "add_missing_column"
        assert action.before_value != ""
        assert action.after_value != ""
        assert action.affected_count >= 0
        assert action.timestamp != ""
        # Timestamp should be ISO 8601 format
        assert "T" in action.timestamp

    def test_apply_fixes_with_studyid_missing(self, fixer: AutoFixer) -> None:
        """Auto-fix STUDYID from spec.study_id."""
        df = pd.DataFrame({"USUBJID": ["S1", "S2"]})
        spec = _make_spec(domain="AE", study_id="STUDY-123")
        issues = [
            _make_result(
                rule_id="ASTR-P001",
                variable="STUDYID",
                message="Required variable STUDYID is missing",
                category=RuleCategory.PRESENCE,
            )
        ]

        fixed_df, _, actions = fixer.apply_fixes("AE", df, spec, issues)

        assert "STUDYID" in fixed_df.columns
        assert list(fixed_df["STUDYID"]) == ["STUDY-123", "STUDY-123"]
        assert len(actions) == 1
        assert actions[0].fix_type == "add_missing_column"

    def test_apply_fixes_label_updates_spec(self, fixer: AutoFixer) -> None:
        """Label truncation updates spec, not DataFrame."""
        long_label = "A" * 50
        df = pd.DataFrame({"AETERM": ["Headache"]})
        spec = _make_spec(
            domain="AE",
            mappings=[_make_vm("AETERM", label=long_label)],
        )
        issues = [
            _make_result(
                rule_id="ASTR-L002",
                variable="AETERM",
                message=f"Label exceeds 40 chars ({len(long_label)})",
                category=RuleCategory.LIMIT,
            )
        ]

        _, fixed_spec, actions = fixer.apply_fixes("AE", df, spec, issues)

        # Original spec unchanged
        assert len(spec.variable_mappings[0].sdtm_label) == 50
        # Fixed spec truncated
        assert len(fixed_spec.variable_mappings[0].sdtm_label) == 40
        assert len(actions) == 1
