"""Integration test for VS domain mapping using synthetic profile data and real LLM calls.

NOTE: No vs.sas7bdat file exists in Fakedata/, so this test uses a synthetic
RawDatasetProfile with VS-like variable names and sample values to exercise
the mapping engine for the Vital Signs domain.

Exercises the full mapping pipeline:
    1. Create synthetic VS profile with SDTM-like variables
    2. Build context with VS eCRF form metadata
    3. Call Claude for structured mapping proposals
    4. Validate and enrich proposals against SDTM-IG + CT
    5. Verify Findings-class variables and CT codelist references (C71148, C66785)

Requires ANTHROPIC_API_KEY environment variable to be set.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from rich.console import Console
from rich.table import Table

from astraea.llm.client import AstraeaLLMClient
from astraea.mapping.engine import MappingEngine
from astraea.models.ecrf import ECRFField, ECRFForm
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    StudyMetadata,
)
from astraea.models.profiling import DatasetProfile, VariableProfile
from astraea.reference import load_ct_reference, load_sdtm_reference

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STUDY_ID = "PHA022121-C301"

# Required VS variables per SDTM-IG v3.4
REQUIRED_VS_VARIABLES = {
    "STUDYID", "DOMAIN", "USUBJID", "VSSEQ", "VSTESTCD", "VSTEST", "VSORRES",
}

# Skip condition: no API key means we cannot run LLM calls
_skip_no_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping integration test",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_synthetic_vs_profile() -> DatasetProfile:
    """Build a synthetic VS dataset profile mimicking vital signs data.

    Creates a DatasetProfile with SDTM-like variable names and realistic
    sample values for Vital Signs measurements (blood pressure, pulse,
    temperature, weight, height).
    """
    variables = [
        VariableProfile(
            name="STUDYID",
            label="Study Identifier",
            dtype="character",
            n_total=500,
            n_missing=0,
            n_unique=1,
            missing_pct=0.0,
            sample_values=["PHA022121-C301"],
        ),
        VariableProfile(
            name="DOMAIN",
            label="Domain Abbreviation",
            dtype="character",
            n_total=500,
            n_missing=0,
            n_unique=1,
            missing_pct=0.0,
            sample_values=["VS"],
        ),
        VariableProfile(
            name="USUBJID",
            label="Unique Subject Identifier",
            dtype="character",
            n_total=500,
            n_missing=0,
            n_unique=50,
            missing_pct=0.0,
            sample_values=["PHA022121-C301-001-001", "PHA022121-C301-002-002"],
        ),
        VariableProfile(
            name="VSSEQ",
            label="Sequence Number",
            dtype="numeric",
            n_total=500,
            n_missing=0,
            n_unique=500,
            missing_pct=0.0,
            sample_values=["1", "2", "3", "4", "5"],
        ),
        VariableProfile(
            name="VSTESTCD",
            label="Vital Signs Test Short Name",
            dtype="character",
            n_total=500,
            n_missing=0,
            n_unique=6,
            missing_pct=0.0,
            sample_values=["SYSBP", "DIABP", "PULSE", "TEMP", "WEIGHT", "HEIGHT"],
        ),
        VariableProfile(
            name="VSTEST",
            label="Vital Signs Test Name",
            dtype="character",
            n_total=500,
            n_missing=0,
            n_unique=6,
            missing_pct=0.0,
            sample_values=[
                "Systolic Blood Pressure",
                "Diastolic Blood Pressure",
                "Pulse Rate",
                "Temperature",
                "Weight",
                "Height",
            ],
        ),
        VariableProfile(
            name="VSORRES",
            label="Result or Finding in Original Units",
            dtype="character",
            n_total=500,
            n_missing=5,
            n_unique=120,
            missing_pct=1.0,
            sample_values=["120", "80", "72", "36.5", "75.2", "170"],
        ),
        VariableProfile(
            name="VSORRESU",
            label="Original Units",
            dtype="character",
            n_total=500,
            n_missing=5,
            n_unique=5,
            missing_pct=1.0,
            sample_values=["mmHg", "beats/min", "C", "kg", "cm"],
        ),
        VariableProfile(
            name="VSPOS",
            label="Vital Signs Position of Subject",
            dtype="character",
            n_total=500,
            n_missing=100,
            n_unique=3,
            missing_pct=20.0,
            sample_values=["SUPINE", "SITTING", "STANDING"],
        ),
        VariableProfile(
            name="VSLAT",
            label="Laterality",
            dtype="character",
            n_total=500,
            n_missing=400,
            n_unique=2,
            missing_pct=80.0,
            sample_values=["LEFT", "RIGHT"],
        ),
        VariableProfile(
            name="VSDTC",
            label="Date/Time of Measurements",
            dtype="character",
            n_total=500,
            n_missing=0,
            n_unique=50,
            missing_pct=0.0,
            sample_values=["2022-03-15", "2022-04-01", "2022-05-10"],
            is_date=True,
            detected_date_format="YYYY-MM-DD",
        ),
        VariableProfile(
            name="VISITNUM",
            label="Visit Number",
            dtype="numeric",
            n_total=500,
            n_missing=0,
            n_unique=10,
            missing_pct=0.0,
            sample_values=["1", "2", "3", "4", "5"],
        ),
        VariableProfile(
            name="VISIT",
            label="Visit Name",
            dtype="character",
            n_total=500,
            n_missing=0,
            n_unique=10,
            missing_pct=0.0,
            sample_values=["SCREENING", "BASELINE", "WEEK 1", "WEEK 4", "END OF STUDY"],
        ),
    ]

    return DatasetProfile(
        filename="vs_synthetic.sas7bdat",
        row_count=500,
        col_count=len(variables),
        variables=variables,
        date_variables=["VSDTC"],
        edc_columns=[],
    )


def _build_vs_ecrf_form() -> ECRFForm:
    """Build a realistic Vital Signs eCRF form with VS-specific fields.

    Includes fields for vital sign measurements including position and
    laterality which are important for CT codelist validation.
    """
    fields = [
        ECRFField(
            field_number=1,
            field_name="VSTESTCD",
            data_type="$10",
            sas_label="Vital Signs Test Short Name",
            coded_values=None,
            field_oid="VSTESTCD",
        ),
        ECRFField(
            field_number=2,
            field_name="VSTEST",
            data_type="$40",
            sas_label="Vital Signs Test Name",
            coded_values=None,
            field_oid="VSTEST",
        ),
        ECRFField(
            field_number=3,
            field_name="VSORRES",
            data_type="$200",
            sas_label="Result or Finding in Original Units",
            coded_values=None,
            field_oid="VSORRES",
        ),
        ECRFField(
            field_number=4,
            field_name="VSORRESU",
            data_type="$40",
            sas_label="Original Units",
            coded_values=None,
            field_oid="VSORRESU",
        ),
        ECRFField(
            field_number=5,
            field_name="VSPOS",
            data_type="$20",
            sas_label="Vital Signs Position of Subject",
            coded_values={"SUPINE": "Supine", "SITTING": "Sitting", "STANDING": "Standing"},
            field_oid="VSPOS",
        ),
        ECRFField(
            field_number=6,
            field_name="VSLAT",
            data_type="$20",
            sas_label="Laterality",
            coded_values={"LEFT": "Left", "RIGHT": "Right"},
            field_oid="VSLAT",
        ),
        ECRFField(
            field_number=7,
            field_name="VSDTC",
            data_type="dd MMM yyyy",
            sas_label="Date/Time of Measurements",
            coded_values=None,
            field_oid="VSDTC",
        ),
    ]

    return ECRFForm(
        form_name="Vital Signs",
        fields=fields,
        page_numbers=[50, 51],
    )


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
def vs_mapping_result() -> DomainMappingSpec:
    """Run the full VS mapping pipeline once and cache the result.

    Uses synthetic profile data since no vs.sas7bdat exists in Fakedata/.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    vs_profile = _build_synthetic_vs_profile()
    ecrf_form = _build_vs_ecrf_form()

    sdtm_ref = load_sdtm_reference()
    ct_ref = load_ct_reference()

    llm_client = AstraeaLLMClient()
    engine = MappingEngine(llm_client, sdtm_ref, ct_ref)

    study_metadata = StudyMetadata(
        study_id=STUDY_ID,
        site_id_variable="SiteNumber",
        subject_id_variable="USUBJID",
    )

    spec = engine.map_domain(
        domain="VS",
        source_profiles=[vs_profile],
        ecrf_forms=[ecrf_form],
        study_metadata=study_metadata,
    )

    _display_mapping_spec(spec, "VS")
    return spec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_api_key
