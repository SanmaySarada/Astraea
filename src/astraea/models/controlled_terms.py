"""NCI Controlled Terminology models.

These models represent CDISC Controlled Terminology (CT) codelists
as distributed by NCI EVS. Used for deterministic codelist lookups
during SDTM mapping -- never for LLM-based matching.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CodelistTerm(BaseModel):
    """A single term within a CDISC controlled terminology codelist."""

    submission_value: str = Field(
        ..., description="The value to use in SDTM submissions (e.g., 'HEADACHE')"
    )
    synonyms: list[str] = Field(
        default_factory=list, description="Alternative names / synonyms for this term"
    )
    definition: str = Field(default="", description="NCI definition of the term")
    nci_preferred_term: str = Field(
        default="", description="NCI preferred term (may differ from submission value)"
    )


class Codelist(BaseModel):
    """A CDISC controlled terminology codelist.

    May be extensible (study-specific values allowed) or
    non-extensible (only listed values permitted).
    """

    code: str = Field(..., description="NCI codelist code (e.g., 'C66729')")
    name: str = Field(..., description="Codelist name (e.g., 'Sex')")
    extensible: bool = Field(
        ..., description="Whether study-specific values are allowed beyond listed terms"
    )
    variable_mappings: list[str] = Field(
        default_factory=list,
        description="SDTM variables that use this codelist (e.g., ['SEX'])",
    )
    terms: dict[str, CodelistTerm] = Field(
        default_factory=dict,
        description="Terms keyed by submission value",
    )


class CTPackage(BaseModel):
    """Complete Controlled Terminology package for a specific version.

    Links a CT release version to its corresponding SDTM-IG version
    and contains all codelists.
    """

    version: str = Field(..., description="CT package version (e.g., '2024-09-27')")
    ig_version: str = Field(..., description="Associated SDTM-IG version (e.g., '3.4')")
    codelists: dict[str, Codelist] = Field(
        default_factory=dict, description="Codelists keyed by codelist code"
    )
