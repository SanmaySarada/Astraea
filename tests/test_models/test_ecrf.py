"""Tests for eCRF metadata models."""

import pytest
from pydantic import ValidationError

from astraea.models import ECRFExtractionResult, ECRFField, ECRFForm


class TestECRFField:
    """Tests for ECRFField model."""

    def test_create_valid_field_all_fields(self) -> None:
        field = ECRFField(
            field_number=1,
            field_name="AETERM",
            data_type="$200",
            sas_label="Reported Term for the Adverse Event",
            units=None,
            coded_values=None,
            field_oid="AE.AETERM",
        )
        assert field.field_number == 1
        assert field.field_name == "AETERM"
        assert field.data_type == "$200"
        assert field.sas_label == "Reported Term for the Adverse Event"
        assert field.units is None
        assert field.coded_values is None
        assert field.field_oid == "AE.AETERM"

    def test_create_field_with_coded_values(self) -> None:
        field = ECRFField(
            field_number=3,
            field_name="AESER",
            data_type="$1",
            sas_label="Serious Event",
            coded_values={"Y": "Yes", "N": "No"},
        )
        assert field.coded_values == {"Y": "Yes", "N": "No"}

    def test_create_field_with_units(self) -> None:
        field = ECRFField(
            field_number=5,
            field_name="VSTEMP",
            data_type="8",
            sas_label="Temperature",
            units="C",
        )
        assert field.units == "C"

    def test_optional_fields_default_to_none(self) -> None:
        field = ECRFField(
            field_number=1,
            field_name="SUBJID",
            data_type="$10",
            sas_label="Subject Identifier",
        )
        assert field.units is None
        assert field.coded_values is None
        assert field.field_oid is None

    def test_rejects_empty_field_name(self) -> None:
        with pytest.raises(ValidationError):
            ECRFField(
                field_number=1,
                field_name="",
                data_type="$10",
                sas_label="Test",
            )

    def test_rejects_field_name_with_spaces(self) -> None:
        with pytest.raises(ValidationError, match="must not contain spaces"):
            ECRFField(
                field_number=1,
                field_name="AE TERM",
                data_type="$200",
                sas_label="Test",
            )

    def test_rejects_field_number_zero(self) -> None:
        with pytest.raises(ValidationError):
            ECRFField(
                field_number=0,
                field_name="AETERM",
                data_type="$200",
                sas_label="Test",
            )

    def test_rejects_negative_field_number(self) -> None:
        with pytest.raises(ValidationError):
            ECRFField(
                field_number=-1,
                field_name="AETERM",
                data_type="$200",
                sas_label="Test",
            )


class TestECRFForm:
    """Tests for ECRFForm model."""

    def test_create_form_with_fields(self) -> None:
        field1 = ECRFField(
            field_number=1,
            field_name="AETERM",
            data_type="$200",
            sas_label="Reported Term",
        )
        field2 = ECRFField(
            field_number=2,
            field_name="AESTDTC",
            data_type="dd MMM yyyy",
            sas_label="Start Date",
        )
        form = ECRFForm(
            form_name="Adverse Events",
            fields=[field1, field2],
            page_numbers=[45, 46, 47],
        )
        assert form.form_name == "Adverse Events"
        assert len(form.fields) == 2
        assert form.page_numbers == [45, 46, 47]

    def test_create_form_empty_fields(self) -> None:
        form = ECRFForm(form_name="Empty Form")
        assert form.fields == []
        assert form.page_numbers == []

    def test_rejects_empty_form_name(self) -> None:
        with pytest.raises(ValidationError):
            ECRFForm(form_name="")


class TestECRFExtractionResult:
    """Tests for ECRFExtractionResult model."""

    def test_create_extraction_result(self) -> None:
        field = ECRFField(
            field_number=1,
            field_name="SUBJID",
            data_type="$10",
            sas_label="Subject ID",
        )
        form = ECRFForm(
            form_name="Demographics",
            fields=[field],
            page_numbers=[10],
        )
        result = ECRFExtractionResult(
            forms=[form],
            source_pdf="ECRF.pdf",
            extraction_timestamp="2026-02-26T12:00:00Z",
        )
        assert len(result.forms) == 1
        assert result.source_pdf == "ECRF.pdf"
        assert result.extraction_timestamp == "2026-02-26T12:00:00Z"

    def test_total_fields_computed(self) -> None:
        fields_a = [
            ECRFField(field_number=i, field_name=f"F{i}", data_type="$10", sas_label=f"Field {i}")
            for i in range(1, 4)
        ]
        fields_b = [
            ECRFField(field_number=i, field_name=f"G{i}", data_type="$10", sas_label=f"Field {i}")
            for i in range(1, 3)
        ]
        result = ECRFExtractionResult(
            forms=[
                ECRFForm(form_name="Form A", fields=fields_a),
                ECRFForm(form_name="Form B", fields=fields_b),
            ],
            source_pdf="test.pdf",
            extraction_timestamp="2026-02-26T12:00:00Z",
        )
        assert result.total_fields == 5

    def test_total_fields_empty(self) -> None:
        result = ECRFExtractionResult(
            forms=[],
            source_pdf="test.pdf",
            extraction_timestamp="2026-02-26T12:00:00Z",
        )
        assert result.total_fields == 0
