"""Tests for SQLite-backed ExampleStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from astraea.learning.example_store import ExampleStore
from astraea.learning.models import CorrectionRecord, MappingExample, StudyMetrics


@pytest.fixture
def store(tmp_path: Path) -> ExampleStore:
    """Create an ExampleStore with a temporary database."""
    s = ExampleStore(tmp_path / "test_learning.db")
    yield s
    s.close()


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
        "mapping_logic": "Direct carry",
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
        "original_logic": "Direct carry",
        "reason": "Needs derivation",
    }
    defaults.update(kwargs)
    return CorrectionRecord(**defaults)


class TestExampleStoreSaveAndRetrieve:
    """Tests for saving and retrieving examples."""

    def test_save_and_retrieve_example(self, store: ExampleStore) -> None:
        """Example survives save and retrieval."""
        example = _make_example()
        store.save_example(example)

        results = store.get_examples_for_domain("AE")
        assert len(results) == 1
        assert results[0].example_id == example.example_id
        assert results[0].study_id == "STUDY001"
        assert results[0].domain == "AE"
        assert results[0].sdtm_variable == "AETERM"
        assert results[0].confidence == 0.95

    def test_save_and_retrieve_correction(self, store: ExampleStore) -> None:
        """Correction survives save and retrieval."""
        correction = _make_correction(
            corrected_pattern="derivation",
            corrected_logic="MedDRA lookup",
        )
        store.save_correction(correction)

        results = store.get_corrections_for_domain("AE")
        assert len(results) == 1
        assert results[0].correction_id == correction.correction_id
        assert results[0].corrected_pattern == "derivation"
        assert results[0].reason == "Needs derivation"

    def test_save_and_retrieve_study_metrics(self, store: ExampleStore) -> None:
        """Study metrics survives save and retrieval."""
        metrics = StudyMetrics(
            study_id="STUDY001",
            domain="AE",
            total_proposed=20,
            approved_unchanged=15,
            corrected=3,
            rejected=1,
            added_by_reviewer=2,
            accuracy_rate=0.75,
            correction_rate=0.15,
            completed_at="2026-02-28T00:00:00+00:00",
        )
        store.save_metrics(metrics)

        results = store.get_study_metrics("STUDY001")
        assert len(results) == 1
        assert results[0].domain == "AE"
        assert results[0].accuracy_rate == 0.75
        assert results[0].total_proposed == 20


class TestExampleStoreFiltering:
    """Tests for domain filtering and invalidation."""

    def test_get_examples_filters_by_domain(self, store: ExampleStore) -> None:
        """Only examples for the requested domain are returned."""
        store.save_example(_make_example(domain="AE", sdtm_variable="AETERM"))
        store.save_example(_make_example(domain="DM", sdtm_variable="USUBJID"))
        store.save_example(_make_example(domain="AE", sdtm_variable="AEDECOD"))

        ae_examples = store.get_examples_for_domain("AE")
        dm_examples = store.get_examples_for_domain("DM")

        assert len(ae_examples) == 2
        assert len(dm_examples) == 1
        assert dm_examples[0].sdtm_variable == "USUBJID"

    def test_get_corrections_excludes_invalidated(self, store: ExampleStore) -> None:
        """Invalidated corrections are excluded by default."""
        store.save_correction(_make_correction(sdtm_variable="AETERM"))
        c2 = _make_correction(sdtm_variable="AEDECOD")
        store.save_correction(c2)
        store.invalidate_correction(c2.correction_id)

        results = store.get_corrections_for_domain("AE")
        assert len(results) == 1
        assert results[0].sdtm_variable == "AETERM"

    def test_get_corrections_includes_invalidated(self, store: ExampleStore) -> None:
        """Invalidated corrections included when requested."""
        store.save_correction(_make_correction(sdtm_variable="AETERM"))
        c2 = _make_correction(sdtm_variable="AEDECOD")
        store.save_correction(c2)
        store.invalidate_correction(c2.correction_id)

        results = store.get_corrections_for_domain("AE", include_invalidated=True)
        assert len(results) == 2

    def test_invalidate_correction(self, store: ExampleStore) -> None:
        """Invalidation marks the correction as invalidated."""
        correction = _make_correction()
        store.save_correction(correction)

        store.invalidate_correction(correction.correction_id)

        results = store.get_corrections_for_domain("AE", include_invalidated=True)
        assert len(results) == 1
        assert results[0].invalidated is True


class TestExampleStoreCounts:
    """Tests for count methods."""

    def test_get_example_count(self, store: ExampleStore) -> None:
        """Example count is accurate."""
        assert store.get_example_count() == 0
        store.save_example(_make_example(sdtm_variable="AETERM"))
        store.save_example(_make_example(sdtm_variable="AEDECOD"))
        assert store.get_example_count() == 2

    def test_get_correction_count(self, store: ExampleStore) -> None:
        """Correction count includes invalidated."""
        assert store.get_correction_count() == 0
        c1 = _make_correction(sdtm_variable="AETERM")
        store.save_correction(c1)
        store.invalidate_correction(c1.correction_id)
        store.save_correction(_make_correction(sdtm_variable="AEDECOD"))
        assert store.get_correction_count() == 2

    def test_duplicate_example_id_handled(self, store: ExampleStore) -> None:
        """Duplicate example_id replaces existing record."""
        example = _make_example(confidence=0.80)
        store.save_example(example)

        updated = MappingExample(
            example_id=example.example_id,
            study_id="STUDY001",
            domain="AE",
            sdtm_variable="AETERM",
            mapping_pattern="direct",
            mapping_logic="Updated logic",
            confidence=0.95,
            final_mapping_json='{"updated": true}',
        )
        store.save_example(updated)

        assert store.get_example_count() == 1
        results = store.get_examples_for_domain("AE")
        assert results[0].confidence == 0.95
        assert results[0].mapping_logic == "Updated logic"
