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
        assert "COUNTRY" in req
        assert "SITEID" in req
        # ARMCD, ARM, ACTARMCD, ACTARM are Exp per SDTM-IG v3.4
        assert "ARMCD" not in req
        assert "ARM" not in req

    def test_get_required_variables_nonexistent_domain(self, ref: SDTMReference) -> None:
        assert ref.get_required_variables("ZZZZ") == []

    def test_get_expected_variables_dm(self, ref: SDTMReference) -> None:
        exp = ref.get_expected_variables("DM")
        assert "RFSTDTC" in exp
        assert "AGE" in exp
        assert "RACE" in exp
        # ETHNIC is Perm per SDTM-IG v3.4, not Exp
        assert "ETHNIC" not in exp
        # ARM variables are Exp per SDTM-IG v3.4
        assert "ARMCD" in exp
        assert "ARM" in exp
        assert "ACTARMCD" in exp
        assert "ACTARM" in exp

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

    # ------------------------------------------------------------------
    # Tests for expanded domains (Gap 2 closure)
    # ------------------------------------------------------------------

    def test_list_domains_returns_at_least_18(self, ref: SDTMReference) -> None:
        domains = ref.list_domains()
        assert len(domains) >= 18
        for code in ["CE", "DA", "DV", "FA", "PE", "QS", "SC", "SV"]:
            assert code in domains, f"Missing domain: {code}"

    def test_new_domains_loadable(self, ref: SDTMReference) -> None:
        """Each new domain should be loadable and have at least 5 variables."""
        new_domains = ["CE", "DA", "DV", "FA", "PE", "QS", "SC", "SV"]
        for code in new_domains:
            spec = ref.get_domain_spec(code)
            assert spec is not None, f"get_domain_spec('{code}') returned None"
            assert len(spec.variables) >= 5, (
                f"{code} has only {len(spec.variables)} variables, expected >= 5"
            )

    def test_new_domain_classes(self, ref: SDTMReference) -> None:
        """Verify domain_class for each new domain."""
        assert ref.get_domain_class("CE") == DomainClass.EVENTS
        assert ref.get_domain_class("DV") == DomainClass.EVENTS
        assert ref.get_domain_class("PE") == DomainClass.FINDINGS
        assert ref.get_domain_class("QS") == DomainClass.FINDINGS
        assert ref.get_domain_class("SC") == DomainClass.FINDINGS
        assert ref.get_domain_class("FA") == DomainClass.FINDINGS
        assert ref.get_domain_class("SV") == DomainClass.SPECIAL_PURPOSE
        assert ref.get_domain_class("DA") == DomainClass.FINDINGS

    def test_ce_required_variables(self, ref: SDTMReference) -> None:
        req = ref.get_required_variables("CE")
        assert "STUDYID" in req
        assert "USUBJID" in req
        assert "CESEQ" in req
        assert "CETERM" in req

    def test_sv_required_variables(self, ref: SDTMReference) -> None:
        req = ref.get_required_variables("SV")
        assert "STUDYID" in req
        assert "USUBJID" in req
        assert "VISITNUM" in req

    def test_fa_required_variables(self, ref: SDTMReference) -> None:
        req = ref.get_required_variables("FA")
        assert "FATESTCD" in req
        assert "FATEST" in req
        assert "FAOBJ" in req
