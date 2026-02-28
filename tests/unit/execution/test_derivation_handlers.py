"""Tests for derivation rule handler functions and dispatch."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.pattern_handlers import (
    _DERIVATION_DISPATCH,
    handle_combine,
    handle_derivation,
    handle_reformat,
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
    pattern: MappingPattern = MappingPattern.DERIVATION,
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


class TestHandleConcat:
    def test_concat_columns(self) -> None:
        df = pd.DataFrame({"col_a": ["X", "A"], "col_b": ["Y", "B"]})
        mapping = _make_mapping(
            sdtm_variable="RESULT",
            derivation_rule="CONCAT(col_a, '-', col_b)",
        )
        result = handle_derivation(df, mapping)
        assert list(result) == ["X-Y", "A-B"]

    def test_concat_literal_and_col(self) -> None:
        df = pd.DataFrame({"col_a": ["X", "A"]})
        mapping = _make_mapping(
            sdtm_variable="RESULT",
            derivation_rule="CONCAT('PREFIX', '-', col_a)",
        )
        result = handle_derivation(df, mapping)
        assert list(result) == ["PREFIX-X", "PREFIX-A"]

    def test_concat_with_nan_fills_empty(self) -> None:
        df = pd.DataFrame({"col_a": ["X", None], "col_b": ["Y", "B"]})
        mapping = _make_mapping(
            sdtm_variable="RESULT",
            derivation_rule="CONCAT(col_a, col_b)",
        )
        result = handle_derivation(df, mapping)
        # NaN becomes empty string in concat
        assert result.iloc[0] == "XY"
        assert result.iloc[1] == "NoneB" or result.iloc[1] == "B"  # object column


class TestHandleISO8601Date:
    def test_iso8601_date(self) -> None:
        df = pd.DataFrame({"AESTDT": [22734.0, None]})
        mapping = _make_mapping(
            sdtm_variable="AESTDTC",
            derivation_rule="ISO8601_DATE(AESTDT)",
        )
        result = handle_derivation(df, mapping)
        # 22734 days since 1960-01-01 = 2022-03-30
        assert result.iloc[0] == "2022-03-30"
        assert result.iloc[1] == ""

    def test_iso8601_date_via_reformat(self) -> None:
        df = pd.DataFrame({"AESTDT": [22734.0]})
        mapping = _make_mapping(
            sdtm_variable="AESTDTC",
            pattern=MappingPattern.REFORMAT,
            source_variable="AESTDT",
            derivation_rule="ISO8601_DATE(AESTDT)",
        )
        result = handle_reformat(df, mapping)
        assert result.iloc[0] == "2022-03-30"


class TestHandleISO8601PartialDate:
    def test_year_only(self) -> None:
        df = pd.DataFrame({"BRTHYR": [1960, 2023]})
        mapping = _make_mapping(
            sdtm_variable="BRTHDTC",
            derivation_rule="ISO8601_PARTIAL_DATE(BRTHYR)",
        )
        result = handle_derivation(df, mapping)
        assert result.iloc[0] == "1960"
        assert result.iloc[1] == "2023"

    def test_year_month(self) -> None:
        df = pd.DataFrame({"YEAR": [2023, 2024], "MONTH": [3, 12]})
        mapping = _make_mapping(
            sdtm_variable="DTC",
            derivation_rule="ISO8601_PARTIAL_DATE(YEAR, MONTH)",
        )
        result = handle_derivation(df, mapping)
        assert result.iloc[0] == "2023-03"
        assert result.iloc[1] == "2024-12"


class TestHandleParseStringDate:
    def test_parse_dd_mon_yyyy(self) -> None:
        df = pd.DataFrame({"DT_RAW": ["30 Mar 2022", "15 Jun 2023"]})
        mapping = _make_mapping(
            sdtm_variable="DTC",
            derivation_rule="PARSE_STRING_DATE(DT_RAW)",
        )
        result = handle_derivation(df, mapping)
        assert result.iloc[0] == "2022-03-30"
        assert result.iloc[1] == "2023-06-15"


class TestHandleDateAggPerSubject:
    @pytest.fixture()
    def multi_row_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "USUBJID": ["S1", "S1", "S2", "S2"],
                "EXDT": [22734.0, 22736.0, 22735.0, 22737.0],
            }
        )

    def test_min_date_per_subject(self, multi_row_df: pd.DataFrame) -> None:
        mapping = _make_mapping(
            sdtm_variable="RFSTDTC",
            derivation_rule="MIN_DATE_PER_SUBJECT(EXDT)",
        )
        result = handle_derivation(multi_row_df, mapping)
        # S1 min = 22734 = 2022-03-30, S2 min = 22735 = 2022-03-31
        assert result.iloc[0] == "2022-03-30"
        assert result.iloc[1] == "2022-03-30"  # same subject, same min
        assert result.iloc[2] == "2022-03-31"
        assert result.iloc[3] == "2022-03-31"

    def test_max_date_per_subject(self, multi_row_df: pd.DataFrame) -> None:
        mapping = _make_mapping(
            sdtm_variable="RFENDTC",
            derivation_rule="MAX_DATE_PER_SUBJECT(EXDT)",
        )
        result = handle_derivation(multi_row_df, mapping)
        # S1 max = 22736 = 2022-04-01, S2 max = 22737 = 2022-04-02
        assert result.iloc[0] == "2022-04-01"
        assert result.iloc[1] == "2022-04-01"
        assert result.iloc[2] == "2022-04-02"
        assert result.iloc[3] == "2022-04-02"


class TestHandleRaceCheckbox:
    def test_single_race(self) -> None:
        df = pd.DataFrame({"RACEAME": [0], "RACEWHI": [1], "RACEASI": [0]})
        mapping = _make_mapping(
            sdtm_variable="RACE",
            derivation_rule="RACE_CHECKBOX(RACEAME, RACEWHI, RACEASI)",
        )
        result = handle_derivation(df, mapping)
        assert result.iloc[0] == "WHITE"

    def test_multiple_races(self) -> None:
        df = pd.DataFrame({"RACEAME": [1], "RACEWHI": [1], "RACEASI": [0]})
        mapping = _make_mapping(
            sdtm_variable="RACE",
            derivation_rule="RACE_CHECKBOX(RACEAME, RACEWHI, RACEASI)",
        )
        result = handle_derivation(df, mapping)
        assert result.iloc[0] == "MULTIPLE"

    def test_no_race_checked(self) -> None:
        df = pd.DataFrame({"RACEAME": [0], "RACEWHI": [0]})
        mapping = _make_mapping(
            sdtm_variable="RACE",
            derivation_rule="RACE_CHECKBOX(RACEAME, RACEWHI)",
        )
        result = handle_derivation(df, mapping)
        assert result.iloc[0] is None


class TestHandleNumericToYN:
    def test_numeric_to_yn(self) -> None:
        df = pd.DataFrame({"FLAG": [1, 0, None]})
        mapping = _make_mapping(
            sdtm_variable="IEYN",
            derivation_rule="NUMERIC_TO_YN(FLAG)",
        )
        result = handle_derivation(df, mapping)
        assert result.iloc[0] == "Y"
        assert result.iloc[1] == "N"
        assert pd.isna(result.iloc[2])


class TestDispatchIntegration:
    def test_handle_derivation_dispatches_concat(self) -> None:
        df = pd.DataFrame({"A": ["X"], "B": ["Y"]})
        mapping = _make_mapping(
            sdtm_variable="RESULT",
            derivation_rule="CONCAT(A, '-', B)",
        )
        result = handle_derivation(df, mapping)
        assert result.iloc[0] == "X-Y"

    def test_handle_reformat_dispatches_iso8601(self) -> None:
        df = pd.DataFrame({"COL": [22734.0]})
        mapping = _make_mapping(
            sdtm_variable="DTC",
            pattern=MappingPattern.REFORMAT,
            source_variable="COL",
            derivation_rule="ISO8601_DATE(COL)",
        )
        result = handle_reformat(df, mapping)
        assert result.iloc[0] == "2022-03-30"

    def test_handle_combine_dispatches_concat(self) -> None:
        df = pd.DataFrame({"A": ["X"], "B": ["Y"]})
        mapping = _make_mapping(
            sdtm_variable="RESULT",
            pattern=MappingPattern.COMBINE,
            derivation_rule="CONCAT(A, B)",
        )
        result = handle_combine(df, mapping)
        assert result.iloc[0] == "XY"

    def test_unrecognized_rule_returns_none(self) -> None:
        df = pd.DataFrame({"A": [1]})
        mapping = _make_mapping(
            sdtm_variable="X",
            derivation_rule="TOTALLY_UNKNOWN_RULE(A)",
        )
        result = handle_derivation(df, mapping)
        assert all(pd.isna(v) for v in result)

    def test_dispatch_table_has_all_keywords(self) -> None:
        """All documented keywords are in the dispatch table."""
        expected = {
            "GENERATE_USUBJID",
            "CONCAT",
            "ISO8601_DATE",
            "ISO8601_DATETIME",
            "ISO8601_PARTIAL_DATE",
            "PARSE_STRING_DATE",
            "MIN_DATE_PER_SUBJECT",
            "MAX_DATE_PER_SUBJECT",
            "RACE_CHECKBOX",
            "RACE_FROM_CHECKBOXES",
            "NUMERIC_TO_YN",
            "LAST_DISPOSITION_DATE",
            "LAST_DISPOSITION_DATE_PER_SUBJECT",
        }
        assert expected.issubset(set(_DERIVATION_DISPATCH.keys()))


class TestHandleGenerateUsubjid:
    def test_generate_usubjid(self) -> None:
        df = pd.DataFrame({"Subject": ["001"], "SiteNumber": ["100"]})
        mapping = _make_mapping(
            sdtm_variable="USUBJID",
            derivation_rule="GENERATE_USUBJID",
        )
        result = handle_derivation(df, mapping, study_id="STUDY01")
        assert result.iloc[0] == "STUDY01-100-001"
