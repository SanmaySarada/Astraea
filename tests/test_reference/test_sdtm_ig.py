"""Tests for SDTM-IG reference data lookup."""

import pytest

from astraea.models.sdtm import DomainClass, DomainSpec, VariableSpec
from astraea.reference import SDTMReference, load_sdtm_reference


@pytest.fixture
def ref() -> SDTMReference:
    """Load SDTM reference from default bundled data."""
    return load_sdtm_reference()


class TestSDTMReference:
    """Tests for SDTMReference lookup class."""

    def test_version(self, ref: SDTMReference) -> None:
        assert ref.version == "3.4"

    def test_list_domains_returns_at_least_10(self, ref: SDTMReference) -> None:
        domains = ref.list_domains()
        assert len(domains) >= 10
        assert "DM" in domains
        assert "AE" in domains
        assert "LB" in domains

    def test_get_domain_spec_dm(self, ref: SDTMReference) -> None:
        spec = ref.get_domain_spec("DM")
        assert spec is not None
        assert isinstance(spec, DomainSpec)
        assert spec.domain == "DM"
        assert spec.description == "Demographics"
        assert len(spec.variables) >= 26

    def test_get_domain_spec_case_insensitive(self, ref: SDTMReference) -> None:
        spec = ref.get_domain_spec("dm")
        assert spec is not None
        assert spec.domain == "DM"

    def test_get_domain_spec_nonexistent(self, ref: SDTMReference) -> None:
        assert ref.get_domain_spec("ZZZZ") is None

    def test_get_required_variables_dm(self, ref: SDTMReference) -> None:
        req = ref.get_required_variables("DM")
        assert "STUDYID" in req
        assert "DOMAIN" in req
        assert "USUBJID" in req
        assert "SUBJID" in req
        assert "SEX" in req
        assert "ARMCD" in req
        assert "ARM" in req
        assert "ACTARMCD" in req
        assert "ACTARM" in req
        assert "COUNTRY" in req
        assert "SITEID" in req

    def test_get_required_variables_nonexistent_domain(self, ref: SDTMReference) -> None:
        assert ref.get_required_variables("ZZZZ") == []

    def test_get_expected_variables_dm(self, ref: SDTMReference) -> None:
        exp = ref.get_expected_variables("DM")
        assert "RFSTDTC" in exp
        assert "AGE" in exp
        assert "RACE" in exp
        assert "ETHNIC" in exp

    def test_get_domain_class_events(self, ref: SDTMReference) -> None:
        assert ref.get_domain_class("AE") == DomainClass.EVENTS
        assert ref.get_domain_class("MH") == DomainClass.EVENTS
        assert ref.get_domain_class("DS") == DomainClass.EVENTS

    def test_get_domain_class_findings(self, ref: SDTMReference) -> None:
        assert ref.get_domain_class("LB") == DomainClass.FINDINGS
        assert ref.get_domain_class("VS") == DomainClass.FINDINGS
        assert ref.get_domain_class("EG") == DomainClass.FINDINGS
        assert ref.get_domain_class("IE") == DomainClass.FINDINGS

    def test_get_domain_class_interventions(self, ref: SDTMReference) -> None:
        assert ref.get_domain_class("CM") == DomainClass.INTERVENTIONS
        assert ref.get_domain_class("EX") == DomainClass.INTERVENTIONS

    def test_get_domain_class_special_purpose(self, ref: SDTMReference) -> None:
        assert ref.get_domain_class("DM") == DomainClass.SPECIAL_PURPOSE

    def test_get_domain_class_nonexistent(self, ref: SDTMReference) -> None:
        assert ref.get_domain_class("ZZZZ") is None

    def test_get_variable_spec_sex(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("DM", "SEX")
        assert spec is not None
        assert isinstance(spec, VariableSpec)
        assert spec.name == "SEX"
        assert spec.data_type == "Char"
        assert spec.codelist_code == "C66731"

    def test_get_variable_spec_age(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("DM", "AGE")
        assert spec is not None
        assert spec.data_type == "Num"

    def test_get_variable_spec_nonexistent(self, ref: SDTMReference) -> None:
        assert ref.get_variable_spec("DM", "ZZZZZ") is None
        assert ref.get_variable_spec("ZZZZ", "SEX") is None

    def test_ae_required_variables(self, ref: SDTMReference) -> None:
        req = ref.get_required_variables("AE")
        assert "STUDYID" in req
        assert "DOMAIN" in req
        assert "USUBJID" in req
        assert "AESEQ" in req
        assert "AETERM" in req
        assert "AEDECOD" in req

    def test_lb_required_variables(self, ref: SDTMReference) -> None:
        req = ref.get_required_variables("LB")
        assert "LBTESTCD" in req
        assert "LBTEST" in req
        assert "LBSEQ" in req
