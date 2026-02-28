"""Tests for pattern handler functions in the execution pipeline."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.pattern_handlers import (
    PATTERN_HANDLERS,
    handle_assign,
    handle_derivation,
    handle_direct,
    handle_lookup_recode,
    handle_reformat,
    handle_rename,
)
from astraea.models.mapping import (
    ConfidenceLevel,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation


def _make_mapping(
    *,
    sdtm_variable: str = "TEST",
    pattern: MappingPattern = MappingPattern.DIRECT,
    source_variable: str | None = None,
    assigned_value: str | None = None,
    derivation_rule: str | None = None,
    codelist_code: str | None = None,
) -> VariableMapping:
    """Helper to create a VariableMapping with minimal boilerplate."""
    return VariableMapping(
        sdtm_variable=sdtm_variable,
        sdtm_label="Test Variable",
        sdtm_data_type="Char",
        core=CoreDesignation.REQ,
        source_variable=source_variable,
        mapping_pattern=pattern,
        mapping_logic="test mapping",
        assigned_value=assigned_value,
        derivation_rule=derivation_rule,
        codelist_code=codelist_code,
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="test",
    )


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    """Fixture DataFrame with typical raw clinical data columns."""
    return pd.DataFrame(
        {
            "Subject": ["001", "002", "003"],
            "AETERM": ["Headache", "Nausea", "Fatigue"],
            "AESTDT": [22738.0, 22739.0, 22740.0],
            "SEX": ["Male", "Female", "Male"],
        }
    )


class TestHandleAssign:
    def test_assign_fills_all_rows(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(
            sdtm_variable="DOMAIN",
            pattern=MappingPattern.ASSIGN,
            assigned_value="AE",
        )
        result = handle_assign(sample_df, mapping)
        assert len(result) == 3
        assert all(result == "AE")

    def test_assign_no_value_raises(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(
            sdtm_variable="DOMAIN",
            pattern=MappingPattern.ASSIGN,
            assigned_value=None,
        )
        with pytest.raises(ValueError, match="no assigned_value"):
            handle_assign(sample_df, mapping)


class TestHandleDirect:
    def test_direct_copies_column(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(
            sdtm_variable="AETERM",
            pattern=MappingPattern.DIRECT,
            source_variable="AETERM",
        )
        result = handle_direct(sample_df, mapping)
        pd.testing.assert_series_equal(result, sample_df["AETERM"], check_names=False)

    def test_direct_missing_col_raises(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(
            sdtm_variable="AETERM",
            pattern=MappingPattern.DIRECT,
            source_variable="NONEXISTENT",
        )
        with pytest.raises(KeyError, match="NONEXISTENT"):
            handle_direct(sample_df, mapping)

    def test_direct_no_source_variable_raises(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(
            sdtm_variable="AETERM",
            pattern=MappingPattern.DIRECT,
            source_variable=None,
        )
        with pytest.raises(ValueError, match="no source_variable"):
            handle_direct(sample_df, mapping)


class TestHandleRename:
    def test_rename_same_as_direct(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(
            sdtm_variable="SUBJID",
            pattern=MappingPattern.RENAME,
            source_variable="Subject",
        )
        result = handle_rename(sample_df, mapping)
        pd.testing.assert_series_equal(result, sample_df["Subject"], check_names=False)


class TestHandleReformat:
    def test_reformat_with_transform(self, sample_df: pd.DataFrame) -> None:
        """SAS datetime numeric -> ISO 8601 string via sas_datetime_to_iso."""
        mapping = _make_mapping(
            sdtm_variable="AESTDTC",
            pattern=MappingPattern.REFORMAT,
            source_variable="AESTDT",
            derivation_rule="sas_datetime_to_iso",
        )
        result = handle_reformat(sample_df, mapping)
        # SAS datetime 22738.0 seconds since 1960-01-01T00:00:00
        # = 1960-01-01 + 22738 seconds = 1960-01-01T06:18:58
        assert result.iloc[0] is not None
        assert isinstance(result.iloc[0], str)
        # Should be an ISO date/datetime string
        assert result.iloc[0].startswith("1960")

    def test_reformat_no_transform_passes_through(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(
            sdtm_variable="AESTDTC",
            pattern=MappingPattern.REFORMAT,
            source_variable="AESTDT",
            derivation_rule="nonexistent_transform",
        )
        result = handle_reformat(sample_df, mapping)
        # Should pass through original values
        pd.testing.assert_series_equal(result, sample_df["AESTDT"], check_names=False)


class TestHandleLookupRecode:
    def test_lookup_recode_with_codelist(self, sample_df: pd.DataFrame) -> None:
        """Recode Male->M, Female->F using a mock CTReference."""
        from unittest.mock import MagicMock

        mock_ct = MagicMock(spec=["lookup_codelist"])
        mock_codelist = MagicMock()
        mock_codelist.terms = {
            "M": MagicMock(nci_preferred_term="Male"),
            "F": MagicMock(nci_preferred_term="Female"),
        }
        mock_ct.lookup_codelist.return_value = mock_codelist

        mapping = _make_mapping(
            sdtm_variable="SEX",
            pattern=MappingPattern.LOOKUP_RECODE,
            source_variable="SEX",
            codelist_code="C66731",
        )
        result = handle_lookup_recode(sample_df, mapping, ct_reference=mock_ct)
        assert list(result) == ["M", "F", "M"]

    def test_lookup_recode_no_codelist_passes_through(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(
            sdtm_variable="SEX",
            pattern=MappingPattern.LOOKUP_RECODE,
            source_variable="SEX",
        )
        result = handle_lookup_recode(sample_df, mapping)
        pd.testing.assert_series_equal(result, sample_df["SEX"], check_names=False)


class TestHandleDerivation:
    def test_derivation_unknown_rule_returns_none(self, sample_df: pd.DataFrame) -> None:
        mapping = _make_mapping(
            sdtm_variable="CUSTOM",
            pattern=MappingPattern.DERIVATION,
            derivation_rule="unknown_rule",
        )
        result = handle_derivation(sample_df, mapping)
        assert len(result) == 3
        assert all(pd.isna(v) for v in result)


class TestPatternRegistry:
    def test_registry_complete(self) -> None:
        """Every MappingPattern enum value must have an entry in PATTERN_HANDLERS."""
        for pattern in MappingPattern:
            assert pattern in PATTERN_HANDLERS, (
                f"MappingPattern.{pattern.name} missing from PATTERN_HANDLERS"
            )

    def test_registry_has_correct_count(self) -> None:
        assert len(PATTERN_HANDLERS) == len(MappingPattern)
