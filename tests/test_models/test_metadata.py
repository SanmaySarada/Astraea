"""Tests for SAS metadata models."""

import pytest
from pydantic import ValidationError

from astraea.models import DatasetMetadata, VariableMetadata


class TestVariableMetadata:
    """Tests for VariableMetadata model."""

    def test_create_valid_numeric_variable(self) -> None:
        var = VariableMetadata(
            name="AGE",
            label="Age in Years",
            sas_format="BEST12.",
            dtype="numeric",
            storage_width=8,
        )
        assert var.name == "AGE"
        assert var.label == "Age in Years"
        assert var.sas_format == "BEST12."
        assert var.dtype == "numeric"
        assert var.storage_width == 8

    def test_create_valid_character_variable(self) -> None:
        var = VariableMetadata(
            name="SUBJID",
            label="Subject Identifier",
            dtype="character",
        )
        assert var.name == "SUBJID"
        assert var.dtype == "character"
        assert var.sas_format is None
        assert var.storage_width is None

    def test_label_defaults_to_empty_string(self) -> None:
        var = VariableMetadata(name="X", dtype="numeric")
        assert var.label == ""

    def test_invalid_dtype_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VariableMetadata(name="X", dtype="boolean")

    def test_negative_storage_width_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VariableMetadata(name="X", dtype="numeric", storage_width=0)

    def test_model_dump_produces_clean_dict(self) -> None:
        var = VariableMetadata(
            name="WEIGHT",
            label="Weight (kg)",
            dtype="numeric",
            sas_format="8.1",
            storage_width=8,
        )
        d = var.model_dump()
        assert isinstance(d, dict)
        assert d["name"] == "WEIGHT"
        assert d["label"] == "Weight (kg)"
        assert d["dtype"] == "numeric"
        assert d["sas_format"] == "8.1"
        assert d["storage_width"] == 8

    def test_model_validate_from_dict(self) -> None:
        data = {"name": "SEX", "label": "Sex", "dtype": "character"}
        var = VariableMetadata.model_validate(data)
        assert var.name == "SEX"
        assert var.dtype == "character"


class TestDatasetMetadata:
    """Tests for DatasetMetadata model."""

    def test_create_valid_dataset(self) -> None:
        var1 = VariableMetadata(name="SUBJID", label="Subject ID", dtype="character")
        var2 = VariableMetadata(name="AGE", label="Age", dtype="numeric")
        ds = DatasetMetadata(
            filename="dm.sas7bdat",
            row_count=150,
            col_count=2,
            variables=[var1, var2],
            file_encoding="utf-8",
        )
        assert ds.filename == "dm.sas7bdat"
        assert ds.row_count == 150
        assert ds.col_count == 2
        assert len(ds.variables) == 2
        assert ds.file_encoding == "utf-8"

    def test_negative_row_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetMetadata(
                filename="ae.sas7bdat",
                row_count=-1,
                col_count=5,
            )

    def test_negative_col_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetMetadata(
                filename="ae.sas7bdat",
                row_count=10,
                col_count=-3,
            )

    def test_zero_counts_allowed(self) -> None:
        ds = DatasetMetadata(
            filename="empty.sas7bdat",
            row_count=0,
            col_count=0,
        )
        assert ds.row_count == 0
        assert ds.col_count == 0
        assert ds.variables == []

    def test_model_dump_serialization(self) -> None:
        var = VariableMetadata(name="X", dtype="numeric")
        ds = DatasetMetadata(
            filename="test.sas7bdat",
            row_count=10,
            col_count=1,
            variables=[var],
        )
        d = ds.model_dump()
        assert isinstance(d, dict)
        assert d["filename"] == "test.sas7bdat"
        assert len(d["variables"]) == 1
        assert d["variables"][0]["name"] == "X"
        assert d["file_encoding"] is None

    def test_empty_variables_list_default(self) -> None:
        ds = DatasetMetadata(
            filename="test.sas7bdat",
            row_count=0,
            col_count=0,
        )
        assert ds.variables == []
