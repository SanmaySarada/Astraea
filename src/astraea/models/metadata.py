"""SAS file metadata models.

These models represent the raw metadata extracted from SAS .sas7bdat files
by pyreadstat, before any profiling or analysis is performed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VariableMetadata(BaseModel):
    """Metadata for a single variable in a SAS dataset.

    Extracted directly from SAS file metadata via pyreadstat.
    """

    name: str = Field(..., description="Variable name as stored in SAS file")
    label: str = Field(default="", description="SAS variable label")
    sas_format: str | None = Field(default=None, description="SAS format (e.g., 'BEST12.', '$25.')")
    dtype: Literal["numeric", "character"] = Field(
        ..., description="SAS data type: numeric or character"
    )
    storage_width: int | None = Field(default=None, ge=1, description="Storage width in bytes")


class DatasetMetadata(BaseModel):
    """Metadata for an entire SAS dataset file.

    Represents the structural information about a .sas7bdat file
    without any profiling or statistical analysis of the data.
    """

    filename: str = Field(..., description="SAS filename (e.g., 'ae.sas7bdat')")
    row_count: int = Field(..., ge=0, description="Number of rows in the dataset")
    col_count: int = Field(..., ge=0, description="Number of columns in the dataset")
    variables: list[VariableMetadata] = Field(
        default_factory=list, description="Ordered list of variable metadata"
    )
    file_encoding: str | None = Field(
        default=None, description="Character encoding of the SAS file"
    )
