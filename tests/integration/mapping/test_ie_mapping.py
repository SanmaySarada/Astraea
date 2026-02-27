"""Integration test for IE domain mapping using real Fakedata and real LLM calls.

This module exercises MappingEngine.map_domain() for Inclusion/Exclusion (IE):
    1. Profile ie.sas7bdat from Fakedata/
    2. Build context with eCRF form metadata for IE
    3. Call Claude for structured mapping proposals
    4. Validate and enrich proposals against SDTM-IG + CT
    5. Export to JSON round-trip

IE validates Findings-class domain without transpose (one row per criterion).

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

# Required IE variables per SDTM-IG v3.4
REQUIRED_IE_VARIABLES = {"STUDYID", "DOMAIN", "USUBJID", "IESEQ", "IETESTCD", "IETEST", "IECAT"}

# Skip condition
_skip_no_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping integration test",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_ie_ecrf_form() -> ECRFForm:
    """Build a realistic IE eCRF form from known ie.sas7bdat structure.

    IE has criteria test codes, inclusion/exclusion category, and result fields.
    """
    fields = [
        ECRFField(
            field_number=1,
            field_name="ICDAT",
            data_type="datetime",
            sas_label="Informed Consent Date",
            coded_values=None,
            field_oid="ICDAT",
        ),
        ECRFField(
            field_number=2,
            field_name="IEPROT",
            data_type="$50",
            sas_label="Protocol Version",
            coded_values=None,
            field_oid="IEPROT",
        ),
        ECRFField(
            field_number=3,
            field_name="IEYN",
            data_type="$3",
            sas_label="Criteria Met?",
            coded_values={"Yes": "Yes", "No": "No"},
            field_oid="IEYN",
        ),
        ECRFField(
            field_number=4,
            field_name="IECAT",
            data_type="$50",
            sas_label="Criteria Category",
            coded_values={"INCLUSION": "Inclusion", "EXCLUSION": "Exclusion"},
            field_oid="IECAT",
        ),
        ECRFField(
            field_number=5,
            field_name="IENUM",
            data_type="3",
            sas_label="Criteria Number",
            coded_values=None,
            field_oid="IENUM",
        ),
        ECRFField(
            field_number=6,
            field_name="IERSCR",
            data_type="$3",
            sas_label="Rescreened?",
            coded_values={"Yes": "Yes", "No": "No"},
            field_oid="IERSCR",
        ),
        ECRFField(
            field_number=7,
            field_name="IEENRP",
            data_type="$50",
            sas_label="Enrolled in Part",
            coded_values=None,
            field_oid="IEENRP",
        ),
    ]

    return ECRFForm(
        form_name="Inclusion Exclusion Criteria",
        fields=fields,
        page_numbers=[12, 13],
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
def ie_mapping_result() -> DomainMappingSpec:
    """Run the full IE mapping pipeline once and cache the result.

    IE is Findings-class but requires no transpose (one row per criterion).
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Profile dataset
    ie_profile = _profile_dataset("ie.sas7bdat")

    # Build eCRF form
    ecrf_form = _build_ie_ecrf_form()

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
        domain="IE",
        source_profiles=[ie_profile],
        ecrf_forms=[ecrf_form],
        study_metadata=study_metadata,
    )

    return spec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_api_key
class TestIEMappingEndToEnd:
    """End-to-end tests for IE domain mapping on real Fakedata."""

    def test_domain_is_ie(self, ie_mapping_result: DomainMappingSpec) -> None:
        """Mapping result targets the IE domain."""
        assert ie_mapping_result.domain == "IE"

    def test_sufficient_variable_count(self, ie_mapping_result: DomainMappingSpec) -> None:
        """At least 7 variables should be mapped for IE."""
        assert ie_mapping_result.total_variables >= 7, (
            f"Expected at least 7 mapped variables, got {ie_mapping_result.total_variables}"
        )

    def test_required_variables_mapped(self, ie_mapping_result: DomainMappingSpec) -> None:
        """All required IE variables must have mappings."""
        mapped_vars = {m.sdtm_variable for m in ie_mapping_result.variable_mappings}
        missing = REQUIRED_IE_VARIABLES - mapped_vars
        assert not missing, (
            f"Missing required IE variables: {missing}. "
            f"Mapped variables: {sorted(mapped_vars)}"
        )

    def test_findings_class(self, ie_mapping_result: DomainMappingSpec) -> None:
        """IE should be identified as Findings-class domain."""
        assert ie_mapping_result.domain_class == "Findings", (
            f"Expected Findings class, got {ie_mapping_result.domain_class}"
        )

    def test_high_confidence_exists(self, ie_mapping_result: DomainMappingSpec) -> None:
        """At least some mappings should have HIGH confidence."""
        assert ie_mapping_result.high_confidence_count > 0, (
            "No HIGH confidence mappings found. Distribution: "
            f"HIGH={ie_mapping_result.high_confidence_count}, "
            f"MEDIUM={ie_mapping_result.medium_confidence_count}, "
            f"LOW={ie_mapping_result.low_confidence_count}"
        )

    def test_ieorres_mapped(self, ie_mapping_result: DomainMappingSpec) -> None:
        """At least IEORRES or IESTRESC should be present."""
        mapped_vars = {m.sdtm_variable for m in ie_mapping_result.variable_mappings}
        has_result = "IEORRES" in mapped_vars or "IESTRESC" in mapped_vars
        assert has_result, (
            f"Neither IEORRES nor IESTRESC found. "
            f"Mapped variables: {sorted(mapped_vars)}"
        )


@pytest.mark.integration
@_skip_no_api_key
class TestIEExportRoundtrip:
    """Test JSON export and round-trip validation for IE mapping."""

    def test_json_export_roundtrip(
        self, ie_mapping_result: DomainMappingSpec, tmp_path: Path
    ) -> None:
        """Export to JSON, read back, and validate round-trip."""
        json_path = tmp_path / "ie_mapping.json"
        json_path.write_text(ie_mapping_result.model_dump_json(indent=2))

        assert json_path.exists()
        assert json_path.stat().st_size > 0

        raw = json.loads(json_path.read_text())
        roundtripped = DomainMappingSpec.model_validate(raw)

        assert roundtripped.domain == ie_mapping_result.domain
        assert roundtripped.total_variables == ie_mapping_result.total_variables
        assert len(roundtripped.variable_mappings) == len(ie_mapping_result.variable_mappings)
