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


class TestDomainsJsonCorrections:
    """Verify all domains.json corrections from Phase 2.1 Plan 04."""

    # ------------------------------------------------------------------
    # Codelist assignment tests
    # ------------------------------------------------------------------

    def test_dm_dthfl_uses_ny_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("DM", "DTHFL")
        assert spec is not None
        assert spec.codelist_code == "C66742"

    def test_dm_race_uses_race_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("DM", "RACE")
        assert spec is not None
        assert spec.codelist_code == "C74457"

    def test_dm_ethnic_uses_ethnic_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("DM", "ETHNIC")
        assert spec is not None
        assert spec.codelist_code == "C66790"

    def test_dm_country_uses_iso3166(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("DM", "COUNTRY")
        assert spec is not None
        assert spec.codelist_code == "ISO3166"

    def test_dm_ageu_uses_age_unit_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("DM", "AGEU")
        assert spec is not None
        assert spec.codelist_code == "C66781"

    def test_ae_aesev_uses_severity_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("AE", "AESEV")
        assert spec is not None
        assert spec.codelist_code == "C66769"

    @pytest.mark.parametrize(
        "varname",
        ["AESER", "AESCAN", "AESCONG", "AESDISAB", "AESDTH", "AESHOSP", "AESLIFE", "AESMIE", "AECONTRT"],
    )
    def test_ae_ny_variables_use_c66742(self, ref: SDTMReference, varname: str) -> None:
        spec = ref.get_variable_spec("AE", varname)
        assert spec is not None, f"{varname} not found in AE"
        assert spec.codelist_code == "C66742", f"{varname} codelist: {spec.codelist_code}"

    def test_cm_route_uses_route_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("CM", "CMROUTE")
        assert spec is not None
        assert spec.codelist_code == "C66729"

    def test_cm_dosu_uses_unit_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("CM", "CMDOSU")
        assert spec is not None
        assert spec.codelist_code == "C71620"

    def test_cm_dosfrq_uses_freq_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("CM", "CMDOSFRQ")
        assert spec is not None
        assert spec.codelist_code == "C71113"

    def test_ex_route_uses_route_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("EX", "EXROUTE")
        assert spec is not None
        assert spec.codelist_code == "C66729"

    def test_lb_unit_vars_use_c71620(self, ref: SDTMReference) -> None:
        for varname in ["LBORRESU", "LBSTRESU"]:
            spec = ref.get_variable_spec("LB", varname)
            assert spec is not None, f"{varname} not found in LB"
            assert spec.codelist_code == "C71620", f"{varname} codelist: {spec.codelist_code}"

    @pytest.mark.parametrize("varname", ["MHPRESP", "MHOCCUR"])
    def test_mh_ny_variables_use_c66742(self, ref: SDTMReference, varname: str) -> None:
        spec = ref.get_variable_spec("MH", varname)
        assert spec is not None, f"{varname} not found in MH"
        assert spec.codelist_code == "C66742", f"{varname} codelist: {spec.codelist_code}"

    # ------------------------------------------------------------------
    # Core designation tests
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("varname", ["ARMCD", "ARM", "ACTARMCD", "ACTARM"])
    def test_dm_arm_variables_are_exp(self, ref: SDTMReference, varname: str) -> None:
        spec = ref.get_variable_spec("DM", varname)
        assert spec is not None
        assert spec.core.value == "Exp", f"{varname} core: {spec.core.value}"

    @pytest.mark.parametrize("varname", ["DTHDTC", "DTHFL"])
    def test_dm_death_variables_are_exp(self, ref: SDTMReference, varname: str) -> None:
        spec = ref.get_variable_spec("DM", varname)
        assert spec is not None
        assert spec.core.value == "Exp", f"{varname} core: {spec.core.value}"

    def test_dm_ethnic_is_perm(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("DM", "ETHNIC")
        assert spec is not None
        assert spec.core.value == "Perm"

    def test_ae_aeout_is_perm(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("AE", "AEOUT")
        assert spec is not None
        assert spec.core.value == "Perm"

    @pytest.mark.parametrize("varname", ["CMDECOD", "CMSTDTC", "CMENDTC", "CMINDC"])
    def test_cm_optional_vars_are_perm(self, ref: SDTMReference, varname: str) -> None:
        spec = ref.get_variable_spec("CM", varname)
        assert spec is not None, f"{varname} not found in CM"
        assert spec.core.value == "Perm", f"{varname} core: {spec.core.value}"

    def test_ex_exroute_is_perm(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("EX", "EXROUTE")
        assert spec is not None
        assert spec.core.value == "Perm"

    def test_lb_lbcat_is_exp(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("LB", "LBCAT")
        assert spec is not None
        assert spec.core.value == "Exp"

    # ------------------------------------------------------------------
    # Structural tests
    # ------------------------------------------------------------------

    def test_da_domain_class_is_findings(self, ref: SDTMReference) -> None:
        assert ref.get_domain_class("DA") == DomainClass.FINDINGS

    def test_dm_has_armnrs(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("DM", "ARMNRS")
        assert spec is not None, "ARMNRS missing from DM"
        assert spec.core.value == "Exp"
        assert spec.data_type == "Char"

    def test_dm_key_variables(self, ref: SDTMReference) -> None:
        spec = ref.get_domain_spec("DM")
        assert spec is not None
        assert spec.key_variables == ["STUDYID", "USUBJID"]

    def test_ae_key_variables(self, ref: SDTMReference) -> None:
        spec = ref.get_domain_spec("AE")
        assert spec is not None
        assert spec.key_variables == ["STUDYID", "USUBJID", "AETERM", "AESTDTC"]

    def test_lb_key_variables_includes_lbspec(self, ref: SDTMReference) -> None:
        spec = ref.get_domain_spec("LB")
        assert spec is not None
        assert spec.key_variables == [
            "STUDYID", "USUBJID", "LBTESTCD", "LBSPEC", "VISITNUM", "LBDTC"
        ]

    def test_all_core_domains_have_keys(self, ref: SDTMReference) -> None:
        core_domains = ["DM", "AE", "CM", "EX", "LB", "VS", "EG", "DS", "MH"]
        for domain in core_domains:
            spec = ref.get_domain_spec(domain)
            assert spec is not None, f"{domain} spec not found"
            assert spec.key_variables is not None, f"{domain} missing key_variables"
            assert len(spec.key_variables) >= 2, f"{domain} key_variables too short"

    # ------------------------------------------------------------------
    # Null codelist fill tests
    # ------------------------------------------------------------------

    def test_ae_aeacn_has_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("AE", "AEACN")
        assert spec is not None
        assert spec.codelist_code == "C66767"

    def test_lb_test_variables_have_codelists(self, ref: SDTMReference) -> None:
        checks = {
            "LBTESTCD": "C65047",
            "LBTEST": "C67154",
            "LBNRIND": "C78736",
            "LBSPEC": "C78734",
        }
        for varname, expected_code in checks.items():
            spec = ref.get_variable_spec("LB", varname)
            assert spec is not None, f"{varname} not found in LB"
            assert spec.codelist_code == expected_code, (
                f"{varname} codelist: {spec.codelist_code}, expected {expected_code}"
            )

    def test_vs_test_variables_have_codelists(self, ref: SDTMReference) -> None:
        checks = {"VSTESTCD": "C66741", "VSTEST": "C67153", "VSPOS": "C71148"}
        for varname, expected_code in checks.items():
            spec = ref.get_variable_spec("VS", varname)
            assert spec is not None, f"{varname} not found in VS"
            assert spec.codelist_code == expected_code, (
                f"{varname} codelist: {spec.codelist_code}, expected {expected_code}"
            )

    def test_eg_test_variables_have_codelists(self, ref: SDTMReference) -> None:
        checks = {"EGTESTCD": "C71153", "EGTEST": "C71152"}
        for varname, expected_code in checks.items():
            spec = ref.get_variable_spec("EG", varname)
            assert spec is not None, f"{varname} not found in EG"
            assert spec.codelist_code == expected_code, (
                f"{varname} codelist: {spec.codelist_code}, expected {expected_code}"
            )

    def test_ex_dosfrm_has_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("EX", "EXDOSFRM")
        assert spec is not None
        assert spec.codelist_code == "C66726"

    def test_ds_dsdecod_has_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("DS", "DSDECOD")
        assert spec is not None
        assert spec.codelist_code == "C66727"

    def test_mh_mhenrf_has_codelist(self, ref: SDTMReference) -> None:
        spec = ref.get_variable_spec("MH", "MHENRF")
        assert spec is not None
        assert spec.codelist_code == "C66728"

    def test_domain_variables_have_codelist(self, ref: SDTMReference) -> None:
        """DOMAIN variable should have C66734 codelist in all domains."""
        for domain_code in ref.list_domains():
            spec = ref.get_variable_spec(domain_code, "DOMAIN")
            if spec is not None:
                assert spec.codelist_code == "C66734", (
                    f"{domain_code}.DOMAIN codelist: {spec.codelist_code}"
                )
