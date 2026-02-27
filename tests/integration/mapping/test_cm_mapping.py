"""Integration test for CM domain mapping using real Fakedata and real LLM calls.

Exercises the full mapping pipeline end-to-end for Concomitant Medications:
    1. Profile real cm.sas7bdat from Fakedata/
    2. Build context with CM eCRF form metadata
    3. Call Claude for structured mapping proposals
    4. Validate and enrich proposals against SDTM-IG + CT
    5. Verify dose, route, frequency, indication mappings

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

# Required CM variables per SDTM-IG v3.4
REQUIRED_CM_VARIABLES = {"STUDYID", "DOMAIN", "USUBJID", "CMSEQ", "CMTRT"}

# Skip condition
_skip_no_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping integration test",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_cm_ecrf_form() -> ECRFForm:
    """Build a realistic Concomitant Medications eCRF form from known cm.sas7bdat structure.

    Includes fields for medication name, dose, route, frequency, indication,
    and start/end dates (including partial date patterns).
    """
    fields = [
        ECRFField(
            field_number=1,
            field_name="CMTRT",
            data_type="$200",
            sas_label="Medication",
            coded_values=None,
            field_oid="CMTRT",
        ),
        ECRFField(
            field_number=2,
            field_name="CMINDC",
            data_type="$200",
            sas_label="Indication",
            coded_values=None,
            field_oid="CMINDC",
        ),
        ECRFField(
            field_number=3,
            field_name="CMDSTXT",
            data_type="$50",
            sas_label="Dose per administration",
            coded_values=None,
            field_oid="CMDSTXT",
        ),
        ECRFField(
            field_number=4,
            field_name="CMDOSU",
            data_type="$20",
            sas_label="Units",
            coded_values=None,
            field_oid="CMDOSU",
        ),
        ECRFField(
            field_number=5,
            field_name="CMDOSFRQ",
            data_type="$30",
            sas_label="Frequency",
            coded_values=None,
            field_oid="CMDOSFRQ",
        ),
        ECRFField(
            field_number=6,
            field_name="CMROUTE",
            data_type="$30",
            sas_label="Route",
            coded_values=None,
            field_oid="CMROUTE",
        ),
        ECRFField(
            field_number=7,
            field_name="CMSTDAT",
            data_type="dd MMM yyyy",
            sas_label="Start Date",
            coded_values=None,
            field_oid="CMSTDAT",
        ),
        ECRFField(
            field_number=8,
            field_name="CMENDAT",
            data_type="dd MMM yyyy",
            sas_label="End Date",
            coded_values=None,
            field_oid="CMENDAT",
        ),
        ECRFField(
            field_number=9,
            field_name="CMONGO",
            data_type="$10",
            sas_label="Is the medication ongoing",
            coded_values={"Y": "Yes", "N": "No"},
            field_oid="CMONGO",
        ),
        ECRFField(
            field_number=10,
            field_name="CMINDPX",
            data_type="$200",
            sas_label="Prophylaxis",
            coded_values=None,
            field_oid="CMINDPX",
        ),
    ]

    return ECRFForm(
        form_name="Concomitant Medications",
        fields=fields,
        page_numbers=[40, 41],
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
def cm_mapping_result() -> DomainMappingSpec:
    """Run the full CM mapping pipeline once and cache the result."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    cm_profile = _profile_dataset("cm.sas7bdat")
    ecrf_form = _build_cm_ecrf_form()

    sdtm_ref = load_sdtm_reference()
    ct_ref = load_ct_reference()

    llm_client = AstraeaLLMClient()
    engine = MappingEngine(llm_client, sdtm_ref, ct_ref)

    study_metadata = StudyMetadata(
        study_id=STUDY_ID,
        site_id_variable="SiteNumber",
        subject_id_variable="Subject",
    )

    spec = engine.map_domain(
        domain="CM",
        source_profiles=[cm_profile],
        ecrf_forms=[ecrf_form],
        study_metadata=study_metadata,
    )

    _display_mapping_spec(spec, "CM")
    return spec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_api_key
