"""Integration test for AE domain mapping using real Fakedata and real LLM calls.

Exercises the full mapping pipeline end-to-end for Adverse Events:
    1. Profile real ae.sas7bdat from Fakedata/
    2. Build context with AE eCRF form metadata
    3. Call Claude for structured mapping proposals
    4. Validate and enrich proposals against SDTM-IG + CT
    5. Export to JSON round-trip

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

# Required AE variables per SDTM-IG v3.4
REQUIRED_AE_VARIABLES = {"STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM", "AEDECOD"}

# Skip condition: no API key means we cannot run LLM calls
_skip_no_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping integration test",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_ae_ecrf_form() -> ECRFForm:
    """Build a realistic Adverse Events eCRF form from known ae.sas7bdat structure.

    Includes fields for the reported term, MedDRA coding, seriousness criteria,
    severity grade, action taken, outcome, causality, and dates.
    """
    fields = [
        ECRFField(
            field_number=1,
            field_name="AETERM",
            data_type="$200",
            sas_label="Adverse Event",
            coded_values=None,
            field_oid="AETERM",
        ),
        ECRFField(
            field_number=2,
            field_name="AETERM_PT",
            data_type="$200",
            sas_label="Adverse Event - MedDRA Preferred Term",
            coded_values=None,
            field_oid="AETERM_PT",
        ),
        ECRFField(
            field_number=3,
            field_name="AETERM_SOC",
            data_type="$200",
            sas_label="Adverse Event - MedDRA System Organ Class",
            coded_values=None,
            field_oid="AETERM_SOC",
        ),
        ECRFField(
            field_number=4,
            field_name="AETERM_LLT",
            data_type="$200",
            sas_label="Adverse Event - MedDRA Lowest Level Term",
            coded_values=None,
            field_oid="AETERM_LLT",
        ),
        ECRFField(
            field_number=5,
            field_name="AETERM_HLT",
            data_type="$200",
            sas_label="Adverse Event - MedDRA High Level Term",
            coded_values=None,
            field_oid="AETERM_HLT",
        ),
        ECRFField(
            field_number=6,
            field_name="AESER",
            data_type="$10",
            sas_label="Is the event serious",
            coded_values={"Y": "Yes", "N": "No"},
            field_oid="AESER",
        ),
        ECRFField(
            field_number=7,
            field_name="AESDTH",
            data_type="1",
            sas_label="Led to death",
            coded_values={"1": "Yes", "0": "No"},
            field_oid="AESDTH",
        ),
        ECRFField(
            field_number=8,
            field_name="AESLIFE",
            data_type="1",
            sas_label="Life-threatening",
            coded_values={"1": "Yes", "0": "No"},
            field_oid="AESLIFE",
        ),
        ECRFField(
            field_number=9,
            field_name="AESHOSP",
            data_type="1",
            sas_label="Required in-patient hospitalization",
            coded_values={"1": "Yes", "0": "No"},
            field_oid="AESHOSP",
        ),
        ECRFField(
            field_number=10,
            field_name="AESDISAB",
            data_type="1",
            sas_label="Persistent or significant incapacity",
            coded_values={"1": "Yes", "0": "No"},
            field_oid="AESDISAB",
        ),
        ECRFField(
            field_number=11,
            field_name="AESCONG",
            data_type="1",
            sas_label="Resulted in congenital anomaly or birth defect",
            coded_values={"1": "Yes", "0": "No"},
            field_oid="AESCONG",
        ),
        ECRFField(
            field_number=12,
            field_name="AESOTH",
            data_type="1",
            sas_label="Important Medical Event",
            coded_values={"1": "Yes", "0": "No"},
            field_oid="AESOTH",
        ),
        ECRFField(
            field_number=13,
            field_name="AEGRSER",
            data_type="$10",
            sas_label="CTCAE Grade",
            coded_values={
                "1": "Grade 1",
                "2": "Grade 2",
                "3": "Grade 3",
                "4": "Grade 4",
                "5": "Grade 5",
            },
            field_oid="AEGRSER",
        ),
        ECRFField(
            field_number=14,
            field_name="AEOUT",
            data_type="$50",
            sas_label="Outcome",
            coded_values=None,
            field_oid="AEOUT",
        ),
        ECRFField(
            field_number=15,
            field_name="AEACN",
            data_type="$50",
            sas_label="Action Taken with Study Drug",
            coded_values=None,
            field_oid="AEACN",
        ),
        ECRFField(
            field_number=16,
            field_name="AEREL",
            data_type="$50",
            sas_label="Relationship to Study Drug",
            coded_values=None,
            field_oid="AEREL",
        ),
        ECRFField(
            field_number=17,
            field_name="AESTDAT",
            data_type="dd MMM yyyy",
            sas_label="Start Date",
            coded_values=None,
            field_oid="AESTDAT",
        ),
        ECRFField(
            field_number=18,
            field_name="AEENDAT",
            data_type="dd MMM yyyy",
            sas_label="End Date",
            coded_values=None,
            field_oid="AEENDAT",
        ),
        ECRFField(
            field_number=19,
            field_name="AEONGO",
            data_type="$10",
            sas_label="Is this event ongoing",
            coded_values={"Y": "Yes", "N": "No"},
            field_oid="AEONGO",
        ),
    ]

    return ECRFForm(
        form_name="Adverse Events",
        fields=fields,
        page_numbers=[30, 31, 32, 33],
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
def ae_mapping_result() -> DomainMappingSpec:
    """Run the full AE mapping pipeline once and cache the result."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    ae_profile = _profile_dataset("ae.sas7bdat")
    ecrf_form = _build_ae_ecrf_form()

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
        domain="AE",
        source_profiles=[ae_profile],
        ecrf_forms=[ecrf_form],
        study_metadata=study_metadata,
    )

    _display_mapping_spec(spec, "AE")
    return spec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_api_key
