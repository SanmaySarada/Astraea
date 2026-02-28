"""Integration test for DS domain mapping using real Fakedata and real LLM calls.

Exercises the full mapping pipeline end-to-end for Disposition:
    1. Profile real ds.sas7bdat AND ds2.sas7bdat from Fakedata/
    2. Build context with DS eCRF form metadata
    3. Call Claude for structured mapping proposals with multi-source input
    4. Validate and enrich proposals against SDTM-IG + CT
    5. Verify multi-source dataset handling and column alignment

Requires ANTHROPIC_API_KEY environment variable to be set.
"""

from __future__ import annotations

import json
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

# Required DS variables per SDTM-IG v3.4
REQUIRED_DS_VARIABLES = {"STUDYID", "DOMAIN", "USUBJID", "DSSEQ", "DSTERM", "DSDECOD"}

# Skip condition
_skip_no_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping integration test",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_ds_ecrf_form() -> ECRFForm:
    """Build a realistic Disposition eCRF form from known ds.sas7bdat + ds2.sas7bdat.

    Includes fields for disposition event, coded status, discontinuation reason,
    and dates from both forms (treatment discontinuation and study completion).
    """
    fields = [
        ECRFField(
            field_number=1,
            field_name="DSDECOD",
            data_type="$200",
            sas_label="What was the subject's status",
            coded_values=None,
            field_oid="DSDECOD",
        ),
        ECRFField(
            field_number=2,
            field_name="DSTERM",
            data_type="$200",
            sas_label="Primary Reason for Discontinuation",
            coded_values=None,
            field_oid="DSTERM",
        ),
        ECRFField(
            field_number=3,
            field_name="DSAE",
            data_type="$50",
            sas_label="Primary AE #",
            coded_values=None,
            field_oid="DSAE",
        ),
        ECRFField(
            field_number=4,
            field_name="DSLTDAT",
            data_type="dd MMM yyyy",
            sas_label="If Lost to Follow-Up, Date of Last Contact",
            coded_values=None,
            field_oid="DSLTDAT",
        ),
        ECRFField(
            field_number=5,
            field_name="DSENDAT2",
            data_type="dd MMM yyyy",
            sas_label="Study Discontinuation Date",
            coded_values=None,
            field_oid="DSENDAT2",
        ),
        ECRFField(
            field_number=6,
            field_name="DSDECOD2",
            data_type="$200",
            sas_label="What was the reason subject permanently discontinued the study?",
            coded_values=None,
            field_oid="DSDECOD2",
        ),
    ]

    return ECRFForm(
        form_name="Disposition",
        fields=fields,
        page_numbers=[50, 51],
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
def ds_mapping_result() -> DomainMappingSpec:
    """Run the full DS mapping pipeline once with multi-source input."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Profile both DS source files
    ds_profile = _profile_dataset("ds.sas7bdat")
    ds2_profile = _profile_dataset("ds2.sas7bdat")

    ecrf_form = _build_ds_ecrf_form()

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
        domain="DS",
        source_profiles=[ds_profile, ds2_profile],
        ecrf_forms=[ecrf_form],
        study_metadata=study_metadata,
    )

    _display_mapping_spec(spec, "DS")
    return spec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_api_key
class TestDSMappingEndToEnd:
    """End-to-end tests for DS domain mapping on real Fakedata."""

    def test_domain_is_ds(self, ds_mapping_result: DomainMappingSpec) -> None:
        assert ds_mapping_result.domain == "DS"

    def test_sufficient_variable_count(self, ds_mapping_result: DomainMappingSpec) -> None:
        """At least 6 variables should be mapped."""
        assert ds_mapping_result.total_variables >= 6, (
            f"Expected at least 6 mapped variables, got {ds_mapping_result.total_variables}"
        )

    def test_required_variables_mapped(self, ds_mapping_result: DomainMappingSpec) -> None:
        """All Required DS variables must have mappings."""
        mapped_vars = {m.sdtm_variable for m in ds_mapping_result.variable_mappings}
        missing = REQUIRED_DS_VARIABLES - mapped_vars
        assert not missing, (
            f"Missing required DS variables: {missing}. Mapped: {sorted(mapped_vars)}"
        )

    def test_dates_mapped(self, ds_mapping_result: DomainMappingSpec) -> None:
        """DSSTDTC should be present in mappings."""
        mapped_vars = {m.sdtm_variable for m in ds_mapping_result.variable_mappings}
        assert "DSSTDTC" in mapped_vars, (
            f"DSSTDTC not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_high_confidence_exists(self, ds_mapping_result: DomainMappingSpec) -> None:
        assert ds_mapping_result.high_confidence_count > 0

    def test_multiple_source_datasets(self, ds_mapping_result: DomainMappingSpec) -> None:
        """spec.source_datasets should have 2 entries (ds + ds2)."""
        assert len(ds_mapping_result.source_datasets) == 2, (
            f"Expected 2 source datasets, got {ds_mapping_result.source_datasets}"
        )


@pytest.mark.integration
@_skip_no_api_key
class TestDSCTValidation:
    """Validate controlled terminology references in DS mapping output."""

    def test_dsdecod_references_codelist(self, ds_mapping_result: DomainMappingSpec) -> None:
        """DSDECOD mapping should reference codelist C66727."""
        dsdecod = [m for m in ds_mapping_result.variable_mappings if m.sdtm_variable == "DSDECOD"]
        if dsdecod and dsdecod[0].codelist_code is not None:
            assert dsdecod[0].codelist_code == "C66727", (
                f"DSDECOD codelist should be C66727, got {dsdecod[0].codelist_code}"
            )


@pytest.mark.integration
@_skip_no_api_key
class TestDSExportRoundtrip:
    """Test JSON export and round-trip validation."""

    def test_json_export_roundtrip(
        self, ds_mapping_result: DomainMappingSpec, tmp_path: Path
    ) -> None:
        """Export to JSON, read back, and validate round-trip."""
        json_path = tmp_path / "ds_mapping.json"
        json_path.write_text(ds_mapping_result.model_dump_json(indent=2))

        assert json_path.exists()
        assert json_path.stat().st_size > 0

        raw = json.loads(json_path.read_text())
        roundtripped = DomainMappingSpec.model_validate(raw)

        assert roundtripped.domain == ds_mapping_result.domain
        assert roundtripped.total_variables == ds_mapping_result.total_variables
        assert len(roundtripped.variable_mappings) == len(ds_mapping_result.variable_mappings)
