"""Integration test for MH domain mapping using real Fakedata and real LLM calls.

This module exercises MappingEngine.map_domain() for Medical History (MH):
    1. Profile BOTH mh.sas7bdat AND haemh.sas7bdat from Fakedata/
    2. Build context with eCRF form metadata for MH
    3. Call Claude for structured mapping proposals
    4. Validate and enrich proposals against SDTM-IG + CT
    5. Export to JSON round-trip

MH validates multi-source MedDRA mapping with two source files.

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

# Required MH variables per SDTM-IG v3.4
REQUIRED_MH_VARIABLES = {"STUDYID", "DOMAIN", "USUBJID", "MHSEQ", "MHTERM"}

# Skip condition: no API key means we cannot run LLM calls
_skip_no_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping integration test",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_mh_ecrf_form() -> ECRFForm:
    """Build a realistic MH eCRF form from known mh.sas7bdat structure.

    MH has MedDRA coded terms (_PT, _SOC), onset date, and ongoing flag.
    """
    fields = [
        ECRFField(
            field_number=1,
            field_name="MHYN",
            data_type="$3",
            sas_label="Any Medical History?",
            coded_values={"Yes": "Yes", "No": "No"},
            field_oid="MHYN",
        ),
        ECRFField(
            field_number=2,
            field_name="MHTERM",
            data_type="$200",
            sas_label="Medical History Term",
            coded_values=None,
            field_oid="MHTERM",
        ),
        ECRFField(
            field_number=3,
            field_name="MHTERM_PT",
            data_type="$200",
            sas_label="MedDRA Preferred Term",
            coded_values=None,
            field_oid="MHTERM_PT",
        ),
        ECRFField(
            field_number=4,
            field_name="MHTERM_SOC",
            data_type="$200",
            sas_label="MedDRA System Organ Class",
            coded_values=None,
            field_oid="MHTERM_SOC",
        ),
        ECRFField(
            field_number=5,
            field_name="MHSTDAT",
            data_type="datetime",
            sas_label="Start Date of Medical History",
            coded_values=None,
            field_oid="MHSTDAT",
        ),
        ECRFField(
            field_number=6,
            field_name="MHSTDAT_RAW",
            data_type="$25",
            sas_label="Start Date (character)",
            coded_values=None,
            field_oid="MHSTDAT_RAW",
        ),
        ECRFField(
            field_number=7,
            field_name="MHONGO",
            data_type="$3",
            sas_label="Ongoing?",
            coded_values={"Yes": "Yes", "No": "No"},
            field_oid="MHONGO",
        ),
        ECRFField(
            field_number=8,
            field_name="MHENDAT",
            data_type="datetime",
            sas_label="End Date of Medical History",
            coded_values=None,
            field_oid="MHENDAT",
        ),
    ]

    return ECRFForm(
        form_name="Medical History",
        fields=fields,
        page_numbers=[25, 26],
    )


def _profile_dataset(filename: str) -> DatasetProfile:
    """Profile a single SAS dataset from Fakedata/."""
    path = FAKEDATA_DIR / filename
    if not path.exists():
        pytest.skip(f"Fakedata file not found: {path}")
    df, meta = read_sas_with_metadata(path)
    return profile_dataset(df, meta)


# ---------------------------------------------------------------------------
# Module-scoped fixture: run mapping once, reuse across tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def mh_mapping_result() -> DomainMappingSpec:
    """Run the full MH mapping pipeline once and cache the result.

    Profiles both mh.sas7bdat and haemh.sas7bdat as multi-source inputs.
    haemh_screen.sas7bdat has 0 rows and is skipped.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Profile primary and secondary datasets
    mh_profile = _profile_dataset("mh.sas7bdat")
    haemh_profile = _profile_dataset("haemh.sas7bdat")
    # haemh_screen.sas7bdat has 0 rows -- skip

    # Build eCRF form
    ecrf_form = _build_mh_ecrf_form()

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

    # Run the mapping with both source profiles
    spec = engine.map_domain(
        domain="MH",
        source_profiles=[mh_profile, haemh_profile],
        ecrf_forms=[ecrf_form],
        study_metadata=study_metadata,
    )

    return spec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_api_key
