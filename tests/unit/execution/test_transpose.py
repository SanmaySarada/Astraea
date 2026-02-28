"""Unit tests for the TRANSPOSE pattern handler and TransposeSpec model."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from astraea.execution.transpose import TransposeSpec, execute_transpose, handle_transpose
from astraea.models.mapping import MappingPattern, VariableMapping


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def vs_spec() -> TransposeSpec:
    """Vital Signs transpose spec with 3 test columns."""
    return TransposeSpec(
        id_vars=["USUBJID", "VISITNUM", "VSDTC"],
        value_vars=["SYSBP", "DIABP", "HR"],
        testcd_mapping={"SYSBP": "SYSBP", "DIABP": "DIABP", "HR": "HR"},
        test_mapping={
            "SYSBP": "Systolic Blood Pressure",
            "DIABP": "Diastolic Blood Pressure",
            "HR": "Heart Rate",
        },
        unit_mapping={"SYSBP": "mmHg", "DIABP": "mmHg", "HR": "beats/min"},
        result_var="VSORRES",
        testcd_var="VSTESTCD",
        test_var="VSTEST",
        unit_var="VSORRESU",
    )


@pytest.fixture()
def wide_vs_df() -> pd.DataFrame:
    """Wide vital signs DataFrame: 2 subjects x 3 visits = 6 rows."""
    return pd.DataFrame(
        {
            "USUBJID": ["S01", "S01", "S01", "S02", "S02", "S02"],
            "VISITNUM": [1, 2, 3, 1, 2, 3],
            "VSDTC": [
                "2022-01-01",
                "2022-02-01",
                "2022-03-01",
                "2022-01-01",
                "2022-02-01",
                "2022-03-01",
            ],
            "SYSBP": [120.0, 125.0, 118.0, 130.0, 128.0, 132.0],
            "DIABP": [80.0, 82.0, 78.0, 85.0, 84.0, 86.0],
            "HR": [72.0, 74.0, 70.0, 68.0, 66.0, 64.0],
        }
    )


# ---------------------------------------------------------------------------
# Tests: basic wide-to-tall
# ---------------------------------------------------------------------------


class TestExecuteTranspose:
    """Tests for execute_transpose()."""

    def test_basic_wide_to_tall(self, wide_vs_df: pd.DataFrame, vs_spec: TransposeSpec) -> None:
        """3 test columns x 6 rows = 18 rows in tall format (no nulls)."""
        result = execute_transpose(wide_vs_df, vs_spec)

        assert len(result) == 18  # 6 rows * 3 tests
        assert "VSTESTCD" in result.columns
        assert "VSTEST" in result.columns
        assert "VSORRES" in result.columns
        assert "VSORRESU" in result.columns
        assert "USUBJID" in result.columns
        assert "VISITNUM" in result.columns

    def test_testcd_mapped_correctly(
        self, wide_vs_df: pd.DataFrame, vs_spec: TransposeSpec
    ) -> None:
        """TESTCD values match the testcd_mapping."""
        result = execute_transpose(wide_vs_df, vs_spec)

        testcds = set(result["VSTESTCD"].unique())
        assert testcds == {"SYSBP", "DIABP", "HR"}

    def test_test_mapped_correctly(
        self, wide_vs_df: pd.DataFrame, vs_spec: TransposeSpec
    ) -> None:
        """TEST labels match the test_mapping."""
        result = execute_transpose(wide_vs_df, vs_spec)

        tests = set(result["VSTEST"].unique())
        assert tests == {"Systolic Blood Pressure", "Diastolic Blood Pressure", "Heart Rate"}

    def test_unit_mapped_correctly(
        self, wide_vs_df: pd.DataFrame, vs_spec: TransposeSpec
    ) -> None:
        """Unit values match the unit_mapping."""
        result = execute_transpose(wide_vs_df, vs_spec)

        # SYSBP rows should have mmHg
        sysbp_rows = result[result["VSTESTCD"] == "SYSBP"]
        assert all(sysbp_rows["VSORRESU"] == "mmHg")

        # HR rows should have beats/min
        hr_rows = result[result["VSTESTCD"] == "HR"]
        assert all(hr_rows["VSORRESU"] == "beats/min")

    def test_null_results_dropped(self, vs_spec: TransposeSpec) -> None:
        """Rows with NaN result values are dropped."""
        df = pd.DataFrame(
            {
                "USUBJID": ["S01", "S01"],
                "VISITNUM": [1, 2],
                "VSDTC": ["2022-01-01", "2022-02-01"],
                "SYSBP": [120.0, np.nan],
                "DIABP": [80.0, 82.0],
                "HR": [np.nan, np.nan],
            }
        )
        result = execute_transpose(df, vs_spec)

        # S01/V1: SYSBP=120, DIABP=80, HR=NaN -> 2 rows
        # S01/V2: SYSBP=NaN, DIABP=82, HR=NaN -> 1 row
        assert len(result) == 3

    def test_mixed_null_units(self) -> None:
        """Some tests have units, some do not."""
        spec = TransposeSpec(
            id_vars=["USUBJID"],
            value_vars=["TEMP", "COMMENT"],
            testcd_mapping={"TEMP": "TEMP", "COMMENT": "VSCOMM"},
            test_mapping={"TEMP": "Temperature", "COMMENT": "VS Comment"},
            unit_mapping={"TEMP": "C"},  # No unit for COMMENT
            result_var="VSORRES",
            testcd_var="VSTESTCD",
            test_var="VSTEST",
            unit_var="VSORRESU",
        )
        df = pd.DataFrame(
            {
                "USUBJID": ["S01"],
                "TEMP": [37.0],
                "COMMENT": ["Normal"],
            }
        )
        result = execute_transpose(df, spec)

        assert len(result) == 2
        temp_row = result[result["VSTESTCD"] == "TEMP"].iloc[0]
        comment_row = result[result["VSTESTCD"] == "VSCOMM"].iloc[0]

        assert temp_row["VSORRESU"] == "C"
        assert pd.isna(comment_row["VSORRESU"])

    def test_empty_dataframe(self, vs_spec: TransposeSpec) -> None:
        """Empty DataFrame returns empty DataFrame with correct columns."""
        df = pd.DataFrame()
        result = execute_transpose(df, vs_spec)

        assert result.empty
        assert "VSTESTCD" in result.columns
        assert "VSORRES" in result.columns

    def test_single_column_transpose(self) -> None:
        """Transpose with a single value column."""
        spec = TransposeSpec(
            id_vars=["USUBJID"],
            value_vars=["WEIGHT"],
            testcd_mapping={"WEIGHT": "WEIGHT"},
            test_mapping={"WEIGHT": "Weight"},
            unit_mapping={"WEIGHT": "kg"},
            result_var="VSORRES",
            testcd_var="VSTESTCD",
            test_var="VSTEST",
            unit_var="VSORRESU",
        )
        df = pd.DataFrame(
            {
                "USUBJID": ["S01", "S02"],
                "WEIGHT": [70.5, 85.0],
            }
        )
        result = execute_transpose(df, spec)

        assert len(result) == 2
        assert set(result["VSTESTCD"]) == {"WEIGHT"}
        assert list(result["VSORRES"]) == [70.5, 85.0]

    def test_result_values_preserved(
        self, wide_vs_df: pd.DataFrame, vs_spec: TransposeSpec
    ) -> None:
        """Original result values are preserved in the tall format."""
        result = execute_transpose(wide_vs_df, vs_spec)

        # Check that S01/V1/SYSBP = 120.0
        s01_v1_sysbp = result[
            (result["USUBJID"] == "S01")
            & (result["VISITNUM"] == 1)
            & (result["VSTESTCD"] == "SYSBP")
        ]
        assert len(s01_v1_sysbp) == 1
        assert s01_v1_sysbp.iloc[0]["VSORRES"] == 120.0

    def test_id_vars_not_in_df_ignored(self) -> None:
        """id_vars not present in DataFrame are silently skipped."""
        spec = TransposeSpec(
            id_vars=["USUBJID", "MISSING_COL"],
            value_vars=["TEMP"],
            testcd_mapping={"TEMP": "TEMP"},
            test_mapping={"TEMP": "Temperature"},
            unit_mapping={"TEMP": "C"},
            result_var="VSORRES",
            testcd_var="VSTESTCD",
            test_var="VSTEST",
            unit_var="VSORRESU",
        )
        df = pd.DataFrame({"USUBJID": ["S01"], "TEMP": [37.0]})
        result = execute_transpose(df, spec)

        assert len(result) == 1
        assert "MISSING_COL" not in result.columns

    def test_no_value_vars_in_df(self) -> None:
        """If no value_vars are found in DataFrame, return empty."""
        spec = TransposeSpec(
            id_vars=["USUBJID"],
            value_vars=["MISSING1", "MISSING2"],
            testcd_mapping={"MISSING1": "M1", "MISSING2": "M2"},
            test_mapping={"MISSING1": "Missing 1", "MISSING2": "Missing 2"},
            unit_mapping={},
            result_var="VSORRES",
            testcd_var="VSTESTCD",
            test_var="VSTEST",
            unit_var="VSORRESU",
        )
        df = pd.DataFrame({"USUBJID": ["S01"]})
        result = execute_transpose(df, spec)

        assert result.empty

    def test_empty_unit_mapping(self) -> None:
        """Empty unit_mapping produces None unit values."""
        spec = TransposeSpec(
            id_vars=["USUBJID"],
            value_vars=["SCORE"],
            testcd_mapping={"SCORE": "SCORE"},
            test_mapping={"SCORE": "Pain Score"},
            unit_mapping={},
            result_var="VSORRES",
            testcd_var="VSTESTCD",
            test_var="VSTEST",
            unit_var="VSORRESU",
        )
        df = pd.DataFrame({"USUBJID": ["S01"], "SCORE": [5]})
        result = execute_transpose(df, spec)

        assert len(result) == 1
        assert result.iloc[0]["VSORRESU"] is None


# ---------------------------------------------------------------------------
# Tests: TransposeSpec validation
# ---------------------------------------------------------------------------


class TestTransposeSpec:
    """Pydantic validation tests for TransposeSpec."""

    def test_valid_spec(self, vs_spec: TransposeSpec) -> None:
        """Valid spec passes validation."""
        assert vs_spec.result_var == "VSORRES"
        assert len(vs_spec.value_vars) == 3

    def test_required_fields(self) -> None:
        """Missing required fields raise ValidationError."""
        with pytest.raises(Exception):  # noqa: B017
            TransposeSpec()  # type: ignore[call-arg]

    def test_unit_mapping_defaults_empty(self) -> None:
        """unit_mapping defaults to empty dict."""
        spec = TransposeSpec(
            id_vars=["USUBJID"],
            value_vars=["X"],
            testcd_mapping={"X": "X"},
            test_mapping={"X": "Test X"},
            result_var="ORRES",
            testcd_var="TESTCD",
            test_var="TEST",
            unit_var="ORRESU",
        )
        assert spec.unit_mapping == {}


# ---------------------------------------------------------------------------
# Tests: handle_transpose stub
# ---------------------------------------------------------------------------


class TestHandleTranspose:
    """Tests for the handle_transpose stub in PATTERN_HANDLERS."""

    def test_returns_empty_series(self) -> None:
        """handle_transpose returns an empty Series."""
        mapping = VariableMapping(
            sdtm_variable="VSTESTCD",
            sdtm_label="Vital Signs Test Short Name",
            sdtm_data_type="Char",
            core="Req",
            mapping_pattern=MappingPattern.TRANSPOSE,
            mapping_logic="Transpose",
            confidence=0.9,
            confidence_level="high",
            confidence_rationale="Standard transpose",
        )
        df = pd.DataFrame({"X": [1, 2, 3]})
        result = handle_transpose(df, mapping)

        assert isinstance(result, pd.Series)
        assert len(result) == 0

    def test_registered_in_pattern_handlers(self) -> None:
        """handle_transpose is registered in PATTERN_HANDLERS."""
        from astraea.execution.pattern_handlers import PATTERN_HANDLERS

        assert MappingPattern.TRANSPOSE in PATTERN_HANDLERS
        assert PATTERN_HANDLERS[MappingPattern.TRANSPOSE] is handle_transpose