class TestAEMappingEndToEnd:
    """End-to-end tests for AE domain mapping on real Fakedata."""

    def test_domain_is_ae(self, ae_mapping_result: DomainMappingSpec) -> None:
        assert ae_mapping_result.domain == "AE"

    def test_sufficient_variable_count(self, ae_mapping_result: DomainMappingSpec) -> None:
        """At least 15 variables should be mapped (AE has 29 possible)."""
        assert ae_mapping_result.total_variables >= 15, (
            f"Expected at least 15 mapped variables, got {ae_mapping_result.total_variables}"
        )

    def test_required_variables_mapped(self, ae_mapping_result: DomainMappingSpec) -> None:
        """All Required AE variables must have mappings."""
        mapped_vars = {m.sdtm_variable for m in ae_mapping_result.variable_mappings}
        missing = REQUIRED_AE_VARIABLES - mapped_vars
        assert not missing, (
            f"Missing required AE variables: {missing}. Mapped: {sorted(mapped_vars)}"
        )

    def test_studyid_is_assign(self, ae_mapping_result: DomainMappingSpec) -> None:
        studyid = [m for m in ae_mapping_result.variable_mappings if m.sdtm_variable == "STUDYID"]
        assert len(studyid) == 1
        assert studyid[0].mapping_pattern == MappingPattern.ASSIGN

    def test_aeterm_has_source(self, ae_mapping_result: DomainMappingSpec) -> None:
        """AETERM should be DIRECT or RENAME from a source variable."""
        aeterm = [m for m in ae_mapping_result.variable_mappings if m.sdtm_variable == "AETERM"]
        assert len(aeterm) >= 1, "AETERM mapping not found"
        assert aeterm[0].mapping_pattern in (
            MappingPattern.DIRECT,
            MappingPattern.RENAME,
        ), f"AETERM pattern should be DIRECT or RENAME, got {aeterm[0].mapping_pattern}"

    def test_aedecod_has_source(self, ae_mapping_result: DomainMappingSpec) -> None:
        """AEDECOD should be mapped from MedDRA PT column or similar."""
        aedecod = [m for m in ae_mapping_result.variable_mappings if m.sdtm_variable == "AEDECOD"]
        assert len(aedecod) >= 1, "AEDECOD mapping not found"
        # Should have a source (from AETERM_PT or AETERM)
        assert aedecod[0].source_variable is not None or aedecod[0].mapping_pattern in (
            MappingPattern.DERIVATION,
            MappingPattern.RENAME,
            MappingPattern.DIRECT,
        ), "AEDECOD should have a source variable or derivation"

    def test_seriousness_flags_mapped(self, ae_mapping_result: DomainMappingSpec) -> None:
        """At least AESDTH, AESER, AESLIFE should be present."""
        mapped_vars = {m.sdtm_variable for m in ae_mapping_result.variable_mappings}
        seriousness_vars = {"AESDTH", "AESER", "AESLIFE"}
        found = seriousness_vars & mapped_vars
        assert len(found) >= 2, (
            f"Expected at least 2 of {seriousness_vars} mapped, found {found}. "
            f"All mapped: {sorted(mapped_vars)}"
        )

    def test_dates_mapped(self, ae_mapping_result: DomainMappingSpec) -> None:
        """AESTDTC should be present in mappings."""
        mapped_vars = {m.sdtm_variable for m in ae_mapping_result.variable_mappings}
        assert "AESTDTC" in mapped_vars, (
            f"AESTDTC not found in mapped variables: {sorted(mapped_vars)}"
        )

    def test_high_confidence_exists(self, ae_mapping_result: DomainMappingSpec) -> None:
        assert ae_mapping_result.high_confidence_count > 0, (
            f"No HIGH confidence mappings. "
            f"HIGH={ae_mapping_result.high_confidence_count}, "
            f"MEDIUM={ae_mapping_result.medium_confidence_count}, "
            f"LOW={ae_mapping_result.low_confidence_count}"
        )

    def test_required_vars_reasonable_confidence(
        self, ae_mapping_result: DomainMappingSpec
    ) -> None:
        """No Required variable should have confidence below 0.5."""
        for m in ae_mapping_result.variable_mappings:
            if m.sdtm_variable in REQUIRED_AE_VARIABLES:
                assert m.confidence >= 0.5, (
                    f"Required variable {m.sdtm_variable} has low confidence: "
                    f"{m.confidence:.2f} ({m.confidence_rationale})"
                )


