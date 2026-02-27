"""Integration test for DV domain mapping using real Fakedata and real LLM calls.

This module exercises MappingEngine.map_domain() for Protocol Deviations (DV):
    1. Profile dv.sas7bdat from Fakedata/
    2. Build context with eCRF form metadata for DV
    3. Call Claude for structured mapping proposals
    4. Validate and enrich proposals against SDTM-IG + CT
    5. Export to JSON round-trip

DV validates handling of non-standard column names (Subject_ID, Site_Number,
Description, Category, Date_Occurred -- not the typical EDC pattern).

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

# Required DV variables per SDTM-IG v3.4
REQUIRED_DV_VARIABLES = {"STUDYID", "DOMAIN", "USUBJID", "DVSEQ", "DVTERM"}

# Non-standard source column names in dv.sas7bdat
NON_STANDARD_SOURCE_VARS = {
    "Description", "Category", "Date_Occurred", "Subject_ID",
    "Site_Number", "Site_Name", "Causality", "Status", "Source",
    "Major_Minor", "Date_Reported", "Deviation_Id", "PD_Code",
}

# Skip condition
_skip_no_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping integration test",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_dv_ecrf_form() -> ECRFForm:
    """Build a DV eCRF form matching the non-standard dv.sas7bdat column names.

    DV uses completely different naming: Description, Category, Date_Occurred,
    Subject_ID, Site_Number -- not the typical EDC pattern.
    """
    fields = [
        ECRFField(
            field_number=1,
            field_name="Description",
            data_type="$500",
            sas_label="Protocol Deviation Description",
            coded_values=None,
            field_oid="Description",
        ),
        ECRFField(
            field_number=2,
            field_name="Category",
            data_type="$200",
            sas_label="Deviation Category",
            coded_values=None,
            field_oid="Category",
        ),
        ECRFField(
            field_number=3,
            field_name="Date_Occurred",
            data_type="$25",
            sas_label="Date Deviation Occurred",
            coded_values=None,
            field_oid="Date_Occurred",
        ),
        ECRFField(
            field_number=4,
            field_name="Subject_ID",
            data_type="$20",
            sas_label="Subject Identifier",
            coded_values=None,
            field_oid="Subject_ID",
        ),
        ECRFField(
            field_number=5,
            field_name="Site_Number",
            data_type="$10",
            sas_label="Site Number",
            coded_values=None,
            field_oid="Site_Number",
        ),
        ECRFField(
            field_number=6,
            field_name="Causality",
            data_type="$100",
            sas_label="Causality of Deviation",
            coded_values=None,
            field_oid="Causality",
        ),
        ECRFField(
            field_number=7,
            field_name="Major_Minor",
            data_type="$10",
            sas_label="Major or Minor Deviation",
            coded_values={"Major": "Major", "Minor": "Minor"},
            field_oid="Major_Minor",
        ),
        ECRFField(
            field_number=8,
            field_name="Status",
            data_type="$50",
            sas_label="Deviation Status",
            coded_values=None,
            field_oid="Status",
        ),
        ECRFField(
            field_number=9,
            field_name="PD_Code",
            data_type="$50",
            sas_label="Protocol Deviation Code",
            coded_values=None,
            field_oid="PD_Code",
        ),
    ]

    return ECRFForm(
        form_name="Protocol Deviations",
        fields=fields,
        page_numbers=[],
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
def dv_mapping_result() -> DomainMappingSpec:
    """Run the full DV mapping pipeline once and cache the result.

    DV has non-standard column names -- the LLM must handle this.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Profile dataset
    dv_profile = _profile_dataset("dv.sas7bdat")

    # Build eCRF form
    ecrf_form = _build_dv_ecrf_form()

    # Initialize references
    sdtm_ref = load_sdtm_reference()
    ct_ref = load_ct_reference()

    # Initialize LLM client and engine
    llm_client = AstraeaLLMClient()
    engine = MappingEngine(llm_client, sdtm_ref, ct_ref)

    # Study metadata -- DV uses non-standard column names
    study_metadata = StudyMetadata(
        study_id=STUDY_ID,
        site_id_variable="Site_Number",
        subject_id_variable="Subject_ID",
    )

    # Run the mapping
    spec = engine.map_domain(
        domain="DV",
        source_profiles=[dv_profile],
        ecrf_forms=[ecrf_form],
        study_metadata=study_metadata,
    )

    return spec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_api_key