class TestVSMappingEndToEnd:
    """End-to-end tests for VS domain mapping using synthetic profile data.

    VS uses synthetic profile because no vs.sas7bdat exists in Fakedata/.
    The synthetic profile contains SDTM-like variable names (VSTESTCD,
    VSTEST, VSORRES, VSORRESU, VSPOS, VSLAT, VSDTC) with realistic
    sample values for blood pressure, pulse, temperature, weight, and height.
    """

    def test_vs_mapping_generates_spec(self, vs_mapping_result: DomainMappingSpec) -> None:
        """Verify DomainMappingSpec returned with domain='VS'."""
        assert vs_mapping_result.domain == "VS"

    def test_vs_mapping_has_testcd(self, vs_mapping_result: DomainMappingSpec) -> None:
        """Verify VSTESTCD mapping exists."""
        mapped_vars = {m.sdtm_variable for m in vs_mapping_result.variable_mappings}
        assert "VSTESTCD" in mapped_vars, (
            f"VSTESTCD not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_vs_mapping_has_orres(self, vs_mapping_result: DomainMappingSpec) -> None:
        """Verify VSORRES mapping exists."""
        mapped_vars = {m.sdtm_variable for m in vs_mapping_result.variable_mappings}
        assert "VSORRES" in mapped_vars, (
            f"VSORRES not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_vs_mapping_required_vars(self, vs_mapping_result: DomainMappingSpec) -> None:
        """Verify all REQ variables present."""
        mapped_vars = {m.sdtm_variable for m in vs_mapping_result.variable_mappings}
        missing = REQUIRED_VS_VARIABLES - mapped_vars
        assert not missing, (
            f"Missing required VS variables: {missing}. "
            f"Mapped: {sorted(mapped_vars)}"
        )

    def test_vs_mapping_domain_class(self, vs_mapping_result: DomainMappingSpec) -> None:
        """Verify domain_class is 'findings' (case-insensitive)."""
        assert vs_mapping_result.domain_class.lower() == "findings", (
            f"Expected domain_class 'findings', got '{vs_mapping_result.domain_class}'"
        )

    def test_vs_mapping_confidence(self, vs_mapping_result: DomainMappingSpec) -> None:
        """Verify average confidence >= 0.5 (lower threshold since synthetic profile)."""
        confidences = [m.confidence for m in vs_mapping_result.variable_mappings]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        assert avg_conf >= 0.5, (
            f"Average confidence {avg_conf:.2f} is below 0.5 threshold"
        )


@pytest.mark.integration
@_skip_no_api_key
class TestVSCTValidation:
    """Validate controlled terminology references in VS mapping output."""

    def test_vs_mapping_position_codelist(
        self, vs_mapping_result: DomainMappingSpec
    ) -> None:
        """Verify VSPOS mapping references CT codelist C71148 (position).

        C71148 is the CDISC CT codelist for Position of Subject during
        data collection. This is a key CT validation for the VS domain.
        """
        vspos = [
            m for m in vs_mapping_result.variable_mappings if m.sdtm_variable == "VSPOS"
        ]
        if vspos:
            assert vspos[0].codelist_code is not None, (
                "VSPOS should reference a CT codelist (C71148 for Position)"
            )
            assert vspos[0].codelist_code == "C71148", (
                f"VSPOS codelist should be C71148 (Position), "
                f"got {vspos[0].codelist_code}"
            )

    def test_vs_mapping_laterality_codelist(
        self, vs_mapping_result: DomainMappingSpec
    ) -> None:
        """If VSLAT mapping exists, verify it references CT codelist C66785 (laterality).

        C66785 is the CDISC CT codelist for Laterality (LEFT, RIGHT, BILATERAL).
        """
        vslat = [
            m for m in vs_mapping_result.variable_mappings if m.sdtm_variable == "VSLAT"
        ]
        if vslat and vslat[0].codelist_code is not None:
            assert vslat[0].codelist_code == "C66785", (
                f"VSLAT codelist should be C66785 (Laterality), "
                f"got {vslat[0].codelist_code}"
            )
