"""Tests for char_length.py Phase 14 additions: validate_char_max_length."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from astraea.transforms.char_length import validate_char_max_length


class TestValidateCharMaxLength:
    """Tests for validate_char_max_length function."""

    def test_no_violations(self) -> None:
        """DataFrame with all values < 200 bytes returns empty dict."""
        df = pd.DataFrame({"A": ["short", "value"], "B": ["ok", "fine"]})
        result = validate_char_max_length(df)
        assert result == {}

    def test_single_violation(self) -> None:
        """One column with one value > 200 bytes is detected."""
        long_val = "x" * 201
        df = pd.DataFrame({"A": ["short", long_val], "B": ["ok", "fine"]})
        result = validate_char_max_length(df)
        assert "A" in result
        assert result["A"] == [1]

    def test_multiple_columns(self) -> None:
        """Multiple columns with violations return correct dict."""
        long_a = "a" * 250
        long_b = "b" * 210
        df = pd.DataFrame({
            "A": [long_a, "short"],
            "B": ["ok", long_b],
            "C": ["fine", "good"],
        })
        result = validate_char_max_length(df)
        assert "A" in result
        assert result["A"] == [0]
        assert "B" in result
        assert result["B"] == [1]
        assert "C" not in result

    def test_numeric_columns_ignored(self) -> None:
        """Numeric columns are not checked."""
        df = pd.DataFrame({"num": [12345678901234567890, 999], "text": ["ok", "fine"]})
        result = validate_char_max_length(df)
        assert result == {}

    def test_null_values_skipped(self) -> None:
        """None/NaN values are not flagged."""
        df = pd.DataFrame({"A": [None, np.nan, "short"]})
        result = validate_char_max_length(df)
        assert result == {}

    def test_custom_max_bytes(self) -> None:
        """Custom max_bytes=100 catches 101-byte values."""
        val_101 = "x" * 101
        df = pd.DataFrame({"A": [val_101, "short"]})
        result = validate_char_max_length(df, max_bytes=100)
        assert "A" in result
        assert result["A"] == [0]


class TestOptimizeCharLengthsCap:
    """Tests for optimize_char_lengths 200-byte cap."""

    def test_cap_at_200(self) -> None:
        """Values > 200 bytes are capped at 200 in optimize_char_lengths."""
        from astraea.transforms.char_length import optimize_char_lengths

        long_val = "x" * 300
        df = pd.DataFrame({"A": [long_val]})
        widths = optimize_char_lengths(df)
        assert widths["A"] == 200