class TestDVMappingEndToEnd:
    """End-to-end tests for DV domain mapping on real Fakedata."""

    def test_domain_is_dv(self, dv_mapping_result: DomainMappingSpec) -> None:
        """Mapping result targets the DV domain."""
        assert dv_mapping_result.domain == "DV"

    def test_sufficient_variable_count(self, dv_mapping_result: DomainMappingSpec) -> None:
        """At least 6 variables should be mapped for DV."""
        assert dv_mapping_result.total_variables >= 6, (
            f"Expected at least 6 mapped variables, got {dv_mapping_result.total_variables}"
        )

    def test_required_variables_mapped(self, dv_mapping_result: DomainMappingSpec) -> None:
        """All required DV variables must have mappings."""
        mapped_vars = {m.sdtm_variable for m in dv_mapping_result.variable_mappings}
        missing = REQUIRED_DV_VARIABLES - mapped_vars
        assert not missing, (
            f"Missing required DV variables: {missing}. "
            f"Mapped variables: {sorted(mapped_vars)}"
        )

    def test_dates_mapped(self, dv_mapping_result: DomainMappingSpec) -> None:
        """DVSTDTC (deviation date) should be mapped."""
        mapped_vars = {m.sdtm_variable for m in dv_mapping_result.variable_mappings}
        assert "DVSTDTC" in mapped_vars, (
            f"DVSTDTC not found. Mapped variables: {sorted(mapped_vars)}"
        )

    def test_high_confidence_exists(self, dv_mapping_result: DomainMappingSpec) -> None:
        """At least some mappings should have HIGH confidence."""
        assert dv_mapping_result.high_confidence_count > 0, (
            "No HIGH confidence mappings found. Distribution: "
            f"HIGH={dv_mapping_result.high_confidence_count}, "
            f"MEDIUM={dv_mapping_result.medium_confidence_count}, "
            f"LOW={dv_mapping_result.low_confidence_count}"
        )

    def test_non_standard_source_handled(self, dv_mapping_result: DomainMappingSpec) -> None:
        """At least one mapping references a non-standard source variable.

        DV uses Description, Category, Date_Occurred, Subject_ID, etc.
        instead of the typical EDC naming pattern.
        """
        all_source_vars = {
            m.source_variable
            for m in dv_mapping_result.variable_mappings
            if m.source_variable is not None
        }
        overlap = all_source_vars & NON_STANDARD_SOURCE_VARS
        assert len(overlap) > 0, (
            f"No non-standard source variables referenced. "
            f"Source vars: {sorted(all_source_vars)}. "
            f"Expected at least one of: {sorted(NON_STANDARD_SOURCE_VARS)}"
        )


@pytest.mark.integration
@_skip_no_api_key
class TestDVExportRoundtrip:
    """Test JSON export and round-trip validation for DV mapping."""

    def test_json_export_roundtrip(
        self, dv_mapping_result: DomainMappingSpec, tmp_path: Path
    ) -> None:
        """Export to JSON, read back, and validate round-trip."""
        json_path = tmp_path / "dv_mapping.json"
        json_path.write_text(dv_mapping_result.model_dump_json(indent=2))

        assert json_path.exists()
        assert json_path.stat().st_size > 0

        raw = json.loads(json_path.read_text())
        roundtripped = DomainMappingSpec.model_validate(raw)

        assert roundtripped.domain == dv_mapping_result.domain
        assert roundtripped.total_variables == dv_mapping_result.total_variables
        assert len(roundtripped.variable_mappings) == len(dv_mapping_result.variable_mappings)
