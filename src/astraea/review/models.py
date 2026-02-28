"""Review data models for the human review gate.

These models define how human corrections are captured (training data for the
learning system), how per-variable and per-domain review status is tracked,
and how review sessions maintain state across process exits.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from astraea.models.mapping import DomainMappingSpec, VariableMapping


class CorrectionType(StrEnum):
    """Type of correction a reviewer makes to a proposed mapping.

    Each type represents a distinct kind of change, enabling the learning
    system to categorize and learn from different correction patterns.
    """

    SOURCE_CHANGE = "source_change"
    LOGIC_CHANGE = "logic_change"
    PATTERN_CHANGE = "pattern_change"
    CT_CHANGE = "ct_change"
    CONFIDENCE_OVERRIDE = "confidence_override"
    REJECT = "reject"
    ADD = "add"


class ReviewStatus(StrEnum):
    """Per-variable review status."""

    PENDING = "pending"
    APPROVED = "approved"
    CORRECTED = "corrected"
    SKIPPED = "skipped"


class DomainReviewStatus(StrEnum):
    """Per-domain review status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class SessionStatus(StrEnum):
    """Overall review session status."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ReviewDecision(BaseModel):
    """A reviewer's decision on a single variable mapping.

    Captures both the original proposal and any correction, along with
    the reviewer's reason for the decision.
    """

    sdtm_variable: str = Field(..., description="SDTM variable this decision applies to")
    status: ReviewStatus = Field(..., description="Review outcome for this variable")
    correction_type: CorrectionType | None = Field(
        default=None,
        description="Type of correction (only set when status is CORRECTED)",
    )
    original_mapping: VariableMapping = Field(..., description="The original proposed mapping")
    corrected_mapping: VariableMapping | None = Field(
        default=None,
        description="The corrected mapping (only set when status is CORRECTED)",
    )
    reason: str = Field(default="", description="Human explanation (required when corrected)")
    timestamp: str = Field(..., description="ISO 8601 timestamp of when the decision was made")

    @model_validator(mode="after")
    def _validate_correction_fields(self) -> ReviewDecision:
        """Ensure corrected_mapping is provided when status is CORRECTED.

        Exception: REJECT corrections have no corrected_mapping (the
        variable is being removed, not replaced).
        """
        if self.status == ReviewStatus.CORRECTED:
            if self.correction_type is None:
                msg = "correction_type is required when status is CORRECTED"
                raise ValueError(msg)
            if self.corrected_mapping is None and self.correction_type != CorrectionType.REJECT:
                msg = "corrected_mapping is required when status is CORRECTED (except REJECT)"
                raise ValueError(msg)
        return self


class HumanCorrection(BaseModel):
    """A structured correction record linking original to corrected mapping.

    This is the primary training signal for the Phase 8 learning system.
    Each correction captures what was proposed, what the reviewer changed,
    and why -- forming input-output pairs for prompt optimization.
    """

    session_id: str = Field(..., description="Review session this correction belongs to")
    domain: str = Field(..., description="SDTM domain (e.g., 'AE', 'DM')")
    sdtm_variable: str = Field(..., description="SDTM variable that was corrected")
    correction_type: CorrectionType = Field(..., description="Type of correction made")
    original_mapping: VariableMapping = Field(..., description="The original proposed mapping")
    corrected_mapping: VariableMapping | None = Field(
        default=None, description="The corrected mapping (None for REJECT)"
    )
    reason: str = Field(..., description="Human explanation for the correction")
    reviewer: str = Field(default="", description="Reviewer identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the correction")


class DomainReview(BaseModel):
    """Review state for a single SDTM domain within a session.

    Tracks the original mapping spec, per-variable decisions, and
    the final reviewed spec after all corrections are applied.
    """

    domain: str = Field(..., description="SDTM domain code")
    status: DomainReviewStatus = Field(
        default=DomainReviewStatus.PENDING,
        description="Overall review status for this domain",
    )
    original_spec: DomainMappingSpec = Field(
        ..., description="The original proposed mapping specification"
    )
    reviewed_spec: DomainMappingSpec | None = Field(
        default=None,
        description="The mapping spec after review (populated after review)",
    )
    decisions: dict[str, ReviewDecision] = Field(
        default_factory=dict,
        description="Per-variable decisions keyed by sdtm_variable",
    )
    corrections: list[HumanCorrection] = Field(
        default_factory=list,
        description="List of corrections made during review",
    )
    reviewed_at: str | None = Field(
        default=None, description="ISO 8601 timestamp of review completion"
    )


class ReviewSession(BaseModel):
    """Top-level review session state.

    A session represents one review pass over a set of domain mapping
    specifications. Sessions persist to SQLite and can be interrupted
    and resumed across process exits.
    """

    session_id: str = Field(..., description="Unique session identifier (12 hex chars)")
    study_id: str = Field(..., description="Study identifier (e.g., 'PHA022121-C301')")
    created_at: str = Field(..., description="ISO 8601 timestamp of session creation")
    updated_at: str = Field(..., description="ISO 8601 timestamp of last update")
    status: SessionStatus = Field(
        default=SessionStatus.IN_PROGRESS,
        description="Overall session status",
    )
    domains: list[str] = Field(..., description="Ordered list of domains to review")
    current_domain_index: int = Field(default=0, description="Index into domains list for resume")
    domain_reviews: dict[str, DomainReview] = Field(
        default_factory=dict,
        description="Per-domain review state keyed by domain code",
    )
