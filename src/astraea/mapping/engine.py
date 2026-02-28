"""Core mapping engine orchestrator.

Coordinates the LLM call, post-proposal validation/enrichment, and
DomainMappingSpec construction for a single SDTM domain. The LLM proposes
WHAT to map; deterministic code validates and enriches HOW.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from loguru import logger

from astraea.llm.client import AstraeaLLMClient
from astraea.mapping.context import MappingContextBuilder
from astraea.mapping.prompts import MAPPING_SYSTEM_PROMPT, MAPPING_USER_INSTRUCTIONS
from astraea.mapping.transform_registry import AVAILABLE_TRANSFORMS, get_transform
from astraea.mapping.validation import check_required_coverage, validate_and_enrich
from astraea.models.ecrf import ECRFForm
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingProposal,
    DomainMappingSpec,
    StudyMetadata,
    VariableMapping,
)
from astraea.models.profiling import DatasetProfile
from astraea.models.sdtm import CoreDesignation
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference

if TYPE_CHECKING:
    from astraea.learning.retriever import LearningRetriever
    from astraea.models.sdtm import DomainSpec

_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_DEFAULT_TEMPERATURE = 0.1
_DEFAULT_MAX_TOKENS = 4096


class MappingEngine:
    """Orchestrates LLM-based SDTM domain variable mapping.

    Coordinates the full mapping flow:
    1. Build focused context from domain spec, profiles, eCRF, CT
    2. Call Claude for structured mapping proposals
    3. Validate proposals against SDTM-IG and CT reference data
    4. Enrich with labels, core designations, codelist names
    5. Construct DomainMappingSpec with summary statistics

    Usage::

        engine = MappingEngine(llm_client, sdtm_ref, ct_ref)
        spec = engine.map_domain(
            domain="DM",
            source_profiles=[dm_profile],
            ecrf_forms=[demographics_form],
            study_metadata=study_meta,
        )
    """

    def __init__(
        self,
        llm_client: AstraeaLLMClient,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
        learning_retriever: LearningRetriever | None = None,
    ) -> None:
        """Initialize the mapping engine with its dependencies.

        Args:
            llm_client: Anthropic API client for LLM calls.
            sdtm_ref: SDTM-IG reference for domain specs.
            ct_ref: CT reference for codelist validation.
            learning_retriever: Optional retriever for injecting past
                mapping examples into LLM prompts. When None (default),
                the engine works identically to pre-learning-system behavior.
        """
        self._llm = llm_client
        self._sdtm = sdtm_ref
        self._ct = ct_ref
        self._context_builder = MappingContextBuilder(sdtm_ref, ct_ref)
        self._transforms = AVAILABLE_TRANSFORMS
        self._learning = learning_retriever

    def resolve_transform(self, name: str) -> bool:
        """Check if a named transform is available in the registry.

        Used to validate that derivation_rule references in mapping specs
        point to actual transform functions.

        Args:
            name: Transform function name (e.g., "sas_date_to_iso").

        Returns:
            True if transform exists, False otherwise.
        """
        return get_transform(name) is not None

    def map_domain(
        self,
        domain: str,
        source_profiles: list[DatasetProfile],
        ecrf_forms: list[ECRFForm],
        study_metadata: StudyMetadata,
        cross_domain_profiles: dict[str, DatasetProfile] | None = None,
        *,
        model: str = _DEFAULT_MODEL,
        temperature: float = _DEFAULT_TEMPERATURE,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> DomainMappingSpec:
        """Map a single SDTM domain from raw source data.

        Orchestrates the full mapping pipeline: context assembly,
        LLM proposal, validation, enrichment, and spec construction.

        Args:
            domain: Target SDTM domain code (e.g., "DM").
            source_profiles: Profiled source datasets for this domain.
            ecrf_forms: eCRF forms matched to this domain.
            study_metadata: Study-level constants.
            cross_domain_profiles: Optional profiles of datasets from other
                domains contributing variables to this domain.
            model: Claude model ID for the mapping call.
            temperature: Sampling temperature for the LLM call.
            max_tokens: Maximum tokens for the LLM response.

        Returns:
            Complete DomainMappingSpec with enriched, validated mappings.

        Raises:
            ValueError: If domain is not found in SDTM-IG reference.
        """
        logger.info("Starting mapping for domain {domain}", domain=domain)

        # Step 1: Get domain spec
        domain_spec = self._sdtm.get_domain_spec(domain)
        if domain_spec is None:
            msg = f"Domain '{domain}' not found in SDTM-IG reference"
            raise ValueError(msg)

        # Step 2: Build context prompt
        prompt = self._context_builder.build_prompt(
            domain=domain,
            source_profiles=source_profiles,
            ecrf_forms=ecrf_forms,
            study_metadata=study_metadata,
            cross_domain_profiles=cross_domain_profiles,
        )

        # Step 2.5: Inject learning examples if available
        examples_section = None
        if self._learning is not None:
            examples_section = self._learning.get_examples_section(
                domain=domain,
                source_profiles=source_profiles,
                max_examples=5,
            )

        # Step 3: Append user instructions
        user_instructions = MAPPING_USER_INSTRUCTIONS.format(domain=domain)
        if examples_section:
            full_prompt = prompt + "\n\n" + examples_section + "\n\n" + user_instructions
        else:
            full_prompt = prompt + "\n" + user_instructions

        # Step 4: Call LLM for structured proposal
        logger.info(
            "Calling LLM for {domain} mapping | model={model} temp={temp}",
            domain=domain,
            model=model,
            temp=temperature,
        )
        try:
            proposal = self._llm.parse(
                model=model,
                messages=[{"role": "user", "content": full_prompt}],
                system=MAPPING_SYSTEM_PROMPT,
                output_format=DomainMappingProposal,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            msg = f"LLM mapping call failed for domain '{domain}': {e}"
            logger.error(msg)
            raise RuntimeError(msg) from e

        # Step 5: Validate and enrich
        enriched_mappings, validation_issues = validate_and_enrich(proposal, domain_spec, self._ct)

        if validation_issues:
            for issue in validation_issues:
                logger.warning("Validation issue: {issue}", issue=issue)

        # Step 6: Check required coverage
        missing_required = check_required_coverage(enriched_mappings, domain_spec)
        if missing_required:
            logger.warning(
                "Missing required variables for {domain}: {vars}",
                domain=domain,
                vars=", ".join(missing_required),
            )

        # Step 7: Build final spec
        spec = _build_spec(
            domain_spec=domain_spec,
            study_id=study_metadata.study_id,
            source_profiles=source_profiles,
            enriched_mappings=enriched_mappings,
            proposal=proposal,
            model_used=model,
            missing_required_variables=missing_required,
        )

        # Step 8: Run predict-and-prevent validation
        try:
            from astraea.validation.predict import (
                predict_and_prevent,
                results_to_issue_dicts,
            )

            pp_results = predict_and_prevent(spec, domain_spec, self._ct)
            spec.predict_prevent_issues = results_to_issue_dicts(pp_results)
            error_count = sum(1 for r in pp_results if r.severity.value == "ERROR")
            if error_count:
                logger.warning(
                    "Predict-and-prevent found {count} errors for {domain}",
                    count=error_count,
                    domain=spec.domain,
                )
        except ImportError:
            logger.debug("Predict-and-prevent module not available, skipping spec-level validation")

        # Step 9: Log summary
        logger.info(
            "Mapping complete for {domain} | total={total} high={high} medium={med} low={low}",
            domain=domain,
            total=spec.total_variables,
            high=spec.high_confidence_count,
            med=spec.medium_confidence_count,
            low=spec.low_confidence_count,
        )

        return spec


def _build_spec(
    *,
    domain_spec: DomainSpec,
    study_id: str,
    source_profiles: list[DatasetProfile],
    enriched_mappings: list[VariableMapping],
    proposal: DomainMappingProposal,
    model_used: str,
    missing_required_variables: list[str] | None = None,
) -> DomainMappingSpec:
    """Construct a DomainMappingSpec from validated mappings.

    Computes summary counts (total, required/expected mapped, confidence
    distribution) and timestamps the mapping.

    Args:
        domain_spec: SDTM-IG domain specification.
        study_id: Study identifier.
        source_profiles: Source dataset profiles.
        enriched_mappings: Validated and enriched variable mappings.
        proposal: Original LLM proposal (for unmapped vars, suppqual).
        model_used: LLM model identifier.

    Returns:
        Complete DomainMappingSpec.
    """
    # Count by confidence level
    high_count = sum(1 for m in enriched_mappings if m.confidence_level == ConfidenceLevel.HIGH)
    medium_count = sum(1 for m in enriched_mappings if m.confidence_level == ConfidenceLevel.MEDIUM)
    low_count = sum(1 for m in enriched_mappings if m.confidence_level == ConfidenceLevel.LOW)

    # Count by core designation
    required_mapped = sum(1 for m in enriched_mappings if m.core == CoreDesignation.REQ)
    expected_mapped = sum(1 for m in enriched_mappings if m.core == CoreDesignation.EXP)

    # Identify cross-domain sources
    cross_domain_sources = []
    for m in enriched_mappings:
        if m.source_dataset and m.mapping_pattern in ("derivation", "lookup_recode"):
            src = m.source_dataset
            if src not in [p.filename for p in source_profiles] and src not in cross_domain_sources:
                cross_domain_sources.append(src)

    timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    return DomainMappingSpec(
        domain=domain_spec.domain,
        domain_label=domain_spec.description,
        domain_class=domain_spec.domain_class.value,
        structure=domain_spec.structure,
        study_id=study_id,
        source_datasets=[p.filename for p in source_profiles],
        cross_domain_sources=cross_domain_sources,
        variable_mappings=enriched_mappings,
        total_variables=len(enriched_mappings),
        required_mapped=required_mapped,
        expected_mapped=expected_mapped,
        high_confidence_count=high_count,
        medium_confidence_count=medium_count,
        low_confidence_count=low_count,
        mapping_timestamp=timestamp,
        model_used=model_used,
        unmapped_source_variables=proposal.unmapped_source_variables,
        suppqual_candidates=proposal.suppqual_candidates,
        missing_required_variables=missing_required_variables or [],
    )
