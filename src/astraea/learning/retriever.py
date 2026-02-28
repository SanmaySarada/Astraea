"""Learning retriever for few-shot example injection into mapping prompts.

Queries the vector store for relevant past mapping examples and corrections,
formats them as a readable prompt section, and returns them for injection
into the mapping engine's LLM context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from astraea.learning.vector_store import LearningVectorStore
    from astraea.models.profiling import DatasetProfile


class LearningRetriever:
    """Retrieves and formats past mapping examples for prompt injection.

    Queries the ChromaDB vector store for semantically similar approved
    mappings and corrections, prioritizes corrections (higher learning
    signal), and formats them as a readable markdown section for the
    mapping engine's LLM prompt.

    Usage::

        retriever = LearningRetriever(vector_store)
        section = retriever.get_examples_section(
            domain="AE",
            source_profiles=[ae_profile],
        )
        # section is a markdown string or None (cold start)
    """

    def __init__(self, vector_store: LearningVectorStore) -> None:
        """Initialize with a vector store instance.

        Args:
            vector_store: ChromaDB vector store for similarity queries.
        """
        self._store = vector_store

    def build_query_text(
        self,
        domain: str,
        source_profiles: list[DatasetProfile],
    ) -> str:
        """Build a natural language query from domain and source profiles.

        Combines the domain name with the first 10 non-EDC variable names
        and labels from the source profiles.

        Args:
            domain: SDTM domain code (e.g., "AE").
            source_profiles: Source dataset profiles.

        Returns:
            Natural language description for similarity search.
        """
        parts = [f"SDTM domain {domain} mapping"]

        # Collect clinical (non-EDC) variables from all profiles
        clinical_vars: list[str] = []
        for profile in source_profiles:
            for var in profile.variables:
                if not var.is_edc_column and len(clinical_vars) < 10:
                    label_part = f" ({var.label})" if var.label else ""
                    clinical_vars.append(f"{var.name}{label_part}")

        if clinical_vars:
            parts.append(f"Source variables: {', '.join(clinical_vars)}")

        return ". ".join(parts)

    def get_examples_section(
        self,
        *,
        domain: str,
        source_profiles: list[DatasetProfile],
        max_examples: int = 5,
    ) -> str | None:
        """Retrieve and format relevant past examples for prompt injection.

        Queries corrections first (up to 3), then fills with approved
        mappings up to max_examples total. Returns None on cold start
        (no data in vector store).

        Args:
            domain: SDTM domain code to search for.
            source_profiles: Source dataset profiles for query building.
            max_examples: Maximum total examples to include.

        Returns:
            Formatted markdown section string, or None if no examples found.
        """
        query_text = self.build_query_text(domain, source_profiles)

        # Query corrections first (higher learning signal)
        corrections = self._store.query_similar_corrections(
            domain=domain,
            query_text=query_text,
            n_results=3,
        )

        # Query approved mappings
        approved = self._store.query_similar_mappings(
            domain=domain,
            query_text=query_text,
            n_results=max_examples,
        )

        # Cold start: no data at all
        if not corrections and not approved:
            logger.debug(
                "No learning examples found for domain {domain} (cold start)",
                domain=domain,
            )
            return None

        section = self.format_examples_section(
            approved=approved,
            corrections=corrections,
            max_total=max_examples,
        )

        example_count = min(len(corrections), 3) + min(
            len(approved), max_examples - min(len(corrections), 3)
        )
        logger.info(
            "Retrieved {n} learning examples for domain {domain}",
            n=example_count,
            domain=domain,
        )

        return section

    def format_examples_section(
        self,
        approved: list[dict],
        corrections: list[dict],
        max_total: int = 5,
    ) -> str:
        """Format retrieved examples into a readable markdown prompt section.

        Corrections appear first (up to 3), then approved examples fill
        remaining slots up to max_total.

        Args:
            approved: List of approved mapping result dicts from vector store.
            corrections: List of correction result dicts from vector store.
            max_total: Maximum total examples to include.

        Returns:
            Markdown-formatted examples section.
        """
        lines: list[str] = [
            "## Relevant Past Mapping Examples",
            "",
            "The following examples are from previously approved mappings for similar variables.",
            "Use them as reference, but adapt to the current source data.",
            "",
        ]

        count = 0

        # Corrections first (up to 3)
        for i, corr in enumerate(corrections[:3]):
            if count >= max_total:
                break
            lines.append(f"### Correction Example {i + 1}")
            lines.extend(_format_correction(corr))
            lines.append("")
            count += 1

        # Fill remaining with approved examples
        remaining = max_total - count
        for i, appr in enumerate(approved[:remaining]):
            if count >= max_total:
                break
            lines.append(f"### Approved Example {i + 1}")
            lines.extend(_format_approved(appr))
            lines.append("")
            count += 1

        return "\n".join(lines)


def _format_correction(corr: dict) -> list[str]:
    """Format a single correction result for the prompt.

    Args:
        corr: Correction result dict with 'document' and 'metadata' keys.

    Returns:
        List of formatted lines.
    """
    meta = corr.get("metadata", {})
    doc = corr.get("document", "")
    lines: list[str] = []

    variable = meta.get("sdtm_variable", "unknown")
    lines.append(f"Variable: {variable}")

    # Try to extract WRONG/CORRECT from document text
    original_logic = None
    corrected_logic = None

    if "WRONG:" in doc and "CORRECT:" in doc:
        # Explicit markers in document
        for part in doc.split(". "):
            if part.strip().startswith("WRONG:"):
                original_logic = part.strip().removeprefix("WRONG:").strip()
            elif part.strip().startswith("CORRECT:"):
                corrected_logic = part.strip().removeprefix("CORRECT:").strip()
    else:
        # Reconstruct from document parts
        for part in doc.split(". "):
            if "original logic:" in part.lower():
                original_logic = part.split(":", 1)[1].strip()
            elif "corrected logic:" in part.lower():
                corrected_logic = part.split(":", 1)[1].strip()

    original_pattern = meta.get("original_pattern", "")
    corrected_pattern = meta.get("corrected_pattern", "")

    wrong_desc = original_logic or f"{original_pattern} mapping"
    correct_desc = corrected_logic or f"{corrected_pattern} mapping"

    lines.append(f"WRONG approach: {wrong_desc}")
    lines.append(f"CORRECT approach: {correct_desc}")

    # Extract reason from document
    for part in doc.split(". "):
        if part.strip().lower().startswith("reason:"):
            reason = part.split(":", 1)[1].strip()
            lines.append(f"Reason: {reason}")
            break

    return lines


def _format_approved(appr: dict) -> list[str]:
    """Format a single approved mapping result for the prompt.

    Args:
        appr: Approved mapping result dict with 'document' and 'metadata' keys.

    Returns:
        List of formatted lines.
    """
    meta = appr.get("metadata", {})
    doc = appr.get("document", "")
    lines: list[str] = []

    variable = meta.get("sdtm_variable", "unknown")
    domain = meta.get("domain", "")
    pattern = meta.get("mapping_pattern", "")

    variable_display = f"{variable} ({domain})" if domain else variable
    lines.append(f"Variable: {variable_display}")
    lines.append(f"Pattern: {pattern}")

    # Extract logic from document
    for part in doc.split(". "):
        if part.strip().lower().startswith("logic:"):
            logic = part.split(":", 1)[1].strip()
            lines.append(f"Logic: {logic}")
            break

    # Extract source from document
    for part in doc.split(". "):
        if part.strip().lower().startswith("source variable:"):
            source = part.split(":", 1)[1].strip()
            lines.append(f"Source: {source}")
            break

    return lines