class TestMHMappingEndToEnd:
    """End-to-end tests for MH domain mapping on real Fakedata."""

    def test_domain_is_mh(self, mh_mapping_result: DomainMappingSpec) -> None:
        """Mapping result targets the MH domain."""
        assert mh_mapping_result.domain == "MH"

    def test_sufficient_variable_count(self, mh_mapping_result: DomainMappingSpec) -> None:
        """At least 8 variables should be mapped for MH."""
        assert mh_mapping_result.total_variables >= 8, (
            f"Expected at least 8 mapped variables, got {mh_mapping_result.total_variables}"
        )

    def test_required_variables_mapped(self, mh_mapping_result: DomainMappingSpec) -> None:
        """All required MH variables must have mappings."""
        mapped_vars = {m.sdtm_variable for m in mh_mapping_result.variable_mappings}
        missing = REQUIRED_MH_VARIABLES - mapped_vars
        assert not missing, (
            f"Missing required MH variables: {missing}. Mapped variables: {sorted(mapped_vars)}"
        )

    def test_mhdecod_mapped(self, mh_mapping_result: DomainMappingSpec) -> None:
        """MHDECOD (MedDRA Preferred Term) should be mapped."""
        mapped_vars = {m.sdtm_variable for m in mh_mapping_result.variable_mappings}
        assert "MHDECOD" in mapped_vars, (
            f"MHDECOD not found. Mapped variables: {sorted(mapped_vars)}"
        )

    def test_dates_mapped(self, mh_mapping_result: DomainMappingSpec) -> None:
        """MHSTDTC (start date) should be mapped."""
        mapped_vars = {m.sdtm_variable for m in mh_mapping_result.variable_mappings}
        assert "MHSTDTC" in mapped_vars, (
            f"MHSTDTC not found. Mapped variables: {sorted(mapped_vars)}"
        )

    def test_high_confidence_exists(self, mh_mapping_result: DomainMappingSpec) -> None:
        """At least some mappings should have HIGH confidence."""
        assert mh_mapping_result.high_confidence_count > 0, (
            "No HIGH confidence mappings found. Distribution: "
            f"HIGH={mh_mapping_result.high_confidence_count}, "
            f"MEDIUM={mh_mapping_result.medium_confidence_count}, "
            f"LOW={mh_mapping_result.low_confidence_count}"
        )

    def test_multiple_source_datasets(self, mh_mapping_result: DomainMappingSpec) -> None:
        """MH should reference both source datasets (mh + haemh)."""
        assert len(mh_mapping_result.source_datasets) == 2, (
            f"Expected 2 source datasets, got {mh_mapping_result.source_datasets}"
        )


@pytest.mark.integration
@_skip_no_api_key
class TestMHCTValidation:
    """Validate controlled terminology references in MH mapping output."""

    def test_yn_codelist_if_present(self, mh_mapping_result: DomainMappingSpec) -> None:
        """If MHPRESP or MHOCCUR mapped, they should reference C66742 (Y/N)."""
        yn_vars = {"MHPRESP", "MHOCCUR"}
        for m in mh_mapping_result.variable_mappings:
            if m.sdtm_variable in yn_vars and m.codelist_code is not None:
                assert m.codelist_code == "C66742", (
                    f"{m.sdtm_variable} codelist should be C66742, got {m.codelist_code}"
                )


@pytest.mark.integration
@_skip_no_api_key
class TestMHExportRoundtrip:
    """Test JSON export and round-trip validation for MH mapping."""

    def test_json_export_roundtrip(
        self, mh_mapping_result: DomainMappingSpec, tmp_path: Path
    ) -> None:
        """Export to JSON, read back, and validate round-trip."""
        json_path = tmp_path / "mh_mapping.json"
        json_path.write_text(mh_mapping_result.model_dump_json(indent=2))

        assert json_path.exists()
        assert json_path.stat().st_size > 0

        raw = json.loads(json_path.read_text())
        roundtripped = DomainMappingSpec.model_validate(raw)

        assert roundtripped.domain == mh_mapping_result.domain
        assert roundtripped.total_variables == mh_mapping_result.total_variables
        assert len(roundtripped.variable_mappings) == len(mh_mapping_result.variable_mappings)
