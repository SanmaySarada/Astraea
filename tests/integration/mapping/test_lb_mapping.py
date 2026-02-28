"""Integration test for LB domain mapping using real Fakedata and real LLM calls.

Exercises the full mapping pipeline end-to-end for Laboratory Results:
    1. Profile real lab_results.sas7bdat from Fakedata/
    2. Build context with LB eCRF form metadata
    3. Call Claude for structured mapping proposals
    4. Validate and enrich proposals against SDTM-IG + CT
    5. Verify Findings-class variables (LBTESTCD, LBTEST, LBORRES, etc.)

The lab_results.sas7bdat file is already in SDTM-like structure with
pre-named variables (LBTESTCD, LBTEST, LBORRES, LBORRESU, etc.),
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
    MappingPattern,
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

# Required LB variables per SDTM-IG v3.4
REQUIRED_LB_VARIABLES = {
    "STUDYID",
    "DOMAIN",
    "USUBJID",
    "LBSEQ",
    "LBTESTCD",
    "LBTEST",
    "LBORRES",
}

# Skip condition: no API key means we cannot run LLM calls
_skip_no_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping integration test",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_lb_ecrf_form() -> ECRFForm:
    """Build a realistic Laboratory Results eCRF form from known lab_results.sas7bdat structure.

    Includes fields for test code, test name, results, units, normal ranges,
    specimen type, and method.
    """
    fields = [
        ECRFField(
            field_number=1,
            field_name="LBTESTCD",
            data_type="$10",
            sas_label="Lab Test or Examination Short Name",
            coded_values=None,
            field_oid="LBTESTCD",
        ),
        ECRFField(
            field_number=2,
            field_name="LBTEST",
            data_type="$40",
            sas_label="Lab Test or Examination Name",
            coded_values=None,
            field_oid="LBTEST",
        ),
        ECRFField(
            field_number=3,
            field_name="LBORRES",
            data_type="$200",
            sas_label="Result in Site-Reported Units",
            coded_values=None,
            field_oid="LBORRES",
        ),
        ECRFField(
            field_number=4,
            field_name="LBORRESU",
            data_type="$40",
            sas_label="Units Reported to Site",
            coded_values=None,
            field_oid="LBORRESU",
        ),
        ECRFField(
            field_number=5,
            field_name="LBSPEC",
            data_type="$40",
            sas_label="Specimen Type",
            coded_values=None,
            field_oid="LBSPEC",
        ),
        ECRFField(
            field_number=6,
            field_name="LBMETHOD",
            data_type="$40",
            sas_label="Method of Test or Examination",
            coded_values=None,
            field_oid="LBMETHOD",
        ),
        ECRFField(
            field_number=7,
            field_name="LBNRIND",
            data_type="$10",
            sas_label="Reference Range Indicator",
            coded_values={"NORMAL": "Normal", "HIGH": "High", "LOW": "Low"},
            field_oid="LBNRIND",
        ),
        ECRFField(
            field_number=8,
            field_name="LBCAT",
            data_type="$40",
            sas_label="Category for Lab Test",
            coded_values=None,
            field_oid="LBCAT",
        ),
    ]

    return ECRFForm(
        form_name="Laboratory Results",
        fields=fields,
        page_numbers=[60, 61, 62],
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
def lb_mapping_result() -> DomainMappingSpec:
    """Run the full LB mapping pipeline once and cache the result."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    lb_profile = _profile_dataset("lab_results.sas7bdat")
    ecrf_form = _build_lb_ecrf_form()

    sdtm_ref = load_sdtm_reference()
    ct_ref = load_ct_reference()

    llm_client = AstraeaLLMClient()
    engine = MappingEngine(llm_client, sdtm_ref, ct_ref)

    study_metadata = StudyMetadata(
        study_id=STUDY_ID,
        site_id_variable="sitenumber",
        subject_id_variable="USUBJID",
    )

    spec = engine.map_domain(
        domain="LB",
        source_profiles=[lb_profile],
        ecrf_forms=[ecrf_form],
        study_metadata=study_metadata,
    )

    _display_mapping_spec(spec, "LB")
    return spec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_api_key
