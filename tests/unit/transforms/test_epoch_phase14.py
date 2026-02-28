"""Tests for epoch.py Phase 14 additions: detect_epoch_overlaps + vectorized SE grouping."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.transforms.epoch import detect_epoch_overlaps


class TestDetectEpochOverlaps:
    """Tests for detect_epoch_overlaps function."""

    def test_no_overlaps(self) -> None:
        """Sequential epochs with no overlap return empty list."""
        se_df = pd.DataFrame({
            "USUBJID": ["S1", "S1", "S1"],
            "SESTDTC": ["2022-01-01", "2022-02-01", "2022-03-01"],
            "SEENDTC": ["2022-02-01", "2022-03-01", "2022-04-01"],
            "EPOCH": ["SCREENING", "TREATMENT", "FOLLOW-UP"],
        })
        result = detect_epoch_overlaps(se_df)
        assert result == []

    def test_overlapping_epochs(self) -> None:
        """Two epochs with overlapping dates are detected."""
        se_df = pd.DataFrame({
            "USUBJID": ["S1", "S1"],
            "SESTDTC": ["2022-01-01", "2022-01-15"],
            "SEENDTC": ["2022-02-01", "2022-03-01"],
            "EPOCH": ["SCREENING", "TREATMENT"],
        })
        result = detect_epoch_overlaps(se_df)
        assert len(result) == 1
        assert result[0]["usubjid"] == "S1"
        assert result[0]["epoch_1"] == "SCREENING"
        assert result[0]["epoch_2"] == "TREATMENT"
        assert result[0]["overlap_start"] == "2022-01-15"
        assert result[0]["overlap_end"] == "2022-02-01"

    def test_adjacent_not_overlapping(self) -> None:
        """End == Start of next is NOT flagged (adjacent, not overlapping)."""
        se_df = pd.DataFrame({
            "USUBJID": ["S1", "S1"],
            "SESTDTC": ["2022-01-01", "2022-02-01"],
            "SEENDTC": ["2022-02-01", "2022-03-01"],
            "EPOCH": ["SCREENING", "TREATMENT"],
        })
        result = detect_epoch_overlaps(se_df)
        assert result == []

    def test_open_ended_epoch(self) -> None:
        """No SEENDTC extends to infinity, overlaps with next."""
        se_df = pd.DataFrame({
            "USUBJID": ["S1", "S1"],
            "SESTDTC": ["2022-01-01", "2022-02-01"],
            "SEENDTC": [None, "2022-03-01"],
            "EPOCH": ["SCREENING", "TREATMENT"],
        })
        result = detect_epoch_overlaps(se_df)
        assert len(result) == 1
        assert result[0]["epoch_1"] == "SCREENING"
        assert result[0]["epoch_2"] == "TREATMENT"

    def test_multiple_subjects(self) -> None:
        """Overlaps are detected per subject independently."""
        se_df = pd.DataFrame({
            "USUBJID": ["S1", "S1", "S2", "S2"],
            "SESTDTC": ["2022-01-01", "2022-01-15", "2022-01-01", "2022-03-01"],
            "SEENDTC": ["2022-02-01", "2022-03-01", "2022-02-01", "2022-04-01"],
            "EPOCH": ["SCREENING", "TREATMENT", "SCREENING", "TREATMENT"],
        })
        result = detect_epoch_overlaps(se_df)
        # S1 has overlap, S2 does not
        assert len(result) == 1
        assert result[0]["usubjid"] == "S1"

    def test_empty_df(self) -> None:
        """Empty DataFrame returns empty list."""
        se_df = pd.DataFrame(columns=["USUBJID", "SESTDTC", "SEENDTC", "EPOCH"])
        result = detect_epoch_overlaps(se_df)
        assert result == []


class TestEpochVectorizedGrouping:
    """Verify that assign_epoch still works after vectorization of SE grouping."""

    def test_assign_epoch_still_works(self) -> None:
        """assign_epoch produces correct results with vectorized SE grouping."""
        from astraea.transforms.epoch import assign_epoch

        df = pd.DataFrame({
            "USUBJID": ["S1", "S1"],
            "AESTDTC": ["2022-01-15", "2022-02-15"],
        })
        se_df = pd.DataFrame({
            "USUBJID": ["S1", "S1"],
            "SESTDTC": ["2022-01-01", "2022-02-01"],
            "SEENDTC": ["2022-02-01", "2022-03-01"],
            "EPOCH": ["SCREENING", "TREATMENT"],
        })
        result = assign_epoch(df, se_df, date_col="AESTDTC")
        assert result.iloc[0] == "SCREENING"
        assert result.iloc[1] == "TREATMENT"
