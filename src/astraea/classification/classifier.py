"""LLM-based domain classifier with heuristic fusion.

Classifies raw SAS datasets to SDTM domains by combining deterministic
heuristic scores with Claude's semantic understanding. The heuristic scores
serve as both context for the LLM and a sanity check against hallucination
(Pitfall C1: hallucination cascading across the agent pipeline).
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

from astraea.classification.heuristic import (
    compute_heuristic_scores,
    detect_merge_groups,
)
from astraea.llm.client import AstraeaLLMClient
from astraea.models.classification import (
    ClassificationResult,
    DomainClassification,
    DomainPlan,
    HeuristicScore,
)
from astraea.models.ecrf import ECRFExtractionResult
from astraea.models.profiling import DatasetProfile
from astraea.reference.sdtm_ig import SDTMReference

# ---------------------------------------------------------------------------
# Internal model for LLM structured output
# ---------------------------------------------------------------------------

# Domain classes for mapping_pattern determination
_FINDINGS_DOMAINS = frozenset({"LB", "VS", "EG", "PE", "QS", "SC", "FA"})


class _LLMClassificationOutput(BaseModel):
    """Internal structured output schema for the LLM classification call."""

    primary_domain: str = Field(
        ...,
        description="Primary SDTM domain code (e.g., 'AE', 'DM') or 'UNCLASSIFIED'",
    )
    secondary_domains: list[str] = Field(
        default_factory=list,
        description="Secondary domains (e.g., ['SUPPAE']) this dataset contributes to",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Classification confidence (0.0 to 1.0)"
    )
    reasoning: str = Field(..., description="Explanation of the classification decision")
    merge_candidates: list[str] = Field(
        default_factory=list,
        description="Other dataset names that should merge with this one into the same domain",
    )


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

CLASSIFICATION_PROMPT = """\
You are classifying a raw clinical trial SAS dataset to an SDTM (Study Data \
Tabulation Model) domain.

Available SDTM domains: {available_domains}

Dataset information:
- Filename: {dataset_name}
- Row count: {row_count}
- Clinical variables (first 30):
{variable_summary}

{ecrf_context}

Heuristic analysis suggests: {heuristic_summary}

