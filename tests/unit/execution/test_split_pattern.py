"""Tests for SPLIT pattern handler -- SUBSTRING, DELIMITER_PART, REGEX_GROUP."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.pattern_handlers import handle_split
from astraea.models.mapping import (
    ConfidenceLevel,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation


def _make_mapping(
    *,
    sdtm_variable: str = "TEST",
    source_variable: str | None = None,
    derivation_rule: str | None = None,
) -> VariableMapping:
    """Helper to create a VariableMapping for SPLIT tests."""
    return VariableMapping(
        sdtm_variable=sdtm_variable,
        sdtm_label="Test Variable",
        sdtm_data_type="Char",
        core=CoreDesignation.REQ,
        source_variable=source_variable,
        mapping_pattern=MappingPattern.SPLIT,
        mapping_logic="test",
        derivation_rule=derivation_rule,
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="test",
    )


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CODE": ["ABC-123", "DEF-456", "GHI-789"],
            "FULLNAME": ["John Smith", "Jane Doe", "Bob Lee"],
        }
    )


# ---- SUBSTRING tests ----


class TestSubstring:
    def test_basic_substring(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(derivation_rule="SUBSTRING(CODE, 0, 3)")
        result = handle_split(sample_df, mapping)
        assert list(result) == ["ABC", "DEF", "GHI"]

    def test_substring_end_range(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(derivation_rule="SUBSTRING(CODE, 4, 7)")
        result = handle_split(sample_df, mapping)
        assert list(result) == ["123", "456", "789"]

    def test_substring_out_of_range(self, sample_df: pd.DataFrame) -> None:
        """Out-of-range indices should return truncated strings, not errors."""
        mapping = _make_mapping(derivation_rule="SUBSTRING(CODE, 0, 100)")
        result = handle_split(sample_df, mapping)
        assert list(result) == ["ABC-123", "DEF-456", "GHI-789"]

    def test_substring_missing_column(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(derivation_rule="SUBSTRING(MISSING, 0, 3)")
        result = handle_split(sample_df, mapping)
        assert result.isna().all()


# ---- DELIMITER_PART tests ----


class TestDelimiterPart:
    def test_dash_delimiter_first(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(derivation_rule="DELIMITER_PART(CODE, -, 0)")
        result = handle_split(sample_df, mapping)
        assert list(result) == ["ABC", "DEF", "GHI"]

    def test_dash_delimiter_second(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(derivation_rule="DELIMITER_PART(CODE, -, 1)")
        result = handle_split(sample_df, mapping)
        assert list(result) == ["123", "456", "789"]

    def test_space_delimiter(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(derivation_rule="DELIMITER_PART(FULLNAME, ' ', 0)")
        result = handle_split(sample_df, mapping)
        assert list(result) == ["John", "Jane", "Bob"]

    def test_missing_column(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(derivation_rule="DELIMITER_PART(GONE, -, 0)")
        result = handle_split(sample_df, mapping)
        assert result.isna().all()


# ---- REGEX_GROUP tests ----


class TestRegexGroup:
    def test_simple_group(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(derivation_rule=r"REGEX_GROUP(CODE, '(\w+)-(\d+)', 0)")
        result = handle_split(sample_df, mapping)
        assert list(result) == ["ABC", "DEF", "GHI"]

    def test_second_group(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(derivation_rule=r"REGEX_GROUP(CODE, '(\w+)-(\d+)', 1)")
        result = handle_split(sample_df, mapping)
        assert list(result) == ["123", "456", "789"]

    def test_default_group_zero(self, sample_df: pd.DataFrame) -> None:
        """When group_index omitted, default to 0."""
        mapping = _make_mapping(derivation_rule=r"REGEX_GROUP(CODE, '(\w+)-\d+')")
        result = handle_split(sample_df, mapping)
        assert list(result) == ["ABC", "DEF", "GHI"]

    def test_missing_column(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(derivation_rule=r"REGEX_GROUP(NOPE, '(\w+)', 0)")
        result = handle_split(sample_df, mapping)
        assert result.isna().all()


# ---- Fallback tests ----


class TestFallback:
    def test_no_rule_with_source_variable(self, sample_df: pd.DataFrame) -> None:
        """No derivation_rule but source_variable set -> return source column copy."""
        mapping = _make_mapping(source_variable="CODE")
        result = handle_split(sample_df, mapping)
        assert list(result) == ["ABC-123", "DEF-456", "GHI-789"]

    def test_unrecognized_rule_with_source(self, sample_df: pd.DataFrame) -> None:
        """Unrecognized derivation_rule -> fall back to source column, not None."""
        mapping = _make_mapping(source_variable="CODE", derivation_rule="UNKNOWN_FUNC(CODE)")
        result = handle_split(sample_df, mapping)
        assert list(result) == ["ABC-123", "DEF-456", "GHI-789"]

    def test_no_source_returns_none(self) -> None:
        """No source_variable and no derivation_rule -> None series."""
        df = pd.DataFrame({"A": [1, 2, 3]})
        mapping = _make_mapping()
        result = handle_split(df, mapping)
        assert result.isna().all()
        assert len(result) == 3
