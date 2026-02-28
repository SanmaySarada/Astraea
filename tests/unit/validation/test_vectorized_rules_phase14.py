"""Tests for vectorized validation rules (Phase 14-04).

Verifies that FDAB009, FDAB030, and ASTR-C005 produce correct results
using vectorized pandas operations (groupby+nunique, merge+comparison).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from astraea.models.mapping import DomainMappingSpec
from astraea.validation.rules.base import RuleSeverity
from astraea.validation.rules.consistency import CrossDomainValidator
from astraea.validation.rules.fda_business import FDAB009Rule, FDAB030Rule


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
def mock_refs() -> tuple[MagicMock, MagicMock]:
    return MagicMock(), MagicMock()


# ---------------------------------------------------------------------------
# FDAB009: Vectorized TESTCD/TEST 1:1 check
# ---------------------------------------------------------------------------


class TestFDAB009Vectorized:
    def test_fdab009_vectorized_detects_violation(self, lb_spec, mock_refs) -> None:
        """TESTCD with multiple TEST values should be caught."""
        rule = FDAB009Rule()
        df = pd.DataFrame(
            {
                "LBTESTCD": ["WBC", "WBC", "RBC"],
                "LBTEST": ["White Blood Cell", "WBC Count", "Red Blood Cell"],
            }
        )
        sdtm_ref, ct_ref = mock_refs
        results = rule.evaluate("LB", df, lb_spec, sdtm_ref, ct_ref)
        assert len(results) >= 1
        testcd_result = [r for r in results if r.variable == "LBTESTCD"]
        assert len(testcd_result) == 1
        assert testcd_result[0].rule_id == "FDAB009"
        assert testcd_result[0].severity == RuleSeverity.ERROR
        assert "WBC" in testcd_result[0].message
        assert testcd_result[0].affected_count == 1

    def test_fdab009_vectorized_no_violation(self, lb_spec, mock_refs) -> None:
        """Clean 1:1 data should produce no issues."""
        rule = FDAB009Rule()
        df = pd.DataFrame(
            {
                "LBTESTCD": ["WBC", "WBC", "RBC", "RBC"],
                "LBTEST": [
                    "White Blood Cell",
                    "White Blood Cell",
                    "Red Blood Cell",
                    "Red Blood Cell",
                ],
            }
        )
        sdtm_ref, ct_ref = mock_refs
        results = rule.evaluate("LB", df, lb_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_fdab009_vectorized_reverse_violation(self, lb_spec, mock_refs) -> None:
        """TEST with multiple TESTCD values should be caught in reverse check."""
        rule = FDAB009Rule()
        df = pd.DataFrame(
            {
                "LBTESTCD": ["WBC", "WBCC"],
                "LBTEST": ["White Blood Cell", "White Blood Cell"],
            }
        )
        sdtm_ref, ct_ref = mock_refs
        results = rule.evaluate("LB", df, lb_spec, sdtm_ref, ct_ref)
        test_result = [r for r in results if r.variable == "LBTEST"]
        assert len(test_result) == 1
        assert "White Blood Cell" in test_result[0].message

    def test_fdab009_vectorized_handles_nulls(self, lb_spec, mock_refs) -> None:
        """Null values should be excluded without crashing."""
        rule = FDAB009Rule()
        df = pd.DataFrame(
            {
                "LBTESTCD": ["WBC", None, "RBC"],
                "LBTEST": ["White Blood Cell", "Orphan", None],
            }
        )
        sdtm_ref, ct_ref = mock_refs
        results = rule.evaluate("LB", df, lb_spec, sdtm_ref, ct_ref)
        # Only 1 valid pair per code -- no violations
        assert len(results) == 0


# ---------------------------------------------------------------------------
# FDAB030: Vectorized STRESU consistency
# ---------------------------------------------------------------------------


class TestFDAB030Vectorized:
    def test_fdab030_vectorized_detects_unit_mismatch(self, lb_spec, mock_refs) -> None:
        """Same TESTCD with different STRESU should be caught."""
        rule = FDAB030Rule()
        df = pd.DataFrame(
            {
                "LBTESTCD": ["WBC", "WBC", "RBC"],
                "LBSTRESU": ["10^9/L", "10^3/uL", "10^12/L"],
            }
        )
        sdtm_ref, ct_ref = mock_refs
        results = rule.evaluate("LB", df, lb_spec, sdtm_ref, ct_ref)
        assert len(results) == 1
        assert results[0].rule_id == "FDAB030"
        assert results[0].severity == RuleSeverity.WARNING
        assert "WBC" in results[0].message
        assert results[0].affected_count == 1

    def test_fdab030_vectorized_clean_data(self, lb_spec, mock_refs) -> None:
        """Consistent units should produce no issues."""
        rule = FDAB030Rule()
        df = pd.DataFrame(
            {
                "LBTESTCD": ["WBC", "WBC", "RBC"],
                "LBSTRESU": ["10^9/L", "10^9/L", "10^12/L"],
            }
        )
        sdtm_ref, ct_ref = mock_refs
        results = rule.evaluate("LB", df, lb_spec, sdtm_ref, ct_ref)
        assert len(results) == 0

    def test_fdab030_vectorized_handles_nulls(self, lb_spec, mock_refs) -> None:
        """Null units should be excluded gracefully."""
        rule = FDAB030Rule()
        df = pd.DataFrame(
            {
                "LBTESTCD": ["WBC", "WBC", "RBC"],
                "LBSTRESU": ["10^9/L", None, "10^12/L"],
            }
        )
        sdtm_ref, ct_ref = mock_refs
        results = rule.evaluate("LB", df, lb_spec, sdtm_ref, ct_ref)
        assert len(results) == 0  # Only 1 unit per TESTCD after dropping nulls


# ---------------------------------------------------------------------------
# ASTR-C005: Vectorized study day sign consistency
# ---------------------------------------------------------------------------


class TestASTRC005Vectorized:
    def test_astr_c005_vectorized_detects_sign_mismatch(self) -> None:
        """Positive DY with DTC before RFSTDTC should be caught."""
        validator = CrossDomainValidator()
        dm_df = pd.DataFrame(
            {
                "USUBJID": ["S1", "S2"],
                "RFSTDTC": ["2022-06-01", "2022-06-01"],
            }
        )
        ae_df = pd.DataFrame(
            {
                "USUBJID": ["S1", "S2"],
                "AESTDTC": ["2022-05-15", "2022-07-01"],  # S1 is BEFORE rfstdtc
                "AESTDY": [5, 31],  # S1 has positive DY but date is before -> mismatch
            }
        )
        domains = {"DM": dm_df, "AE": ae_df}
        results = validator._check_studyday_consistency(domains)
        assert len(results) == 1
        assert results[0].rule_id == "ASTR-C005"
        assert results[0].severity == RuleSeverity.WARNING
        assert results[0].domain == "AE"
        assert results[0].affected_count == 1

    def test_astr_c005_vectorized_clean_data(self) -> None:
        """Consistent signs should produce no issues."""
        validator = CrossDomainValidator()
        dm_df = pd.DataFrame(
            {
                "USUBJID": ["S1", "S2"],
                "RFSTDTC": ["2022-06-01", "2022-06-01"],
            }
        )
        ae_df = pd.DataFrame(
            {
                "USUBJID": ["S1", "S2"],
                "AESTDTC": ["2022-07-01", "2022-05-15"],
                "AESTDY": [31, -17],  # Positive for after, negative for before
            }
        )
        domains = {"DM": dm_df, "AE": ae_df}
        results = validator._check_studyday_consistency(domains)
        assert len(results) == 0

    def test_astr_c005_vectorized_handles_missing_dm(self) -> None:
        """No DM data should return empty gracefully (no crash)."""
        validator = CrossDomainValidator()
        ae_df = pd.DataFrame(
            {
                "USUBJID": ["S1"],
                "AESTDTC": ["2022-07-01"],
                "AESTDY": [5],
            }
        )
        domains = {"AE": ae_df}
        results = validator._check_studyday_consistency(domains)
        assert len(results) == 0

    def test_astr_c005_vectorized_handles_empty_rfstdtc(self) -> None:
        """DM with no RFSTDTC should return empty gracefully."""
        validator = CrossDomainValidator()
        dm_df = pd.DataFrame(
            {
                "USUBJID": ["S1"],
                "RFSTDTC": [None],
            }
        )
        ae_df = pd.DataFrame(
            {
                "USUBJID": ["S1"],
                "AESTDTC": ["2022-07-01"],
                "AESTDY": [5],
            }
        )
        domains = {"DM": dm_df, "AE": ae_df}
        results = validator._check_studyday_consistency(domains)
        assert len(results) == 0

    def test_astr_c005_vectorized_multiple_dy_columns(self) -> None:
        """Multiple --DY columns should each be checked independently."""
        validator = CrossDomainValidator()
        dm_df = pd.DataFrame(
            {
                "USUBJID": ["S1"],
                "RFSTDTC": ["2022-06-01"],
            }
        )
        ae_df = pd.DataFrame(
            {
                "USUBJID": ["S1"],
                "AESTDTC": ["2022-05-15"],
                "AESTDY": [5],  # Positive but date before -> mismatch
                "AEENDTC": ["2022-05-20"],
                "AEENDY": [10],  # Positive but date before -> mismatch
            }
        )
        domains = {"DM": dm_df, "AE": ae_df}
        results = validator._check_studyday_consistency(domains)
        assert len(results) == 2  # One per DY column
