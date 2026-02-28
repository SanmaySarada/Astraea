"""Tests for ChromaDB-backed LearningVectorStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from astraea.learning.models import CorrectionRecord, MappingExample
from astraea.learning.vector_store import LearningVectorStore


@pytest.fixture
def vstore(tmp_path: Path) -> LearningVectorStore:
    """Create a LearningVectorStore with temporary storage."""
    return LearningVectorStore(tmp_path / "chroma_test")


def _make_example(
    domain: str = "AE",
    sdtm_variable: str = "AETERM",
    **kwargs,
) -> MappingExample:
    """Helper to create a MappingExample with defaults."""
    defaults = {
        "study_id": "STUDY001",
        "domain": domain,
        "sdtm_variable": sdtm_variable,
        "mapping_pattern": "direct",
        "mapping_logic": "Direct carry from source",
        "confidence": 0.95,
        "final_mapping_json": '{"sdtm_variable": "' + sdtm_variable + '"}',
    }
    defaults.update(kwargs)
    return MappingExample(**defaults)


def _make_correction(
    domain: str = "AE",
    sdtm_variable: str = "AEDECOD",
    **kwargs,
) -> CorrectionRecord:
    """Helper to create a CorrectionRecord with defaults."""
    defaults = {
        "study_id": "STUDY001",
        "session_id": "abc123",
        "domain": domain,
        "sdtm_variable": sdtm_variable,
        "correction_type": "logic_change",
        "original_pattern": "direct",
        "original_logic": "Direct carry from AETERM",
        "corrected_pattern": "derivation",
        "corrected_logic": "MedDRA preferred term lookup",
        "reason": "AEDECOD requires dictionary coding",
    }
    defaults.update(kwargs)
    return CorrectionRecord(**defaults)


class TestLearningVectorStoreExamples:
    """Tests for adding and querying mapping examples."""

    def test_add_and_query_example(self, vstore: LearningVectorStore) -> None:
        """Added example can be retrieved via query."""
        example = _make_example()
        vstore.add_example(example)

        results = vstore.query_similar_mappings(
            domain="AE",
            query_text="SDTM AE domain adverse event term mapping",
        )
        assert len(results) >= 1
        assert results[0]["metadata"]["domain"] == "AE"
        assert results[0]["metadata"]["sdtm_variable"] == "AETERM"
        assert "document" in results[0]
        assert "distance" in results[0]

    def test_domain_filter(self, vstore: LearningVectorStore) -> None:
        """Domain filter returns only matching domain examples."""
        vstore.add_example(_make_example(domain="AE", sdtm_variable="AETERM"))
        vstore.add_example(
            _make_example(
                domain="DM",
                sdtm_variable="USUBJID",
                mapping_logic="Derive from STUDYID + SITEID + SUBJID",
            )
        )

        ae_results = vstore.query_similar_mappings(
            domain="AE",
            query_text="adverse event term",
        )
        dm_results = vstore.query_similar_mappings(
            domain="DM",
            query_text="subject identifier",
        )

        # AE query returns only AE examples
        for r in ae_results:
            assert r["metadata"]["domain"] == "AE"

        # DM query returns only DM examples
        for r in dm_results:
            assert r["metadata"]["domain"] == "DM"


class TestLearningVectorStoreCorrections:
    """Tests for adding and querying corrections."""

    def test_add_and_query_correction(self, vstore: LearningVectorStore) -> None:
        """Added correction can be retrieved via query."""
        correction = _make_correction()
        vstore.add_correction(correction)

        results = vstore.query_similar_corrections(
            domain="AE",
            query_text="adverse event decoded term dictionary",
        )
        assert len(results) >= 1
        assert results[0]["metadata"]["domain"] == "AE"
        assert results[0]["metadata"]["correction_type"] == "logic_change"


class TestLearningVectorStoreCounts:
    """Tests for collection counts and edge cases."""

    def test_collection_counts(self, vstore: LearningVectorStore) -> None:
        """Collection counts are accurate."""
        assert vstore.get_collection_counts() == {
            "approved_mappings": 0,
            "corrections": 0,
        }

        vstore.add_example(_make_example())
        vstore.add_example(_make_example(sdtm_variable="AEDECOD", mapping_logic="Derivation"))
        vstore.add_correction(_make_correction())

        counts = vstore.get_collection_counts()
        assert counts["approved_mappings"] == 2
        assert counts["corrections"] == 1

    def test_query_empty_collection(self, vstore: LearningVectorStore) -> None:
        """Query on empty collection returns empty list."""
        results = vstore.query_similar_mappings(
            domain="AE",
            query_text="anything",
        )
        assert results == []

        correction_results = vstore.query_similar_corrections(
            domain="AE",
            query_text="anything",
        )
        assert correction_results == []

    def test_close_is_noop(self, vstore: LearningVectorStore) -> None:
        """Close method does not raise."""
        vstore.close()