Instructions:
1. Classify this dataset to a primary SDTM domain based on its variables, \
filename, and any eCRF form association.
2. If this dataset contains variables for a supplemental qualifier domain \
(SUPPQUAL), list it in secondary_domains (e.g., "SUPPAE").
3. If this dataset should be merged with other datasets into the same domain \
(e.g., multiple lab files merging into LB), list those dataset names in \
merge_candidates.
4. If no standard SDTM domain fits, use "UNCLASSIFIED" as primary_domain.
5. Provide a confidence score (0.0 to 1.0) reflecting your certainty.
6. Explain your reasoning briefly.
"""


# ---------------------------------------------------------------------------
# Classification functions
# ---------------------------------------------------------------------------


def _build_variable_summary(profile: DatasetProfile, max_vars: int = 30) -> str:
    """Build a formatted variable summary for the LLM prompt."""
    lines: list[str] = []
    clinical_vars = [v for v in profile.variables if not v.is_edc_column]
    for v in clinical_vars[:max_vars]:
        label = v.label or "(no label)"
        lines.append(f"  - {v.name}: {v.dtype}, label='{label}'")
    if len(clinical_vars) > max_vars:
        lines.append(f"  ... and {len(clinical_vars) - max_vars} more variables")
    return "\n".join(lines) if lines else "  (no clinical variables)"


def _build_heuristic_summary(scores: list[HeuristicScore]) -> str:
    """Format heuristic scores for the LLM prompt."""
    if not scores or (len(scores) == 1 and scores[0].domain == "UNCLASSIFIED"):
        return "No strong heuristic match found."
    parts = [f"{s.domain} ({s.score:.2f})" for s in scores[:5]]
    return ", ".join(parts)


def classify_dataset(
    *,
    dataset_name: str,
    profile: DatasetProfile,
    heuristic_scores: list[HeuristicScore],
    ecrf_form_name: str | None,
    client: AstraeaLLMClient,
    ref: SDTMReference,
) -> DomainClassification:
    """Classify a single dataset to an SDTM domain using heuristic + LLM fusion.

    Args:
        dataset_name: Raw dataset filename.
        profile: Profiled dataset metadata.
        heuristic_scores: Pre-computed heuristic scores for this dataset.
        ecrf_form_name: Associated eCRF form name, if known.
        client: Configured LLM client.
        ref: SDTM-IG reference.

    Returns:
        DomainClassification with fused confidence score.
    """
    # Build prompt context
    variable_summary = _build_variable_summary(profile)
    heuristic_summary = _build_heuristic_summary(heuristic_scores)
    available_domains = ", ".join(ref.list_domains())

    ecrf_context = ""
    if ecrf_form_name:
        ecrf_context = (
            f"eCRF form association: This dataset is associated with "
            f"the '{ecrf_form_name}' eCRF form."
        )

    prompt = CLASSIFICATION_PROMPT.format(
        available_domains=available_domains,
        dataset_name=dataset_name,
        row_count=profile.row_count,
        variable_summary=variable_summary,
        ecrf_context=ecrf_context,
        heuristic_summary=heuristic_summary,
    )

    # Call LLM
    llm_result = client.parse(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": prompt}],
        output_format=_LLMClassificationOutput,
        temperature=0.1,
        max_tokens=1024,
    )

    # Fuse heuristic and LLM scores
    top_heuristic = heuristic_scores[0] if heuristic_scores else None
    top_heuristic_score = (
        top_heuristic.score if top_heuristic and top_heuristic.domain != "UNCLASSIFIED" else 0.0
    )
    top_heuristic_domain = (
        top_heuristic.domain if top_heuristic and top_heuristic.domain != "UNCLASSIFIED" else None
    )

    final_domain = llm_result.primary_domain.upper()
    final_confidence = llm_result.confidence

    if (
        top_heuristic_score >= 0.95
        and top_heuristic_domain is not None
        and top_heuristic_domain != final_domain
    ):
        # Override LLM with very-high-confidence heuristic (prevents
        # hallucination cascading -- Pitfall C1)
        logger.warning(
            "Heuristic override (score={h_score:.2f}): using {h_domain} "
            "instead of LLM {l_domain} for {name}",
            h_score=top_heuristic_score,
            h_domain=top_heuristic_domain,
            l_domain=final_domain,
            name=dataset_name,
        )
        final_domain = top_heuristic_domain
        final_confidence = top_heuristic_score
    elif top_heuristic_score >= 0.9 and top_heuristic_domain == final_domain:
        # Strong agreement: boost confidence
        final_confidence = max(top_heuristic_score, llm_result.confidence)
    elif (
        top_heuristic_score >= 0.8
        and top_heuristic_domain is not None
        and top_heuristic_domain != final_domain
    ):
        # Disagreement with moderate heuristic: flag for review
        logger.warning(
            "Heuristic-LLM disagreement for {name}: "
            "heuristic={h_domain} ({h_score:.2f}), LLM={l_domain} ({l_conf:.2f})",
            name=dataset_name,
            h_domain=top_heuristic_domain,
            h_score=top_heuristic_score,
            l_domain=final_domain,
            l_conf=llm_result.confidence,
        )
        final_confidence = min(top_heuristic_score, llm_result.confidence) * 0.7

    return DomainClassification(
        raw_dataset=dataset_name,
        primary_domain=final_domain,
        secondary_domains=llm_result.secondary_domains,
        confidence=round(final_confidence, 3),
        reasoning=llm_result.reasoning,
        merge_candidates=llm_result.merge_candidates,
        heuristic_scores=heuristic_scores,
    )


def _determine_mapping_pattern(domain: str, source_count: int, ref: SDTMReference | None) -> str:
    """Determine the mapping pattern for a domain plan.

    Returns:
        One of "direct", "merge", "transpose", or "mixed".
    """
    is_findings = domain.upper() in _FINDINGS_DOMAINS
    if not is_findings and ref is not None:
        # Also check via SDTM reference
        from astraea.models.sdtm import DomainClass

        domain_class = ref.get_domain_class(domain)
        if domain_class == DomainClass.FINDINGS:
            is_findings = True

    if source_count == 1 and not is_findings:
        return "direct"
    elif source_count == 1 and is_findings:
        return "transpose"
    elif source_count > 1 and not is_findings:
        return "merge"
    else:
        return "mixed"  # multi-source + findings (merge + transpose)


def classify_all(
    profiles: list[DatasetProfile],
    ecrf_result: ECRFExtractionResult | None = None,
    form_matches: dict[str, list[tuple[str, float]]] | None = None,
    client: AstraeaLLMClient | None = None,
    ref: SDTMReference | None = None,
) -> ClassificationResult:
    """Classify all datasets to SDTM domains with heuristic + LLM fusion.

    Orchestrator function that:
    1. Computes heuristic scores per dataset
    2. Finds associated eCRF form (if available)
    3. Calls classify_dataset for each profile
    4. Detects merge groups
    5. Builds DomainPlan objects

    Args:
        profiles: List of profiled raw datasets.
        ecrf_result: Optional parsed eCRF result.
        form_matches: Optional form-to-dataset matches (from form_dataset_matcher).
        client: Optional LLM client. Created if None.
        ref: Optional SDTM-IG reference. Created if None.

    Returns:
        ClassificationResult with all classifications, domain plans, and
        unclassified list.
    """
    if client is None:
        client = AstraeaLLMClient()
    if ref is None:
        ref = SDTMReference()

    # Invert form_matches to get dataset -> form_name lookup
    dataset_to_form: dict[str, str] = {}
    if form_matches:
        for form_name, matches in form_matches.items():
            for dataset_name, _score in matches:
                # Take the first (highest-scoring) form for each dataset
                if dataset_name not in dataset_to_form:
                    dataset_to_form[dataset_name] = form_name

    # Classify each dataset
    classifications: list[DomainClassification] = []
    for profile in profiles:
        heuristic_scores = compute_heuristic_scores(profile.filename, profile=profile, ref=ref)
        ecrf_form_name = dataset_to_form.get(profile.filename)

        classification = classify_dataset(
            dataset_name=profile.filename,
            profile=profile,
            heuristic_scores=heuristic_scores,
            ecrf_form_name=ecrf_form_name,
            client=client,
            ref=ref,
        )
        classifications.append(classification)

    # Detect merge groups from filenames
    all_dataset_names = [p.filename for p in profiles]
    heuristic_merge_groups = detect_merge_groups(all_dataset_names)

    # Build domain plans
    domain_sources: dict[str, list[str]] = {}
    for cls in classifications:
        if cls.primary_domain == "UNCLASSIFIED":
            continue
        domain_sources.setdefault(cls.primary_domain, []).append(cls.raw_dataset)
        # Also add merge candidates from LLM
        for candidate in cls.merge_candidates:
            if candidate not in domain_sources.get(cls.primary_domain, []):
                domain_sources.setdefault(cls.primary_domain, []).append(candidate)

    # Cross-reference with heuristic merge groups
    for domain, members in heuristic_merge_groups.items():
        existing = domain_sources.get(domain, [])
        for member in members:
            if member not in existing:
                domain_sources.setdefault(domain, []).append(member)

    domain_plans: list[DomainPlan] = []
    for domain, sources in sorted(domain_sources.items()):
        pattern = _determine_mapping_pattern(domain, len(sources), ref)
        domain_plans.append(
            DomainPlan(
                domain=domain,
                source_datasets=sorted(sources),
                mapping_pattern=pattern,
                notes="",
            )
        )

    # Collect unclassified
    unclassified = [
        cls.raw_dataset for cls in classifications if cls.primary_domain == "UNCLASSIFIED"
    ]

    result = ClassificationResult(
        classifications=classifications,
        domain_plans=domain_plans,
        unclassified_datasets=unclassified,
    )

    logger.info(
        "Classified {n} datasets to {m} domains, {k} unclassified",
        n=len(classifications),
        m=len(domain_plans),
        k=len(unclassified),
    )

    return result


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def save_classification(
    result: ClassificationResult,
    output_path: str | Path,
) -> None:
    """Save a ClassificationResult to JSON for caching.

    Args:
        result: The classification result to persist.
        output_path: File path to write the JSON to.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2))
    logger.info("Saved classification to {path}", path=path)


def load_classification(path: str | Path) -> ClassificationResult:
    """Load a cached ClassificationResult from JSON.

    Args:
        path: File path to read the JSON from.

    Returns:
        Validated ClassificationResult.

    Raises:
        FileNotFoundError: If path does not exist.
    """
    p = Path(path)
    if not p.exists():
        msg = f"Classification cache not found: {p}"
        raise FileNotFoundError(msg)

    raw = p.read_text()
    result = ClassificationResult.model_validate_json(raw)
    logger.info(
        "Loaded classification from {path}: {n} datasets",
        path=p,
        n=len(result.classifications),
    )
    return result
