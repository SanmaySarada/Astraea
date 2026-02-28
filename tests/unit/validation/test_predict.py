"""Tests for predict-and-prevent spec-level validation.

Verifies all 7 ASTR-PP rules and the results_to_issue_dicts helper.
"""

from __future__ import annotations

import pytest

from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)
from astraea.models.sdtm import CoreDesignation, DomainClass, DomainSpec, VariableSpec
from astraea.reference.controlled_terms import CTReference
from astraea.validation.predict import predict_and_prevent, results_to_issue_dicts
from astraea.validation.rules.base import RuleSeverity

# ── Fixtures ──────────────────────────────────────────────────────────


def _make_var_spec(
    name: str,
    core: CoreDesignation = CoreDesignation.PERM,
    data_type: str = "Char",
    order: int = 1,
    codelist_code: str | None = None,
) -> VariableSpec:
    return VariableSpec(
        name=name,
        label=f"Label for {name}",
        data_type=data_type,
        core=core,
        order=order,
        codelist_code=codelist_code,
    )


def _make_domain_spec(
    domain: str = "AE",
    variables: list[VariableSpec] | None = None,
) -> DomainSpec:
    if variables is None:
        variables = [
            _make_var_spec("STUDYID", CoreDesignation.REQ, order=1),
            _make_var_spec("DOMAIN", CoreDesignation.REQ, order=2),
            _make_var_spec("USUBJID", CoreDesignation.REQ, order=3),
            _make_var_spec("AESEQ", CoreDesignation.REQ, "Num", order=4),
            _make_var_spec("AETERM", CoreDesignation.REQ, order=5),
            _make_var_spec("AEDECOD", CoreDesignation.REQ, order=6),
            _make_var_spec("AESTDTC", CoreDesignation.EXP, order=7),
            _make_var_spec("AEENDTC", CoreDesignation.EXP, order=8),
            _make_var_spec("AESER", CoreDesignation.EXP, order=9, codelist_code="C66742"),
        ]
    return DomainSpec(
        domain=domain,
        description="Adverse Events",
        domain_class=DomainClass.EVENTS,
        structure="One record per adverse event per subject",
        variables=variables,
    )


def _make_mapping(
    sdtm_variable: str,
    pattern: MappingPattern = MappingPattern.DIRECT,
    source_variable: str | None = "SRC",
    assigned_value: str | None = None,
    codelist_code: str | None = None,
    origin: VariableOrigin | None = VariableOrigin.CRF,
    computational_method: str | None = None,
) -> VariableMapping:
    return VariableMapping(
        sdtm_variable=sdtm_variable,
        sdtm_label=f"Label for {sdtm_variable}",
        sdtm_data_type="Char",
        core=CoreDesignation.REQ,
        source_dataset="ae.sas7bdat",
        source_variable=source_variable,
        mapping_pattern=pattern,
        mapping_logic="Test mapping",
        assigned_value=assigned_value,
        codelist_code=codelist_code,
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="Test",
        origin=origin,
        computational_method=computational_method,
    )


def _make_spec(
    domain: str = "AE",
    mappings: list[VariableMapping] | None = None,
) -> DomainMappingSpec:
    if mappings is None:
        mappings = []
    return DomainMappingSpec(
        domain=domain,
        domain_label="Adverse Events",
        domain_class="Events",
        structure="One record per adverse event per subject",
        study_id="TEST-001",
        source_datasets=["ae.sas7bdat"],
        variable_mappings=mappings,
        total_variables=len(mappings),
        required_mapped=0,
        expected_mapped=0,
        high_confidence_count=0,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00Z",
        model_used="test",
    )


@pytest.fixture
def ct_ref() -> CTReference:
    """Real CT reference loaded from bundled data."""
    return CTReference()


# ── PP001: Required variables ────────────────────────────────────────


