"""Tests for cross-domain consistency validation rules (VAL-03)."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.validation.rules.base import RuleCategory, RuleSeverity
from astraea.validation.rules.consistency import CrossDomainValidator


@pytest.fixture()
def validator() -> CrossDomainValidator:
    return CrossDomainValidator()


@pytest.fixture()
def dm_df() -> pd.DataFrame:
    """DM domain with 3 subjects."""
    return pd.DataFrame(
        {
            "STUDYID": ["STUDY1", "STUDY1", "STUDY1"],
            "DOMAIN": ["DM", "DM", "DM"],
            "USUBJID": ["STUDY1-001", "STUDY1-002", "STUDY1-003"],
            "RFSTDTC": ["2022-01-15", "2022-02-01", "2022-03-10"],
        }
    )


@pytest.fixture()
def ae_df() -> pd.DataFrame:
    """AE domain with known subjects."""
    return pd.DataFrame(
        {
            "STUDYID": ["STUDY1", "STUDY1"],
            "DOMAIN": ["AE", "AE"],
            "USUBJID": ["STUDY1-001", "STUDY1-002"],
            "AESTDTC": ["2022-01-20", "2022-02-10"],
        }
    )


# ---------------------------------------------------------------------------
# ASTR-C001: USUBJID consistency
# ---------------------------------------------------------------------------


class TestUSUBJIDConsistency:
    def test_all_usubjids_in_dm_passes(self, validator, dm_df, ae_df) -> None:
        domains = {"DM": dm_df, "AE": ae_df}
        results = validator._check_usubjid_consistency(domains)
        assert len(results) == 0

    def test_orphan_usubjid_detected(self, validator, dm_df) -> None:
        ae_with_orphan = pd.DataFrame(
            {
                "STUDYID": ["STUDY1", "STUDY1"],
                "DOMAIN": ["AE", "AE"],
                "USUBJID": ["STUDY1-001", "STUDY1-ORPHAN"],
            }
        )
        domains = {"DM": dm_df, "AE": ae_with_orphan}
        results = validator._check_usubjid_consistency(domains)
        assert len(results) == 1
        assert results[0].rule_id == "ASTR-C001"
        assert results[0].severity == RuleSeverity.ERROR
        assert results[0].domain == "AE"
        assert results[0].affected_count == 1
        assert "STUDY1-ORPHAN" in results[0].message

    def test_missing_dm_domain(self, validator, ae_df) -> None:
        domains = {"AE": ae_df}
        results = validator._check_usubjid_consistency(domains)
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert "DM domain not present" in results[0].message

    def test_dm_missing_usubjid_column(self, validator) -> None:
        dm_no_usubjid = pd.DataFrame({"STUDYID": ["S1"], "DOMAIN": ["DM"]})
        domains = {"DM": dm_no_usubjid}
        results = validator._check_usubjid_consistency(domains)
        assert len(results) == 1
        assert "missing USUBJID column" in results[0].message

    def test_p21_equivalent(self, validator, dm_df) -> None:
        ae_orphan = pd.DataFrame(
            {
                "USUBJID": ["STUDY1-ORPHAN"],
                "DOMAIN": ["AE"],
            }
        )
        domains = {"DM": dm_df, "AE": ae_orphan}
        results = validator._check_usubjid_consistency(domains)
        assert results[0].p21_equivalent == "SD0085"


# ---------------------------------------------------------------------------
# ASTR-C002: STUDYID consistency
# ---------------------------------------------------------------------------


class TestSTUDYIDConsistency:
    def test_consistent_studyid_passes(self, validator, dm_df, ae_df) -> None:
        domains = {"DM": dm_df, "AE": ae_df}
        results = validator._check_studyid_consistency(domains)
        assert len(results) == 0

    def test_inconsistent_studyid_detected(self, validator, dm_df) -> None:
        ae_wrong_study = pd.DataFrame(
            {
                "STUDYID": ["STUDY2"],
                "DOMAIN": ["AE"],
                "USUBJID": ["STUDY2-001"],
            }
        )
        domains = {"DM": dm_df, "AE": ae_wrong_study}
        results = validator._check_studyid_consistency(domains)
        assert len(results) == 1
        assert results[0].rule_id == "ASTR-C002"
        assert results[0].severity == RuleSeverity.ERROR
        assert "STUDY1" in results[0].message
        assert "STUDY2" in results[0].message

    def test_no_studyid_anywhere(self, validator) -> None:
        dm = pd.DataFrame({"DOMAIN": ["DM"], "USUBJID": ["S1"]})
        domains = {"DM": dm}
        results = validator._check_studyid_consistency(domains)
        assert len(results) == 1
        assert "No STUDYID values found" in results[0].message


# ---------------------------------------------------------------------------
# ASTR-C003: RFSTDTC consistency
# ---------------------------------------------------------------------------


class TestRFSTDTCConsistency:
    def test_matching_rfstdtc_and_exstdtc(self, validator, dm_df) -> None:
        ex_df = pd.DataFrame(
            {
                "STUDYID": ["STUDY1", "STUDY1"],
                "DOMAIN": ["EX", "EX"],
                "USUBJID": ["STUDY1-001", "STUDY1-001"],
                "EXSTDTC": ["2022-01-15", "2022-01-20"],  # earliest = 2022-01-15 = RFSTDTC
            }
        )
        domains = {"DM": dm_df, "EX": ex_df}
        results = validator._check_rfstdtc_consistency(domains)
        assert len(results) == 0

    def test_mismatched_rfstdtc_and_exstdtc(self, validator, dm_df) -> None:
        ex_df = pd.DataFrame(
            {
                "STUDYID": ["STUDY1"],
                "DOMAIN": ["EX"],
                "USUBJID": ["STUDY1-001"],
                "EXSTDTC": ["2022-02-01"],  # does not match RFSTDTC=2022-01-15
            }
        )
        domains = {"DM": dm_df, "EX": ex_df}
        results = validator._check_rfstdtc_consistency(domains)
        assert len(results) == 1
        assert results[0].rule_id == "ASTR-C003"
        assert results[0].severity == RuleSeverity.WARNING

    def test_no_dm_returns_empty(self, validator) -> None:
        ex_df = pd.DataFrame({"EXSTDTC": ["2022-01-15"], "USUBJID": ["S1"]})
        results = validator._check_rfstdtc_consistency({"EX": ex_df})
        assert len(results) == 0

    def test_no_ex_returns_empty(self, validator, dm_df) -> None:
        results = validator._check_rfstdtc_consistency({"DM": dm_df})
        assert len(results) == 0


# ---------------------------------------------------------------------------
# ASTR-C004: DOMAIN column consistency
# ---------------------------------------------------------------------------


class TestDOMAINColumnConsistency:
    def test_correct_domain_values_pass(self, validator, dm_df, ae_df) -> None:
        domains = {"DM": dm_df, "AE": ae_df}
        specs: dict = {}
        results = validator._check_domain_column_consistency(domains, specs)
        assert len(results) == 0

    def test_wrong_domain_value_detected(self, validator) -> None:
        ae_wrong = pd.DataFrame(
            {
                "DOMAIN": ["AE", "CM"],  # CM is wrong in AE domain
                "USUBJID": ["S1", "S2"],
            }
        )
        domains = {"AE": ae_wrong}
        specs: dict = {}
        results = validator._check_domain_column_consistency(domains, specs)
        assert len(results) == 1
        assert results[0].rule_id == "ASTR-C004"
        assert results[0].severity == RuleSeverity.ERROR
        assert results[0].domain == "AE"
        assert results[0].affected_count == 1


# ---------------------------------------------------------------------------
# ASTR-C005: Study day consistency
# ---------------------------------------------------------------------------


class TestStudyDayConsistency:
    def test_consistent_studyday_passes(self, validator, dm_df) -> None:
        ae_df = pd.DataFrame(
            {
                "USUBJID": ["STUDY1-001"],
                "AESTDTC": ["2022-01-20"],
                "AESTDY": [6],  # positive, date is after RFSTDTC (2022-01-15)
            }
        )
        domains = {"DM": dm_df, "AE": ae_df}
        results = validator._check_studyday_consistency(domains)
        assert len(results) == 0

    def test_inconsistent_positive_dy_before_rfstdtc(self, validator, dm_df) -> None:
        ae_df = pd.DataFrame(
            {
                "USUBJID": ["STUDY1-001"],
                "AESTDTC": ["2022-01-10"],  # before RFSTDTC=2022-01-15
                "AESTDY": [5],  # positive but date is before RFSTDTC
            }
        )
        domains = {"DM": dm_df, "AE": ae_df}
        results = validator._check_studyday_consistency(domains)
        assert len(results) == 1
        assert results[0].rule_id == "ASTR-C005"
        assert results[0].severity == RuleSeverity.WARNING
        assert results[0].affected_count == 1

    def test_inconsistent_negative_dy_after_rfstdtc(self, validator, dm_df) -> None:
        ae_df = pd.DataFrame(
            {
                "USUBJID": ["STUDY1-001"],
                "AESTDTC": ["2022-01-20"],  # after RFSTDTC=2022-01-15
                "AESTDY": [-3],  # negative but date is after RFSTDTC
            }
        )
        domains = {"DM": dm_df, "AE": ae_df}
        results = validator._check_studyday_consistency(domains)
        assert len(results) == 1
        assert results[0].rule_id == "ASTR-C005"

    def test_no_dm_returns_empty(self, validator) -> None:
        ae_df = pd.DataFrame({"AESTDY": [1], "AESTDTC": ["2022-01-20"], "USUBJID": ["S1"]})
        results = validator._check_studyday_consistency({"AE": ae_df})
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Full validate() integration
# ---------------------------------------------------------------------------


class TestCrossDomainValidatorFull:
    def test_validate_all_pass(self, validator, dm_df, ae_df) -> None:
        domains = {"DM": dm_df, "AE": ae_df}
        specs: dict = {}
        results = validator.validate(domains, specs)
        assert len(results) == 0

    def test_validate_catches_multiple_issues(self, validator, dm_df) -> None:
        ae_bad = pd.DataFrame(
            {
                "STUDYID": ["STUDY2"],  # wrong STUDYID
                "DOMAIN": ["CM"],  # wrong DOMAIN
                "USUBJID": ["STUDY1-ORPHAN"],  # not in DM
            }
        )
        domains = {"DM": dm_df, "AE": ae_bad}
        specs: dict = {}
        results = validator.validate(domains, specs)
        # Should catch: STUDYID inconsistency, USUBJID orphan, DOMAIN mismatch
        assert len(results) >= 3
        rule_ids = {r.rule_id for r in results}
        assert "ASTR-C001" in rule_ids
        assert "ASTR-C002" in rule_ids
        assert "ASTR-C004" in rule_ids