class TestCMMappingEndToEnd:
    """End-to-end tests for CM domain mapping on real Fakedata."""

    def test_domain_is_cm(self, cm_mapping_result: DomainMappingSpec) -> None:
        assert cm_mapping_result.domain == "CM"

    def test_sufficient_variable_count(self, cm_mapping_result: DomainMappingSpec) -> None:
        """At least 10 variables should be mapped."""
        assert cm_mapping_result.total_variables >= 10, (
            f"Expected at least 10 mapped variables, got {cm_mapping_result.total_variables}"
        )

    def test_required_variables_mapped(self, cm_mapping_result: DomainMappingSpec) -> None:
        """All Required CM variables must have mappings."""
        mapped_vars = {m.sdtm_variable for m in cm_mapping_result.variable_mappings}
        missing = REQUIRED_CM_VARIABLES - mapped_vars
        assert not missing, (
            f"Missing required CM variables: {missing}. "
            f"Mapped: {sorted(mapped_vars)}"
        )

    def test_cmtrt_has_source(self, cm_mapping_result: DomainMappingSpec) -> None:
        """CMTRT should be mapped from source."""
        cmtrt = [m for m in cm_mapping_result.variable_mappings if m.sdtm_variable == "CMTRT"]
        assert len(cmtrt) >= 1, "CMTRT mapping not found"
        assert cmtrt[0].mapping_pattern in (
            MappingPattern.DIRECT,
            MappingPattern.RENAME,
        ), f"CMTRT should be DIRECT or RENAME, got {cmtrt[0].mapping_pattern}"

    def test_dates_mapped(self, cm_mapping_result: DomainMappingSpec) -> None:
        """CMSTDTC should be present in mappings."""
        mapped_vars = {m.sdtm_variable for m in cm_mapping_result.variable_mappings}
        assert "CMSTDTC" in mapped_vars, (
            f"CMSTDTC not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_high_confidence_exists(self, cm_mapping_result: DomainMappingSpec) -> None:
        assert cm_mapping_result.high_confidence_count > 0

    def test_dose_variables_mapped(self, cm_mapping_result: DomainMappingSpec) -> None:
        """At least one of CMDOSE, CMDOSU, CMROUTE should be present."""
        mapped_vars = {m.sdtm_variable for m in cm_mapping_result.variable_mappings}
        dose_vars = {"CMDOSE", "CMDOSTXT", "CMDOSU", "CMROUTE"}
        found = dose_vars & mapped_vars
        assert len(found) >= 1, (
            f"Expected at least one dose variable from {dose_vars}, "
            f"found none. Mapped: {sorted(mapped_vars)}"
        )


@pytest.mark.integration
@_skip_no_api_key
class TestCMCTValidation:
    """Validate controlled terminology references in CM mapping output."""

    def test_route_references_codelist(
        self, cm_mapping_result: DomainMappingSpec
    ) -> None:
        """CMROUTE mapping should reference codelist C66729 if present."""
        cmroute = [
            m for m in cm_mapping_result.variable_mappings if m.sdtm_variable == "CMROUTE"
        ]
        if cmroute and cmroute[0].codelist_code is not None:
            assert cmroute[0].codelist_code == "C66729", (
                f"CMROUTE codelist should be C66729, got {cmroute[0].codelist_code}"
            )

    def test_frequency_references_codelist(
        self, cm_mapping_result: DomainMappingSpec
    ) -> None:
        """CMDOSFRQ mapping should reference codelist C71113 if present."""
        cmdosfrq = [
            m for m in cm_mapping_result.variable_mappings if m.sdtm_variable == "CMDOSFRQ"
        ]
        if cmdosfrq and cmdosfrq[0].codelist_code is not None:
            assert cmdosfrq[0].codelist_code == "C71113", (
                f"CMDOSFRQ codelist should be C71113, got {cmdosfrq[0].codelist_code}"
            )
