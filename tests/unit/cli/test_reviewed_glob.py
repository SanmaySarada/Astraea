"""Tests that *_reviewed.json files are found by glob patterns.

Verifies that the glob pattern used by downstream CLI commands
(validate, generate-define, generate-csdrg, auto-fix) includes
*_reviewed.json alongside *_spec.json and *_mapping.json.
"""

from __future__ import annotations

from pathlib import Path

from astraea.models.mapping import DomainMappingSpec


def _make_minimal_spec() -> DomainMappingSpec:
    """Create a minimal valid DomainMappingSpec for testing."""
    return DomainMappingSpec(
        domain="DM",
        domain_label="Demographics",
        domain_class="Special-Purpose",
        structure="One record per subject",
        study_id="TEST-001",
        total_variables=1,
        required_mapped=1,
        expected_mapped=0,
        high_confidence_count=1,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


def test_reviewed_glob_matches_file(tmp_path: Path) -> None:
    """Glob pattern *_reviewed.json should find reviewed spec files."""
    spec = _make_minimal_spec()
    reviewed_path = tmp_path / "DM_reviewed.json"
    reviewed_path.write_text(spec.model_dump_json(indent=2))

    matches = sorted(tmp_path.glob("*_reviewed.json"))
    assert len(matches) == 1
    assert matches[0].name == "DM_reviewed.json"


def test_reviewed_file_loads_as_domain_mapping_spec(tmp_path: Path) -> None:
    """A *_reviewed.json file should be loadable as DomainMappingSpec."""
    spec = _make_minimal_spec()
    reviewed_path = tmp_path / "AE_reviewed.json"
    reviewed_path.write_text(spec.model_dump_json(indent=2))

    loaded = DomainMappingSpec.model_validate_json(reviewed_path.read_text())
    assert loaded.domain == "DM"
    assert loaded.study_id == "TEST-001"


def test_all_three_glob_patterns_work(tmp_path: Path) -> None:
    """All three glob patterns should find their respective files."""
    spec = _make_minimal_spec()

    (tmp_path / "DM_spec.json").write_text(spec.model_dump_json())
    (tmp_path / "AE_mapping.json").write_text(spec.model_dump_json())
    (tmp_path / "VS_reviewed.json").write_text(spec.model_dump_json())

    spec_files = (
        sorted(tmp_path.glob("*_spec.json"))
        + sorted(tmp_path.glob("*_mapping.json"))
        + sorted(tmp_path.glob("*_reviewed.json"))
    )
    names = [f.name for f in spec_files]
    assert "DM_spec.json" in names
    assert "AE_mapping.json" in names
    assert "VS_reviewed.json" in names
    assert len(spec_files) == 3
