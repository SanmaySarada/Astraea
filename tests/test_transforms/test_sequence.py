"""Tests for SDTM --SEQ (sequence number) generation."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.transforms.sequence import generate_seq


class TestGenerateSeq:
    """Test the generate_seq function."""

    def test_single_subject(self) -> None:
        """Three rows for one subject produce SEQ 1, 2, 3."""
        df = pd.DataFrame(
            {
                "USUBJID": ["S001", "S001", "S001"],
                "AESTDTC": ["2022-01-01", "2022-02-01", "2022-03-01"],
            }
        )
        result = generate_seq(df, "AE", ["AESTDTC"])

        assert result.dtype == "Int64"
        assert list(result) == [1, 2, 3]

    def test_multiple_subjects(self) -> None:
        """Two subjects with different row counts each start at 1."""
        df = pd.DataFrame(
            {
                "USUBJID": ["S001", "S001", "S002", "S001", "S002"],
                "AESTDTC": [
                    "2022-01-01",
                    "2022-02-01",
                    "2022-01-15",
                    "2022-03-01",
                    "2022-02-15",
                ],
            }
        )
        result = generate_seq(df, "AE", ["AESTDTC"])

        # After sorting by USUBJID + AESTDTC, reindexed to original order:
        # Original idx 0: S001 2022-01-01 -> sorted pos 0 within S001 -> SEQ 1
        # Original idx 1: S001 2022-02-01 -> sorted pos 1 within S001 -> SEQ 2
        # Original idx 2: S002 2022-01-15 -> sorted pos 0 within S002 -> SEQ 1
        # Original idx 3: S001 2022-03-01 -> sorted pos 2 within S001 -> SEQ 3
        # Original idx 4: S002 2022-02-15 -> sorted pos 1 within S002 -> SEQ 2
        assert list(result) == [1, 2, 1, 3, 2]

    def test_preserves_original_index(self) -> None:
        """Output index matches input DataFrame index, not sorted order."""
        df = pd.DataFrame(
            {
                "USUBJID": ["S002", "S001", "S001"],
                "AESTDTC": ["2022-03-01", "2022-01-01", "2022-02-01"],
            },
            index=[10, 20, 30],
        )
        result = generate_seq(df, "AE", ["AESTDTC"])

        assert list(result.index) == [10, 20, 30]
        assert result.loc[10] == 1  # S002 only row -> SEQ 1
        assert result.loc[20] == 1  # S001 first date -> SEQ 1
        assert result.loc[30] == 2  # S001 second date -> SEQ 2

    def test_missing_sort_keys_skipped(self) -> None:
        """Sort keys not in DataFrame are silently skipped."""
        df = pd.DataFrame(
            {
                "USUBJID": ["S001", "S001"],
                "AESTDTC": ["2022-02-01", "2022-01-01"],
            }
        )
        # NONEXISTENT column should be skipped without error
        result = generate_seq(df, "AE", ["AESTDTC", "NONEXISTENT"])

        assert list(result) == [2, 1]  # Sorted by AESTDTC

    def test_empty_dataframe(self) -> None:
        """Empty DataFrame returns empty series."""
        df = pd.DataFrame({"USUBJID": pd.Series(dtype="str")})
        result = generate_seq(df, "AE", ["AESTDTC"])

        assert result.dtype == "Int64"
        assert len(result) == 0

    def test_missing_usubjid_raises(self) -> None:
        """Missing USUBJID column raises KeyError."""
        df = pd.DataFrame({"AESTDTC": ["2022-01-01"]})
        with pytest.raises(KeyError, match="USUBJID"):
            generate_seq(df, "AE", ["AESTDTC"])
