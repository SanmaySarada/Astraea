"""Tests for recoding transforms (numeric_to_yn, etc.)."""

from __future__ import annotations

import math

import pytest

from astraea.transforms.recoding import numeric_to_yn


class TestNumericToYN:
    """Tests for numeric_to_yn function."""

    def test_numeric_1_returns_y(self) -> None:
        assert numeric_to_yn(1) == "Y"

    def test_numeric_0_returns_n(self) -> None:
        assert numeric_to_yn(0) == "N"

    def test_float_1_returns_y(self) -> None:
        assert numeric_to_yn(1.0) == "Y"

    def test_float_0_returns_n(self) -> None:
        assert numeric_to_yn(0.0) == "N"

    def test_nan_returns_none(self) -> None:
        assert numeric_to_yn(float("nan")) is None

    def test_none_returns_none(self) -> None:
        assert numeric_to_yn(None) is None

    def test_string_1_returns_y(self) -> None:
        assert numeric_to_yn("1") == "Y"

    def test_string_0_returns_n(self) -> None:
        assert numeric_to_yn("0") == "N"

    def test_string_10_returns_y(self) -> None:
        assert numeric_to_yn("1.0") == "Y"

    def test_string_00_returns_n(self) -> None:
        assert numeric_to_yn("0.0") == "N"

    def test_unexpected_value_returns_none(self) -> None:
        assert numeric_to_yn("maybe") is None

    def test_unexpected_numeric_returns_none(self) -> None:
        assert numeric_to_yn(2) is None

    def test_math_nan_returns_none(self) -> None:
        assert numeric_to_yn(math.nan) is None

    def test_whitespace_string_1_returns_y(self) -> None:
        assert numeric_to_yn(" 1 ") == "Y"

    def test_whitespace_string_0_returns_n(self) -> None:
        assert numeric_to_yn(" 0 ") == "N"

    def test_registered_in_registry(self) -> None:
        from astraea.mapping.transform_registry import get_transform

        assert get_transform("numeric_to_yn") is not None

    def test_registered_function_is_same_object(self) -> None:
        from astraea.mapping.transform_registry import get_transform

        assert get_transform("numeric_to_yn") is numeric_to_yn
