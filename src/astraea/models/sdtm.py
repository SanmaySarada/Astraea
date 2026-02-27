"""SDTM Implementation Guide reference data models.

These models represent the structural specifications from the SDTM-IG,
including domain definitions, variable specifications, and classification
enumerations. Used for lookup during mapping, not for storing mapped data.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class DomainClass(str, Enum):
    """SDTM domain classification per SDTM-IG v3.4."""

    INTERVENTIONS = "Interventions"
    EVENTS = "Events"
    FINDINGS = "Findings"
    SPECIAL_PURPOSE = "Special-Purpose"
    TRIAL_DESIGN = "Trial Design"
    RELATIONSHIP = "Relationship"
    ASSOCIATED_PERSONS = "Associated Persons"


class CoreDesignation(str, Enum):
    """SDTM variable core designation.

    REQ = Required (must be present in dataset)
    EXP = Expected (should be present if data collected)
    PERM = Permissible (optional)
    """

    REQ = "Req"
    EXP = "Exp"
    PERM = "Perm"


class VariableSpec(BaseModel):
    """Specification for a single SDTM variable within a domain.

    Represents the SDTM-IG definition of what a variable should be,
    including its expected type, core status, and associated codelist.
    """

    name: str = Field(..., description="SDTM variable name (e.g., 'AETERM')")
    label: str = Field(..., description="Variable label (e.g., 'Reported Term for the Adverse Event')")
    data_type: Literal["Char", "Num"] = Field(
        ..., description="SDTM data type: Char or Num"
    )
    core: CoreDesignation = Field(
        ..., description="Core designation: Req, Exp, or Perm"
    )
    cdisc_notes: str = Field(default="", description="CDISC implementation notes")
    codelist_code: str | None = Field(
        default=None, description="NCI codelist code (e.g., 'C66729') if applicable"
    )
    order: int = Field(..., ge=1, description="Display order within the domain")


class DomainSpec(BaseModel):
    """Specification for an SDTM domain.

    Defines the structure and variables expected in a domain
    per the SDTM Implementation Guide.
    """

    domain: str = Field(
        ..., min_length=1, max_length=8, description="Domain abbreviation (e.g., 'AE', 'DM', 'SUPPQUAL')"
    )
    description: str = Field(..., description="Domain description (e.g., 'Adverse Events')")
    domain_class: DomainClass = Field(..., description="Domain classification")
    structure: str = Field(
        ..., description="Dataset structure (e.g., 'One record per adverse event per subject')"
    )
    variables: list[VariableSpec] = Field(
        default_factory=list, description="Ordered list of variable specifications"
    )
    key_variables: list[str] | None = Field(
        default=None,
        description="Natural key variables for uniqueness validation (e.g., ['STUDYID', 'USUBJID'] for DM)",
    )


class SDTMIGPackage(BaseModel):
    """Complete SDTM Implementation Guide package.

    Contains all domain specifications for a given IG version.
    """

    version: str = Field(..., description="SDTM-IG version (e.g., '3.4')")
    domains: dict[str, DomainSpec] = Field(
        default_factory=dict, description="Domain specs keyed by domain abbreviation"
    )