class TestLBMappingEndToEnd:
    """End-to-end tests for LB domain mapping on real Fakedata."""

    def test_lb_mapping_generates_spec(self, lb_mapping_result: DomainMappingSpec) -> None:
        """Verify DomainMappingSpec returned with domain='LB'."""
        assert lb_mapping_result.domain == "LB"

    def test_lb_mapping_has_testcd(self, lb_mapping_result: DomainMappingSpec) -> None:
        """Verify LBTESTCD mapping exists with DIRECT pattern (source already has it)."""
        testcd = [m for m in lb_mapping_result.variable_mappings if m.sdtm_variable == "LBTESTCD"]
        assert len(testcd) >= 1, "LBTESTCD mapping not found"
        assert testcd[0].mapping_pattern in (
            MappingPattern.DIRECT,
            MappingPattern.RENAME,
        ), f"LBTESTCD should be DIRECT or RENAME, got {testcd[0].mapping_pattern}"

    def test_lb_mapping_has_test(self, lb_mapping_result: DomainMappingSpec) -> None:
        """Verify LBTEST mapping exists."""
        mapped_vars = {m.sdtm_variable for m in lb_mapping_result.variable_mappings}
        assert "LBTEST" in mapped_vars, (
            f"LBTEST not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_lb_mapping_has_orres(self, lb_mapping_result: DomainMappingSpec) -> None:
        """Verify LBORRES mapping exists."""
        mapped_vars = {m.sdtm_variable for m in lb_mapping_result.variable_mappings}
        assert "LBORRES" in mapped_vars, (
            f"LBORRES not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_lb_mapping_has_orresu(self, lb_mapping_result: DomainMappingSpec) -> None:
        """Verify LBORRESU mapping exists."""
        mapped_vars = {m.sdtm_variable for m in lb_mapping_result.variable_mappings}
        assert "LBORRESU" in mapped_vars, (
            f"LBORRESU not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_lb_mapping_has_stresc_stresn(self, lb_mapping_result: DomainMappingSpec) -> None:
        """Verify LBSTRESC and LBSTRESN mappings exist."""
        mapped_vars = {m.sdtm_variable for m in lb_mapping_result.variable_mappings}
        assert "LBSTRESC" in mapped_vars, (
            f"LBSTRESC not found in mapped variables: {sorted(mapped_vars)}"
        )
        assert "LBSTRESN" in mapped_vars, (
            f"LBSTRESN not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_lb_mapping_has_nrind(self, lb_mapping_result: DomainMappingSpec) -> None:
        """Verify LBNRIND mapping exists (normal range indicator)."""
        mapped_vars = {m.sdtm_variable for m in lb_mapping_result.variable_mappings}
        assert "LBNRIND" in mapped_vars, (
            f"LBNRIND not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_lb_mapping_required_vars(self, lb_mapping_result: DomainMappingSpec) -> None:
        """Verify all REQ variables present."""
        mapped_vars = {m.sdtm_variable for m in lb_mapping_result.variable_mappings}
        missing = REQUIRED_LB_VARIABLES - mapped_vars
        assert not missing, (
            f"Missing required LB variables: {missing}. Mapped: {sorted(mapped_vars)}"
        )

    def test_lb_mapping_domain_class(self, lb_mapping_result: DomainMappingSpec) -> None:
        """Verify domain_class is 'findings' (case-insensitive)."""
        assert lb_mapping_result.domain_class.lower() == "findings", (
            f"Expected domain_class 'findings', got '{lb_mapping_result.domain_class}'"
        )

    def test_lb_mapping_confidence(self, lb_mapping_result: DomainMappingSpec) -> None:
        """Verify average confidence >= 0.6."""
        confidences = [m.confidence for m in lb_mapping_result.variable_mappings]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        assert avg_conf >= 0.6, f"Average confidence {avg_conf:.2f} is below 0.6 threshold"


@pytest.mark.integration
@_skip_no_api_key
class TestLBCTValidation:
    """Validate controlled terminology references in LB mapping output."""

    def test_lb_mapping_specimen_codelist(self, lb_mapping_result: DomainMappingSpec) -> None:
        """Verify LBSPEC mapping references CT codelist C66789 (specimen condition) if present."""
        lbspec = [m for m in lb_mapping_result.variable_mappings if m.sdtm_variable == "LBSPEC"]
        if lbspec and lbspec[0].codelist_code is not None:
            assert lbspec[0].codelist_code == "C66789", (
                f"LBSPEC codelist should be C66789 (Specimen Type), got {lbspec[0].codelist_code}"
            )
