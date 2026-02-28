"""Mapping specification models for the SDTM mapping pipeline.

These models define the contract between the LLM proposal stage, the
validation/enrichment engine, and the output exporters. They represent
both the raw LLM output (proposal models) and the enriched/validated
mapping specifications used for dataset generation.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from astraea.models.sdtm import CoreDesignation


class MappingPattern(StrEnum):
    """Mapping pattern describing how a source variable maps to an SDTM target.

    Each pattern represents a distinct transformation type:
    - ASSIGN: Constant value assignment (no source variable)
    - DIRECT: Direct carry from source to target (no transformation)
    - RENAME: Same data, different variable name
    - REFORMAT: Same data, different format (e.g., date conversion)
    - SPLIT: One source variable splits into multiple targets
    - COMBINE: Multiple source variables combine into one target
    - DERIVATION: Calculated from one or more sources using logic
    - LOOKUP_RECODE: Value mapped via codelist or lookup table
    - TRANSPOSE: Horizontal-to-vertical structural transformation
    """

    ASSIGN = "assign"
    DIRECT = "direct"
    RENAME = "rename"
    REFORMAT = "reformat"
    SPLIT = "split"
    COMBINE = "combine"
    DERIVATION = "derivation"
    LOOKUP_RECODE = "lookup_recode"
    TRANSPOSE = "transpose"


class VariableOrigin(StrEnum):
    """Variable origin type for define.xml 2.0 Origin element.

    Describes the source of a variable's value:
    - CRF: Collected on Case Report Form
    - DERIVED: Calculated from other variables
    - ASSIGNED: Set by the sponsor (constant values)
    - PROTOCOL: Defined by the study protocol
    - EDT: Electronic data transfer (external source)
    - PREDECESSOR: Carried from a predecessor variable
    """

    CRF = "CRF"
    DERIVED = "Derived"
    ASSIGNED = "Assigned"
    PROTOCOL = "Protocol"
    EDT = "eDT"
    PREDECESSOR = "Predecessor"


class ConfidenceLevel(StrEnum):
    """Categorical confidence level derived from a numeric confidence score.

    Used to route human attention: LOW confidence mappings are flagged
    for mandatory review, HIGH confidence may be batch-approved.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def confidence_level_from_score(score: float) -> ConfidenceLevel:
    """Convert a numeric confidence score to a categorical level.

    Args:
        score: Confidence score between 0.0 and 1.0.

    Returns:
        HIGH if score >= 0.85, MEDIUM if score >= 0.6, else LOW.
    """
    if score >= 0.85:
        return ConfidenceLevel.HIGH
    if score >= 0.6:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


