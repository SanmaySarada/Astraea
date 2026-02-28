"""Review-to-learning ingestion pipeline.

Extracts approved mappings and corrections from completed domain reviews
and ingests them into both the SQLite example store and ChromaDB vector
store. Also computes and saves accuracy metrics per domain.

Ingestion is idempotent: re-ingesting the same review does not create
duplicates thanks to deterministic IDs based on study + domain + variable.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from astraea.learning.example_store import ExampleStore
from astraea.learning.metrics import compute_domain_accuracy
from astraea.learning.models import CorrectionRecord, MappingExample
from astraea.learning.vector_store import LearningVectorStore
from astraea.review.models import (
    CorrectionType,
    DomainReview,
    DomainReviewStatus,
    ReviewSession,
    ReviewStatus,
)


def ingest_domain_review(
    domain_review: DomainReview,
    study_id: str,
    example_store: ExampleStore,
    vector_store: LearningVectorStore,
    *,
    session_id: str = "",
) -> int:
    """Ingest a completed domain review into the learning stores.

    For each variable mapping in the reviewed spec (or original spec if
    no reviewed spec exists), creates a MappingExample with a deterministic
    ID and saves it to both the SQLite store and ChromaDB vector store.

    For each correction in the domain review, creates a CorrectionRecord
    with a deterministic ID and saves it to both stores.

    Args:
        domain_review: Completed domain review with decisions and corrections.
        study_id: Study identifier for the examples.
        example_store: SQLite-backed structured storage.
        vector_store: ChromaDB vector store for semantic search.
        session_id: Review session ID (used for correction IDs).

    Returns:
        Total count of examples + corrections ingested.
    """
    # Use reviewed spec if available, else original
    spec = domain_review.reviewed_spec or domain_review.original_spec
    domain = spec.domain
    count = 0

    # Build set of corrected variables for quick lookup
    corrected_vars: set[str] = set()
    for decision in domain_review.decisions.values():
        if decision.status == ReviewStatus.CORRECTED and decision.correction_type not in (
            CorrectionType.REJECT,
            CorrectionType.ADD,
        ):
            corrected_vars.add(decision.sdtm_variable)

    # Ingest each variable mapping as a MappingExample
    for mapping in spec.variable_mappings:
        example_id = f"{study_id}_{domain}_{mapping.sdtm_variable}"
        example = MappingExample(
            example_id=example_id,
            study_id=study_id,
            domain=domain,
            sdtm_variable=mapping.sdtm_variable,
            mapping_pattern=mapping.mapping_pattern.value,
            mapping_logic=mapping.mapping_logic,
            source_variable=mapping.source_variable,
            source_dataset=mapping.source_dataset,
            source_label=mapping.source_label,
            confidence=mapping.confidence,
            was_corrected=mapping.sdtm_variable in corrected_vars,
            final_mapping_json=mapping.model_dump_json(),
        )
        example_store.save_example(example)
        vector_store.add_example(example)
        count += 1

    # Ingest each correction as a CorrectionRecord
    for correction in domain_review.corrections:
        correction_id = (
            f"{session_id}_{domain}_{correction.sdtm_variable}_{correction.correction_type.value}"
        )
        record = CorrectionRecord(
            correction_id=correction_id,
            study_id=study_id,
            session_id=correction.session_id,
            domain=domain,
            sdtm_variable=correction.sdtm_variable,
            correction_type=correction.correction_type.value,
            original_pattern=correction.original_mapping.mapping_pattern.value,
            corrected_pattern=(
                correction.corrected_mapping.mapping_pattern.value
                if correction.corrected_mapping
                else None
            ),
            original_logic=correction.original_mapping.mapping_logic,
            corrected_logic=(
                correction.corrected_mapping.mapping_logic if correction.corrected_mapping else None
            ),
            reason=correction.reason,
        )
        example_store.save_correction(record)
        vector_store.add_correction(record)
        count += 1

    logger.info(
        "Ingested {} items for domain {} (study {})",
        count,
        domain,
        study_id,
    )
    return count


def ingest_session(
    session: ReviewSession,
    example_store: ExampleStore,
    vector_store: LearningVectorStore,
) -> dict[str, Any]:
    """Ingest all completed domain reviews from a session.

    Iterates over all domain reviews in the session, ingests those
    that are completed, and computes/saves accuracy metrics for each.

    Args:
        session: Review session with domain reviews.
        example_store: SQLite-backed structured storage.
        vector_store: ChromaDB vector store for semantic search.

    Returns:
        Summary dict with keys:
        - total_examples: int
        - total_corrections: int
        - domains_ingested: list[str]
    """
    total_examples = 0
    total_corrections = 0
    domains_ingested: list[str] = []

    for domain, review in session.domain_reviews.items():
        if review.status != DomainReviewStatus.COMPLETED:
            logger.debug("Skipping domain {} (status: {})", domain, review.status)
            continue

        ingest_domain_review(
            domain_review=review,
            study_id=session.study_id,
            example_store=example_store,
            vector_store=vector_store,
            session_id=session.session_id,
        )

        # Count examples vs corrections separately
        spec = review.reviewed_spec or review.original_spec
        n_examples = len(spec.variable_mappings)
        n_corrections = len(review.corrections)
        total_examples += n_examples
        total_corrections += n_corrections

        # Compute and save accuracy metrics
        metrics = compute_domain_accuracy(review, session.study_id)
        example_store.save_metrics(metrics)

        domains_ingested.append(domain)
        logger.info(
            "Domain {} metrics: accuracy={:.1%}, corrections={}",
            domain,
            metrics.accuracy_rate,
            metrics.corrected,
        )

    return {
        "total_examples": total_examples,
        "total_corrections": total_corrections,
        "domains_ingested": domains_ingested,
    }
