"""Tests for merge_findings_sources with merge_mode='join' (horizontal key-based merge)."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.findings import merge_findings_sources


@pytest.fixture()
def source_a() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "USUBJID": ["S001", "S002", "S003"],
            "VISITNUM": [1, 1, 1],
            "LBTESTCD": ["ALB", "ALB", "ALB"],
            "LBORRES": ["4.0", "3.5", "4.2"],
        }
    )


@pytest.fixture()
def source_b() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "USUBJID": ["S001", "S002", "S003"],
            "VISITNUM": [1, 1, 1],
            "LBTESTCD": ["ALB", "ALB", "ALB"],
            "LBORRESU": ["g/dL", "g/dL", "g/dL"],
        }
    )


class TestHorizontalMerge:
    def test_join_mode_merges_on_keys(
        self, source_a: pd.DataFrame, source_b: pd.DataFrame
    ) -> None:
        """Join mode should horizontally merge on USUBJID/VISITNUM/LBTESTCD."""
        dfs = {"src_a": source_a, "src_b": source_b}
        merged, _ = merge_findings_sources(dfs, "LB", merge_mode="join")
        assert len(merged) == 3
        assert "LBORRES" in merged.columns
        assert "LBORRESU" in merged.columns

    def test_join_mode_outer_includes_all_rows(self) -> None:
        """Outer join should include rows from both sources even when keys differ."""
        df1 = pd.DataFrame(
            {"USUBJID": ["S001", "S002"], "VISITNUM": [1, 1], "COL_A": [10, 20]}
        )
        df2 = pd.DataFrame(
            {"USUBJID": ["S002", "S003"], "VISITNUM": [1, 1], "COL_B": [30, 40]}
        )
        dfs = {"d1": df1, "d2": df2}
        merged, _ = merge_findings_sources(dfs, "LB", merge_mode="join")
        assert len(merged) == 3  # S001, S002, S003

    def test_join_mode_suffixes_overlapping_columns(self) -> None:
        """Overlapping non-key columns should be suffixed to avoid collisions."""
        df1 = pd.DataFrame(
            {"USUBJID": ["S001"], "VISITNUM": [1], "VALUE": ["A"]}
        )
        df2 = pd.DataFrame(
            {"USUBJID": ["S001"], "VISITNUM": [1], "VALUE": ["B"]}
        )
        dfs = {"src1": df1, "src2": df2}
        merged, _ = merge_findings_sources(dfs, "LB", merge_mode="join")
        assert len(merged) == 1
        # One column should be VALUE, the other VALUE_src2
        value_cols = [c for c in merged.columns if c.startswith("VALUE")]
        assert len(value_cols) == 2


class TestConcatModeUnchanged:
    def test_concat_default_stacks_vertically(
        self, source_a: pd.DataFrame, source_b: pd.DataFrame
    ) -> None:
        """Default concat mode should stack rows vertically."""
        dfs = {"src_a": source_a, "src_b": source_b}
        merged, _ = merge_findings_sources(dfs, "LB")
        # Concat stacks: 3 + 3 = 6 rows
        assert len(merged) == 6

    def test_concat_explicit_mode(
        self, source_a: pd.DataFrame, source_b: pd.DataFrame
    ) -> None:
        """Explicit merge_mode='concat' should behave same as default."""
        dfs = {"src_a": source_a, "src_b": source_b}
        merged, _ = merge_findings_sources(dfs, "LB", merge_mode="concat")
        assert len(merged) == 6


class TestSingleSource:
    def test_single_source_ignores_merge_mode(self) -> None:
        """Single source should return as-is regardless of merge_mode."""
        df = pd.DataFrame({"USUBJID": ["S001"], "LBORRES": ["5.0"]})
        merged_concat, _ = merge_findings_sources({"only": df}, "LB", merge_mode="concat")
        merged_join, _ = merge_findings_sources({"only": df}, "LB", merge_mode="join")
        assert len(merged_concat) == 1
        assert len(merged_join) == 1
