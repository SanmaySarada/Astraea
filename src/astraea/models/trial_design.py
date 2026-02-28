"""Trial design models for SDTM Trial Summary (TS) domain.

Provides TSParameter and TSConfig Pydantic models for specifying
study-level metadata that populates the TS domain -- a mandatory
dataset for FDA submissions.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class TSParameter(BaseModel):
    """A single Trial Summary parameter (one row in TS domain).

    Attributes:
        tsparmcd: Parameter short name / code (max 8 chars, e.g., "ADDON").
        tsparm: Parameter long name (max 40 chars, e.g., "Added on to Existing Treatments").
        tsval: Parameter value (e.g., "Y").
    """

    tsparmcd: str = Field(..., max_length=8, description="Parameter code (max 8 chars)")
    tsparm: str = Field(..., max_length=40, description="Parameter name (max 40 chars)")
    tsval: str = Field(..., min_length=1, description="Parameter value")

    @field_validator("tsparmcd")
    @classmethod
    def _uppercase_tsparmcd(cls, v: str) -> str:
        return v.strip().upper()


class TSConfig(BaseModel):
    """Configuration for building a Trial Summary (TS) domain dataset.

    Contains all study-level metadata needed to populate the TS domain.
    Required fields map to FDA-mandatory TS parameters; optional fields
    are included only when provided.

    Attributes:
        study_id: STUDYID -- unique study identifier.
        study_title: TITLE -- official study title.
        sponsor: SPONSOR -- sponsoring organization name.
        indication: INDIC -- disease or condition under study.
        treatment: TRT -- investigational therapy / treatment.
        pharmacological_class: PCLAS -- pharmacological class of treatment.
        study_type: STYPE -- type of study (default "INTERVENTIONAL").
        sdtm_version: SDTMVER -- SDTM-IG version (default "3.4").
        trial_phase: TPHASE -- clinical trial phase (default "PHASE III TRIAL").
        planned_enrollment: PLESSION -- planned number of subjects.
        number_of_arms: NARMS -- number of study arms.
        accession_number: ACESSION -- regulatory accession number.
        addon: ADDON -- added on to existing treatments (Y/N).
        additional_params: Extra study-specific TS parameters.
    """

    study_id: str = Field(..., min_length=1, description="Study identifier (STUDYID)")
    study_title: str = Field(..., min_length=1, description="Study title (TITLE)")
    sponsor: str = Field(..., min_length=1, description="Sponsor name (SPONSOR)")
    indication: str = Field(..., min_length=1, description="Indication (INDIC)")
    treatment: str = Field(..., min_length=1, description="Treatment (TRT)")
    pharmacological_class: str = Field(
        ..., min_length=1, description="Pharmacological class (PCLAS)"
    )
    study_type: str = Field(
        default="INTERVENTIONAL", description="Study type (STYPE)"
    )
    sdtm_version: str = Field(
        default="3.4", description="SDTM-IG version (SDTMVER)"
    )
    trial_phase: str = Field(
        default="PHASE III TRIAL", description="Trial phase (TPHASE)"
    )
    planned_enrollment: int | None = Field(
        default=None, ge=1, description="Planned enrollment (PLESSION)"
    )
    number_of_arms: int | None = Field(
        default=None, ge=1, description="Number of arms (NARMS)"
    )
    accession_number: str | None = Field(
        default=None, description="Accession number (ACESSION)"
    )
    addon: str | None = Field(
        default=None, description="Added on to existing treatments (ADDON)"
    )
    additional_params: list[TSParameter] = Field(
        default_factory=list,
        description="Additional study-specific TS parameters",
    )
