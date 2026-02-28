"""Tests for DSPy optimizer wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import dspy

    HAS_DSPY = True
except ImportError:
    HAS_DSPY = False

pytestmark = pytest.mark.skipif(not HAS_DSPY, reason="dspy not installed")

from astraea.learning.dspy_optimizer import (  # noqa: E402
    SDTMMapperModule,
    _extract_pattern,
    _extract_variable_name,
    build_trainset,
    load_compiled_program,
    mapping_accuracy_metric,
)
from astraea.learning.models import MappingExample  # noqa: E402


def _make_example(
    domain: str = "AE",
    sdtm_variable: str = "AETERM",
    mapping_pattern: str = "direct",
    mapping_logic: str = "Direct carry from source",
    source_variable: str | None = "AETERM",
    source_label: str | None = "Adverse Event Term",
) -> MappingExample:
    """Create a test MappingExample."""
    return MappingExample(
        example_id=f"test_{domain}_{sdtm_variable}",
        study_id="TEST-001",
        domain=domain,
        sdtm_variable=sdtm_variable,
        mapping_pattern=mapping_pattern,
        mapping_logic=mapping_logic,
        source_variable=source_variable,
        source_label=source_label,
        confidence=0.9,
        was_corrected=False,
        final_mapping_json="{}",
    )


class TestBuildTrainset:
    """Tests for build_trainset function."""

    def test_returns_none_when_insufficient_examples(self, tmp_path: Path) -> None:
        """Should return None when fewer than min_examples available."""
        from astraea.learning.example_store import ExampleStore

        store = ExampleStore(tmp_path / "test.db")
        # Save only 3 examples (less than default min of 10)
        for i in range(3):
            store.save_example(_make_example(sdtm_variable=f"VAR{i}"))

        result = build_trainset(store, domain="AE", min_examples=10)
        assert result is None

    def test_returns_examples_when_sufficient(self, tmp_path: Path) -> None:
        """Should return list of dspy.Example when enough data exists."""
        from astraea.learning.example_store import ExampleStore

        store = ExampleStore(tmp_path / "test.db")
        # Save 12 examples
        for i in range(12):
            store.save_example(_make_example(sdtm_variable=f"VAR{i}"))

        result = build_trainset(store, domain="AE", min_examples=10)
        assert result is not None
        assert len(result) == 12
        assert isinstance(result[0], dspy.Example)

    def test_example_has_correct_fields(self, tmp_path: Path) -> None:
        """Each Example has domain_spec, source_profile, ecrf_context, variable_mapping."""
        from astraea.learning.example_store import ExampleStore

        store = ExampleStore(tmp_path / "test.db")
        for i in range(10):
            store.save_example(_make_example(sdtm_variable=f"VAR{i}"))

        result = build_trainset(store, domain="AE", min_examples=5)
        assert result is not None

        ex = result[0]
        assert hasattr(ex, "domain_spec")
        assert hasattr(ex, "source_profile")
        assert hasattr(ex, "ecrf_context")
        assert hasattr(ex, "variable_mapping")
        assert "Domain AE" in ex.domain_spec

    def test_custom_min_examples(self, tmp_path: Path) -> None:
        """Should respect custom min_examples parameter."""
        from astraea.learning.example_store import ExampleStore

        store = ExampleStore(tmp_path / "test.db")
        for i in range(3):
            store.save_example(_make_example(sdtm_variable=f"VAR{i}"))

        # With min=5, should fail
        assert build_trainset(store, domain="AE", min_examples=5) is None

        # With min=2, should succeed
        result = build_trainset(store, domain="AE", min_examples=2)
        assert result is not None
        assert len(result) == 3


class TestMappingAccuracyMetric:
    """Tests for mapping_accuracy_metric function."""

    def test_returns_true_on_exact_match(self) -> None:
        """Should return True when variable and pattern match."""
        example = dspy.Example(variable_mapping="AETERM -> direct from AETERM. Logic: Direct carry")
        prediction = dspy.Prediction(
            variable_mapping="AETERM -> direct from AETERM. Logic: Direct carry"
        )
        assert mapping_accuracy_metric(example, prediction) is True

    def test_returns_true_on_case_insensitive_match(self) -> None:
        """Should match case-insensitively."""
        example = dspy.Example(variable_mapping="AETERM -> DIRECT from AETERM. Logic: Direct carry")
        prediction = dspy.Prediction(
            variable_mapping="aeterm -> direct from aeterm. Logic: Direct carry"
        )
        assert mapping_accuracy_metric(example, prediction) is True

    def test_returns_false_on_variable_mismatch(self) -> None:
        """Should return False when variable names differ."""
        example = dspy.Example(variable_mapping="AETERM -> direct from AETERM. Logic: Direct carry")
        prediction = dspy.Prediction(
            variable_mapping="AEDECOD -> direct from AETERM. Logic: Direct carry"
        )
        assert mapping_accuracy_metric(example, prediction) is False

    def test_returns_false_on_pattern_mismatch(self) -> None:
        """Should return False when patterns differ."""
        example = dspy.Example(variable_mapping="AETERM -> direct from AETERM. Logic: Direct carry")
        prediction = dspy.Prediction(
            variable_mapping="AETERM -> derive from AETERM. Logic: Derivation"
        )
        assert mapping_accuracy_metric(example, prediction) is False


class TestExtractHelpers:
    """Tests for _extract_variable_name and _extract_pattern."""

    def test_extract_variable_name(self) -> None:
        assert _extract_variable_name("AETERM -> direct from AETERM") == "AETERM"

    def test_extract_variable_name_empty(self) -> None:
        assert _extract_variable_name("") == ""

    def test_extract_pattern(self) -> None:
        assert _extract_pattern("AETERM -> direct from AETERM") == "direct"

    def test_extract_pattern_no_from(self) -> None:
        assert _extract_pattern("AETERM -> direct") == "direct"


class TestLoadCompiledProgram:
    """Tests for load_compiled_program function."""

    def test_returns_none_for_nonexistent_path(self, tmp_path: Path) -> None:
        """Should return None when path does not exist."""
        result = load_compiled_program(tmp_path / "nonexistent.json")
        assert result is None


class TestSDTMMapperModule:
    """Tests for SDTMMapperModule class."""

    def test_can_instantiate(self) -> None:
        """Should be able to create an SDTMMapperModule."""
        module = SDTMMapperModule()
        assert module is not None
