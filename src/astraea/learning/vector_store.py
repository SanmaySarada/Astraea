"""ChromaDB vector store wrapper for semantic similarity search.

Provides embedding-based retrieval of mapping examples and corrections,
enabling few-shot learning from past approved mappings and human corrections.
"""

from __future__ import annotations

from pathlib import Path

import chromadb

from astraea.learning.models import (
    CorrectionRecord,
    MappingExample,
    mapping_to_embedding_text,
)


class LearningVectorStore:
    """ChromaDB wrapper for semantic similarity search on mapping data.

    Maintains two collections:
    - approved_mappings: Approved variable mappings from completed reviews
    - corrections: Human corrections with original and corrected mapping

    Uses ChromaDB's default embedding model (all-MiniLM-L6-v2 via ONNX)
    for local, GPU-free embedding generation.
    """

    def __init__(self, persist_dir: Path) -> None:
        """Create or open ChromaDB persistent storage.

        Args:
            persist_dir: Directory for ChromaDB persistent storage.
        """
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._approved = self._client.get_or_create_collection(
            name="approved_mappings",
            metadata={"description": "Approved SDTM variable mappings from completed reviews"},
        )
        self._corrections = self._client.get_or_create_collection(
            name="corrections",
            metadata={
                "description": "Human corrections with original and corrected mapping"
            },
        )

    def add_example(self, example: MappingExample) -> None:
        """Add a mapping example to the approved_mappings collection.

        Converts the example to natural language embedding text and stores
        with metadata for filtered retrieval.

        Args:
            example: The mapping example to index.
        """
        text = mapping_to_embedding_text(
            domain=example.domain,
            sdtm_variable=example.sdtm_variable,
            mapping_pattern=example.mapping_pattern,
            mapping_logic=example.mapping_logic,
            source_variable=example.source_variable,
            source_label=example.source_label,
        )
        # ChromaDB metadata values must be str, int, float, or bool
        metadata = {
            "study_id": example.study_id,
            "domain": example.domain,
            "sdtm_variable": example.sdtm_variable,
            "mapping_pattern": example.mapping_pattern,
            "was_corrected": str(example.was_corrected).lower(),
            "confidence": example.confidence,
        }
        self._approved.upsert(
            ids=[example.example_id],
            documents=[text],
            metadatas=[metadata],
        )

    def add_correction(self, correction: CorrectionRecord) -> None:
        """Add a correction to the corrections collection.

        Creates embedding text from original + corrected logic and stores
        with metadata for filtered retrieval.

        Args:
            correction: The correction record to index.
        """
        parts = [
            f"SDTM domain {correction.domain} variable {correction.sdtm_variable}",
            f"original pattern: {correction.original_pattern}",
            f"original logic: {correction.original_logic}",
        ]
        if correction.corrected_pattern:
            parts.append(f"corrected pattern: {correction.corrected_pattern}")
        if correction.corrected_logic:
            parts.append(f"corrected logic: {correction.corrected_logic}")
        parts.append(f"reason: {correction.reason}")
        text = ". ".join(parts)

        metadata = {
            "study_id": correction.study_id,
            "domain": correction.domain,
            "sdtm_variable": correction.sdtm_variable,
            "correction_type": correction.correction_type,
            "original_pattern": correction.original_pattern,
            "corrected_pattern": correction.corrected_pattern or "",
            "invalidated": str(correction.invalidated).lower(),
        }
        self._corrections.upsert(
            ids=[correction.correction_id],
            documents=[text],
            metadatas=[metadata],
        )

    def query_similar_mappings(
        self,
        domain: str,
        query_text: str,
        n_results: int = 5,
    ) -> list[dict]:
        """Query approved mappings by semantic similarity with domain filter.

        Args:
            domain: SDTM domain code to filter by.
            query_text: Natural language query for similarity search.
            n_results: Maximum number of results to return.

        Returns:
            List of dicts with keys: document, metadata, distance.
            Empty list if no results found.
        """
        # Check collection has documents before querying
        if self._approved.count() == 0:
            return []

        results = self._approved.query(
            query_texts=[query_text],
            n_results=min(n_results, self._approved.count()),
            where={"domain": domain},
        )

        output = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                output.append({
                    "document": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                })
        return output

    def query_similar_corrections(
        self,
        domain: str,
        query_text: str,
        n_results: int = 3,
    ) -> list[dict]:
        """Query corrections by semantic similarity with domain filter.

        Excludes invalidated corrections from results.

        Args:
            domain: SDTM domain code to filter by.
            query_text: Natural language query for similarity search.
            n_results: Maximum number of results to return.

        Returns:
            List of dicts with keys: document, metadata, distance.
            Empty list if no results found.
        """
        if self._corrections.count() == 0:
            return []

        results = self._corrections.query(
            query_texts=[query_text],
            n_results=min(n_results, self._corrections.count()),
            where={
                "$and": [
                    {"domain": domain},
                    {"invalidated": "false"},
                ]
            },
        )

        output = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                output.append({
                    "document": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                })
        return output

    def get_collection_counts(self) -> dict[str, int]:
        """Return document counts for each collection.

        Returns:
            Dict with keys 'approved_mappings' and 'corrections'.
        """
        return {
            "approved_mappings": self._approved.count(),
            "corrections": self._corrections.count(),
        }

    def close(self) -> None:
        """No-op for ChromaDB PersistentClient (auto-persists).

        Included for API consistency with ExampleStore.
        """
