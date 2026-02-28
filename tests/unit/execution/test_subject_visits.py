"""Tests for SV (Subject Visits) domain builder."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.subject_visits import build_sv_domain, extract_visit_dates


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_raw_df(
    subjects: list[str],
    visits: list[tuple[str, str, float]],
    date_col: str = "VISITDAT",
    dates: list[str] | None = None,
) -> pd.DataFrame:
    """Create a raw EDC DataFrame with visit metadata columns."""
    rows = []
    idx = 0
    for subj in subjects:
        for inst, folder, seq in visits:
            dt = dates[idx] if dates and idx < len(dates) else f"2022-01-{idx + 1:02d}"
            rows.append(
                {
                    "Subject": subj,
                    "InstanceName": inst,
                    "FolderName": folder,
                    "FolderSeq": seq,
                    date_col: dt,
                }
            )
            idx += 1
    return pd.DataFrame(rows)


@pytest.fixture
def basic_raw_dfs() -> dict[str, pd.DataFrame]:
    """Two subjects, three visits each."""
    visits = [
        ("Screening", "SCRN", 1.0),
        ("Week 4", "WK4", 2.0),
        ("Week 8", "WK8", 3.0),
    ]
    return {
        "ae": _make_raw_df(
            ["S001", "S002"],
            visits,
            dates=[
                "2022-01-10", "2022-02-07", "2022-03-07",
                "2022-01-15", "2022-02-12", "2022-03-12",
            ],
        )
    }


@pytest.fixture
def multi_source_dfs() -> dict[str, pd.DataFrame]:
    """Visit data spread across two source files."""
    visits_ae = [("Screening", "SCRN", 1.0), ("Week 4", "WK4", 2.0)]
    visits_cm = [("Week 8", "WK8", 3.0)]
    return {
        "ae": _make_raw_df(["S001"], visits_ae, dates=["2022-01-10", "2022-02-07"]),
        "cm": _make_raw_df(["S001"], visits_cm, dates=["2022-03-07"]),
    }


# ---------------------------------------------------------------------------
# extract_visit_dates tests
# ---------------------------------------------------------------------------


class TestExtractVisitDates:
    def test_extract_visit_dates_basic(self, basic_raw_dfs: dict[str, pd.DataFrame]) -> None:
        result = extract_visit_dates(basic_raw_dfs)
        assert len(result) == 6  # 2 subjects x 3 visits
        assert list(result.columns) == [
            "subject_id", "visit_name", "visit_folder",
            "visit_seq", "earliest_date", "latest_date",
        ]

    def test_extract_visit_dates_multi_source(
        self, multi_source_dfs: dict[str, pd.DataFrame]
    ) -> None:
        result = extract_visit_dates(multi_source_dfs)
        # S001 has 3 unique visits across 2 sources
        assert len(result) == 3
        visit_names = set(result["visit_name"])
        assert visit_names == {"Screening", "Week 4", "Week 8"}

    def test_extract_visit_dates_no_visit_cols(self) -> None:
        """DataFrame without InstanceName should produce empty result."""
        df_no_visits = pd.DataFrame(
            {"Subject": ["S001"], "AETERM": ["Headache"]}
        )
        result = extract_visit_dates({"ae": df_no_visits})
        assert result.empty
        assert "subject_id" in result.columns


# ---------------------------------------------------------------------------
# build_sv_domain tests
# ---------------------------------------------------------------------------


class TestBuildSVDomain:
    def test_build_sv_basic(self, basic_raw_dfs: dict[str, pd.DataFrame]) -> None:
        visit_data = extract_visit_dates(basic_raw_dfs)
        sv = build_sv_domain(visit_data, "STUDY01")

        assert len(sv) == 6
        required_cols = {"STUDYID", "DOMAIN", "USUBJID", "SVSEQ", "VISITNUM", "VISIT", "SVSTDTC", "SVENDTC"}
        assert required_cols.issubset(set(sv.columns))
        assert (sv["DOMAIN"] == "SV").all()
        assert (sv["STUDYID"] == "STUDY01").all()

    def test_build_sv_visitnum(self, basic_raw_dfs: dict[str, pd.DataFrame]) -> None:
        visit_data = extract_visit_dates(basic_raw_dfs)
        sv = build_sv_domain(visit_data, "STUDY01")
        # VISITNUM should come from FolderSeq
        assert sv["VISITNUM"].notna().all()
        assert set(sv["VISITNUM"].unique()) == {1.0, 2.0, 3.0}

    def test_build_sv_dates(self, basic_raw_dfs: dict[str, pd.DataFrame]) -> None:
        visit_data = extract_visit_dates(basic_raw_dfs)
        sv = build_sv_domain(visit_data, "STUDY01")
        # earliest and latest should be populated
        assert sv["SVSTDTC"].notna().all()
        assert sv["SVENDTC"].notna().all()

    def test_build_sv_seq(self, basic_raw_dfs: dict[str, pd.DataFrame]) -> None:
        visit_data = extract_visit_dates(basic_raw_dfs)
        sv = build_sv_domain(visit_data, "STUDY01")
        # SVSEQ should be monotonic per subject
        for _, group in sv.groupby("USUBJID"):
            seq_vals = group["SVSEQ"].tolist()
            assert seq_vals == list(range(1, len(seq_vals) + 1))

    def test_build_sv_sort_order(self, basic_raw_dfs: dict[str, pd.DataFrame]) -> None:
        visit_data = extract_visit_dates(basic_raw_dfs)
        sv = build_sv_domain(visit_data, "STUDY01")
        # Should be sorted by STUDYID, USUBJID, VISITNUM
        sorted_sv = sv.sort_values(
            ["STUDYID", "USUBJID", "VISITNUM"], na_position="last"
        ).reset_index(drop=True)
        pd.testing.assert_frame_equal(sv, sorted_sv)

    def test_build_sv_usubjid_lookup(self) -> None:
        visit_data = pd.DataFrame(
            {
                "subject_id": ["S001", "S001"],
                "visit_name": ["Screening", "Week 4"],
                "visit_folder": ["SCRN", "WK4"],
                "visit_seq": [1.0, 2.0],
                "earliest_date": ["2022-01-10", "2022-02-07"],
                "latest_date": ["2022-01-10", "2022-02-07"],
            }
        )
        lookup = {"S001": "STUDY01-SITE01-S001"}
        sv = build_sv_domain(visit_data, "STUDY01", usubjid_lookup=lookup)
        assert (sv["USUBJID"] == "STUDY01-SITE01-S001").all()

    def test_build_sv_empty_input(self) -> None:
        empty = pd.DataFrame(
            columns=["subject_id", "visit_name", "visit_folder", "visit_seq", "earliest_date", "latest_date"]
        )
        sv = build_sv_domain(empty, "STUDY01")
        assert sv.empty
        assert "STUDYID" in sv.columns
