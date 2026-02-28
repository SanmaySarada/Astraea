"""Integration test for EG domain mapping using real Fakedata and real LLM calls.

Exercises the full mapping pipeline end-to-end for ECG Results:
    1. Profile real ecg_results.sas7bdat from Fakedata/
    2. Build context with EG eCRF form metadata
    3. Call Claude for structured mapping proposals
    4. Validate and enrich proposals against SDTM-IG + CT
    5. Verify Findings-class variables and CT codelist references

The ecg_results.sas7bdat file is already in SDTM-like structure with
pre-named variables (EGTESTCD, EGTEST, EGORRES, EGPOS, etc.),
so the LLM should propose mostly DIRECT mappings.

Requires ANTHROPIC_API_KEY environment variable to be set.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from rich.console import Console
from rich.table import Table

from astraea.io.sas_reader import read_sas_with_metadata
from astraea.llm.client import AstraeaLLMClient
from astraea.mapping.engine import MappingEngine
from astraea.models.ecrf import ECRFField, ECRFForm
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    StudyMetadata,
)
from astraea.models.profiling import DatasetProfile
from astraea.profiling.profiler import profile_dataset
from astraea.reference import load_ct_reference, load_sdtm_reference

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKEDATA_DIR = Path(__file__).resolve().parents[3] / "Fakedata"
STUDY_ID = "PHA022121-C301"

# Required EG variables per SDTM-IG v3.4
REQUIRED_EG_VARIABLES = {
    "STUDYID",
    "DOMAIN",
    "USUBJID",
    "EGSEQ",
    "EGTESTCD",
    "EGTEST",
    "EGORRES",
}

# Skip condition: no API key means we cannot run LLM calls
_skip_no_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping integration test",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_eg_ecrf_form() -> ECRFForm:
    """Build a realistic ECG Results eCRF form from known ecg_results.sas7bdat structure.

    Includes fields for test code, test name, results, units, position,
    method, lead, and time point.
    """
    fields = [
        ECRFField(
            field_number=1,
            field_name="EGTESTCD",
            data_type="$10",
            sas_label="ECG Test or Examination Short Name",
            coded_values=None,
            field_oid="EGTESTCD",
        ),
        ECRFField(
            field_number=2,
            field_name="EGTEST",
            data_type="$40",
            sas_label="ECG Test or Examination Name",
            coded_values=None,
            field_oid="EGTEST",
        ),
        ECRFField(
            field_number=3,
            field_name="EGORRES",
            data_type="$200",
            sas_label="Result or Finding in Original Units",
            coded_values=None,
            field_oid="EGORRES",
        ),
        ECRFField(
            field_number=4,
            field_name="EGORRESU",
            data_type="$40",
            sas_label="Original Units",
            coded_values=None,
            field_oid="EGORRESU",
        ),
        ECRFField(
            field_number=5,
            field_name="EGPOS",
            data_type="$20",
            sas_label="ECG Position of Subject",
            coded_values={"SUPINE": "Supine", "SITTING": "Sitting", "STANDING": "Standing"},
            field_oid="EGPOS",
        ),
        ECRFField(
            field_number=6,
            field_name="EGMETHOD",
            data_type="$40",
            sas_label="Method of Test or Examination",
            coded_values=None,
            field_oid="EGMETHOD",
        ),
        ECRFField(
            field_number=7,
            field_name="EGLEAD",
            data_type="$10",
            sas_label="Lead Number",
            coded_values=None,
            field_oid="EGLEAD",
        ),
        ECRFField(
            field_number=8,
            field_name="EGTPT",
            data_type="$40",
            sas_label="Planned Time Point Name",
            coded_values=None,
            field_oid="EGTPT",
        ),
        ECRFField(
            field_number=9,
            field_name="EGCAT",
            data_type="$40",
            sas_label="Category for ECG",
            coded_values=None,
            field_oid="EGCAT",
        ),
    ]

    return ECRFForm(
        form_name="ECG Results",
        fields=fields,
        page_numbers=[70, 71],
    )


def _profile_dataset(filename: str) -> DatasetProfile:
    """Profile a single SAS dataset from Fakedata/."""
    path = FAKEDATA_DIR / filename
    if not path.exists():
        pytest.skip(f"Fakedata file not found: {path}")
    df, meta = read_sas_with_metadata(path)
    return profile_dataset(df, meta)


def _display_mapping_spec(spec: DomainMappingSpec, domain_label: str) -> None:
    """Display the mapping spec using Rich for human inspection."""
    console = Console()
    console.print()
    console.rule(f"[bold blue]{domain_label} Mapping Specification[/bold blue]")
    console.print(f"Domain: {spec.domain} ({spec.domain_label})")
    console.print(f"Model: {spec.model_used}")
    console.print(f"Source datasets: {', '.join(spec.source_datasets)}")
    console.print()

    table = Table(title=f"Variable Mappings ({spec.total_variables} total)")
    table.add_column("#", style="dim", width=3)
    table.add_column("SDTM Variable", style="bold cyan", width=12)
    table.add_column("Label", width=30)
    table.add_column("Core", width=5)
    table.add_column("Source", width=20)
    table.add_column("Pattern", width=14)
    table.add_column("Conf", width=6)

    for i, m in enumerate(spec.variable_mappings, 1):
        if m.confidence_level == ConfidenceLevel.HIGH:
            conf_style = "[green]"
        elif m.confidence_level == ConfidenceLevel.MEDIUM:
            conf_style = "[yellow]"
        else:
            conf_style = "[red]"

        source_str = ""
        if m.source_dataset and m.source_variable:
            source_str = f"{m.source_dataset}.{m.source_variable}"
        elif m.source_variable:
            source_str = m.source_variable
        elif m.assigned_value:
            source_str = f'"{m.assigned_value}"'

        table.add_row(
            str(i),
            m.sdtm_variable,
            m.sdtm_label[:30],
            m.core.value,
            source_str,
            m.mapping_pattern.value,
            f"{conf_style}{m.confidence:.2f}[/]",
        )

    console.print(table)
    console.print()
    console.print(
        f"  [green]{spec.high_confidence_count} HIGH[/green] | "
        f"[yellow]{spec.medium_confidence_count} MEDIUM[/yellow] | "
        f"[red]{spec.low_confidence_count} LOW[/red]"
    )
    console.rule()


# ---------------------------------------------------------------------------
# Module-scoped fixture: run mapping once, reuse across tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def eg_mapping_result() -> DomainMappingSpec:
    """Run the full EG mapping pipeline once and cache the result."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    eg_profile = _profile_dataset("ecg_results.sas7bdat")
    ecrf_form = _build_eg_ecrf_form()

    sdtm_ref = load_sdtm_reference()
    ct_ref = load_ct_reference()

    llm_client = AstraeaLLMClient()
    engine = MappingEngine(llm_client, sdtm_ref, ct_ref)

    study_metadata = StudyMetadata(
        study_id=STUDY_ID,
        site_id_variable="SiteNumber",
        subject_id_variable="SUBJID",
    )

    spec = engine.map_domain(
        domain="EG",
        source_profiles=[eg_profile],
        ecrf_forms=[ecrf_form],
        study_metadata=study_metadata,
    )

    _display_mapping_spec(spec, "EG")
    return spec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_api_key
