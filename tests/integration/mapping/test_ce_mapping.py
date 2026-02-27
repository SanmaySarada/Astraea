"""Integration test for CE domain mapping using real Fakedata and real LLM calls.

This module exercises MappingEngine.map_domain() for Clinical Events (CE):
    1. Profile ce.sas7bdat from Fakedata/
    2. Build context with eCRF form metadata for CE
    3. Call Claude for structured mapping proposals
    4. Validate and enrich proposals against SDTM-IG + CT
    5. Export to JSON round-trip

CE validates study-specific HAE attack event mapping.

Requires ANTHROPIC_API_KEY environment variable to be set.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from astraea.io.sas_reader import read_sas_with_metadata
from astraea.llm.client import AstraeaLLMClient
from astraea.mapping.engine import MappingEngine
from astraea.models.ecrf import ECRFField, ECRFForm
from astraea.models.mapping import (
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

# Required CE variables per SDTM-IG v3.4
REQUIRED_CE_VARIABLES = {"STUDYID", "DOMAIN", "USUBJID", "CESEQ", "CETERM"}

# Skip condition
_skip_no_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping integration test",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_ce_ecrf_form() -> ECRFForm:
    """Build a realistic CE eCRF form from known ce.sas7bdat structure.

    CE has HAE attack events with location checkboxes, severity, dates.
    """
    fields = [
        ECRFField(
            field_number=1,
            field_name="CESTDAT",
            data_type="datetime",
            sas_label="Attack Start Date",
            coded_values=None,
            field_oid="CESTDAT",
        ),
        ECRFField(
            field_number=2,
            field_name="CESTDAT_RAW",
            data_type="$25",
            sas_label="Attack Start Date (character)",
            coded_values=None,
            field_oid="CESTDAT_RAW",
        ),
        ECRFField(
            field_number=3,
            field_name="CEENDAT",
            data_type="datetime",
            sas_label="Attack End Date",
            coded_values=None,
            field_oid="CEENDAT",
        ),
        ECRFField(
            field_number=4,
            field_name="CESTTIM",
            data_type="$8",
            sas_label="Attack Start Time",
            coded_values=None,
            field_oid="CESTTIM",
        ),
        ECRFField(
            field_number=5,
            field_name="CELOCAIR",
            data_type="1",
            sas_label="Location - Airway",
            coded_values={"1": "Yes", "0": "No"},
            field_oid="CELOCAIR",
        ),
        ECRFField(
            field_number=6,
            field_name="CELOCGI",
            data_type="1",
            sas_label="Location - GI",
            coded_values={"1": "Yes", "0": "No"},
            field_oid="CELOCGI",
        ),
        ECRFField(
            field_number=7,
            field_name="CELOCFAC",
            data_type="1",
            sas_label="Location - Face",
            coded_values={"1": "Yes", "0": "No"},
            field_oid="CELOCFAC",
        ),
        ECRFField(
            field_number=8,
            field_name="CELOCTRUN",
            data_type="1",
            sas_label="Location - Trunk",
            coded_values={"1": "Yes", "0": "No"},
            field_oid="CELOCTRUN",
        ),
        ECRFField(
            field_number=9,
            field_name="CESEV",
            data_type="$20",
            sas_label="Severity",
            coded_values={"Mild": "Mild", "Moderate": "Moderate", "Severe": "Severe"},
            field_oid="CESEV",
        ),
        ECRFField(
            field_number=10,
            field_name="CEHOSP",
            data_type="$3",
            sas_label="Hospitalized?",
            coded_values={"Yes": "Yes", "No": "No"},
            field_oid="CEHOSP",
        ),
        ECRFField(
            field_number=11,
            field_name="CECON",
            data_type="$200",
            sas_label="Concomitant Treatment 1",
            coded_values=None,
            field_oid="CECON",
        ),
    ]

    return ECRFForm(
        form_name="Clinical Events - HAE Attacks",
        fields=fields,
        page_numbers=[40, 41, 42],
    )


def _profile_dataset(filename: str) -> DatasetProfile:
    """Profile a single SAS dataset from Fakedata/."""
    path = FAKEDATA_DIR / filename
    if not path.exists():
        pytest.skip(f"Fakedata file not found: {path}")
    df, meta = read_sas_with_metadata(path)
    return profile_dataset(df, meta)


# ---------------------------------------------------------------------------
# Module-scoped fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ce_mapping_result() -> DomainMappingSpec:
    """Run the full CE mapping pipeline once and cache the result."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Profile dataset
    ce_profile = _profile_dataset("ce.sas7bdat")

    # Build eCRF form
    ecrf_form = _build_ce_ecrf_form()

    # Initialize references
    sdtm_ref = load_sdtm_reference()
    ct_ref = load_ct_reference()

    # Initialize LLM client and engine
    llm_client = AstraeaLLMClient()
    engine = MappingEngine(llm_client, sdtm_ref, ct_ref)

    # Study metadata
    study_metadata = StudyMetadata(
        study_id=STUDY_ID,
        site_id_variable="SiteNumber",
        subject_id_variable="Subject",
    )

    # Run the mapping
    spec = engine.map_domain(
        domain="CE",
        source_profiles=[ce_profile],
        ecrf_forms=[ecrf_form],
        study_metadata=study_metadata,
    )

    return spec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_api_key
