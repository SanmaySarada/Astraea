"""Tests for SDTM VISITNUM/VISIT assignment."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.transforms.visit import assign_visit


class TestAssignVisit:
    """Test the assign_visit function."""

    def test_mapped_visits(self) -> None:
        """Known visit names produce correct VISITNUM and VISIT."""
        df = pd.DataFrame(
            {
                "InstanceName": ["Screening", "Week 1", "Week 4"],
            }
        )
        visit_mapping = {
            "Screening": (1.0, "SCREENING"),
            "Week 1": (2.0, "WEEK 1"),
            "Week 4": (3.0, "WEEK 4"),
        }
        visitnum, visit = assign_visit(df, visit_mapping)

        assert visitnum.dtype == "Float64"
        assert list(visitnum) == [1.0, 2.0, 3.0]
        assert list(visit) == ["SCREENING", "WEEK 1", "WEEK 4"]

    def test_unmatched_visit(self) -> None:
        """Raw visit not in mapping produces NaN for both."""
        df = pd.DataFrame(
            {
                "InstanceName": ["Screening", "Unknown Visit"],
            }
        )
        visit_mapping = {"Screening": (1.0, "SCREENING")}
        visitnum, visit = assign_visit(df, visit_mapping)

        assert visitnum.iloc[0] == 1.0
        assert visit.iloc[0] == "SCREENING"
        assert pd.isna(visitnum.iloc[1])
        assert pd.isna(visit.iloc[1])

    def test_empty_mapping(self) -> None:
        """Empty mapping dict produces all NaN."""
        df = pd.DataFrame(
            {
                "InstanceName": ["Screening", "Week 1"],
            }
        )
        visitnum, visit = assign_visit(df, {})

        assert pd.isna(visitnum.iloc[0])
        assert pd.isna(visitnum.iloc[1])
        assert pd.isna(visit.iloc[0])
        assert pd.isna(visit.iloc[1])

    def test_decimal_visitnum(self) -> None:
        """Unplanned visits can have decimal VISITNUM values."""
        df = pd.DataFrame(
            {
                "InstanceName": ["Week 1", "Unplanned 1", "Week 2"],
            }
        )
        visit_mapping = {
            "Week 1": (2.0, "WEEK 1"),
            "Unplanned 1": (2.1, "UNPLANNED"),
            "Week 2": (3.0, "WEEK 2"),
        }
        visitnum, visit = assign_visit(df, visit_mapping)

        assert visitnum.iloc[0] == 2.0
        assert visitnum.iloc[1] == 2.1
        assert visitnum.iloc[2] == 3.0
        assert visit.iloc[1] == "UNPLANNED"

    def test_custom_raw_visit_col(self) -> None:
        """Custom raw visit column name works."""
        df = pd.DataFrame(
            {
                "VISIT_RAW": ["Screening"],
            }
        )
        visit_mapping = {"Screening": (1.0, "SCREENING")}
        visitnum, visit = assign_visit(df, visit_mapping, raw_visit_col="VISIT_RAW")

        assert visitnum.iloc[0] == 1.0
        assert visit.iloc[0] == "SCREENING"

    def test_missing_column_raises(self) -> None:
        """Missing raw visit column raises KeyError."""
        df = pd.DataFrame({"OTHER": ["val"]})
        with pytest.raises(KeyError, match="InstanceName"):
            assign_visit(df, {})

    def test_nan_raw_visit(self) -> None:
        """NaN raw visit value produces NaN output."""
        df = pd.DataFrame(
            {
                "InstanceName": [None, "Screening"],
            }
        )
        visit_mapping = {"Screening": (1.0, "SCREENING")}
        visitnum, visit = assign_visit(df, visit_mapping)

        assert pd.isna(visitnum.iloc[0])
        assert pd.isna(visit.iloc[0])
        assert visitnum.iloc[1] == 1.0