@pytest.mark.integration
@_skip_no_api_key
class TestAECTValidation:
    """Validate controlled terminology references in AE mapping output."""

    def test_severity_references_codelist(self, ae_mapping_result: DomainMappingSpec) -> None:
        """AESEV or AETOXGR mapping should reference C66769 or have reasonable CT."""
        sev_vars = [
            m
            for m in ae_mapping_result.variable_mappings
            if m.sdtm_variable in ("AESEV", "AETOXGR")
        ]
        if sev_vars:
            sev = sev_vars[0]
            if sev.codelist_code is not None:
                assert sev.codelist_code in ("C66769", "C66781", "C66783"), (
                    f"Severity codelist should be C66769, got {sev.codelist_code}"
                )

    def test_outcome_references_codelist(self, ae_mapping_result: DomainMappingSpec) -> None:
        """AEOUT mapping should reference C66768."""
        aeout = [m for m in ae_mapping_result.variable_mappings if m.sdtm_variable == "AEOUT"]
        if aeout and aeout[0].codelist_code is not None:
            assert aeout[0].codelist_code == "C66768", (
                f"AEOUT codelist should be C66768, got {aeout[0].codelist_code}"
            )

    def test_action_references_codelist(self, ae_mapping_result: DomainMappingSpec) -> None:
        """AEACN mapping should reference C66767."""
        aeacn = [m for m in ae_mapping_result.variable_mappings if m.sdtm_variable == "AEACN"]
        if aeacn and aeacn[0].codelist_code is not None:
            assert aeacn[0].codelist_code == "C66767", (
                f"AEACN codelist should be C66767, got {aeacn[0].codelist_code}"
            )


@pytest.mark.integration
@_skip_no_api_key
class TestAEExportRoundtrip:
    """Test JSON export and round-trip validation."""

    def test_json_export_roundtrip(
        self, ae_mapping_result: DomainMappingSpec, tmp_path: Path
    ) -> None:
        """Export to JSON, read back, and validate round-trip."""
        json_path = tmp_path / "ae_mapping.json"
        json_path.write_text(ae_mapping_result.model_dump_json(indent=2))

        assert json_path.exists()
        assert json_path.stat().st_size > 0

        raw = json.loads(json_path.read_text())
        roundtripped = DomainMappingSpec.model_validate(raw)

        assert roundtripped.domain == ae_mapping_result.domain
        assert roundtripped.total_variables == ae_mapping_result.total_variables
        assert len(roundtripped.variable_mappings) == len(ae_mapping_result.variable_mappings)
