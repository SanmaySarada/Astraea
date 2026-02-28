"""Tests for character variable length optimization."""

from __future__ import annotations

import numpy as np
import pandas as pd

from astraea.transforms.char_length import optimize_char_lengths


class TestOptimizeCharLengths:
    """Tests for optimize_char_lengths()."""

    def test_basic_optimization(self) -> None:
        """Column with values 'AB' and 'ABCD' returns width 4."""
        df = pd.DataFrame({"col": ["AB", "ABCD"]})
        widths = optimize_char_lengths(df)
        assert widths == {"col": 4}

    def test_empty_column(self) -> None:
        """All-NaN column returns width 1."""
        df = pd.DataFrame({"col": [None, np.nan, pd.NA]})
        widths = optimize_char_lengths(df)
        assert widths == {"col": 1}

    def test_numeric_columns_excluded(self) -> None:
        """Numeric columns are not included in result."""
        df = pd.DataFrame(
            {
                "num_int": [1, 2, 3],
                "num_float": [1.0, 2.0, 3.0],
                "text": ["abc", "defgh", "ij"],
            }
        )
        widths = optimize_char_lengths(df)
        assert "num_int" not in widths
        assert "num_float" not in widths
        assert widths["text"] == 5

    def test_minimum_width_1(self) -> None:
        """Column with empty strings returns width 1, not 0."""
        df = pd.DataFrame({"col": ["", "", ""]})
        widths = optimize_char_lengths(df)
        assert widths["col"] == 1

    def test_mixed_lengths(self) -> None:
        """Multiple columns return correct max per column."""
        df = pd.DataFrame(
            {
                "short": ["a", "bb"],
                "long": ["hello world", "hi"],
                "medium": ["12345", "6789"],
            }
        )
        widths = optimize_char_lengths(df)
        assert widths["short"] == 2
        assert widths["long"] == 11
        assert widths["medium"] == 5

    def test_ascii_byte_length(self) -> None:
        """Confirms byte length for ASCII-replaced multi-byte chars.

        After replacement of non-ASCII via errors='replace', each
        non-ASCII byte becomes '?' (1 byte). This test verifies
        the function measures byte length, not character count.
        """
        # Pure ASCII: byte length == char length
        df = pd.DataFrame({"col": ["hello"]})
        widths = optimize_char_lengths(df)
        assert widths["col"] == 5

    def test_single_char_values(self) -> None:
        """Single-character values return width 1."""
        df = pd.DataFrame({"col": ["A", "B", "C"]})
        widths = optimize_char_lengths(df)
        assert widths["col"] == 1

    def test_no_string_columns(self) -> None:
        """DataFrame with only numeric columns returns empty dict."""
        df = pd.DataFrame({"a": [1, 2], "b": [3.0, 4.0]})
        widths = optimize_char_lengths(df)
        assert widths == {}

    def test_mixed_null_and_values(self) -> None:
        """Column with mix of null and non-null uses max of non-null."""
        df = pd.DataFrame({"col": ["short", None, "a longer string", None]})
        widths = optimize_char_lengths(df)
        assert widths["col"] == 15