class TestEGMappingEndToEnd:
    """End-to-end tests for EG domain mapping on real Fakedata."""

    def test_eg_mapping_generates_spec(self, eg_mapping_result: DomainMappingSpec) -> None:
        """Verify DomainMappingSpec returned with domain='EG'."""
        assert eg_mapping_result.domain == "EG"

    def test_eg_mapping_has_testcd(self, eg_mapping_result: DomainMappingSpec) -> None:
        """Verify EGTESTCD mapping exists."""
        mapped_vars = {m.sdtm_variable for m in eg_mapping_result.variable_mappings}
        assert "EGTESTCD" in mapped_vars, (
            f"EGTESTCD not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_eg_mapping_has_orres(self, eg_mapping_result: DomainMappingSpec) -> None:
        """Verify EGORRES mapping exists."""
        mapped_vars = {m.sdtm_variable for m in eg_mapping_result.variable_mappings}
        assert "EGORRES" in mapped_vars, (
            f"EGORRES not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_eg_mapping_has_tpt(self, eg_mapping_result: DomainMappingSpec) -> None:
        """Verify EGTPT (time point reference) mapping exists."""
        mapped_vars = {m.sdtm_variable for m in eg_mapping_result.variable_mappings}
        assert "EGTPT" in mapped_vars, f"EGTPT not found in mapped variables: {sorted(mapped_vars)}"

    def test_eg_mapping_required_vars(self, eg_mapping_result: DomainMappingSpec) -> None:
        """Verify all REQ variables present."""
        mapped_vars = {m.sdtm_variable for m in eg_mapping_result.variable_mappings}
        missing = REQUIRED_EG_VARIABLES - mapped_vars
        assert not missing, (
            f"Missing required EG variables: {missing}. Mapped: {sorted(mapped_vars)}"
        )

    def test_eg_mapping_domain_class(self, eg_mapping_result: DomainMappingSpec) -> None:
        """Verify domain_class is 'findings' (case-insensitive)."""
        assert eg_mapping_result.domain_class.lower() == "findings", (
            f"Expected domain_class 'findings', got '{eg_mapping_result.domain_class}'"
        )

    def test_eg_mapping_confidence(self, eg_mapping_result: DomainMappingSpec) -> None:
        """Verify average confidence >= 0.6."""
        confidences = [m.confidence for m in eg_mapping_result.variable_mappings]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        assert avg_conf >= 0.6, f"Average confidence {avg_conf:.2f} is below 0.6 threshold"


@pytest.mark.integration
@_skip_no_api_key
class TestEGCTValidation:
    """Validate controlled terminology references in EG mapping output."""

    def test_eg_mapping_position_codelist(self, eg_mapping_result: DomainMappingSpec) -> None:
        """If EGPOS mapping exists, verify it references CT codelist C71148 (position).

        C71148 is the CDISC CT codelist for Position of Subject during
        data collection (SUPINE, SITTING, STANDING, etc.).
        """
        egpos = [m for m in eg_mapping_result.variable_mappings if m.sdtm_variable == "EGPOS"]
        if egpos:
            assert egpos[0].codelist_code is not None, (
                "EGPOS should reference a CT codelist (C71148 for Position)"
            )
            assert egpos[0].codelist_code == "C71148", (
                f"EGPOS codelist should be C71148 (Position), got {egpos[0].codelist_code}"
            )
