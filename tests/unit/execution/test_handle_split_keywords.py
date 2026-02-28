"""Tests for handle_split keyword coverage -- SUBSTRING, DELIMITER_PART, REGEX_GROUP.

Validates that all three SPLIT derivation keywords produce correct output
and that unknown keywords / missing rules fall back to source column copy.
"""

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


def _split_mapping(
    *,
    sdtm_variable: str = "TESTVAR",
    source_variable: str | None = None,
    derivation_rule: str | None = None,
) -> VariableMapping:
    """Create a minimal SPLIT VariableMapping for testing."""
    return VariableMapping(
        sdtm_variable=sdtm_variable,
        sdtm_label="Test",
        sdtm_data_type="Char",
        core=CoreDesignation.REQ,
        source_variable=source_variable,
        mapping_pattern=MappingPattern.SPLIT,
        mapping_logic="split test",
        derivation_rule=derivation_rule,
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="test",
    )


@pytest.fixture()
def df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "VAL": ["alpha-100", "beta-200", "gamma-300"],
        }
    )


def test_substring_keyword(df: pd.DataFrame) -> None:
    """SUBSTRING(col, 0, 3) extracts first 3 chars."""
    mapping = _split_mapping(derivation_rule="SUBSTRING(VAL, 0, 3)")
    result = handle_split(df, mapping)
    assert list(result) == ["alp", "bet", "gam"]


def test_delimiter_part_keyword(df: pd.DataFrame) -> None:
    """DELIMITER_PART(col, '-', 0) extracts before first dash."""
    mapping = _split_mapping(derivation_rule="DELIMITER_PART(VAL, -, 0)")
    result = handle_split(df, mapping)
    assert list(result) == ["alpha", "beta", "gamma"]


def test_regex_group_keyword(df: pd.DataFrame) -> None:
    r"""REGEX_GROUP(col, '(\d+)', 0) extracts first number."""
    mapping = _split_mapping(derivation_rule=r"REGEX_GROUP(VAL, '(\d+)', 0)")
    result = handle_split(df, mapping)
    assert list(result) == ["100", "200", "300"]


def test_unknown_keyword_falls_back_to_source(df: pd.DataFrame) -> None:
    """Unrecognized keyword returns source column copy, not None."""
    mapping = _split_mapping(
        source_variable="VAL",
        derivation_rule="MAGIC_FUNC(VAL, 1, 2)",
    )
    result = handle_split(df, mapping)
    assert list(result) == ["alpha-100", "beta-200", "gamma-300"]


def test_no_rule_copies_source(df: pd.DataFrame) -> None:
    """No derivation_rule just copies source column."""
    mapping = _split_mapping(source_variable="VAL")
    result = handle_split(df, mapping)
    assert list(result) == ["alpha-100", "beta-200", "gamma-300"]