class VariableMappingProposal(BaseModel):
    """LLM output schema for a single variable mapping proposal.

    This is the simpler model used as the Claude tool output schema.
    It captures what the LLM proposes before enrichment with reference
    data (labels, core status, codelist names).
    """

    sdtm_variable: str = Field(
        ..., description="Target SDTM variable name (e.g., 'AETERM', 'USUBJID')"
    )
    source_dataset: str | None = Field(
        default=None, description="Source dataset name (None for ASSIGN pattern)"
    )
    source_variable: str | None = Field(
        default=None, description="Source variable name (None for ASSIGN pattern)"
    )
    mapping_pattern: MappingPattern = Field(..., description="How the source maps to the target")
    mapping_logic: str = Field(..., description="Human-readable description of the mapping logic")
    derivation_rule: str | None = Field(
        default=None,
        description="Pseudo-code DSL for the execution engine (for DERIVATION, COMBINE, etc.)",
    )
    assigned_value: str | None = Field(
        default=None, description="Constant value for ASSIGN pattern"
    )
    codelist_code: str | None = Field(
        default=None, description="NCI codelist code (e.g., 'C66729') if applicable"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")
    rationale: str = Field(..., description="Explanation of why this mapping was chosen")
    origin: str | None = Field(
        default=None,
        description="Proposed origin type (CRF, Derived, Assigned, Protocol, eDT)",
    )


class DomainMappingProposal(BaseModel):
    """Complete LLM output for mapping all variables in one SDTM domain.

    This is the top-level tool output schema sent to/from Claude.
    Contains the list of variable proposals plus metadata about
    unmapped variables and SUPPQUAL candidates.
    """

    domain: str = Field(..., description="Target SDTM domain code (e.g., 'AE', 'DM')")
    variable_proposals: list[VariableMappingProposal] = Field(
        default_factory=list, description="Proposed mappings for each SDTM variable"
    )
    unmapped_source_variables: list[str] = Field(
        default_factory=list,
        description="Source variables not mapped to any SDTM target",
    )
    suppqual_candidates: list[str] = Field(
        default_factory=list,
        description="Source variables recommended for SUPPQUAL domain",
    )
    mapping_notes: str = Field(default="", description="General notes about the mapping approach")


class VariableMapping(BaseModel):
    """Enriched and validated mapping for a single SDTM variable.

    This is the full specification produced after enriching the LLM proposal
    with reference data (labels, core status, codelist names) and validating
    against the SDTM-IG domain spec.
    """

    sdtm_variable: str = Field(..., description="Target SDTM variable name (e.g., 'AETERM')")
    sdtm_label: str = Field(..., description="SDTM variable label from the IG spec")
    sdtm_data_type: Literal["Char", "Num"] = Field(..., description="SDTM data type: Char or Num")
    core: CoreDesignation = Field(
        ..., description="Core designation from SDTM-IG: Req, Exp, or Perm"
    )
    source_dataset: str | None = Field(default=None, description="Source dataset name")
    source_variable: str | None = Field(default=None, description="Source variable name")
    source_label: str | None = Field(
        default=None, description="Source variable label from SAS metadata"
    )
    mapping_pattern: MappingPattern = Field(..., description="How the source maps to the target")
    mapping_logic: str = Field(..., description="Human-readable description of the mapping logic")
    derivation_rule: str | None = Field(
        default=None, description="Pseudo-code DSL for the execution engine"
    )
    assigned_value: str | None = Field(
        default=None, description="Constant value for ASSIGN pattern"
    )
    codelist_code: str | None = Field(default=None, description="NCI codelist code if applicable")
    codelist_name: str | None = Field(default=None, description="NCI codelist name if applicable")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")
    confidence_level: ConfidenceLevel = Field(
        ..., description="Categorical confidence level derived from score"
    )
    confidence_rationale: str = Field(..., description="Explanation of the confidence assessment")
    notes: str = Field(default="", description="Additional notes about this mapping")
    order: int = Field(
        default=0,
        ge=0,
        description="Display order within domain from SDTM-IG spec",
    )
    length: int | None = Field(
        default=None,
        description="Character variable length for XPT generation",
    )
    origin: VariableOrigin | None = Field(
        default=None,
        description="Variable origin type for define.xml (CRF, Derived, Assigned, Protocol, eDT)",
    )
    computational_method: str | None = Field(
        default=None,
        description="Derivation algorithm description for define.xml MethodDef",
    )


class DomainMappingSpec(BaseModel):
    """Complete mapping specification for one SDTM domain.

    Aggregates all variable mappings with domain-level metadata and
    summary statistics. This is the artifact reviewed by humans and
    used by the dataset generator.
    """

    domain: str = Field(..., description="SDTM domain code (e.g., 'AE', 'DM')")
    domain_label: str = Field(..., description="Domain description (e.g., 'Adverse Events')")
    domain_class: str = Field(..., description="Domain class (e.g., 'Events', 'Findings')")
    structure: str = Field(..., description="Dataset structure description")
    study_id: str = Field(..., description="Study identifier (e.g., 'PHA022121-C301')")
    source_datasets: list[str] = Field(
        default_factory=list, description="Source datasets used for this domain"
    )
    cross_domain_sources: list[str] = Field(
        default_factory=list,
        description="Variables sourced from other domains (e.g., DM for RFSTDTC)",
    )
    variable_mappings: list[VariableMapping] = Field(
        default_factory=list, description="Ordered list of variable mappings"
    )
    total_variables: int = Field(..., ge=0, description="Total number of mapped variables")
    required_mapped: int = Field(..., ge=0, description="Number of Req variables with mappings")
    expected_mapped: int = Field(..., ge=0, description="Number of Exp variables with mappings")
    high_confidence_count: int = Field(..., ge=0, description="Number of HIGH confidence mappings")
    medium_confidence_count: int = Field(
        ..., ge=0, description="Number of MEDIUM confidence mappings"
    )
    low_confidence_count: int = Field(..., ge=0, description="Number of LOW confidence mappings")
    mapping_timestamp: str = Field(
        ..., description="ISO 8601 timestamp of when mapping was performed"
    )
    model_used: str = Field(..., description="LLM model identifier used for mapping")
    unmapped_source_variables: list[str] = Field(
        default_factory=list,
        description="Source variables not mapped to any SDTM target",
    )
    suppqual_candidates: list[str] = Field(
        default_factory=list,
        description="Source variables recommended for SUPPQUAL domain",
    )
    missing_required_variables: list[str] = Field(
        default_factory=list,
        description="Required SDTM variables not mapped by LLM proposal",
    )
    predict_prevent_issues: list[dict[str, str | None]] = Field(
        default_factory=list,
        description="Predict-and-prevent validation issues found at spec time. "
        "Each dict has: rule_id, severity, domain, variable (optional), "
        "message, fix_suggestion (optional). Populated by validation/predict.py "
        "and surfaced during human review.",
    )


class StudyMetadata(BaseModel):
    """Study-level constants used across all domain mappings.

    Captures the study identifier and the variable names in the raw data
    that contain site and subject identifiers, needed for USUBJID construction.
    """

    study_id: str = Field(..., description="Study identifier (e.g., 'PHA022121-C301')")
    site_id_variable: str = Field(
        default="SiteNumber",
        description="Raw variable name containing site identifier",
    )
    subject_id_variable: str = Field(
        default="Subject",
        description="Raw variable name containing subject identifier",
    )
    study_env_site_variable: str = Field(
        default="StudyEnvSiteNumber",
        description="Raw variable name containing study-environment site number",
    )
