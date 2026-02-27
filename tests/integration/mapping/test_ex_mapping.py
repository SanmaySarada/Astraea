"""Integration test for EX domain mapping using real Fakedata and real LLM calls.

Exercises the full mapping pipeline end-to-end for Exposure:
    1. Profile real ex.sas7bdat AND ex_ole.sas7bdat from Fakedata/
    2. Build context with EX eCRF form metadata
    3. Call Claude for structured mapping proposals with multi-source input
    4. Validate and enrich proposals against SDTM-IG + CT
    5. Verify multi-source dataset handling

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

# Required EX variables per SDTM-IG v3.4
REQUIRED_EX_VARIABLES = {"STUDYID", "DOMAIN", "USUBJID", "EXSEQ", "EXTRT"}

# Skip condition
_skip_no_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping integration test",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_ex_ecrf_form() -> ECRFForm:
    """Build a realistic Exposure eCRF form from known ex.sas7bdat structure.

    Includes fields for treatment name, administration flag, dose, route,
    and administration date/time.
    """
    fields = [
        ECRFField(
            field_number=1,
            field_name="EXYN",
            data_type="$10",
            sas_label="Was drug administered at this visit?",
            coded_values={"Y": "Yes", "N": "No"},
            field_oid="EXYN",
        ),
        ECRFField(
            field_number=2,
            field_name="EXDAT",
            data_type="dd MMM yyyy",
            sas_label="Administration Date",
            coded_values=None,
            field_oid="EXDAT",
        ),
        ECRFField(
            field_number=3,
            field_name="EXTIM2",
            data_type="HH:MM",
            sas_label="Administration Time",
            coded_values=None,
            field_oid="EXTIM2",
        ),
        ECRFField(
            field_number=4,
            field_name="EXREASO2",
            data_type="$200",
            sas_label="If No, Reason",
            coded_values=None,
            field_oid="EXREASO2",
        ),
        ECRFField(
            field_number=5,
            field_name="EXOLEDAT",
            data_type="dd MMM yyyy",
            sas_label="Date of First OLE dose",
            coded_values=None,
            field_oid="EXOLEDAT",
        ),
        ECRFField(
            field_number=6,
            field_name="EXOLETIM",
            data_type="HH:MM",
            sas_label="Time of First OLE dose",
            coded_values=None,
            field_oid="EXOLETIM",
        ),
    ]

    return ECRFForm(
        form_name="Exposure",
        fields=fields,
        page_numbers=[20, 21],
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
def ex_mapping_result() -> DomainMappingSpec:
    """Run the full EX mapping pipeline once with multi-source input."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Profile both EX source files
    ex_profile = _profile_dataset("ex.sas7bdat")
    ex_ole_profile = _profile_dataset("ex_ole.sas7bdat")

    ecrf_form = _build_ex_ecrf_form()

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
        domain="EX",
        source_profiles=[ex_profile, ex_ole_profile],
        ecrf_forms=[ecrf_form],
        study_metadata=study_metadata,
    )

    _display_mapping_spec(spec, "EX")
    return spec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_api_key
class TestEXMappingEndToEnd:
    """End-to-end tests for EX domain mapping on real Fakedata."""

    def test_domain_is_ex(self, ex_mapping_result: DomainMappingSpec) -> None:
        assert ex_mapping_result.domain == "EX"

    def test_sufficient_variable_count(self, ex_mapping_result: DomainMappingSpec) -> None:
        """At least 8 variables should be mapped."""
        assert ex_mapping_result.total_variables >= 8, (
            f"Expected at least 8 mapped variables, got {ex_mapping_result.total_variables}"
        )

    def test_required_variables_mapped(self, ex_mapping_result: DomainMappingSpec) -> None:
        """All Required EX variables must have mappings."""
        mapped_vars = {m.sdtm_variable for m in ex_mapping_result.variable_mappings}
        missing = REQUIRED_EX_VARIABLES - mapped_vars
        assert not missing, (
            f"Missing required EX variables: {missing}. "
            f"Mapped: {sorted(mapped_vars)}"
        )

    def test_extrt_has_source(self, ex_mapping_result: DomainMappingSpec) -> None:
        """EXTRT should be mapped from source."""
        extrt = [m for m in ex_mapping_result.variable_mappings if m.sdtm_variable == "EXTRT"]
        assert len(extrt) >= 1, "EXTRT mapping not found"
        # EXTRT may be ASSIGN (study drug name) or DIRECT/RENAME
        assert extrt[0].mapping_pattern in (
            MappingPattern.DIRECT,
            MappingPattern.RENAME,
            MappingPattern.ASSIGN,
        ), f"EXTRT pattern unexpected: {extrt[0].mapping_pattern}"

    def test_dates_mapped(self, ex_mapping_result: DomainMappingSpec) -> None:
        """EXSTDTC should be present in mappings."""
        mapped_vars = {m.sdtm_variable for m in ex_mapping_result.variable_mappings}
        assert "EXSTDTC" in mapped_vars, (
            f"EXSTDTC not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_high_confidence_exists(self, ex_mapping_result: DomainMappingSpec) -> None:
        assert ex_mapping_result.high_confidence_count > 0

    def test_multiple_source_datasets(self, ex_mapping_result: DomainMappingSpec) -> None:
        """spec.source_datasets should have 2 entries (ex + ex_ole)."""
        assert len(ex_mapping_result.source_datasets) == 2, (
            f"Expected 2 source datasets, got {ex_mapping_result.source_datasets}"
        )


@pytest.mark.integration
@_skip_no_api_key
class TestEXCTValidation:
    """Validate controlled terminology references in EX mapping output."""

    def test_dose_form_references_codelist(
        self, ex_mapping_result: DomainMappingSpec
    ) -> None:
        """EXDOSFRM mapping should reference codelist C66726 if present."""
        exdosfrm = [
            m for m in ex_mapping_result.variable_mappings if m.sdtm_variable == "EXDOSFRM"
        ]
        if exdosfrm and exdosfrm[0].codelist_code is not None:
            assert exdosfrm[0].codelist_code == "C66726", (
                f"EXDOSFRM codelist should be C66726, got {exdosfrm[0].codelist_code}"
            )

    def test_route_references_codelist(
        self, ex_mapping_result: DomainMappingSpec
    ) -> None:
        """EXROUTE mapping should reference codelist C66729 if present."""
        exroute = [
            m for m in ex_mapping_result.variable_mappings if m.sdtm_variable == "EXROUTE"
        ]
        if exroute and exroute[0].codelist_code is not None:
            assert exroute[0].codelist_code == "C66729", (
                f"EXROUTE codelist should be C66729, got {exroute[0].codelist_code}"
            )
