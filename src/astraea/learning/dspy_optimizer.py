"""DSPy prompt optimizer for SDTM mapping.

Provides a DSPy Module wrapping the mapping task, trainset construction
from the ExampleStore, a mapping accuracy metric, and compilation/loading
of optimized programs. DSPy automates few-shot example selection for
optimal mapping quality (Tier 2 learning per ARCHITECTURE.md).

All DSPy imports are guarded so the rest of the learning system works
even if dspy is not installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from astraea.learning.example_store import ExampleStore

try:
    import dspy

    HAS_DSPY = True
except ImportError:
    HAS_DSPY = False


def _require_dspy() -> None:
    """Raise ImportError with clear message if dspy is not installed."""
    if not HAS_DSPY:
        msg = (
            "dspy is required for prompt optimization but is not installed. "
            "Install it with: pip install dspy"
        )
        raise ImportError(msg)


class SDTMMapperModule:
    """DSPy module wrapping the SDTM variable mapping task.

    Uses ChainOfThought to generate variable mappings given domain spec,
    source profile, and eCRF context. This module is compiled with
    BootstrapFewShot to optimize few-shot example selection.
    """

    def __init__(self) -> None:
        """Create the ChainOfThought mapping predictor."""
        _require_dspy()
        self._module = _DSPyMapperModule()

    def forward(
        self,
        domain_spec: str,
        source_profile: str,
        ecrf_context: str,
    ) -> dspy.Prediction:
        """Run the mapping predictor.

        Args:
            domain_spec: Domain specification text.
            source_profile: Source variable profile text.
            ecrf_context: eCRF context text.

        Returns:
            dspy.Prediction with variable_mapping field.
        """
        return self._module(
            domain_spec=domain_spec,
            source_profile=source_profile,
            ecrf_context=ecrf_context,
        )

    def save(self, path: str) -> None:
        """Save the compiled module to disk."""
        self._module.save(path)

    def load(self, path: str) -> SDTMMapperModule:
        """Load a compiled module from disk."""
        self._module.load(path)
        return self


if HAS_DSPY:

    class _DSPyMapperModule(dspy.Module):
        """Internal DSPy Module subclass for compilation."""

        def __init__(self) -> None:
            super().__init__()
            self.map_variable = dspy.ChainOfThought(
                "domain_spec, source_profile, ecrf_context -> variable_mapping"
            )

        def forward(
            self,
            domain_spec: str,
            source_profile: str,
            ecrf_context: str,
        ) -> dspy.Prediction:
            return self.map_variable(
                domain_spec=domain_spec,
                source_profile=source_profile,
                ecrf_context=ecrf_context,
            )


def build_trainset(
    example_store: ExampleStore,
    domain: str | None = None,
    min_examples: int = 10,
) -> list | None:
    """Build a DSPy trainset from stored mapping examples.

    Queries the ExampleStore for approved examples (optionally filtered
    by domain) and converts each to a dspy.Example with marked inputs.

    Args:
        example_store: SQLite-backed structured storage.
        domain: Optional domain code to filter by.
        min_examples: Minimum number of examples needed (default 10).

    Returns:
        List of dspy.Example objects, or None if fewer than min_examples.
    """
    _require_dspy()

    if domain is not None:
        examples = example_store.get_examples_for_domain(domain, limit=200)
    else:
        # Get all examples by querying without domain filter
        all_metrics = example_store.get_study_metrics()
        all_domains = {m.domain for m in all_metrics}
        examples = []
        for d in all_domains:
            examples.extend(example_store.get_examples_for_domain(d, limit=200))

        # If no metrics exist, try to get count to check if there are any
        if not examples:
            count = example_store.get_example_count()
            if count == 0:
                return None

    if len(examples) < min_examples:
        logger.info(
            "Insufficient examples for optimization: {} < {}",
            len(examples),
            min_examples,
        )
        return None

    trainset = []
    for ex in examples:
        dspy_example = dspy.Example(
            domain_spec=f"Domain {ex.domain}",
            source_profile=(
                f"Source: {ex.source_variable or 'N/A'} ({ex.source_label or 'no label'})"
            ),
            ecrf_context=f"Variable: {ex.sdtm_variable}",
            variable_mapping=(
                f"{ex.sdtm_variable} -> {ex.mapping_pattern} "
                f"from {ex.source_variable}. "
                f"Logic: {ex.mapping_logic}"
            ),
        ).with_inputs("domain_spec", "source_profile", "ecrf_context")
        trainset.append(dspy_example)

    logger.info("Built trainset with {} examples", len(trainset))
    return trainset


def mapping_accuracy_metric(
    example: dspy.Example,
    prediction: dspy.Prediction,
    trace: object = None,
) -> bool:
    """Evaluate whether a prediction matches the expected mapping.

    Extracts the SDTM variable name and mapping pattern from both
    the example's variable_mapping and prediction's variable_mapping,
    returning True if both match.

    Args:
        example: Ground-truth dspy.Example.
        prediction: Model's dspy.Prediction.
        trace: Optional trace object (unused, required by DSPy API).

    Returns:
        True if variable name and pattern match.
    """
    _require_dspy()

    expected = getattr(example, "variable_mapping", "")
    predicted = getattr(prediction, "variable_mapping", "")

    # Extract variable name (first token before " ->")
    expected_var = _extract_variable_name(expected)
    predicted_var = _extract_variable_name(predicted)

    # Extract pattern (token after "-> ")
    expected_pattern = _extract_pattern(expected)
    predicted_pattern = _extract_pattern(predicted)

    return (
        expected_var.upper() == predicted_var.upper()
        and expected_pattern.upper() == predicted_pattern.upper()
    )


def _extract_variable_name(mapping_str: str) -> str:
    """Extract the SDTM variable name from a mapping string.

    Expected format: "VARNAME -> pattern from source. Logic: ..."
    """
    parts = mapping_str.split("->")
    if parts:
        return parts[0].strip()
    return ""


def _extract_pattern(mapping_str: str) -> str:
    """Extract the mapping pattern from a mapping string.

    Expected format: "VARNAME -> pattern from source. Logic: ..."
    """
    parts = mapping_str.split("->")
    if len(parts) >= 2:
        remainder = parts[1].strip()
        # Pattern is before " from "
        from_idx = remainder.lower().find(" from ")
        if from_idx >= 0:
            return remainder[:from_idx].strip()
        return remainder.split(".")[0].strip()
    return ""


def compile_optimizer(
    example_store: ExampleStore,
    output_path: Path,
    *,
    domain: str | None = None,
    model: str = "anthropic/claude-sonnet-4-20250514",
    max_rounds: int = 1,
    max_bootstrapped_demos: int = 4,
) -> Path | None:
    """Compile a DSPy BootstrapFewShot optimizer from stored examples.

    Builds a trainset from the example store, configures DSPy with the
    specified model, runs BootstrapFewShot compilation, and saves the
    compiled program to disk.

    Args:
        example_store: SQLite-backed structured storage with training data.
        output_path: Path to save the compiled program.
        domain: Optional domain code to filter examples.
        model: LiteLLM model string (default: Claude Sonnet).
        max_rounds: Maximum compilation rounds (default: 1).
        max_bootstrapped_demos: Maximum bootstrapped demonstrations (default: 4).

    Returns:
        output_path if compilation succeeded, None if insufficient data.
    """
    _require_dspy()

    trainset = build_trainset(example_store, domain=domain)
    if trainset is None:
        return None

    logger.info(
        "Compiling DSPy optimizer with {} examples, model={}",
        len(trainset),
        model,
    )

    dspy.configure(lm=dspy.LM(model, temperature=0.1, max_tokens=4096))

    optimizer = dspy.BootstrapFewShot(
        metric=mapping_accuracy_metric,
        max_bootstrapped_demos=max_bootstrapped_demos,
        max_rounds=max_rounds,
    )

    compiled = optimizer.compile(
        student=_DSPyMapperModule(),
        trainset=trainset,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    compiled.save(str(output_path))
    logger.info("Compiled program saved to {}", output_path)
    return output_path


def load_compiled_program(program_path: Path) -> SDTMMapperModule | None:
    """Load a previously compiled DSPy program from disk.

    Args:
        program_path: Path to the saved compiled program.

    Returns:
        Loaded SDTMMapperModule, or None if path does not exist.
    """
    _require_dspy()

    if not program_path.exists():
        logger.warning("Compiled program not found at {}", program_path)
        return None

    module = SDTMMapperModule()
    module.load(str(program_path))
    logger.info("Loaded compiled program from {}", program_path)
    return module
