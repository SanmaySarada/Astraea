"""Domain classification models.

These models represent the results of classifying raw SAS datasets to SDTM
domains. Includes heuristic scoring, LLM-based classification with confidence
and reasoning, and the resulting domain plan for downstream mapping.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HeuristicScore(BaseModel):
    """Deterministic heuristic score for a candidate domain match.

    Produced by rule-based analysis of filename, variable names, and SAS labels
    before any LLM involvement.
    """

    domain: str = Field(..., description="SDTM domain code (e.g., 'AE', 'DM', 'LB')")
    score: float = Field(..., ge=0.0, le=1.0, description="Heuristic confidence score (0.0 to 1.0)")
    signals: list[str] = Field(
        default_factory=list,
        description="What matched (e.g., 'filename exact match', 'variable AETERM found')",
    )


class DomainClassification(BaseModel):
    """Classification result for a single raw dataset.

    Captures the primary domain assignment, any secondary domains (e.g., SUPPQUAL),
    confidence score, and the LLM's reasoning.
    """

    raw_dataset: str = Field(..., description="Raw SAS dataset filename (e.g., 'ae.sas7bdat')")
    primary_domain: str = Field(
        ...,
        description="Primary SDTM domain code (e.g., 'AE') or 'UNCLASSIFIED'",
    )
    secondary_domains: list[str] = Field(
        default_factory=list,
        description="Secondary domains this dataset contributes to (e.g., ['SUPPAE'])",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Classification confidence (0.0 to 1.0)"
    )
    reasoning: str = Field(default="", description="Explanation of the classification decision")
    merge_candidates: list[str] = Field(
        default_factory=list,
        description="Other datasets that should merge with this one into the same domain",
    )
    heuristic_scores: list[HeuristicScore] = Field(
        default_factory=list,
        description="Heuristic scores considered during classification",
    )


class DomainPlan(BaseModel):
    """Mapping plan for a single SDTM domain.

    Describes which source datasets feed into this domain and the expected
    mapping pattern (direct 1:1, merge multiple sources, transpose, or mixed).
    """

    domain: str = Field(..., description="SDTM domain code (e.g., 'LB', 'AE')")
    source_datasets: list[str] = Field(
        default_factory=list,
        description="Raw datasets contributing to this domain",
    )
    mapping_pattern: Literal["direct", "merge", "transpose", "mixed"] = Field(
        ..., description="Expected mapping pattern for this domain"
    )
    notes: str = Field(default="", description="Additional notes about the mapping plan")


class ClassificationResult(BaseModel):
    """Complete result of the domain classification stage.

    Contains per-dataset classifications, the consolidated domain plans,
    and a list of any datasets that could not be classified.
    """

    classifications: list[DomainClassification] = Field(
        default_factory=list, description="Per-dataset classification results"
    )
    domain_plans: list[DomainPlan] = Field(
        default_factory=list, description="Consolidated domain mapping plans"
    )
    unclassified_datasets: list[str] = Field(
        default_factory=list, description="Datasets that could not be classified"
    )
