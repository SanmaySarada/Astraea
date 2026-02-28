"""Pydantic model for SUPPQUAL variable specification.

Defines SuppVariable, which describes a supplemental qualifier variable
to be extracted from a parent domain DataFrame into a SUPP-- dataset.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator


class SuppVariable(BaseModel):
    """Specification for one supplemental qualifier variable.

    Describes how to extract a SUPPQUAL record from the parent domain
    DataFrame. QNAM is limited to 8 alphanumeric characters per XPT
    constraints. QLABEL is limited to 40 characters per SAS Transport.

    Attributes:
        qnam: SUPPQUAL variable name (max 8 chars, alphanumeric).
        qlabel: Variable label (max 40 chars).
        source_col: Source column name in parent DataFrame.
        qorig: Origin type (CRF, ASSIGNED, DERIVED, PROTOCOL).
        qeval: Evaluator (optional, e.g., INVESTIGATOR).
    """

    qnam: str = Field(
        ...,
        min_length=1,
        max_length=8,
        description="SUPPQUAL variable name (max 8 chars, alphanumeric)",
    )
    qlabel: str = Field(
        ...,
        min_length=1,
        max_length=40,
        description="Variable label (max 40 chars)",
    )
    source_col: str = Field(
        ..., description="Source column name in parent DataFrame"
    )
    qorig: str = Field(
        ..., description="Origin: CRF, ASSIGNED, DERIVED, or PROTOCOL"
    )
    qeval: str = Field(
        default="",
        description="Evaluator (optional, e.g., INVESTIGATOR)",
    )

    @field_validator("qnam")
    @classmethod
    def validate_qnam_alphanumeric(cls, v: str) -> str:
        """QNAM must be alphanumeric (letters and digits only)."""
        if not re.match(r"^[A-Za-z0-9]+$", v):
            msg = f"QNAM must be alphanumeric, got: '{v}'"
            raise ValueError(msg)
        return v.upper()

    @field_validator("qorig")
    @classmethod
    def validate_qorig(cls, v: str) -> str:
        """QORIG must be a valid origin type."""
        valid = {"CRF", "ASSIGNED", "DERIVED", "PROTOCOL"}
        if v.upper() not in valid:
            msg = f"QORIG must be one of {valid}, got: '{v}'"
            raise ValueError(msg)
        return v.upper()
