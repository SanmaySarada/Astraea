"""Learning system data models.

Pydantic models for mapping examples, correction records, and study-level
accuracy metrics. These are the foundational data structures for the learning
system's storage and retrieval layers.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class MappingExample(BaseModel):
    """A single approved/corrected variable mapping from a completed review.

    Captures the final mapping (after any corrections) along with metadata
    about the study, domain, and source data. Used as few-shot examples for
    future mapping proposals.
    """

    example_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Unique identifier for this example",
    )
    study_id: str = Field(
        ..., description="Study identifier (e.g., 'PHA022121-C301')"
    )
    domain: str = Field(
        ..., description="SDTM domain code (e.g., 'AE', 'DM')"
    )
    sdtm_variable: str = Field(
        ..., description="Target SDTM variable name (e.g., 'AETERM')"
    )
    mapping_pattern: str = Field(
        ..., description="Mapping pattern used (from MappingPattern enum values)"
    )
    mapping_logic: str = Field(
        ..., description="Human-readable mapping logic description"
    )
    source_variable: str | None = Field(
        default=None, description="Source variable name (None for ASSIGN)"
    )
    source_dataset: str | None = Field(
        default=None, description="Source dataset name"
    )
    source_label: str | None = Field(
        default=None, description="Source variable label from SAS metadata"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)"
    )
    was_corrected: bool = Field(
        default=False,
        description="Whether this mapping was corrected by a human reviewer",
    )
    final_mapping_json: str = Field(
        ..., description="Serialized VariableMapping JSON"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(),
        description="ISO 8601 timestamp of when this example was created",
    )


class CorrectionRecord(BaseModel):
    """An original-to-corrected mapping pair from a review session.

    Captures what was proposed, what was corrected, and why. These records
    are higher-signal training data than plain approved examples because
    they show exactly where the system went wrong.
    """

    correction_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Unique identifier for this correction",
    )
    study_id: str = Field(
        ..., description="Study identifier"
    )
    session_id: str = Field(
        ..., description="Review session this correction belongs to"
    )
    domain: str = Field(
        ..., description="SDTM domain code"
    )
    sdtm_variable: str = Field(
        ..., description="SDTM variable that was corrected"
    )
    correction_type: str = Field(
        ..., description="Type of correction (from CorrectionType enum values)"
    )
    original_pattern: str = Field(
        ..., description="Original mapping pattern proposed"
    )
    corrected_pattern: str | None = Field(
        default=None, description="Corrected mapping pattern (None for reject)"
    )
    original_logic: str = Field(
        ..., description="Original mapping logic proposed"
    )
    corrected_logic: str | None = Field(
        default=None, description="Corrected mapping logic (None for reject)"
    )
    reason: str = Field(
        ..., description="Human explanation for the correction"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(),
        description="ISO 8601 timestamp of when this correction was recorded",
    )
    invalidated: bool = Field(
        default=False,
        description="Whether this correction has been marked as invalid "
        "(for poisoning protection per RESEARCH.md pitfall 2)",
    )


class StudyMetrics(BaseModel):
    """Per-domain per-study accuracy tracking.

    Computed after a domain review completes. Tracks how many mappings
    were approved unchanged vs corrected vs rejected, providing the
    primary signal for measuring learning system improvement.
    """

    study_id: str = Field(
        ..., description="Study identifier"
    )
    domain: str = Field(
        ..., description="SDTM domain code"
    )
    total_proposed: int = Field(
        ..., ge=0, description="Total number of proposed mappings"
    )
    approved_unchanged: int = Field(
        ..., ge=0, description="Mappings approved without changes"
    )
    corrected: int = Field(
        ..., ge=0, description="Mappings that were corrected"
    )
    rejected: int = Field(
        ..., ge=0, description="Mappings that were rejected"
    )
    added_by_reviewer: int = Field(
        ..., ge=0, description="Mappings added by the reviewer (not proposed)"
    )
    accuracy_rate: float = Field(
        ..., ge=0.0, le=1.0,
        description="Fraction approved unchanged (approved_unchanged / total_proposed)",
    )
    correction_rate: float = Field(
        ..., ge=0.0, le=1.0,
        description="Fraction corrected (corrected / total_proposed)",
    )
    completed_at: str = Field(
        ..., description="ISO 8601 timestamp of review completion"
    )


def mapping_to_embedding_text(
    domain: str,
    sdtm_variable: str,
    mapping_pattern: str,
    mapping_logic: str,
    source_variable: str | None = None,
    source_label: str | None = None,
) -> str:
    """Convert mapping metadata to natural language text for ChromaDB embedding.

    Creates a structured sentence combining domain context with mapping
    semantics. Uses natural language (not raw JSON) because the default
    ChromaDB embedding model (all-MiniLM-L6-v2) is trained on natural
    language, not JSON (per RESEARCH.md anti-pattern guidance).

    Args:
        domain: SDTM domain code (e.g., 'AE').
        sdtm_variable: Target SDTM variable name.
        mapping_pattern: Mapping pattern used.
        mapping_logic: Human-readable mapping logic.
        source_variable: Source variable name (optional).
        source_label: Source variable label (optional).

    Returns:
        Structured natural language string for embedding.
    """
    parts = [
        f"SDTM domain {domain} variable {sdtm_variable}",
        f"mapping pattern: {mapping_pattern}",
        f"logic: {mapping_logic}",
    ]
    if source_variable:
        parts.append(f"source variable: {source_variable}")
    if source_label:
        parts.append(f"source label: {source_label}")
    return ". ".join(parts)
