"""Tests for visit.py Phase 14 additions: build_visit_mapping_from_tv + vectorized assign_visit."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.transforms.visit import assign_visit, build_visit_mapping_from_tv


class TestBuildVisitMappingFromTV:
    """Tests for build_visit_mapping_from_tv function."""

    def test_basic(self) -> None:
        """TV with VISITNUM/VISIT produces correct mapping."""
        tv_df = pd.DataFrame({
            "VISITNUM": [1.0, 2.0, 3.0],
            "VISIT": ["SCREENING", "WEEK 1", "WEEK 2"],
        })
        mapping = build_visit_mapping_from_tv(tv_df)
        assert mapping == {
            "SCREENING": (1.0, "SCREENING"),
            "WEEK 1": (2.0, "WEEK 1"),
            "WEEK 2": (3.0, "WEEK 2"),
        }

    def test_empty(self) -> None:
        """Empty TV returns empty dict."""
        tv_df = pd.DataFrame(columns=["VISITNUM", "VISIT"])
        mapping = build_visit_mapping_from_tv(tv_df)
        assert mapping == {}

    def test_missing_columns(self) -> None:
        """TV without required columns returns empty dict gracefully."""
        tv_df = pd.DataFrame({"OTHER": ["x", "y"]})
        mapping = build_visit_mapping_from_tv(tv_df)
        assert mapping == {}

    def test_with_armcd_filter(self) -> None:
        """TV with ARMCD column filters to specified arm."""
        tv_df = pd.DataFrame({
            "VISITNUM": [1.0, 2.0, 1.0, 2.0],
            "VISIT": ["SCREENING", "WEEK 1", "SCREENING", "WEEK 1"],
            "ARMCD": ["A", "A", "B", "B"],
        })
        mapping = build_visit_mapping_from_tv(tv_df, armcd="B")
        assert "SCREENING" in mapping
        assert mapping["SCREENING"] == (1.0, "SCREENING")

    def test_with_armcd_default_first(self) -> None:
        """TV with ARMCD but no armcd param uses first arm."""
        tv_df = pd.DataFrame({
            "VISITNUM": [1.0, 2.0, 1.0],
            "VISIT": ["SCREENING", "WEEK 1", "SCREENING"],
            "ARMCD": ["A", "A", "B"],
        })
        mapping = build_visit_mapping_from_tv(tv_df)
        assert len(mapping) == 2  # Only arm A entries


class TestAssignVisitVectorized:
    """Verify assign_visit still works correctly after vectorization."""

    def test_basic_mapping(self) -> None:
        """Vectorized assign_visit maps visits correctly."""
        df = pd.DataFrame({"InstanceName": ["Screening", "Week 1", "Week 2"]})
        mapping = {
            "Screening": (1.0, "SCREENING"),
            "Week 1": (2.0, "WEEK 1"),
            "Week 2": (3.0, "WEEK 2"),
        }
        visitnum, visit = assign_visit(df, mapping)
        assert visitnum.iloc[0] == 1.0
        assert visit.iloc[0] == "SCREENING"
        assert visitnum.iloc[2] == 3.0

    def test_unmatched_values(self) -> None:
        """Unmatched values produce NaN."""
        df = pd.DataFrame({"InstanceName": ["Screening", "Unknown Visit"]})
        mapping = {"Screening": (1.0, "SCREENING")}
        visitnum, visit = assign_visit(df, mapping)
        assert visitnum.iloc[0] == 1.0
        assert pd.isna(visitnum.iloc[1])

    def test_null_values(self) -> None:
        """Null raw visit values produce NaN."""
        df = pd.DataFrame({"InstanceName": ["Screening", None]})
        mapping = {"Screening": (1.0, "SCREENING")}
        visitnum, visit = assign_visit(df, mapping)
        assert visitnum.iloc[0] == 1.0
        assert pd.isna(visitnum.iloc[1])
