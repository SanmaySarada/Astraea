"""Dataset profiling result models.

These models represent the output of the profiling stage, where raw SAS
datasets are analyzed to produce statistical summaries, detect date formats,
and identify EDC system columns.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValueDistribution(BaseModel):
    """Frequency distribution entry for a single value."""

    value: str = Field(..., description="The observed value (as string)")
    count: int = Field(..., ge=0, description="Number of occurrences")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of total rows")


class VariableProfile(BaseModel):
    """Statistical profile of a single variable in a dataset.

    Combines metadata with distribution analysis, date detection,
    and EDC column identification.
    """

    name: str = Field(..., description="Variable name")
    label: str = Field(default="", description="Variable label from SAS metadata")
    dtype: str = Field(..., description="Data type (numeric or character)")
    sas_format: str | None = Field(default=None, description="SAS format string")
    n_total: int = Field(..., ge=0, description="Total number of rows")
    n_missing: int = Field(..., ge=0, description="Number of missing values")
    n_unique: int = Field(..., ge=0, description="Number of unique non-missing values")
    missing_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of missing values")
    sample_values: list[str] = Field(
        default_factory=list, description="Sample of unique non-missing values"
    )
    top_values: list[ValueDistribution] = Field(
        default_factory=list, description="Most frequent values with counts"
    )
    is_date: bool = Field(default=False, description="Whether this variable contains date values")
    detected_date_format: str | None = Field(
        default=None, description="Detected date format (e.g., 'DD Mon YYYY', 'SAS_DATETIME')"
    )
    is_edc_column: bool = Field(
        default=False, description="Whether this is an EDC system column (not clinical data)"
    )


class DatasetProfile(BaseModel):
    """Complete profile of a raw SAS dataset.

    Aggregates variable-level profiles with dataset-level summaries
    for date variables and EDC system columns.
    """

    filename: str = Field(..., description="Source SAS filename")
    row_count: int = Field(..., ge=0, description="Number of rows in the dataset")
    col_count: int = Field(..., ge=0, description="Number of columns in the dataset")
    variables: list[VariableProfile] = Field(
        default_factory=list, description="Ordered list of variable profiles"
    )
    date_variables: list[str] = Field(
        default_factory=list, description="Names of variables detected as dates"
    )
    edc_columns: list[str] = Field(default_factory=list, description="Names of EDC system columns")
