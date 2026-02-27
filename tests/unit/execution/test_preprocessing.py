"""Tests for pre-execution utilities (filter_rows, align_multi_source_columns)."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.preprocessing import align_multi_source_columns, filter_rows


class TestFilterRows:
    """Tests for filter_rows function."""

    def _make_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "EXYN": ["Y", "Y", "N", "Y", "N"],
            "EXDOSE": [100, 200, 0, 150, 0],
        })

    def test_keep_values_filters_correctly(self) -> None:
        df = self._make_df()
        result = filter_rows(df, column="EXYN", keep_values={"Y"})
        assert len(result) == 3
        assert list(result["EXYN"]) == ["Y", "Y", "Y"]

    def test_exclude_values_filters_correctly(self) -> None:
        df = self._make_df()
        result = filter_rows(df, column="EXYN", exclude_values={"N"})
        assert len(result) == 3
        assert list(result["EXYN"]) == ["Y", "Y", "Y"]

    def test_case_insensitive_matching(self) -> None:
        df = pd.DataFrame({"STATUS": ["y", "Y", "n", "N"]})
        result = filter_rows(df, column="STATUS", keep_values={"Y"})
        assert len(result) == 2

    def test_missing_column_raises_keyerror(self) -> None:
        df = self._make_df()
        with pytest.raises(KeyError, match="NONEXIST"):
            filter_rows(df, column="NONEXIST", keep_values={"Y"})

    def test_both_keep_and_exclude_raises_valueerror(self) -> None:
        df = self._make_df()
        with pytest.raises(ValueError, match="Exactly one"):
            filter_rows(df, column="EXYN", keep_values={"Y"}, exclude_values={"N"})

    def test_neither_keep_nor_exclude_raises_valueerror(self) -> None:
        df = self._make_df()
        with pytest.raises(ValueError, match="Exactly one"):
            filter_rows(df, column="EXYN")

    def test_returns_copy_with_reset_index(self) -> None:
        df = self._make_df()
        result = filter_rows(df, column="EXYN", keep_values={"Y"})
        # Index should be 0,1,2 (reset), not 0,1,3 (original)
        assert list(result.index) == [0, 1, 2]
        # Should be a copy, not a view
        result.iloc[0, 0] = "MODIFIED"
        assert df.iloc[0, 0] == "Y"

    def test_empty_result_returns_empty_df(self) -> None:
        df = self._make_df()
        result = filter_rows(df, column="EXYN", keep_values={"X"})
        assert len(result) == 0
        assert list(result.columns) == ["EXYN", "EXDOSE"]

    def test_whitespace_handling(self) -> None:
        df = pd.DataFrame({"COL": [" Y ", "N", " y"]})
        result = filter_rows(df, column="COL", keep_values={"Y"})
        assert len(result) == 2

    def test_exclude_multiple_values(self) -> None:
        df = pd.DataFrame({"STATUS": ["A", "B", "C", "D"]})
        result = filter_rows(df, column="STATUS", exclude_values={"A", "C"})
        assert len(result) == 2
        assert list(result["STATUS"]) == ["B", "D"]


class TestAlignMultiSourceColumns:
    """Tests for align_multi_source_columns function."""

    def test_renames_columns_correctly(self) -> None:
        dfs = {
            "ds2": pd.DataFrame({"DSDECOD2": ["A", "B"], "DSSTDTC2": ["2022-01", "2022-02"]}),
        }
        rename_maps = {
            "ds2": {"DSDECOD2": "DSDECOD", "DSSTDTC2": "DSSTDTC"},
        }
        result = align_multi_source_columns(dfs, rename_maps)
        assert "DSDECOD" in result["ds2"].columns
        assert "DSSTDTC" in result["ds2"].columns
        assert "DSDECOD2" not in result["ds2"].columns

    def test_sources_without_rename_pass_through(self) -> None:
        dfs = {
            "ds1": pd.DataFrame({"DSDECOD": ["A"]}),
            "ds2": pd.DataFrame({"DSDECOD2": ["B"]}),
        }
        rename_maps = {
            "ds2": {"DSDECOD2": "DSDECOD"},
        }
        result = align_multi_source_columns(dfs, rename_maps)
        assert list(result["ds1"].columns) == ["DSDECOD"]
        assert list(result["ds2"].columns) == ["DSDECOD"]

    def test_returns_copies_not_originals(self) -> None:
        original = pd.DataFrame({"A": [1, 2, 3]})
        dfs = {"src": original}
        result = align_multi_source_columns(dfs, {})
        result["src"].iloc[0, 0] = 999
        assert original.iloc[0, 0] == 1

    def test_empty_rename_maps_returns_copies(self) -> None:
        dfs = {"src": pd.DataFrame({"A": [1]})}
        result = align_multi_source_columns(dfs, {})
        assert list(result["src"].columns) == ["A"]

    def test_multiple_sources_renamed(self) -> None:
        dfs = {
            "mh1": pd.DataFrame({"MHTERM1": ["Headache"]}),
            "mh2": pd.DataFrame({"MHTERM2": ["Fever"]}),
        }
        rename_maps = {
            "mh1": {"MHTERM1": "MHTERM"},
            "mh2": {"MHTERM2": "MHTERM"},
        }
        result = align_multi_source_columns(dfs, rename_maps)
        assert "MHTERM" in result["mh1"].columns
        assert "MHTERM" in result["mh2"].columns