class TestCEMappingEndToEnd:
    """End-to-end tests for CE domain mapping on real Fakedata."""

    def test_domain_is_ce(self, ce_mapping_result: DomainMappingSpec) -> None:
        """Mapping result targets the CE domain."""
        assert ce_mapping_result.domain == "CE"

    def test_sufficient_variable_count(self, ce_mapping_result: DomainMappingSpec) -> None:
        """At least 7 variables should be mapped for CE."""
        assert ce_mapping_result.total_variables >= 7, (
            f"Expected at least 7 mapped variables, got {ce_mapping_result.total_variables}"
        )

    def test_required_variables_mapped(self, ce_mapping_result: DomainMappingSpec) -> None:
        """All required CE variables must have mappings."""
        mapped_vars = {m.sdtm_variable for m in ce_mapping_result.variable_mappings}
        missing = REQUIRED_CE_VARIABLES - mapped_vars
        assert not missing, (
            f"Missing required CE variables: {missing}. "
            f"Mapped variables: {sorted(mapped_vars)}"
        )

    def test_cedecod_mapped(self, ce_mapping_result: DomainMappingSpec) -> None:
        """CEDECOD (coded event term) should be mapped."""
        mapped_vars = {m.sdtm_variable for m in ce_mapping_result.variable_mappings}
        assert "CEDECOD" in mapped_vars, (
            f"CEDECOD not found. Mapped variables: {sorted(mapped_vars)}"
        )

    def test_dates_mapped(self, ce_mapping_result: DomainMappingSpec) -> None:
        """CESTDTC (start date) should be mapped."""
        mapped_vars = {m.sdtm_variable for m in ce_mapping_result.variable_mappings}
        assert "CESTDTC" in mapped_vars, (
            f"CESTDTC not found. Mapped variables: {sorted(mapped_vars)}"
        )

    def test_high_confidence_exists(self, ce_mapping_result: DomainMappingSpec) -> None:
        """At least some mappings should have HIGH confidence."""
        assert ce_mapping_result.high_confidence_count > 0, (
            "No HIGH confidence mappings found. Distribution: "
            f"HIGH={ce_mapping_result.high_confidence_count}, "
            f"MEDIUM={ce_mapping_result.medium_confidence_count}, "
            f"LOW={ce_mapping_result.low_confidence_count}"
        )


@pytest.mark.integration
@_skip_no_api_key
class TestCECTValidation:
    """Validate controlled terminology references in CE mapping output."""

    def test_yn_codelist_if_present(self, ce_mapping_result: DomainMappingSpec) -> None:
        """If CEPRESP or CEOCCUR mapped, they should reference C66742 (Y/N)."""
        yn_vars = {"CEPRESP", "CEOCCUR"}
        for m in ce_mapping_result.variable_mappings:
            if m.sdtm_variable in yn_vars and m.codelist_code is not None:
                assert m.codelist_code == "C66742", (
                    f"{m.sdtm_variable} codelist should be C66742, got {m.codelist_code}"
                )


@pytest.mark.integration
@_skip_no_api_key
class TestCEExportRoundtrip:
    """Test JSON export and round-trip validation for CE mapping."""

    def test_json_export_roundtrip(
        self, ce_mapping_result: DomainMappingSpec, tmp_path: Path
    ) -> None:
        """Export to JSON, read back, and validate round-trip."""
        json_path = tmp_path / "ce_mapping.json"
        json_path.write_text(ce_mapping_result.model_dump_json(indent=2))

        assert json_path.exists()
        assert json_path.stat().st_size > 0

        raw = json.loads(json_path.read_text())
        roundtripped = DomainMappingSpec.model_validate(raw)

        assert roundtripped.domain == ce_mapping_result.domain
        assert roundtripped.total_variables == ce_mapping_result.total_variables
        assert len(roundtripped.variable_mappings) == len(ce_mapping_result.variable_mappings)