class TestPP001RequiredVariables:
    """ASTR-PP001: All Required variables must have mappings."""

    def test_missing_required_detected(self, ct_ref: CTReference) -> None:
        """Missing required variables produce ERROR results."""
        spec = _make_spec(
            mappings=[
                _make_mapping("STUDYID"),
                _make_mapping("DOMAIN"),
                # Missing USUBJID, AESEQ, AETERM, AEDECOD
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp001 = [r for r in results if r.rule_id == "ASTR-PP001"]
        assert len(pp001) == 4
        missing_vars = {r.variable for r in pp001}
        assert missing_vars == {"USUBJID", "AESEQ", "AETERM", "AEDECOD"}
        assert all(r.severity == RuleSeverity.ERROR for r in pp001)

    def test_all_required_present(self, ct_ref: CTReference) -> None:
        """No PP001 issues when all required variables are mapped."""
        spec = _make_spec(
            mappings=[
                _make_mapping("STUDYID"),
                _make_mapping("DOMAIN"),
                _make_mapping("USUBJID"),
                _make_mapping("AESEQ"),
                _make_mapping("AETERM"),
                _make_mapping("AEDECOD"),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp001 = [r for r in results if r.rule_id == "ASTR-PP001"]
        assert len(pp001) == 0


# ── PP002: Duplicate mappings ────────────────────────────────────────


class TestPP002DuplicateMappings:
    """ASTR-PP002: No duplicate variable mappings."""

    def test_duplicate_detected(self, ct_ref: CTReference) -> None:
        """Duplicate SDTM variable mappings produce ERROR."""
        spec = _make_spec(
            mappings=[
                _make_mapping("STUDYID"),
                _make_mapping("STUDYID"),  # duplicate
                _make_mapping("DOMAIN"),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp002 = [r for r in results if r.rule_id == "ASTR-PP002"]
        assert len(pp002) == 1
        assert pp002[0].variable == "STUDYID"
        assert pp002[0].severity == RuleSeverity.ERROR

    def test_no_duplicates(self, ct_ref: CTReference) -> None:
        """No PP002 issues when all variables are unique."""
        spec = _make_spec(
            mappings=[
                _make_mapping("STUDYID"),
                _make_mapping("DOMAIN"),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp002 = [r for r in results if r.rule_id == "ASTR-PP002"]
        assert len(pp002) == 0


# ── PP003: Codelist exists ───────────────────────────────────────────


class TestPP003CodelistExists:
    """ASTR-PP003: Referenced codelist codes must exist in CT."""

    def test_missing_codelist_detected(self, ct_ref: CTReference) -> None:
        """Nonexistent codelist code produces WARNING."""
        spec = _make_spec(
            mappings=[
                _make_mapping("AESER", codelist_code="C99999"),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp003 = [r for r in results if r.rule_id == "ASTR-PP003"]
        assert len(pp003) == 1
        assert pp003[0].severity == RuleSeverity.WARNING
        assert "C99999" in pp003[0].message

    def test_valid_codelist_no_issue(self, ct_ref: CTReference) -> None:
        """Valid codelist code produces no PP003 issue."""
        spec = _make_spec(
            mappings=[
                _make_mapping("AESER", codelist_code="C66742"),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp003 = [r for r in results if r.rule_id == "ASTR-PP003"]
        assert len(pp003) == 0


# ── PP004: ASSIGN values in non-extensible codelists ─────────────────


class TestPP004AssignCTValues:
    """ASTR-PP004: ASSIGN values must be valid in non-extensible codelists."""

    def test_invalid_assign_value_detected(self, ct_ref: CTReference) -> None:
        """Invalid ASSIGN value in non-extensible codelist produces ERROR."""
        spec = _make_spec(
            mappings=[
                _make_mapping(
                    "AESER",
                    pattern=MappingPattern.ASSIGN,
                    source_variable=None,
                    assigned_value="INVALID",
                    codelist_code="C66742",
                ),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp004 = [r for r in results if r.rule_id == "ASTR-PP004"]
        assert len(pp004) == 1
        assert pp004[0].severity == RuleSeverity.ERROR
        assert "INVALID" in pp004[0].message

    def test_valid_assign_value_no_issue(self, ct_ref: CTReference) -> None:
        """Valid ASSIGN value in non-extensible codelist produces no issue."""
        # C66742 is NY (No Yes) codelist - "Y" and "N" are valid
        spec = _make_spec(
            mappings=[
                _make_mapping(
                    "AESER",
                    pattern=MappingPattern.ASSIGN,
                    source_variable=None,
                    assigned_value="Y",
                    codelist_code="C66742",
                ),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp004 = [r for r in results if r.rule_id == "ASTR-PP004"]
        assert len(pp004) == 0


# ── PP005: Variable names in SDTM-IG ─────────────────────────────────


class TestPP005VariableInIG:
    """ASTR-PP005: Mapped variables should exist in SDTM-IG."""

    def test_unknown_variable_detected(self, ct_ref: CTReference) -> None:
        """Variable not in SDTM-IG produces WARNING."""
        spec = _make_spec(
            mappings=[
                _make_mapping("AEUNKNOWN"),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp005 = [r for r in results if r.rule_id == "ASTR-PP005"]
        assert len(pp005) == 1
        assert pp005[0].severity == RuleSeverity.WARNING
        assert "AEUNKNOWN" in pp005[0].message

    def test_known_variable_no_issue(self, ct_ref: CTReference) -> None:
        """Variable that exists in SDTM-IG produces no PP005 issue."""
        spec = _make_spec(
            mappings=[
                _make_mapping("STUDYID"),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp005 = [r for r in results if r.rule_id == "ASTR-PP005"]
        assert len(pp005) == 0


# ── PP006: Origin populated ──────────────────────────────────────────


class TestPP006OriginPopulated:
    """ASTR-PP006: All mappings should have origin set."""

    def test_missing_origin_detected(self, ct_ref: CTReference) -> None:
        """Missing origin produces NOTICE."""
        spec = _make_spec(
            mappings=[
                _make_mapping("STUDYID", origin=None),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp006 = [r for r in results if r.rule_id == "ASTR-PP006"]
        assert len(pp006) == 1
        assert pp006[0].severity == RuleSeverity.NOTICE

    def test_origin_present_no_issue(self, ct_ref: CTReference) -> None:
        """Origin present produces no PP006 issue."""
        spec = _make_spec(
            mappings=[
                _make_mapping("STUDYID", origin=VariableOrigin.ASSIGNED),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp006 = [r for r in results if r.rule_id == "ASTR-PP006"]
        assert len(pp006) == 0


# ── PP007: Computational method for derivations ─────────────────────


class TestPP007ComputationalMethod:
    """ASTR-PP007: Derived variables should have computational_method."""

    def test_missing_method_detected(self, ct_ref: CTReference) -> None:
        """Derivation without computational_method produces NOTICE."""
        spec = _make_spec(
            mappings=[
                _make_mapping(
                    "AESEQ",
                    pattern=MappingPattern.DERIVATION,
                    computational_method=None,
                ),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp007 = [r for r in results if r.rule_id == "ASTR-PP007"]
        assert len(pp007) == 1
        assert pp007[0].severity == RuleSeverity.NOTICE

    def test_method_present_no_issue(self, ct_ref: CTReference) -> None:
        """Derivation with computational_method produces no issue."""
        spec = _make_spec(
            mappings=[
                _make_mapping(
                    "AESEQ",
                    pattern=MappingPattern.DERIVATION,
                    computational_method="Sequence number by USUBJID and AESTDTC",
                ),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp007 = [r for r in results if r.rule_id == "ASTR-PP007"]
        assert len(pp007) == 0

    def test_non_derivation_no_issue(self, ct_ref: CTReference) -> None:
        """Non-derivation patterns do not trigger PP007."""
        spec = _make_spec(
            mappings=[
                _make_mapping("AETERM", pattern=MappingPattern.DIRECT),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp007 = [r for r in results if r.rule_id == "ASTR-PP007"]
        assert len(pp007) == 0


# ── results_to_issue_dicts ───────────────────────────────────────────


class TestResultsToIssueDicts:
    """Verify conversion from RuleResult to plain dict."""

    def test_converts_correctly(self, ct_ref: CTReference) -> None:
        """Dicts have correct keys and values."""
        spec = _make_spec(
            mappings=[
                _make_mapping("STUDYID"),
                _make_mapping("STUDYID"),  # duplicate
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        pp002 = [r for r in results if r.rule_id == "ASTR-PP002"]
        assert len(pp002) >= 1

        dicts = results_to_issue_dicts(pp002)
        assert len(dicts) == len(pp002)

        d = dicts[0]
        assert d["rule_id"] == "ASTR-PP002"
        assert d["severity"] == "ERROR"
        assert d["domain"] == "AE"
        assert d["variable"] == "STUDYID"
        assert "message" in d
        assert "fix_suggestion" in d

    def test_empty_results(self) -> None:
        """Empty input produces empty output."""
        assert results_to_issue_dicts([]) == []


# ── Integration: full predict_and_prevent ─────────────────────────────


class TestPredictAndPreventIntegration:
    """Integration tests combining multiple checks."""

    def test_clean_spec_minimal_issues(self, ct_ref: CTReference) -> None:
        """A well-formed spec has only NOTICE-level issues (origin, method)."""
        spec = _make_spec(
            mappings=[
                _make_mapping(
                    "STUDYID",
                    pattern=MappingPattern.ASSIGN,
                    source_variable=None,
                    assigned_value="TEST-001",
                ),
                _make_mapping(
                    "DOMAIN",
                    pattern=MappingPattern.ASSIGN,
                    source_variable=None,
                    assigned_value="AE",
                ),
                _make_mapping("USUBJID"),
                _make_mapping(
                    "AESEQ",
                    pattern=MappingPattern.DERIVATION,
                    computational_method="Sequence by USUBJID",
                ),
                _make_mapping("AETERM"),
                _make_mapping("AEDECOD"),
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)
        errors = [r for r in results if r.severity == RuleSeverity.ERROR]
        assert len(errors) == 0

    def test_multiple_issues_combined(self, ct_ref: CTReference) -> None:
        """Multiple issue types detected in single run."""
        spec = _make_spec(
            mappings=[
                _make_mapping("STUDYID"),
                _make_mapping("STUDYID"),  # duplicate
                _make_mapping("AEUNKNOWN", origin=None),  # unknown var + no origin
                # missing DOMAIN, USUBJID, AESEQ, AETERM, AEDECOD
            ]
        )
        domain_spec = _make_domain_spec()
        results = predict_and_prevent(spec, domain_spec, ct_ref)

        rule_ids = {r.rule_id for r in results}
        assert "ASTR-PP001" in rule_ids  # missing required
        assert "ASTR-PP002" in rule_ids  # duplicate
        assert "ASTR-PP005" in rule_ids  # unknown var
        assert "ASTR-PP006" in rule_ids  # missing origin
