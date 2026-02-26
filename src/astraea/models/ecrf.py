"""eCRF (electronic Case Report Form) metadata models.

These models represent the structured metadata extracted from an eCRF PDF,
including form definitions, field specifications with data types, SAS labels,
coded values, and OIDs. Used as input for domain classification and variable
mapping in subsequent pipeline stages.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ECRFField(BaseModel):
    """A single field definition within an eCRF form.

    Represents one row from the eCRF field table, containing the SAS variable
    name, data type, label, optional units, coded values, and field OID.
    """

    field_number: int = Field(..., ge=1, description="Field sequence number within the form")
    field_name: str = Field(
        ..., min_length=1, description="SAS variable name (e.g., 'AETERM', 'BRTHDAT')"
    )
    data_type: str = Field(
        ..., description="Data type from eCRF (e.g., '$25', '1', 'dd MMM yyyy')"
    )
    sas_label: str = Field(..., description="SAS label describing the field")
    units: str | None = Field(default=None, description="Unit of measurement if applicable")
    coded_values: dict[str, str] | None = Field(
        default=None,
        description="Code-decode pairs (e.g., {'Y': 'Yes', 'N': 'No'})",
    )
    field_oid: str | None = Field(default=None, description="Field OID from the eCRF")

    @field_validator("field_name")
    @classmethod
    def field_name_no_whitespace(cls, v: str) -> str:
        """SAS variable names must not contain spaces."""
        if " " in v:
            msg = f"field_name must not contain spaces, got '{v}'"
            raise ValueError(msg)
        return v


class ECRFForm(BaseModel):
    """A single eCRF form containing multiple field definitions.

    Represents a complete form (e.g., 'Adverse Events', 'Demographics') with
    all its fields and the PDF page numbers where it appears.
    """

    form_name: str = Field(..., min_length=1, description="Form name as it appears in the eCRF")
    fields: list[ECRFField] = Field(
        default_factory=list, description="Ordered list of field definitions"
    )
    page_numbers: list[int] = Field(
        default_factory=list, description="PDF page numbers where this form appears"
    )


class ECRFExtractionResult(BaseModel):
    """Complete result of eCRF PDF extraction.

    Aggregates all extracted forms with metadata about the extraction process.
    """

    forms: list[ECRFForm] = Field(
        default_factory=list, description="All extracted eCRF forms"
    )
    source_pdf: str = Field(..., description="Path or name of the source PDF file")
    extraction_timestamp: str = Field(
        ..., description="ISO 8601 timestamp of when extraction was performed"
    )

    @property
    def total_fields(self) -> int:
        """Total number of fields across all forms."""
        return sum(len(form.fields) for form in self.forms)
