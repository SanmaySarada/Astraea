"""Tests for XPT v5 writer with pre-write validation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyreadstat
import pytest

from astraea.io.xpt_writer import XPTValidationError, validate_for_xpt_v5, write_xpt_v5

# --- Fixtures ---


@pytest.fixture
def simple_df() -> pd.DataFrame:
    """A small DataFrame that passes all XPT v5 constraints."""
    return pd.DataFrame(
        {
            "STUDYID": ["STUDY01", "STUDY01", "STUDY01"],
            "USUBJID": ["S01-001", "S01-002", "S01-003"],
            "SEX": ["M", "F", "M"],
            "AGE": [45.0, 32.0, 58.0],
        }
    )


@pytest.fixture
def simple_labels() -> dict[str, str]:
    """Column labels for simple_df."""
    return {
        "STUDYID": "Study Identifier",
        "USUBJID": "Unique Subject Identifier",
        "SEX": "Sex",
        "AGE": "Age",
    }


# --- validate_for_xpt_v5 tests ---


class TestValidateForXptV5:
    def test_valid_data_returns_empty(self, simple_df: pd.DataFrame, simple_labels: dict) -> None:
        errors = validate_for_xpt_v5(simple_df, simple_labels, "DM")
        assert errors == []

    def test_catches_long_variable_name(self) -> None:
        df = pd.DataFrame({"LONGVARNAME": [1, 2, 3]})
        errors = validate_for_xpt_v5(df, {"LONGVARNAME": "Label"}, "DM")
        assert len(errors) >= 1
        assert "LONGVARNAME" in errors[0]
        assert "exceeds 8 characters" in errors[0]

    def test_catches_long_label(self) -> None:
        df = pd.DataFrame({"VAR1": [1, 2, 3]})
        long_label = "A" * 41
        errors = validate_for_xpt_v5(df, {"VAR1": long_label}, "DM")
        assert len(errors) >= 1
        assert "exceeds 40 characters" in errors[0]

    def test_catches_non_ascii_characters(self) -> None:
        df = pd.DataFrame({"VAR1": ["hello", "caf\u00e9", "world"]})
        errors = validate_for_xpt_v5(df, {"VAR1": "Label"}, "DM")
        assert len(errors) >= 1
        assert "non-ASCII" in errors[0]

    def test_catches_table_name_too_long(self) -> None:
        df = pd.DataFrame({"VAR1": [1]})
        errors = validate_for_xpt_v5(df, {"VAR1": "Label"}, "LONGNAME9")
        assert len(errors) >= 1
        assert "Table name" in errors[0]
        assert "exceeds 8 characters" in errors[0]

    def test_catches_table_name_starts_with_number(self) -> None:
        df = pd.DataFrame({"VAR1": [1]})
        errors = validate_for_xpt_v5(df, {"VAR1": "Label"}, "1DM")
        assert len(errors) >= 1
        assert "Table name" in errors[0]

    def test_catches_column_name_starts_with_number(self) -> None:
        df = pd.DataFrame({"1VAR": [1, 2]})
        errors = validate_for_xpt_v5(df, {"1VAR": "Label"}, "DM")
        assert len(errors) >= 1
        assert "1VAR" in errors[0]

    def test_catches_value_exceeding_200_bytes(self) -> None:
        long_val = "A" * 201
        df = pd.DataFrame({"VAR1": [long_val]})
        errors = validate_for_xpt_v5(df, {"VAR1": "Label"}, "DM")
        assert len(errors) >= 1
        assert "200 bytes" in errors[0]

    def test_multiple_errors_all_reported(self) -> None:
        df = pd.DataFrame({"TOOLONGNAME": ["caf\u00e9"]})
        long_label = "B" * 50
        errors = validate_for_xpt_v5(df, {"TOOLONGNAME": long_label}, "WAYLONGTABLE")
        # Should catch: table name too long, column name too long, label too long, non-ASCII
        assert len(errors) >= 3

    def test_null_character_values_skipped(self) -> None:
        """Columns with all NaN should not cause errors."""
        df = pd.DataFrame({"VAR1": pd.array([None, None, None], dtype=object)})
        errors = validate_for_xpt_v5(df, {"VAR1": "Label"}, "DM")
        assert errors == []


# --- write_xpt_v5 tests ---


class TestWriteXptV5:
    def test_valid_write_and_readback(
        self, simple_df: pd.DataFrame, simple_labels: dict, tmp_path: object
    ) -> None:
        out_path = tmp_path / "dm.xpt"  # type: ignore[operator]
        write_xpt_v5(simple_df, out_path, "DM", simple_labels)
        assert out_path.exists()  # type: ignore[union-attr]

        # Read back and verify
        df_back, meta = pyreadstat.read_xport(str(out_path))
        assert len(df_back) == len(simple_df)
        assert set(df_back.columns) == {c.upper() for c in simple_df.columns}

    def test_raises_on_invalid_data(self, tmp_path: object) -> None:
        df = pd.DataFrame({"TOOLONGNAME": [1, 2, 3]})
        out_path = tmp_path / "bad.xpt"  # type: ignore[operator]
        with pytest.raises(XPTValidationError) as exc_info:
            write_xpt_v5(df, out_path, "DM", {"TOOLONGNAME": "Label"})
        assert len(exc_info.value.errors) >= 1
        assert "exceeds 8 characters" in exc_info.value.errors[0]

    def test_round_trip_data_integrity(
        self, simple_df: pd.DataFrame, simple_labels: dict, tmp_path: object
    ) -> None:
        """Write then read back and verify data values match."""
        out_path = tmp_path / "dm.xpt"  # type: ignore[operator]
        write_xpt_v5(simple_df, out_path, "DM", simple_labels)

        df_back, meta = pyreadstat.read_xport(str(out_path))

        # Check character columns
        for col in ["STUDYID", "USUBJID", "SEX"]:
            assert list(df_back[col]) == list(simple_df[col])

        # Check numeric columns (float comparison)
        np.testing.assert_array_almost_equal(df_back["AGE"].values, simple_df["AGE"].values)

    def test_columns_uppercased(self, tmp_path: object) -> None:
        """Verify column names are uppercased in the output."""
        df = pd.DataFrame({"var1": [1, 2], "var2": ["a", "b"]})
        labels = {"var1": "Variable One", "var2": "Variable Two"}
        out_path = tmp_path / "test.xpt"  # type: ignore[operator]
        write_xpt_v5(df, out_path, "TEST", labels)

        df_back, _ = pyreadstat.read_xport(str(out_path))
        assert "VAR1" in df_back.columns
        assert "VAR2" in df_back.columns

    def test_file_not_created_on_validation_failure(self, tmp_path: object) -> None:
        """If validation fails, no file should be written."""
        df = pd.DataFrame({"TOOLONGNAME": [1]})
        out_path = tmp_path / "nope.xpt"  # type: ignore[operator]
        with pytest.raises(XPTValidationError):
            write_xpt_v5(df, out_path, "DM", {"TOOLONGNAME": "Label"})
        assert not out_path.exists()  # type: ignore[union-attr]

    def test_labels_preserved_in_readback(
        self, simple_df: pd.DataFrame, simple_labels: dict, tmp_path: object
    ) -> None:
        """Verify column labels survive the round-trip."""
        out_path = tmp_path / "dm.xpt"  # type: ignore[operator]
        write_xpt_v5(simple_df, out_path, "DM", simple_labels)

        _, meta = pyreadstat.read_xport(str(out_path))
        for col, expected_label in simple_labels.items():
            actual_label = meta.column_names_to_labels.get(col.upper(), "")
            assert actual_label == expected_label


# --- Table label validation tests ---


class TestTableLabelValidation:
    def test_table_label_too_long(self) -> None:
        """Table label exceeding 40 chars should be an error."""
        df = pd.DataFrame({"VAR1": [1]})
        long_label = "A" * 41
        errors = validate_for_xpt_v5(df, {"VAR1": "Label"}, "DM", table_label=long_label)
        assert any("Table label exceeds 40 characters" in e for e in errors)

    def test_table_label_at_limit(self) -> None:
        """Table label of exactly 40 chars should not produce a table label error."""
        df = pd.DataFrame({"VAR1": [1]})
        label_40 = "A" * 40
        errors = validate_for_xpt_v5(df, {"VAR1": "Label"}, "DM", table_label=label_40)
        assert not any("Table label" in e for e in errors)

    def test_table_label_none_backward_compat(self) -> None:
        """table_label=None (default) should not produce table label errors."""
        df = pd.DataFrame({"VAR1": [1]})
        errors = validate_for_xpt_v5(df, {"VAR1": "Label"}, "DM")
        assert not any("Table label" in e for e in errors)


class TestUnlabeledColumnValidation:
    def test_unlabeled_column_detected(self) -> None:
        """A column with no label should produce an error."""
        df = pd.DataFrame({"VAR1": [1], "VAR2": [2]})
        errors = validate_for_xpt_v5(df, {"VAR1": "Label One"}, "DM")
        assert any("VAR2" in e and "no label" in e for e in errors)

    def test_all_columns_labeled_no_error(self) -> None:
        """When all columns have labels, no unlabeled-column error."""
        df = pd.DataFrame({"VAR1": [1], "VAR2": [2]})
        labels = {"VAR1": "Label One", "VAR2": "Label Two"}
        errors = validate_for_xpt_v5(df, labels, "DM")
        assert not any("no label" in e for e in errors)

    def test_case_insensitive_label_match(self) -> None:
        """Label keys with different case should still match columns."""
        df = pd.DataFrame({"var1": [1]})
        labels = {"VAR1": "Label One"}
        errors = validate_for_xpt_v5(df, labels, "DM")
        assert not any("no label" in e for e in errors)
