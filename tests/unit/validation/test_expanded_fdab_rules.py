"""Tests for expanded FDA Business Rules (FDAB001-036, FDAB-POP).

Tests all 14 new FDAB rules added to cover AE, CM, EX, DM, LB,
and cross-domain validation checks.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from astraea.models.mapping import DomainMappingSpec
from astraea.validation.rules.base import RuleSeverity
from astraea.validation.rules.fda_business import (
    FDAB001Rule,
    FDAB002Rule,
    FDAB003Rule,
    FDAB004Rule,
    FDAB005Rule,
    FDAB016Rule,
    FDAB020Rule,
    FDAB021Rule,
    FDAB022Rule,
    FDAB025Rule,
    FDAB026Rule,
    FDAB035Rule,
    FDAB036Rule,
    PopulationFlagRule,
    get_fda_business_rules,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_spec(domain: str, label: str = "Test") -> DomainMappingSpec:
    return DomainMappingSpec(
        domain=domain,
        domain_label=label,
        domain_class="General",
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
def ae_spec() -> DomainMappingSpec:
    return _make_spec("AE", "Adverse Events")


@pytest.fixture()
def dm_spec() -> DomainMappingSpec:
    return _make_spec("DM", "Demographics")


@pytest.fixture()
def cm_spec() -> DomainMappingSpec:
    return _make_spec("CM", "Concomitant Medications")


@pytest.fixture()
def ex_spec() -> DomainMappingSpec:
    return _make_spec("EX", "Exposure")


@pytest.fixture()
def lb_spec() -> DomainMappingSpec:
    return _make_spec("LB", "Laboratory Test Results")


@pytest.fixture()
def mock_sdtm_ref() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def mock_ct_ref() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# FDAB001: AE.AESER
# ---------------------------------------------------------------------------


class TestFDAB001:
    def test_valid_aeser_passes(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB001Rule()
        df = pd.DataFrame({"AESER": ["Y", "N", "Y"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_invalid_aeser_detected(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB001Rule()
        df = pd.DataFrame({"AESER": ["Y", "Yes", "N"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB001"
        assert results[0].severity == RuleSeverity.ERROR
        assert "Yes" in results[0].message

    def test_skips_non_ae(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB001Rule()
        df = pd.DataFrame({"AESER": ["BAD"]})
        results = rule.evaluate("DM", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_no_aeser_column_skips(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB001Rule()
        df = pd.DataFrame({"AETERM": ["Headache"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# FDAB002: AE.AEREL
# ---------------------------------------------------------------------------


class TestFDAB002:
    def test_valid_aerel_passes(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB002Rule()
        df = pd.DataFrame({"AEREL": ["RELATED", "NOT RELATED"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_invalid_aerel_detected(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB002Rule()
        df = pd.DataFrame({"AEREL": ["RELATED", "Maybe"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB002"
        assert "Maybe" in results[0].message

    def test_skips_non_ae(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB002Rule()
        results = rule.evaluate("DM", pd.DataFrame({"AEREL": ["X"]}), dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# FDAB003: AE.AEOUT
# ---------------------------------------------------------------------------


class TestFDAB003:
    def test_valid_aeout_passes(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB003Rule()
        df = pd.DataFrame({"AEOUT": ["RECOVERED/RESOLVED", "FATAL"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_invalid_aeout_detected(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB003Rule()
        df = pd.DataFrame({"AEOUT": ["RECOVERED/RESOLVED", "Cured"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB003"
        assert "Cured" in results[0].message


# ---------------------------------------------------------------------------
# FDAB004: AE.AEACN
# ---------------------------------------------------------------------------


class TestFDAB004:
    def test_valid_aeacn_passes(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB004Rule()
        df = pd.DataFrame({"AEACN": ["DOSE REDUCED", "NOT APPLICABLE"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_invalid_aeacn_detected(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB004Rule()
        df = pd.DataFrame({"AEACN": ["DOSE REDUCED", "Stopped"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB004"
        assert "Stopped" in results[0].message


# ---------------------------------------------------------------------------
# FDAB005: AE date ordering
# ---------------------------------------------------------------------------


class TestFDAB005:
    def test_valid_dates_pass(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB005Rule()
        df = pd.DataFrame({
            "AESTDTC": ["2022-01-01", "2022-03-15"],
            "AEENDTC": ["2022-01-10", "2022-03-20"],
        })
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_start_after_end_detected(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB005Rule()
        df = pd.DataFrame({
            "AESTDTC": ["2022-03-20"],
            "AEENDTC": ["2022-03-01"],
        })
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB005"
        assert results[0].severity == RuleSeverity.WARNING

    def test_partial_dates_skipped(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        """Partial dates (< 10 chars) should not be compared."""
        rule = FDAB005Rule()
        df = pd.DataFrame({
            "AESTDTC": ["2022-03"],  # partial
            "AEENDTC": ["2022-01"],  # partial -- would be a violation if compared
        })
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_skips_non_ae(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB005Rule()
        df = pd.DataFrame({"AESTDTC": ["2022-03-20"], "AEENDTC": ["2022-03-01"]})
        results = rule.evaluate("DM", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# FDAB016: DM.COUNTRY
# ---------------------------------------------------------------------------


class TestFDAB016:
    def test_valid_country_passes(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB016Rule()
        df = pd.DataFrame({"COUNTRY": ["USA", "GBR", "DEU"]})
        results = rule.evaluate("DM", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_invalid_country_detected(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB016Rule()
        df = pd.DataFrame({"COUNTRY": ["USA", "NARNIA"]})
        results = rule.evaluate("DM", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB016"
        assert results[0].severity == RuleSeverity.WARNING
        assert "NARNIA" in results[0].message

    def test_skips_non_dm(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB016Rule()
        results = rule.evaluate("AE", pd.DataFrame({"COUNTRY": ["ZZZ"]}), ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# FDAB025: CM.CMTRT
# ---------------------------------------------------------------------------


class TestFDAB025:
    def test_populated_cmtrt_passes(self, cm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB025Rule()
        df = pd.DataFrame({"CMTRT": ["ASPIRIN", "IBUPROFEN"]})
        results = rule.evaluate("CM", df, cm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_null_cmtrt_detected(self, cm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB025Rule()
        df = pd.DataFrame({"CMTRT": ["ASPIRIN", None]})
        results = rule.evaluate("CM", df, cm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB025"
        assert results[0].severity == RuleSeverity.ERROR

    def test_skips_non_cm(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB025Rule()
        results = rule.evaluate("AE", pd.DataFrame({"CMTRT": [None]}), ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# FDAB026: EX.EXTRT
# ---------------------------------------------------------------------------


class TestFDAB026:
    def test_populated_extrt_passes(self, ex_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB026Rule()
        df = pd.DataFrame({"EXTRT": ["DRUG A", "PLACEBO"]})
        results = rule.evaluate("EX", df, ex_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_null_extrt_detected(self, ex_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB026Rule()
        df = pd.DataFrame({"EXTRT": ["DRUG A", None]})
        results = rule.evaluate("EX", df, ex_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB026"

    def test_skips_non_ex(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB026Rule()
        results = rule.evaluate("AE", pd.DataFrame({"EXTRT": [None]}), ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# FDAB020: VISITNUM numeric
# ---------------------------------------------------------------------------


class TestFDAB020:
    def test_numeric_visitnum_passes(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB020Rule()
        df = pd.DataFrame({"VISITNUM": [1, 2, 3.5]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_non_numeric_visitnum_detected(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB020Rule()
        df = pd.DataFrame({"VISITNUM": [1, "SCREENING", 3]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB020"
        assert results[0].severity == RuleSeverity.ERROR

    def test_applies_to_any_domain(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        """VISITNUM check applies regardless of domain."""
        rule = FDAB020Rule()
        df = pd.DataFrame({"VISITNUM": ["BAD"]})
        results = rule.evaluate("DM", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1

    def test_no_visitnum_column_skips(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB020Rule()
        df = pd.DataFrame({"AETERM": ["Headache"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# FDAB021: DY Day 0
# ---------------------------------------------------------------------------


class TestFDAB021:
    def test_valid_dy_passes(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB021Rule()
        df = pd.DataFrame({"AEDY": [-1, 1, 5, 10]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_day_zero_detected(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB021Rule()
        df = pd.DataFrame({"AEDY": [-1, 0, 1]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB021"
        assert results[0].severity == RuleSeverity.ERROR
        assert "Day 0" in results[0].message

    def test_multiple_dy_columns(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        """Should check all columns ending in DY."""
        rule = FDAB021Rule()
        df = pd.DataFrame({"AESTDY": [0], "AEENDY": [5]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].variable == "AESTDY"


# ---------------------------------------------------------------------------
# FDAB022: DTC ISO 8601
# ---------------------------------------------------------------------------


class TestFDAB022:
    def test_valid_iso_dates_pass(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB022Rule()
        df = pd.DataFrame({"AESTDTC": ["2022-03-15", "2022", "2022-03"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_invalid_date_format_detected(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB022Rule()
        df = pd.DataFrame({"AESTDTC": ["2022-03-15", "03/15/2022"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB022"
        assert results[0].severity == RuleSeverity.ERROR
        assert "03/15/2022" in results[0].message

    def test_valid_datetime_with_time(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB022Rule()
        df = pd.DataFrame({"AESTDTC": ["2022-03-15T14:30", "2022-03-15T14:30:00"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_checks_all_dtc_columns(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB022Rule()
        df = pd.DataFrame({
            "AESTDTC": ["2022-03-15"],
            "AEENDTC": ["BAD-DATE"],
        })
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].variable == "AEENDTC"


# ---------------------------------------------------------------------------
# FDAB035: LB.LBORRES/LBORRESU paired
# ---------------------------------------------------------------------------


class TestFDAB035:
    def test_paired_passes(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB035Rule()
        df = pd.DataFrame({"LBORRES": ["5.2", "3.1"], "LBORRESU": ["mg/dL", "g/dL"]})
        results = rule.evaluate("LB", df, lb_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_unpaired_detected(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB035Rule()
        df = pd.DataFrame({"LBORRES": ["5.2", "3.1"], "LBORRESU": ["mg/dL", None]})
        results = rule.evaluate("LB", df, lb_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB035"
        assert results[0].severity == RuleSeverity.WARNING

    def test_skips_non_lb(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB035Rule()
        results = rule.evaluate("AE", pd.DataFrame({"LBORRES": ["X"]}), ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# FDAB036: LB.LBSTRESN/LBSTRESU paired
# ---------------------------------------------------------------------------


class TestFDAB036:
    def test_paired_passes(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB036Rule()
        df = pd.DataFrame({"LBSTRESN": [5.2, 3.1], "LBSTRESU": ["mmol/L", "g/L"]})
        results = rule.evaluate("LB", df, lb_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_unpaired_detected(self, lb_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB036Rule()
        df = pd.DataFrame({"LBSTRESN": [5.2, 3.1], "LBSTRESU": ["mmol/L", None]})
        results = rule.evaluate("LB", df, lb_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB036"
        assert results[0].severity == RuleSeverity.WARNING

    def test_skips_non_lb(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = FDAB036Rule()
        results = rule.evaluate("AE", pd.DataFrame({"LBSTRESN": [1]}), ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# PopulationFlagRule (FDAB-POP)
# ---------------------------------------------------------------------------


class TestPopulationFlagRule:
    def test_no_flags_passes(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = PopulationFlagRule()
        df = pd.DataFrame({"USUBJID": ["S1"], "SEX": ["M"]})
        results = rule.evaluate("DM", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0

    def test_flag_detected(self, dm_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = PopulationFlagRule()
        df = pd.DataFrame({"USUBJID": ["S1"], "ITT": ["Y"], "SAFETY": ["Y"]})
        results = rule.evaluate("DM", df, dm_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB-POP"
        assert results[0].severity == RuleSeverity.ERROR
        assert "ITT" in results[0].message
        assert "SAFETY" in results[0].message

    def test_skips_non_dm(self, ae_spec, mock_sdtm_ref, mock_ct_ref) -> None:
        rule = PopulationFlagRule()
        df = pd.DataFrame({"ITT": ["Y"]})
        results = rule.evaluate("AE", df, ae_spec, mock_sdtm_ref, mock_ct_ref)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Registry count
# ---------------------------------------------------------------------------


class TestExpandedRuleCount:
    def test_total_rule_count_is_21(self) -> None:
        rules = get_fda_business_rules()
        assert len(rules) == 21

    def test_all_rule_ids_unique(self) -> None:
        rules = get_fda_business_rules()
        rule_ids = [r.rule_id for r in rules]
        assert len(rule_ids) == len(set(rule_ids))
