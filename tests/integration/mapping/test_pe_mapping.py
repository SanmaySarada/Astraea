"""Integration test for PE domain mapping using real Fakedata and real LLM calls.

Exercises the full mapping pipeline end-to-end for Physical Examination:
    1. Profile real pe.sas7bdat from Fakedata/ (only 11 rows, very minimal)
    2. Build context with PE eCRF form metadata
    3. Call Claude for structured mapping proposals
    4. Validate and enrich proposals against SDTM-IG + CT
    5. Verify Findings-class variables (PEORRES, PEDTC, etc.)

The pe.sas7bdat file is raw EDC data with minimal clinical content
(PEPERF performed flag, PEDAT assessment date). The LLM must propose
SDTM PE domain mappings from this sparse source data.

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

# Required PE variables per SDTM-IG v3.4
REQUIRED_PE_VARIABLES = {"STUDYID", "DOMAIN", "USUBJID", "PESEQ"}

# Skip condition: no API key means we cannot run LLM calls
_skip_no_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping integration test",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_pe_ecrf_form() -> ECRFForm:
    """Build a realistic Physical Examination eCRF form from known pe.sas7bdat structure.

    The PE data is very sparse -- only a performed flag (PEPERF) and assessment
    date (PEDAT). The eCRF form reflects this minimal structure.
    """
    fields = [
        ECRFField(
            field_number=1,
            field_name="PEPERF",
            data_type="$10",
            sas_label="Was a Physical Examination performed",
            coded_values={"Y": "Yes", "N": "No"},
            field_oid="PEPERF",
        ),
        ECRFField(
            field_number=2,
            field_name="PEPERF_STD",
            data_type="$10",
            sas_label="Was a Physical Examination performed Coded Value",
            coded_values=None,
            field_oid="PEPERF_STD",
        ),
        ECRFField(
            field_number=3,
            field_name="PEDAT",
            data_type="dd MMM yyyy",
            sas_label="Assessment Date",
            coded_values=None,
            field_oid="PEDAT",
        ),
    ]

    return ECRFForm(
        form_name="Physical Examination",
        fields=fields,
        page_numbers=[25],
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
def pe_mapping_result() -> DomainMappingSpec:
    """Run the full PE mapping pipeline once and cache the result."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    pe_profile = _profile_dataset("pe.sas7bdat")
    ecrf_form = _build_pe_ecrf_form()

    sdtm_ref = load_sdtm_reference()
    ct_ref = load_ct_reference()

    llm_client = AstraeaLLMClient()
    engine = MappingEngine(llm_client, sdtm_ref, ct_ref)

    study_metadata = StudyMetadata(
        study_id=STUDY_ID,
        site_id_variable="SiteNumber",
        subject_id_variable="subject",
    )

    spec = engine.map_domain(
        domain="PE",
        source_profiles=[pe_profile],
        ecrf_forms=[ecrf_form],
        study_metadata=study_metadata,
    )

    _display_mapping_spec(spec, "PE")
    return spec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_api_key
class TestPEMappingEndToEnd:
    """End-to-end tests for PE domain mapping on real Fakedata.

    PE data is very sparse (only 11 rows, 3 clinical fields: PEPERF,
    PEPERF_STD, PEDAT). The LLM must work with minimal data to propose
    a reasonable PE domain mapping specification.
    """

    def test_pe_mapping_generates_spec(self, pe_mapping_result: DomainMappingSpec) -> None:
        """Verify DomainMappingSpec returned with domain='PE'."""
        assert pe_mapping_result.domain == "PE"

    def test_pe_mapping_has_peorres(self, pe_mapping_result: DomainMappingSpec) -> None:
        """Verify PEORRES mapping exists."""
        mapped_vars = {m.sdtm_variable for m in pe_mapping_result.variable_mappings}
        assert "PEORRES" in mapped_vars, (
            f"PEORRES not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_pe_mapping_has_pedtc(self, pe_mapping_result: DomainMappingSpec) -> None:
        """Verify PEDTC mapping exists."""
        mapped_vars = {m.sdtm_variable for m in pe_mapping_result.variable_mappings}
        assert "PEDTC" in mapped_vars, (
            f"PEDTC not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_pe_mapping_required_vars(self, pe_mapping_result: DomainMappingSpec) -> None:
        """Verify all REQ variables present."""
        mapped_vars = {m.sdtm_variable for m in pe_mapping_result.variable_mappings}
        missing = REQUIRED_PE_VARIABLES - mapped_vars
        assert not missing, (
            f"Missing required PE variables: {missing}. "
            f"Mapped: {sorted(mapped_vars)}"
        )

    def test_pe_mapping_domain_class(self, pe_mapping_result: DomainMappingSpec) -> None:
        """Verify domain_class is 'findings' (case-insensitive)."""
        assert pe_mapping_result.domain_class.lower() == "findings", (
            f"Expected domain_class 'findings', got '{pe_mapping_result.domain_class}'"
        )

    def test_pe_mapping_confidence(self, pe_mapping_result: DomainMappingSpec) -> None:
        """Verify average confidence >= 0.5 (lower threshold since PE data is very sparse)."""
        confidences = [m.confidence for m in pe_mapping_result.variable_mappings]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        assert avg_conf >= 0.5, (
            f"Average confidence {avg_conf:.2f} is below 0.5 threshold"
        )
