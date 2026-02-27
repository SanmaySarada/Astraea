"""Tests for ASCII validation and cleanup transforms."""

from __future__ import annotations

import pandas as pd

from astraea.transforms.ascii_validation import (
    _MAX_ISSUES,
    _NON_ASCII_REPLACEMENTS,
    fix_common_non_ascii,
    validate_ascii,
)


class TestValidateAscii:
    """Tests for validate_ascii()."""

    def test_all_ascii_no_issues(self) -> None:
        """DataFrame with only ASCII data returns empty list."""
        df = pd.DataFrame({
            "name": ["Alice", "Bob", "Charlie"],
            "code": ["A01", "B02", "C03"],
        })
        issues = validate_ascii(df)
        assert issues == []

    def test_detects_non_ascii(self) -> None:
        """DataFrame with curly quotes produces issue entries."""
        df = pd.DataFrame({
            "text": ["normal", "has \u201csmart\u201d quotes", "ok"],
        })
        issues = validate_ascii(df)
        assert len(issues) == 1
        assert issues[0]["column"] == "text"
        assert issues[0]["row"] == 1
        assert "\u201c" in issues[0]["non_ascii_chars"]
        assert "\u201d" in issues[0]["non_ascii_chars"]

    def test_issue_cap(self) -> None:
        """DataFrame with >100 non-ASCII values returns exactly 100 issues."""
        # Create 150 rows each with a non-ASCII character
        df = pd.DataFrame({
            "text": [f"value\u00b0{i}" for i in range(150)],
        })
        issues = validate_ascii(df)
        assert len(issues) == _MAX_ISSUES

    def test_numeric_columns_skipped(self) -> None:
        """Numeric columns are not checked for ASCII."""
        df = pd.DataFrame({
            "num_int": [1, 2, 3],
            "num_float": [1.0, 2.0, 3.0],
            "text": ["a", "b", "c"],
        })
        issues = validate_ascii(df)
        assert issues == []

    def test_null_values_skipped(self) -> None:
        """NaN/None values do not produce issues."""
        df = pd.DataFrame({
            "text": ["hello", None, pd.NA],
        })
        issues = validate_ascii(df)
        assert issues == []

    def test_multiple_columns(self) -> None:
        """Issues across multiple columns are detected."""
        df = pd.DataFrame({
            "col_a": ["fine", "has \u2013 dash"],
            "col_b": ["\u00b0C", "ok"],
        })
        issues = validate_ascii(df)
        assert len(issues) == 2
        columns = {i["column"] for i in issues}
        assert columns == {"col_a", "col_b"}


class TestFixCommonNonAscii:
    """Tests for fix_common_non_ascii()."""

    def test_fix_curly_quotes(self) -> None:
        """Curly double quotes replaced with straight quotes."""
        df = pd.DataFrame({"text": ["He said \u201chello\u201d"]})
        result = fix_common_non_ascii(df)
        assert result["text"].iloc[0] == 'He said "hello"'

    def test_fix_single_curly_quotes(self) -> None:
        """Curly single quotes replaced with straight apostrophe."""
        df = pd.DataFrame({"text": ["it\u2019s"]})
        result = fix_common_non_ascii(df)
        assert result["text"].iloc[0] == "it's"

    def test_fix_en_dash(self) -> None:
        """En-dash replaced with hyphen."""
        df = pd.DataFrame({"text": ["1\u20132"]})
        result = fix_common_non_ascii(df)
        assert result["text"].iloc[0] == "1-2"

    def test_fix_em_dash(self) -> None:
        """Em-dash replaced with hyphen."""
        df = pd.DataFrame({"text": ["word\u2014another"]})
        result = fix_common_non_ascii(df)
        assert result["text"].iloc[0] == "word-another"

    def test_fix_degree_sign(self) -> None:
        """Degree sign replaced with 'deg'."""
        df = pd.DataFrame({"text": ["37\u00b0C"]})
        result = fix_common_non_ascii(df)
        assert result["text"].iloc[0] == "37degC"

    def test_fix_micro_sign(self) -> None:
        """Micro sign replaced with 'u'."""
        df = pd.DataFrame({"text": ["5\u00b5g"]})
        result = fix_common_non_ascii(df)
        assert result["text"].iloc[0] == "5ug"

    def test_fix_plus_minus(self) -> None:
        """Plus-minus sign replaced with '+-'."""
        df = pd.DataFrame({"text": ["10\u00b12"]})
        result = fix_common_non_ascii(df)
        assert result["text"].iloc[0] == "10+-2"

    def test_fix_comparison_signs(self) -> None:
        """Less-than-or-equal and greater-than-or-equal replaced."""
        df = pd.DataFrame({"text": ["\u2264 5", "\u2265 10"]})
        result = fix_common_non_ascii(df)
        assert result["text"].iloc[0] == "<= 5"
        assert result["text"].iloc[1] == ">= 10"

    def test_fix_ellipsis(self) -> None:
        """Ellipsis replaced with three dots."""
        df = pd.DataFrame({"text": ["wait\u2026"]})
        result = fix_common_non_ascii(df)
        assert result["text"].iloc[0] == "wait..."

    def test_fix_preserves_ascii(self) -> None:
        """Pure ASCII columns remain unchanged."""
        df = pd.DataFrame({"text": ["hello", "world", "123"]})
        result = fix_common_non_ascii(df)
        pd.testing.assert_frame_equal(result, df)

    def test_fix_does_not_modify_original(self) -> None:
        """Original DataFrame is not modified."""
        df = pd.DataFrame({"text": ["has \u201cquotes\u201d"]})
        original_val = df["text"].iloc[0]
        _ = fix_common_non_ascii(df)
        assert df["text"].iloc[0] == original_val

    def test_all_12_replacements_exist(self) -> None:
        """Replacement map has exactly 12 entries."""
        assert len(_NON_ASCII_REPLACEMENTS) == 12
