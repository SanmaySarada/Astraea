"""Integration tests for TS domain with DM data.

Tests that the TS domain builder correctly derives study dates
(SSTDTC, SENDTC) from a DM DataFrame and that all FDA-mandatory
parameters are present and valid.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from astraea.execution.trial_summary import (
    FDA_REQUIRED_PARAMS,
    build_ts_domain,
    validate_ts_completeness,
)
from astraea.models.trial_design import TSConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dm_df() -> pd.DataFrame:
    """Realistic DM DataFrame with 5 subjects."""
    return pd.DataFrame(
        {
            "STUDYID": ["PHA022121-C301"] * 5,
            "DOMAIN": ["DM"] * 5,
            "USUBJID": [
                "PHA022121-C301-001-001",
                "PHA022121-C301-001-002",
                "PHA022121-C301-002-003",
                "PHA022121-C301-002-004",
                "PHA022121-C301-003-005",
            ],
            "RFSTDTC": [
                "2021-06-15",
                "2021-07-01",
                "2021-08-10",
                "2021-09-22",
                "2021-10-05",
            ],
            "RFENDTC": [
                "2022-06-15",
                None,  # subject still on study
                "2022-08-10",
                "2022-09-22",
                "2022-10-05",
            ],
        }
    )


@pytest.fixture
def ts_config() -> TSConfig:
    """TSConfig with study-specific values matching the HAE trial."""
    return TSConfig(
        study_id="PHA022121-C301",
        study_title="A Phase 3 Study of C1-INH in HAE",
        sponsor="Test Pharma",
        indication="Hereditary Angioedema",
        treatment="C1-INH (Human)",
        pharmacological_class="Complement Inhibitor",
        trial_phase="PHASE III TRIAL",
        planned_enrollment=120,
        number_of_arms=3,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTSWithDM:
    def test_ts_with_dm_derives_sstdtc(
        self, ts_config: TSConfig, dm_df: pd.DataFrame
    ) -> None:
        """SSTDTC should be derived as min(RFSTDTC) from DM."""
        ts = build_ts_domain(ts_config, dm_df=dm_df)
        sstdtc_row = ts[ts["TSPARMCD"] == "SSTDTC"]
        assert len(sstdtc_row) == 1
        assert sstdtc_row["TSVAL"].iloc[0] == "2021-06-15"

    def test_ts_with_dm_derives_sendtc(
        self, ts_config: TSConfig, dm_df: pd.DataFrame
    ) -> None:
        """SENDTC should be derived as max(RFENDTC) from DM."""
        ts = build_ts_domain(ts_config, dm_df=dm_df)
        sendtc_row = ts[ts["TSPARMCD"] == "SENDTC"]
        assert len(sendtc_row) == 1
        # max of non-null RFENDTC values
        assert sendtc_row["TSVAL"].iloc[0] == "2022-10-05"

    def test_ts_all_mandatory_present(
        self, ts_config: TSConfig, dm_df: pd.DataFrame
    ) -> None:
        """validate_ts_completeness should return 0 errors."""
        ts = build_ts_domain(ts_config, dm_df=dm_df)
        issues = validate_ts_completeness(ts)
        assert issues == [], f"Unexpected validation issues: {issues}"

    def test_ts_without_dm(self, ts_config: TSConfig) -> None:
        """Without DM, SSTDTC and SENDTC should not be present."""
        ts = build_ts_domain(ts_config, dm_df=None)
        assert "SSTDTC" not in ts["TSPARMCD"].values
        assert "SENDTC" not in ts["TSPARMCD"].values

    def test_ts_xpt_roundtrip(
        self, ts_config: TSConfig, dm_df: pd.DataFrame
    ) -> None:
        """Write TS to XPT, read back, verify all parameters survive."""
        from astraea.io.xpt_writer import write_xpt_v5

        ts = build_ts_domain(ts_config, dm_df=dm_df)

        with tempfile.TemporaryDirectory() as tmpdir:
            xpt_path = Path(tmpdir) / "ts.xpt"

            # Build labels
            labels = {
                "STUDYID": "Study Identifier",
                "DOMAIN": "Domain Abbreviation",
                "TSSEQ": "Sequence Number",
                "TSPARMCD": "Parameter Short Name",
                "TSPARM": "Parameter Name",
                "TSVAL": "Parameter Value",
            }

            write_xpt_v5(
                ts,
                xpt_path,
                table_name="TS",
                column_labels=labels,
                table_label="Trial Summary",
            )

            # Read back
            import pyreadstat

            ts_read, _ = pyreadstat.read_xport(str(xpt_path))

            # All parameters should survive roundtrip
            assert len(ts_read) == len(ts)
            assert set(ts_read["TSPARMCD"]) == set(ts["TSPARMCD"])

    def test_ts_row_count(
        self, ts_config: TSConfig, dm_df: pd.DataFrame
    ) -> None:
        """TS should have at least 10 rows (8 core + SSTDTC + SENDTC + optional)."""
        ts = build_ts_domain(ts_config, dm_df=dm_df)
        # 8 core + PLESSION + NARMS + SSTDTC + SENDTC = 12
        assert len(ts) >= 10

    def test_ts_studyid_consistent(
        self, ts_config: TSConfig, dm_df: pd.DataFrame
    ) -> None:
        """All rows should have the same STUDYID."""
        ts = build_ts_domain(ts_config, dm_df=dm_df)
        assert (ts["STUDYID"] == "PHA022121-C301").all()

    def test_ts_tsseq_unique(
        self, ts_config: TSConfig, dm_df: pd.DataFrame
    ) -> None:
        """TSSEQ values should be unique integers."""
        ts = build_ts_domain(ts_config, dm_df=dm_df)
        tsseq_values = ts["TSSEQ"].tolist()
        assert len(tsseq_values) == len(set(tsseq_values)), "TSSEQ values not unique"
        assert all(isinstance(v, int) for v in tsseq_values), "TSSEQ values not integers"
