"""Tests for SUPPQUAL referential integrity and variable ordering rules."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.validation.rules.base import RuleCategory, RuleSeverity
from astraea.validation.rules.ordering import VariableOrderingRule, get_ordering_rules
from astraea.validation.rules.suppqual_validation import (
    SUPPQUALIntegrityRule,
    get_suppqual_rules,
)


@pytest.fixture()
def sdtm_ref():
    """Load real SDTM reference."""
    from astraea.reference import load_sdtm_reference

    return load_sdtm_reference()


@pytest.fixture()
def ct_ref():
    """Load real CT reference."""
    from astraea.reference import load_ct_reference

    return load_ct_reference()


def _make_spec(domain: str, domain_label: str) -> object:
    """Create a minimal DomainMappingSpec for testing."""
    from astraea.models.mapping import DomainMappingSpec

    return DomainMappingSpec(
        domain=domain,
        domain_label=domain_label,
        domain_class="Events",
        structure="One record per event per subject",
        study_id="TEST-001",
        source_datasets=["ae.sas7bdat"],
        variable_mappings=[],
        total_variables=0,
        required_mapped=0,
        expected_mapped=0,
        high_confidence_count=0,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def dummy_spec():
    """Create a minimal AE DomainMappingSpec for testing."""
    return _make_spec("AE", "Adverse Events")


@pytest.fixture()
def supp_spec():
    """Create a minimal SUPPAE spec for testing."""
    return _make_spec("SUPPAE", "Supplemental Qualifiers for AE")


class TestSUPPQUALIntegrityRule:
    """Tests for SUPPQUALIntegrityRule (ASTR-S001)."""

    def test_rule_metadata(self) -> None:
        """Rule has correct ID and severity."""
        rule = SUPPQUALIntegrityRule()
        assert rule.rule_id == "ASTR-S001"
        assert rule.severity == RuleSeverity.ERROR
        assert rule.category == RuleCategory.CONSISTENCY

    def test_skips_non_supp_domains(self, sdtm_ref, ct_ref, dummy_spec) -> None:
        """Rule does not apply to non-SUPP* domains."""
        rule = SUPPQUALIntegrityRule()
        df = pd.DataFrame({"STUDYID": ["S1"], "DOMAIN": ["AE"]})
        results = rule.evaluate("AE", df, dummy_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_valid_suppqual(self, sdtm_ref, ct_ref, supp_spec) -> None:
        """Valid SUPPQUAL data produces no errors."""
        rule = SUPPQUALIntegrityRule()
        df = pd.DataFrame({
            "STUDYID": ["S1", "S1"],
            "RDOMAIN": ["AE", "AE"],
            "USUBJID": ["S1-001", "S1-002"],
            "IDVAR": ["AESEQ", "AESEQ"],
            "IDVARVAL": ["1", "2"],
            "QNAM": ["AEACNOT", "AEACNOT"],
            "QLABEL": ["Other Action", "Other Action"],
            "QVAL": ["None", "Dose reduced"],
            "QORIG": ["CRF", "CRF"],
        })
        results = rule.evaluate("SUPPAE", df, supp_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_invalid_rdomain(self, sdtm_ref, ct_ref, supp_spec) -> None:
        """Invalid RDOMAIN values are flagged."""
        rule = SUPPQUALIntegrityRule()
        df = pd.DataFrame({
            "RDOMAIN": ["123", "AE"],
            "USUBJID": ["S1-001", "S1-002"],
            "IDVAR": ["AESEQ", "AESEQ"],
            "IDVARVAL": ["1", "2"],
            "QNAM": ["AEACNOT", "AEREL"],
            "QLABEL": ["Other Action", "Relatedness"],
            "QVAL": ["None", "Y"],
        })
        results = rule.evaluate("SUPPAE", df, supp_spec, sdtm_ref, ct_ref)
        rdomain_errors = [r for r in results if r.variable == "RDOMAIN"]
        assert len(rdomain_errors) >= 1
        assert "123" in rdomain_errors[0].message

    def test_invalid_qnam(self, sdtm_ref, ct_ref, supp_spec) -> None:
        """Invalid QNAM values are flagged."""
        rule = SUPPQUALIntegrityRule()
        df = pd.DataFrame({
            "RDOMAIN": ["AE"],
            "USUBJID": ["S1-001"],
            "IDVAR": ["AESEQ"],
            "IDVARVAL": ["1"],
            "QNAM": ["toolongname"],  # >8 chars
            "QLABEL": ["Something"],
            "QVAL": ["Value"],
        })
        results = rule.evaluate("SUPPAE", df, supp_spec, sdtm_ref, ct_ref)
        qnam_errors = [r for r in results if r.variable == "QNAM"]
        assert len(qnam_errors) >= 1

    def test_missing_rdomain_column(self, sdtm_ref, ct_ref, supp_spec) -> None:
        """Missing RDOMAIN column is flagged."""
        rule = SUPPQUALIntegrityRule()
        df = pd.DataFrame({
            "USUBJID": ["S1-001"],
            "QNAM": ["TEST"],
            "QVAL": ["val"],
        })
        results = rule.evaluate("SUPPAE", df, supp_spec, sdtm_ref, ct_ref)
        rdomain_errors = [r for r in results if r.variable == "RDOMAIN"]
        assert len(rdomain_errors) >= 1
        assert "missing" in rdomain_errors[0].message.lower()

    def test_get_suppqual_rules_returns_list(self) -> None:
        """get_suppqual_rules returns a list with the rule."""
        rules = get_suppqual_rules()
        assert len(rules) >= 1
        assert any(r.rule_id == "ASTR-S001" for r in rules)


class TestVariableOrderingRule:
    """Tests for VariableOrderingRule (ASTR-O001)."""

    def test_rule_metadata(self) -> None:
        """Rule has correct ID and severity."""
        rule = VariableOrderingRule()
        assert rule.rule_id == "ASTR-O001"
        assert rule.severity == RuleSeverity.WARNING
        assert rule.category == RuleCategory.FORMAT

    def test_correct_order_passes(self, sdtm_ref, ct_ref, dummy_spec) -> None:
        """Correctly ordered variables produce no findings."""
        rule = VariableOrderingRule()
        # Get AE domain expected order from SDTM-IG
        ae_spec = sdtm_ref.get_domain_spec("AE")
        assert ae_spec is not None
        expected_vars = [v.name for v in ae_spec.variables]

        # Create DataFrame with correct order (at least first few)
        cols = expected_vars[:5]
        df = pd.DataFrame({c: ["test"] for c in cols})
        results = rule.evaluate("AE", df, dummy_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_wrong_order_warns(self, sdtm_ref, ct_ref, dummy_spec) -> None:
        """Incorrectly ordered variables produce a warning."""
        rule = VariableOrderingRule()
        ae_spec = sdtm_ref.get_domain_spec("AE")
        assert ae_spec is not None
        expected_vars = [v.name for v in ae_spec.variables]

        # Reverse the first few variables
        cols = list(reversed(expected_vars[:5]))
        df = pd.DataFrame({c: ["test"] for c in cols})
        results = rule.evaluate("AE", df, dummy_spec, sdtm_ref, ct_ref)
        assert len(results) >= 1
        assert results[0].severity == RuleSeverity.WARNING
        assert results[0].p21_equivalent == "SD0066"

    def test_skips_supp_domains(self, sdtm_ref, ct_ref, supp_spec) -> None:
        """Rule skips SUPP* domains."""
        rule = VariableOrderingRule()
        df = pd.DataFrame({"STUDYID": ["S1"], "RDOMAIN": ["AE"]})
        results = rule.evaluate("SUPPAE", df, supp_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_unknown_domain_skips(self, sdtm_ref, ct_ref, dummy_spec) -> None:
        """Rule skips unknown domains."""
        rule = VariableOrderingRule()
        df = pd.DataFrame({"COL1": ["test"]})
        results = rule.evaluate("ZZZZ", df, dummy_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_get_ordering_rules_returns_list(self) -> None:
        """get_ordering_rules returns a list with the rule."""
        rules = get_ordering_rules()
        assert len(rules) >= 1
        assert any(r.rule_id == "ASTR-O001" for r in rules)
