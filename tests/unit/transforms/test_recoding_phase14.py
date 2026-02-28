"""Tests for recoding.py Phase 14 additions: recode_sex, recode_race, recode_ethnic."""

from __future__ import annotations

import numpy as np
import pytest

from astraea.transforms.recoding import recode_ethnic, recode_race, recode_sex


class TestRecodeSex:
    """Tests for recode_sex function."""

    @pytest.mark.parametrize("raw,expected", [
        ("Male", "M"),
        ("male", "M"),
        ("M", "M"),
        ("m", "M"),
        ("1", "M"),
    ])
    def test_male_variants(self, raw: str, expected: str) -> None:
        assert recode_sex(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("Female", "F"),
        ("female", "F"),
        ("F", "F"),
        ("f", "F"),
        ("2", "F"),
    ])
    def test_female_variants(self, raw: str, expected: str) -> None:
        assert recode_sex(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("Unknown", "U"),
        ("U", "U"),
    ])
    def test_unknown(self, raw: str, expected: str) -> None:
        assert recode_sex(raw) == expected

    def test_none(self) -> None:
        assert recode_sex(None) is None

    def test_nan(self) -> None:
        assert recode_sex(np.nan) is None

    def test_unrecognized(self) -> None:
        assert recode_sex("other") is None

    def test_whitespace(self) -> None:
        assert recode_sex(" Male ") == "M"


class TestRecodeRace:
    """Tests for recode_race function."""

    @pytest.mark.parametrize("raw,expected", [
        ("White", "WHITE"),
        ("white", "WHITE"),
        ("Asian", "ASIAN"),
    ])
    def test_standard(self, raw: str, expected: str) -> None:
        assert recode_race(raw) == expected

    def test_aliases(self) -> None:
        assert recode_race("african american") == "BLACK OR AFRICAN AMERICAN"
        assert recode_race("caucasian") == "WHITE"
        assert recode_race("native american") == "AMERICAN INDIAN OR ALASKA NATIVE"

    @pytest.mark.parametrize("raw,expected", [
        ("1", "WHITE"),
        ("2", "BLACK OR AFRICAN AMERICAN"),
        ("3", "ASIAN"),
    ])
    def test_numeric(self, raw: str, expected: str) -> None:
        assert recode_race(raw) == expected

    def test_none(self) -> None:
        assert recode_race(None) is None

    def test_unrecognized(self) -> None:
        assert recode_race("martian") is None


class TestRecodeEthnic:
    """Tests for recode_ethnic function."""

    def test_standard(self) -> None:
        assert recode_ethnic("Hispanic or Latino") == "HISPANIC OR LATINO"

    def test_short(self) -> None:
        assert recode_ethnic("hispanic") == "HISPANIC OR LATINO"
        assert recode_ethnic("not hispanic") == "NOT HISPANIC OR LATINO"

    @pytest.mark.parametrize("raw,expected", [
        ("1", "HISPANIC OR LATINO"),
        ("2", "NOT HISPANIC OR LATINO"),
        ("3", "UNKNOWN"),
        ("4", "NOT REPORTED"),
    ])
    def test_numeric(self, raw: str, expected: str) -> None:
        assert recode_ethnic(raw) == expected

    def test_none(self) -> None:
        assert recode_ethnic(None) is None

    def test_nan(self) -> None:
        assert recode_ethnic(np.nan) is None

    def test_unrecognized(self) -> None:
        assert recode_ethnic("prefer not to say") is None
