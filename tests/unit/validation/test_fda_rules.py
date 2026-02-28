"""Tests for FDA Business Rules and TRC pre-checks."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from astraea.models.mapping import DomainMappingSpec
from astraea.validation.rules.base import RuleSeverity
from astraea.validation.rules.fda_business import (
    FDAB009Rule,
    FDAB030Rule,
    FDAB039Rule,
    FDAB055Rule,
    FDAB057Rule,
    get_fda_business_rules,
)
from astraea.validation.rules.fda_trc import TRCPreCheck

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dm_spec() -> DomainMappingSpec:
    return DomainMappingSpec(
        domain="DM",
        domain_label="Demographics",
        domain_class="Special-Purpose",
        structure="One record per subject",
        study_id="TEST-001",
        total_variables=5,
        required_mapped=5,
        expected_mapped=0,
        high_confidence_count=5,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def lb_spec() -> DomainMappingSpec:
    return DomainMappingSpec(
        domain="LB",
        domain_label="Laboratory Test Results",
        domain_class="Findings",
        structure="One record per lab test per visit per subject",
        study_id="TEST-001",
        total_variables=5,
        required_mapped=5,
        expected_mapped=0,
        high_confidence_count=5,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def mock_ct_ref() -> MagicMock:
    """Mock CTReference with C66790 and C74457 codelists."""
    ct_ref = MagicMock()

    # C66790: Ethnic Group
    ethnic_codelist = MagicMock()
    ethnic_term_1 = MagicMock()
    ethnic_term_1.submission_value = "HISPANIC OR LATINO"
    ethnic_term_2 = MagicMock()
    ethnic_term_2.submission_value = "NOT HISPANIC OR LATINO"
    ethnic_term_3 = MagicMock()
    ethnic_term_3.submission_value = "NOT REPORTED"
    ethnic_term_4 = MagicMock()
    ethnic_term_4.submission_value = "UNKNOWN"
    ethnic_codelist.terms = [ethnic_term_1, ethnic_term_2, ethnic_term_3, ethnic_term_4]

    # C74457: Race
    race_codelist = MagicMock()
    race_terms = []
    for val in [
        "AMERICAN INDIAN OR ALASKA NATIVE",
        "ASIAN",
        "BLACK OR AFRICAN AMERICAN",
        "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
        "WHITE",
        "MULTIPLE",
        "OTHER",
    ]:
        t = MagicMock()
        t.submission_value = val
        race_terms.append(t)
    race_codelist.terms = race_terms

    def get_codelist(code):
        if code == "C66790":
            return ethnic_codelist
        if code == "C74457":
            return race_codelist
        return None

    ct_ref.get_codelist = get_codelist
    return ct_ref


@pytest.fixture()
def mock_sdtm_ref() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# FDAB057: DM.ETHNIC
# ---------------------------------------------------------------------------


class TestFDAB057:
    def test_valid_ethnic_passes(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB057Rule()
        df = pd.DataFrame(
            {
                "ETHNIC": ["HISPANIC OR LATINO", "NOT HISPANIC OR LATINO"],
                "USUBJID": ["S1", "S2"],
            }
        )
        results = rule.evaluate("DM", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_invalid_ethnic_detected(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB057Rule()
        df = pd.DataFrame(
            {
                "ETHNIC": ["HISPANIC OR LATINO", "Latino"],  # "Latino" is wrong
                "USUBJID": ["S1", "S2"],
            }
        )
        results = rule.evaluate("DM", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB057"
        assert results[0].severity == RuleSeverity.WARNING
        assert "Latino" in results[0].message

    def test_skips_non_dm_domain(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB057Rule()
        df = pd.DataFrame({"ETHNIC": ["BAD"]})
        results = rule.evaluate("AE", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_missing_ethnic_column(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB057Rule()
        df = pd.DataFrame({"USUBJID": ["S1"]})
        results = rule.evaluate("DM", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert "missing ETHNIC" in results[0].message


# ---------------------------------------------------------------------------
# FDAB055: DM.RACE
# ---------------------------------------------------------------------------


class TestFDAB055:
    def test_valid_race_passes(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB055Rule()
        df = pd.DataFrame({"RACE": ["WHITE", "ASIAN"], "USUBJID": ["S1", "S2"]})
        results = rule.evaluate("DM", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_invalid_race_detected(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB055Rule()
        df = pd.DataFrame({"RACE": ["WHITE", "Caucasian"], "USUBJID": ["S1", "S2"]})
        results = rule.evaluate("DM", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB055"
        assert "Caucasian" in results[0].message

    def test_skips_non_dm(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB055Rule()
        results = rule.evaluate(
            "AE", pd.DataFrame({"RACE": ["X"]}), dm_spec, mock_sdtm_ref, mock_ct_ref
        )
        assert len(results) == 0


# ---------------------------------------------------------------------------
# FDAB039: Normal range numeric check
# ---------------------------------------------------------------------------


class TestFDAB039:
    def test_numeric_normal_ranges_pass(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB039Rule()
        df = pd.DataFrame(
            {
                "LBSTRESN": [5.2, 3.1],
                "LBORNRLO": [3.0, 2.0],
                "LBORNRHI": [8.0, 5.0],
                "LBTESTCD": ["WBC", "RBC"],
            }
        )
        results = rule.evaluate("LB", df, lb_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_non_numeric_normal_range_detected(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB039Rule()
        df = pd.DataFrame(
            {
                "LBSTRESN": [5.2, 3.1],
                "LBORNRLO": ["low", 2.0],  # "low" is non-numeric
                "LBORNRHI": [8.0, "high"],  # "high" is non-numeric
            }
        )
        results = rule.evaluate("LB", df, lb_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 2  # one for ORNRLO, one for ORNRHI
        assert all(r.rule_id == "FDAB039" for r in results)

    def test_skips_non_findings(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB039Rule()
        df = pd.DataFrame({"LBSTRESN": [5.2], "LBORNRLO": ["low"]})
        results = rule.evaluate("DM", df, lb_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# FDAB009: TESTCD/TEST 1:1 relationship
# ---------------------------------------------------------------------------


class TestFDAB009:
    def test_consistent_testcd_test_passes(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB009Rule()
        df = pd.DataFrame(
            {
                "LBTESTCD": ["WBC", "WBC", "RBC"],
                "LBTEST": ["White Blood Cell", "White Blood Cell", "Red Blood Cell"],
            }
        )
        results = rule.evaluate("LB", df, lb_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_testcd_maps_to_multiple_tests(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB009Rule()
        df = pd.DataFrame(
            {
                "LBTESTCD": ["WBC", "WBC"],
                "LBTEST": ["White Blood Cell", "WBC Count"],  # same code, different names
            }
        )
        results = rule.evaluate("LB", df, lb_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) >= 1
        assert any(r.variable == "LBTESTCD" for r in results)
        assert results[0].severity == RuleSeverity.ERROR

    def test_test_maps_to_multiple_testcds(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB009Rule()
        df = pd.DataFrame(
            {
                "LBTESTCD": ["WBC", "WBCC"],  # different codes
                "LBTEST": ["White Blood Cell", "White Blood Cell"],  # same name
            }
        )
        results = rule.evaluate("LB", df, lb_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) >= 1
        assert any(r.variable == "LBTEST" for r in results)

    def test_skips_non_findings(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB009Rule()
        results = rule.evaluate(
            "AE", pd.DataFrame({"LBTESTCD": ["X"]}), lb_spec, mock_sdtm_ref, mock_ct_ref
        )
        assert len(results) == 0


# ---------------------------------------------------------------------------
# FDAB030: STRESU consistency per TESTCD
# ---------------------------------------------------------------------------


class TestFDAB030:
    def test_consistent_units_pass(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB030Rule()
        df = pd.DataFrame(
            {
                "LBTESTCD": ["WBC", "WBC", "RBC"],
                "LBSTRESU": ["10^9/L", "10^9/L", "10^12/L"],
            }
        )
        results = rule.evaluate("LB", df, lb_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_inconsistent_units_detected(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB030Rule()
        df = pd.DataFrame(
            {
                "LBTESTCD": ["WBC", "WBC"],
                "LBSTRESU": ["10^9/L", "10^3/uL"],  # different units for same test
            }
        )
        results = rule.evaluate("LB", df, lb_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB030"
        assert results[0].severity == RuleSeverity.WARNING
        assert "WBC" in results[0].message


# ---------------------------------------------------------------------------
# get_fda_business_rules()
# ---------------------------------------------------------------------------


class TestGetFDABusinessRules:
    def test_returns_five_rules(self) -> None:
        rules = get_fda_business_rules()
        assert len(rules) == 5
        rule_ids = {r.rule_id for r in rules}
        assert rule_ids == {"FDAB057", "FDAB055", "FDAB039", "FDAB009", "FDAB030"}


# ---------------------------------------------------------------------------
# TRC Pre-checks
# ---------------------------------------------------------------------------


class TestTRCPreCheck:
    @pytest.fixture()
    def trc(self) -> TRCPreCheck:
        return TRCPreCheck()

    @pytest.fixture()
    def dm_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "STUDYID": ["STUDY1"],
                "DOMAIN": ["DM"],
                "USUBJID": ["STUDY1-001"],
            }
        )

    @pytest.fixture()
    def ts_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "STUDYID": ["STUDY1", "STUDY1"],
                "TSPARMCD": ["SSTDTC", "SPONSOR"],
                "TSVAL": ["2022-01-01", "ACME"],
            }
        )

    def test_missing_dm_detected(self, trc, ts_df, tmp_path) -> None:
        results = trc._check_dm_present({"TS": ts_df})
        assert len(results) == 1
        assert results[0].rule_id == "FDA-TRC-1736"
        assert results[0].severity == RuleSeverity.ERROR

    def test_empty_dm_detected(self, trc) -> None:
        empty_dm = pd.DataFrame(columns=["STUDYID", "USUBJID"])
        results = trc._check_dm_present({"DM": empty_dm})
        assert len(results) == 1
        assert "zero records" in results[0].message

    def test_dm_present_passes(self, trc, dm_df) -> None:
        results = trc._check_dm_present({"DM": dm_df})
        assert len(results) == 0

    def test_missing_ts_detected(self, trc, dm_df) -> None:
        results = trc._check_ts_present({"DM": dm_df})
        assert len(results) == 1
        assert results[0].rule_id == "FDA-TRC-1734"

    def test_ts_missing_sstdtc(self, trc) -> None:
        ts_no_sstdtc = pd.DataFrame(
            {
                "TSPARMCD": ["SPONSOR"],
                "TSVAL": ["ACME"],
            }
        )
        results = trc._check_ts_present({"TS": ts_no_sstdtc})
        assert len(results) == 1
        assert "SSTDTC" in results[0].message

    def test_ts_with_sstdtc_passes(self, trc, ts_df) -> None:
        results = trc._check_ts_present({"TS": ts_df})
        assert len(results) == 0

    def test_missing_define_xml(self, trc, tmp_path) -> None:
        results = trc._check_define_xml_present(tmp_path)
        assert len(results) == 1
        assert results[0].rule_id == "FDA-TRC-1735"

    def test_define_xml_present(self, trc, tmp_path) -> None:
        (tmp_path / "define.xml").write_text("<xml/>")
        results = trc._check_define_xml_present(tmp_path)
        assert len(results) == 0

    def test_studyid_mismatch(self, trc) -> None:
        domains = {
            "DM": pd.DataFrame({"STUDYID": ["STUDY1"]}),
            "AE": pd.DataFrame({"STUDYID": ["STUDY2"]}),
        }
        results = trc._check_studyid_consistent(domains, "STUDY1")
        assert len(results) == 1
        assert results[0].rule_id == "FDA-TRC-STUDYID"
        assert "AE" in results[0].message

    def test_studyid_consistent_passes(self, trc) -> None:
        domains = {
            "DM": pd.DataFrame({"STUDYID": ["STUDY1"]}),
            "AE": pd.DataFrame({"STUDYID": ["STUDY1"]}),
        }
        results = trc._check_studyid_consistent(domains, "STUDY1")
        assert len(results) == 0

    def test_non_lowercase_filename(self, trc, tmp_path) -> None:
        (tmp_path / "DM.xpt").write_bytes(b"")
        results = trc._check_filename_convention(tmp_path)
        assert len(results) == 1
        assert results[0].rule_id == "FDA-TRC-FILENAME"

    def test_lowercase_filename_passes(self, trc, tmp_path) -> None:
        (tmp_path / "dm.xpt").write_bytes(b"")
        results = trc._check_filename_convention(tmp_path)
        assert len(results) == 0

    def test_check_all_integration(self, trc, dm_df, ts_df, tmp_path) -> None:
        (tmp_path / "define.xml").write_text("<xml/>")
        (tmp_path / "dm.xpt").write_bytes(b"")
        domains = {"DM": dm_df, "TS": ts_df}
        results = trc.check_all(domains, tmp_path, "STUDY1")
        # Should pass all checks
        assert len(results) == 0

    def test_check_all_catches_multiple_issues(self, trc, tmp_path) -> None:
        # No DM, no TS, no define.xml
        results = trc.check_all({}, tmp_path, "STUDY1")
        rule_ids = {r.rule_id for r in results}
        assert "FDA-TRC-1736" in rule_ids  # missing DM
        assert "FDA-TRC-1734" in rule_ids  # missing TS
        assert "FDA-TRC-1735" in rule_ids  # missing define.xml
