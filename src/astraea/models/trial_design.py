"""Trial design models for SDTM domains.

Provides Pydantic models for:
- TSParameter / TSConfig: Trial Summary (TS) domain metadata
- ArmDef / ElementDef / VisitDef / IEDef / TrialDesignConfig:
  Trial design domain configuration (TA, TE, TV, TI)

TS is a mandatory FDA submission dataset. Trial design domains
(TA, TE, TV, TI) describe study structure and are required for
submission completeness.
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


# ---------------------------------------------------------------------------
# Trial Design Models (TA, TE, TV, TI)
# ---------------------------------------------------------------------------


class ArmDef(BaseModel):
    """Definition of a single trial arm.

    Attributes:
        armcd: Planned arm code (max 8 chars, e.g., "DRUG").
        arm: Description of the arm (e.g., "Drug 1000 IU").
        taetord: Order of element within the arm (1-based).
        etcd: Element code for this position in the arm.
    """

    armcd: str = Field(..., min_length=1, max_length=8, description="Arm code")
    arm: str = Field(..., min_length=1, description="Arm description")
    taetord: int = Field(..., ge=1, description="Element order within arm")
    etcd: str = Field(..., min_length=1, max_length=8, description="Element code")

    @field_validator("armcd")
    @classmethod
    def _uppercase_armcd(cls, v: str) -> str:
        return v.strip().upper()


class ElementDef(BaseModel):
    """Definition of a single trial element.

    Attributes:
        etcd: Element code (max 8 chars, e.g., "SCRN").
        element: Element description (e.g., "Screening").
        testrl: Rule for start of element (e.g., "Informed consent signed").
        teenrl: Rule for end of element.
        tedur: Planned duration of element (ISO 8601, e.g., "P14D").
    """

    etcd: str = Field(..., min_length=1, max_length=8, description="Element code")
    element: str = Field(..., min_length=1, description="Element description")
    testrl: str = Field(default="", description="Start rule for element")
    teenrl: str = Field(default="", description="End rule for element")
    tedur: str = Field(default="", description="Planned duration (ISO 8601)")

    @field_validator("etcd")
    @classmethod
    def _uppercase_etcd(cls, v: str) -> str:
        return v.strip().upper()


class VisitDef(BaseModel):
    """Definition of a single planned visit.

    Attributes:
        visitnum: Planned visit number (integer or decimal for unplanned).
        visit: Visit name (e.g., "Screening", "Week 4").
        visitdy: Planned study day of visit.
        armcd: Arm code this visit belongs to (for arm-specific schedules).
        tvstrl: Rule for start of visit window.
        tvenrl: Rule for end of visit window.
    """

    visitnum: float = Field(..., ge=0, description="Visit number")
    visit: str = Field(..., min_length=1, description="Visit name")
    visitdy: int | None = Field(default=None, description="Planned study day")
    armcd: str = Field(..., min_length=1, max_length=8, description="Arm code")
    tvstrl: str = Field(default="", description="Visit window start rule")
    tvenrl: str = Field(default="", description="Visit window end rule")

    @field_validator("armcd")
    @classmethod
    def _uppercase_armcd(cls, v: str) -> str:
        return v.strip().upper()


class IEDef(BaseModel):
    """Definition of a single inclusion/exclusion criterion.

    Attributes:
        ietestcd: I/E criterion short name (max 8 chars, e.g., "INCL01").
        ietest: I/E criterion full text.
        iecat: Category -- "INCLUSION" or "EXCLUSION".
        tirl: Rule for evaluating the criterion.
    """

    ietestcd: str = Field(
        ..., min_length=1, max_length=8, description="I/E criterion code"
    )
    ietest: str = Field(..., min_length=1, description="I/E criterion text")
    iecat: str = Field(..., description="INCLUSION or EXCLUSION")
    tirl: str = Field(default="", description="Evaluation rule")

    @field_validator("ietestcd")
    @classmethod
    def _uppercase_ietestcd(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("iecat")
    @classmethod
    def _validate_iecat(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ("INCLUSION", "EXCLUSION"):
            msg = f"iecat must be 'INCLUSION' or 'EXCLUSION', got '{v}'"
            raise ValueError(msg)
        return v


class TrialDesignConfig(BaseModel):
    """Configuration for building trial design domains (TA, TE, TV, TI).

    Contains all study structural definitions needed to produce the
    TA (Trial Arms), TE (Trial Elements), TV (Trial Visits), and
    TI (Trial Inclusion/Exclusion) domains.

    Attributes:
        arms: Arm definitions for TA domain (one entry per element per arm).
        elements: Element definitions for TE domain.
        visits: Visit definitions for TV domain.
        inclusion_exclusion: I/E criteria for TI domain. None = no TI data.
    """

    arms: list[ArmDef] = Field(
        ..., min_length=1, description="Arm-element definitions for TA"
    )
    elements: list[ElementDef] = Field(
        ..., min_length=1, description="Element definitions for TE"
    )
    visits: list[VisitDef] = Field(
        ..., min_length=1, description="Visit definitions for TV"
    )
    inclusion_exclusion: list[IEDef] | None = Field(
        default=None,
        description="I/E criteria for TI domain (None = empty TI)",
    )
