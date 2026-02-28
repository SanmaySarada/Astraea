"""Unit tests for the Trial Summary (TS) domain builder.

Tests TSConfig model validation, build_ts_domain output structure,
date derivation from DM, optional parameter inclusion, TSSEQ
sequencing, and validate_ts_completeness error detection.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.trial_summary import (
    FDA_REQUIRED_PARAMS,
    build_ts_domain,
    validate_ts_completeness,
)
from astraea.models.trial_design import TSConfig, TSParameter


@pytest.fixture()
def minimal_config() -> TSConfig:
    """Minimal TSConfig with only required fields."""
    return TSConfig(
        study_id="PHA022121-C301",
        study_title="Phase 3 Study of Drug X in HAE",
        sponsor="Pharma Corp",
        indication="Hereditary Angioedema",
        treatment="Drug X 300mg SC",
        pharmacological_class="Kallikrein Inhibitor",
    )


class TestTSBasicBuild:
    def test_ts_basic_build(self, minimal_config: TSConfig) -> None:
        """Build with minimal TSConfig should produce all 8 core parameters."""
        ts_df = build_ts_domain(minimal_config)

        # Should have exactly 8 rows (core parameters only, no DM dates)
        assert len(ts_df) == 8

        codes = set(ts_df["TSPARMCD"].values)
        expected_core = {"TITLE", "SPONSOR", "INDIC", "TRT", "PCLAS", "STYPE", "SDTMVER", "TPHASE"}
        assert codes == expected_core

    def test_ts_domain_column(self, minimal_config: TSConfig) -> None:
        """DOMAIN should be 'TS' for all rows."""
        ts_df = build_ts_domain(minimal_config)
        assert all(ts_df["DOMAIN"] == "TS")

    def test_ts_studyid_column(self, minimal_config: TSConfig) -> None:
        """STUDYID should match config for all rows."""
        ts_df = build_ts_domain(minimal_config)
        assert all(ts_df["STUDYID"] == "PHA022121-C301")

    def test_ts_columns(self, minimal_config: TSConfig) -> None:
        """TS should have exactly the 6 required columns."""
        ts_df = build_ts_domain(minimal_config)
        expected_cols = {"STUDYID", "DOMAIN", "TSSEQ", "TSPARMCD", "TSPARM", "TSVAL"}
        assert set(ts_df.columns) == expected_cols


class TestTSWithDMDates:
    def test_ts_with_dm_dates(self, minimal_config: TSConfig) -> None:
        """Build with DM DataFrame should derive SSTDTC and SENDTC."""
        dm_df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001", "SUBJ-002", "SUBJ-003"],
                "RFSTDTC": ["2022-01-15", "2022-02-01", "2022-03-10"],
                "RFENDTC": ["2022-06-15", "2022-07-01", "2022-08-10"],
            }
        )
        ts_df = build_ts_domain(minimal_config, dm_df=dm_df)

        codes = set(ts_df["TSPARMCD"].values)
        assert "SSTDTC" in codes
        assert "SENDTC" in codes

        # SSTDTC should be min RFSTDTC
        sstdtc_row = ts_df[ts_df["TSPARMCD"] == "SSTDTC"]
        assert sstdtc_row["TSVAL"].iloc[0] == "2022-01-15"

        # SENDTC should be max RFENDTC
        sendtc_row = ts_df[ts_df["TSPARMCD"] == "SENDTC"]
        assert sendtc_row["TSVAL"].iloc[0] == "2022-08-10"

    def test_ts_with_dm_no_rfendtc(self, minimal_config: TSConfig) -> None:
        """DM without RFENDTC should derive SSTDTC only, no SENDTC."""
        dm_df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001", "SUBJ-002"],
                "RFSTDTC": ["2022-01-15", "2022-02-01"],
            }
        )
        ts_df = build_ts_domain(minimal_config, dm_df=dm_df)

        codes = set(ts_df["TSPARMCD"].values)
        assert "SSTDTC" in codes
        assert "SENDTC" not in codes


class TestTSOptionalParams:
    def test_ts_optional_params(self, minimal_config: TSConfig) -> None:
        """Build with optional params should include PLESSION and NARMS."""
        config = minimal_config.model_copy(
            update={"planned_enrollment": 300, "number_of_arms": 3}
        )
        ts_df = build_ts_domain(config)

        codes = set(ts_df["TSPARMCD"].values)
        assert "PLESSION" in codes
        assert "NARMS" in codes

        # Check values
        plession_row = ts_df[ts_df["TSPARMCD"] == "PLESSION"]
        assert plession_row["TSVAL"].iloc[0] == "300"

        narms_row = ts_df[ts_df["TSPARMCD"] == "NARMS"]
        assert narms_row["TSVAL"].iloc[0] == "3"

    def test_ts_accession_and_addon(self, minimal_config: TSConfig) -> None:
        """Build with accession number and addon should include them."""
        config = minimal_config.model_copy(
            update={"accession_number": "NDA-123456", "addon": "Y"}
        )
        ts_df = build_ts_domain(config)

        codes = set(ts_df["TSPARMCD"].values)
        assert "ACESSION" in codes
        assert "ADDON" in codes

    def test_ts_additional_params(self, minimal_config: TSConfig) -> None:
        """Build with custom TSParameter entries should include them."""
        config = minimal_config.model_copy(
            update={
                "additional_params": [
                    TSParameter(tsparmcd="REGID", tsparm="Registry Identifier", tsval="NCT12345678"),
                    TSParameter(tsparmcd="OBJPRIM", tsparm="Trial Primary Objective", tsval="Efficacy"),
                ]
            }
        )
        ts_df = build_ts_domain(config)

        codes = set(ts_df["TSPARMCD"].values)
        assert "REGID" in codes
        assert "OBJPRIM" in codes

        regid_row = ts_df[ts_df["TSPARMCD"] == "REGID"]
        assert regid_row["TSVAL"].iloc[0] == "NCT12345678"


class TestTSSeq:
    def test_ts_seq_monotonic(self, minimal_config: TSConfig) -> None:
        """TSSEQ should be 1, 2, 3, ... (1-based, monotonically increasing)."""
        ts_df = build_ts_domain(minimal_config)
        seq_values = list(ts_df["TSSEQ"])
        expected = list(range(1, len(ts_df) + 1))
        assert seq_values == expected

    def test_ts_seq_with_optional_params(self, minimal_config: TSConfig) -> None:
        """TSSEQ should remain sequential even with optional params."""
        config = minimal_config.model_copy(
            update={
                "planned_enrollment": 200,
                "additional_params": [
                    TSParameter(tsparmcd="REGID", tsparm="Registry Identifier", tsval="NCT99999999"),
                ],
            }
        )
        ts_df = build_ts_domain(config)
        seq_values = list(ts_df["TSSEQ"])
        expected = list(range(1, len(ts_df) + 1))
        assert seq_values == expected


class TestTSValidation:
    def test_ts_validate_complete(self, minimal_config: TSConfig) -> None:
        """A complete TS (with SSTDTC from DM) should pass validation."""
        dm_df = pd.DataFrame(
            {
                "USUBJID": ["SUBJ-001"],
                "RFSTDTC": ["2022-01-15"],
            }
        )
        ts_df = build_ts_domain(minimal_config, dm_df=dm_df)
        issues = validate_ts_completeness(ts_df)
        assert issues == []

    def test_ts_validate_missing_sponsor(self) -> None:
        """Validation should catch missing SPONSOR."""
        # Build a TS manually missing SPONSOR
        ts_df = pd.DataFrame(
            {
                "STUDYID": ["STUDY1"] * 6,
                "DOMAIN": ["TS"] * 6,
                "TSSEQ": [1, 2, 3, 4, 5, 6],
                "TSPARMCD": ["SSTDTC", "INDIC", "TRT", "STYPE", "SDTMVER", "TPHASE"],
                "TSPARM": ["Study Start Date", "Indication", "Treatment", "Study Type", "SDTM Version", "Trial Phase"],
                "TSVAL": ["2022-01-01", "HAE", "Drug X", "INTERVENTIONAL", "3.4", "PHASE III TRIAL"],
            }
        )
        issues = validate_ts_completeness(ts_df)
        assert any("SPONSOR" in i for i in issues)

    def test_ts_validate_empty_tsval(self) -> None:
        """Validation should catch empty TSVAL for a required parameter."""
        ts_df = pd.DataFrame(
            {
                "STUDYID": ["STUDY1"] * 7,
                "DOMAIN": ["TS"] * 7,
                "TSSEQ": list(range(1, 8)),
                "TSPARMCD": ["SSTDTC", "SPONSOR", "INDIC", "TRT", "STYPE", "SDTMVER", "TPHASE"],
                "TSPARM": ["a"] * 7,
                "TSVAL": ["2022-01-01", "", "HAE", "Drug X", "INTERVENTIONAL", "3.4", "PHASE III TRIAL"],
            }
        )
        issues = validate_ts_completeness(ts_df)
        assert any("SPONSOR" in i and "empty" in i.lower() for i in issues)

    def test_ts_validate_empty_dataframe(self) -> None:
        """Validation of empty TS should report error."""
        ts_df = pd.DataFrame()
        issues = validate_ts_completeness(ts_df)
        assert len(issues) > 0
        assert any("empty" in i.lower() for i in issues)


class TestTSParameterModel:
    def test_tsparmcd_uppercase(self) -> None:
        """TSPARMCD should be auto-uppercased."""
        param = TSParameter(tsparmcd="title", tsparm="Trial Title", tsval="My Study")
        assert param.tsparmcd == "TITLE"

    def test_tsparmcd_max_length(self) -> None:
        """TSPARMCD longer than 8 chars should be rejected."""
        with pytest.raises(ValueError):
            TSParameter(tsparmcd="TOOLONGCD", tsparm="Too Long", tsval="val")

    def test_tsval_not_empty(self) -> None:
        """TSVAL must not be empty string."""
        with pytest.raises(ValueError):
            TSParameter(tsparmcd="TEST", tsparm="Test", tsval="")


class TestFDARequiredParams:
    def test_fda_required_params_is_frozenset(self) -> None:
        """FDA_REQUIRED_PARAMS should be a frozenset."""
        assert isinstance(FDA_REQUIRED_PARAMS, frozenset)

    def test_fda_required_params_contents(self) -> None:
        """FDA_REQUIRED_PARAMS should contain the 7 mandatory codes."""
        expected = {"SSTDTC", "SPONSOR", "INDIC", "TRT", "STYPE", "SDTMVER", "TPHASE"}
        assert FDA_REQUIRED_PARAMS == expected
