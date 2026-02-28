"""Tests for the mapping context builder.

Verifies that MappingContextBuilder produces focused, well-structured
LLM prompt strings with EDC columns filtered out and only relevant
CT codelists included.
"""

from __future__ import annotations

import pytest

from astraea.mapping.context import MappingContextBuilder, _get_relevant_codelists
from astraea.models.ecrf import ECRFField, ECRFForm
from astraea.models.mapping import StudyMetadata
from astraea.models.profiling import DatasetProfile, VariableProfile
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference


@pytest.fixture()
def sdtm_ref() -> SDTMReference:
    """Load real SDTM-IG reference from bundled data."""
    return SDTMReference()


@pytest.fixture()
def ct_ref() -> CTReference:
    """Load real CT reference from bundled data."""
    return CTReference()


@pytest.fixture()
def builder(sdtm_ref: SDTMReference, ct_ref: CTReference) -> MappingContextBuilder:
    """Create a MappingContextBuilder with real reference data."""
    return MappingContextBuilder(sdtm_ref, ct_ref)


@pytest.fixture()
def study_metadata() -> StudyMetadata:
    """Minimal study metadata for DM domain testing."""
    return StudyMetadata(
        study_id="PHA022121-C301",
        site_id_variable="SiteNumber",
        subject_id_variable="Subject",
    )


@pytest.fixture()
def dm_source_profile() -> DatasetProfile:
    """Source dataset profile mimicking a DM dataset with EDC + clinical vars."""
    return DatasetProfile(
        filename="dm.sas7bdat",
        row_count=150,
        col_count=25,
        variables=[
            # EDC columns (should be filtered out)
            VariableProfile(
                name="projectid",
                label="Project ID",
                dtype="character",
                n_total=150,
                n_missing=0,
                n_unique=1,
                missing_pct=0.0,
                sample_values=["PHA022121-C301"],
                is_edc_column=True,
            ),
            VariableProfile(
                name="instanceId",
                label="Instance ID",
                dtype="numeric",
                n_total=150,
                n_missing=0,
                n_unique=150,
                missing_pct=0.0,
                sample_values=["1001", "1002"],
                is_edc_column=True,
            ),
            # Clinical columns (should be included)
            VariableProfile(
                name="AGE",
                label="Age",
                dtype="numeric",
                n_total=150,
                n_missing=2,
                n_unique=45,
                missing_pct=1.3,
                sample_values=["25", "30", "40", "55", "67"],
            ),
            VariableProfile(
                name="SEX_STD",
                label="Sex",
                dtype="character",
                n_total=150,
                n_missing=0,
                n_unique=2,
                missing_pct=0.0,
                sample_values=["M", "F"],
            ),
            VariableProfile(
                name="ETHNIC_STD",
                label="Ethnicity",
                dtype="character",
                n_total=150,
                n_missing=5,
                n_unique=3,
                missing_pct=3.3,
                sample_values=["HISPANIC OR LATINO", "NOT HISPANIC OR LATINO"],
            ),
        ],
        date_variables=[],
        edc_columns=["projectid", "instanceId"],
    )


@pytest.fixture()
def dm_ecrf_form() -> ECRFForm:
    """eCRF form mimicking a Demographics form."""
    return ECRFForm(
        form_name="Demographics",
        fields=[
            ECRFField(
                field_number=1,
                field_name="BRTHDAT",
                data_type="dd MMM yyyy",
                sas_label="Date of Birth",
            ),
            ECRFField(
                field_number=2,
                field_name="SEX",
                data_type="$1",
                sas_label="Sex",
                coded_values={"M": "Male", "F": "Female"},
            ),
            ECRFField(
                field_number=3,
                field_name="ETHNIC",
                data_type="$25",
                sas_label="Ethnicity",
            ),
        ],
        page_numbers=[5, 6],
    )


@pytest.fixture()
def cross_domain_profile() -> DatasetProfile:
    """Profile for a cross-domain dataset (e.g., SV for visit dates)."""
    return DatasetProfile(
        filename="sv.sas7bdat",
        row_count=500,
        col_count=10,
        variables=[
            VariableProfile(
                name="projectid",
                label="Project ID",
                dtype="character",
                n_total=500,
                n_missing=0,
                n_unique=1,
                missing_pct=0.0,
                sample_values=["PHA022121-C301"],
                is_edc_column=True,
            ),
            VariableProfile(
                name="SVSTDTC",
                label="Start Date",
                dtype="character",
                n_total=500,
                n_missing=10,
                n_unique=120,
                missing_pct=2.0,
                sample_values=["2022-01-15", "2022-02-20"],
            ),
            VariableProfile(
                name="VISIT",
                label="Visit Name",
                dtype="character",
                n_total=500,
                n_missing=0,
                n_unique=8,
                missing_pct=0.0,
                sample_values=["Screening", "Baseline", "Week 4"],
            ),
        ],
        date_variables=["SVSTDTC"],
        edc_columns=["projectid"],
    )


class TestBuildPromptDomainHeader:
    """Test that the domain header section is correctly formatted."""

    def test_build_prompt_contains_domain_header(
        self,
        builder: MappingContextBuilder,
        dm_source_profile: DatasetProfile,
        dm_ecrf_form: ECRFForm,
        study_metadata: StudyMetadata,
    ) -> None:
        output = builder.build_prompt(
            domain="DM",
            source_profiles=[dm_source_profile],
            ecrf_forms=[dm_ecrf_form],
            study_metadata=study_metadata,
        )
        assert "## SDTM Domain: DM" in output


class TestBuildPromptEDCFiltering:
    """Test that EDC system columns are excluded from output."""

    def test_build_prompt_excludes_edc_columns(
        self,
        builder: MappingContextBuilder,
        dm_source_profile: DatasetProfile,
        dm_ecrf_form: ECRFForm,
        study_metadata: StudyMetadata,
    ) -> None:
        output = builder.build_prompt(
            domain="DM",
            source_profiles=[dm_source_profile],
            ecrf_forms=[dm_ecrf_form],
            study_metadata=study_metadata,
        )
        # EDC columns should not appear in the source data section
        assert "projectid" not in output.split("## Source Data")[1].split("## eCRF")[0]
        assert "instanceId" not in output.split("## Source Data")[1].split("## eCRF")[0]


class TestBuildPromptClinicalVariables:
    """Test that clinical variables are included in source data section."""

    def test_build_prompt_includes_clinical_variables(
        self,
        builder: MappingContextBuilder,
        dm_source_profile: DatasetProfile,
        dm_ecrf_form: ECRFForm,
        study_metadata: StudyMetadata,
    ) -> None:
        output = builder.build_prompt(
            domain="DM",
            source_profiles=[dm_source_profile],
            ecrf_forms=[dm_ecrf_form],
            study_metadata=study_metadata,
        )
        assert "AGE" in output
        assert "SEX_STD" in output
        assert "ETHNIC_STD" in output


class TestBuildPromptCTCodelists:
    """Test that relevant CT codelists are included."""

    def test_build_prompt_includes_ct_codelists(
        self,
        builder: MappingContextBuilder,
        dm_source_profile: DatasetProfile,
        dm_ecrf_form: ECRFForm,
        study_metadata: StudyMetadata,
    ) -> None:
        output = builder.build_prompt(
            domain="DM",
            source_profiles=[dm_source_profile],
            ecrf_forms=[dm_ecrf_form],
            study_metadata=study_metadata,
        )
        # DM domain has SEX variable referencing C66731 (Sex codelist)
        assert "C66731" in output or "Sex" in output


class TestBuildPromptECRFFields:
    """Test that eCRF form fields appear in output."""

    def test_build_prompt_includes_ecrf_fields(
        self,
        builder: MappingContextBuilder,
        dm_source_profile: DatasetProfile,
        dm_ecrf_form: ECRFForm,
        study_metadata: StudyMetadata,
    ) -> None:
        output = builder.build_prompt(
            domain="DM",
            source_profiles=[dm_source_profile],
            ecrf_forms=[dm_ecrf_form],
            study_metadata=study_metadata,
        )
        assert "BRTHDAT" in output
        assert "Date of Birth" in output
        assert "Demographics" in output


class TestBuildPromptStudyMetadata:
    """Test that study metadata is included."""

    def test_build_prompt_includes_study_metadata(
        self,
        builder: MappingContextBuilder,
        dm_source_profile: DatasetProfile,
        dm_ecrf_form: ECRFForm,
        study_metadata: StudyMetadata,
    ) -> None:
        output = builder.build_prompt(
            domain="DM",
            source_profiles=[dm_source_profile],
            ecrf_forms=[dm_ecrf_form],
            study_metadata=study_metadata,
        )
        assert "PHA022121-C301" in output


class TestGetRelevantCodelists:
    """Test the codelist filtering helper."""

    def test_get_relevant_codelists_filters_correctly(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        dm_spec = sdtm_ref.get_domain_spec("DM")
        assert dm_spec is not None
        codelists = _get_relevant_codelists(dm_spec, ct_ref)
        # Should only include codelists referenced by DM variables
        # Every returned codelist code must be referenced by at least one DM variable
        dm_codelist_codes = {v.codelist_code for v in dm_spec.variables if v.codelist_code}
        for code in codelists:
            assert code in dm_codelist_codes


class TestBuildPromptCrossDomain:
    """Test cross-domain source profile handling."""

    def test_build_prompt_with_cross_domain(
        self,
        builder: MappingContextBuilder,
        dm_source_profile: DatasetProfile,
        dm_ecrf_form: ECRFForm,
        study_metadata: StudyMetadata,
        cross_domain_profile: DatasetProfile,
    ) -> None:
        output = builder.build_prompt(
            domain="DM",
            source_profiles=[dm_source_profile],
            ecrf_forms=[dm_ecrf_form],
            study_metadata=study_metadata,
            cross_domain_profiles={"SV": cross_domain_profile},
        )
        assert "## Cross-Domain Sources Available" in output
        assert "sv.sas7bdat" in output
        # EDC columns from cross-domain should also be filtered
        assert "SVSTDTC" in output

    def test_build_prompt_without_cross_domain(
        self,
        builder: MappingContextBuilder,
        dm_source_profile: DatasetProfile,
        dm_ecrf_form: ECRFForm,
        study_metadata: StudyMetadata,
    ) -> None:
        output = builder.build_prompt(
            domain="DM",
            source_profiles=[dm_source_profile],
            ecrf_forms=[dm_ecrf_form],
            study_metadata=study_metadata,
            cross_domain_profiles=None,
        )
        assert "## Cross-Domain Sources Available" in output
        assert "None." in output


class TestBuildPromptOutputSize:
    """Test that context stays under 20KB for DM-sized input."""

    def test_build_prompt_output_size(
        self,
        builder: MappingContextBuilder,
        dm_source_profile: DatasetProfile,
        dm_ecrf_form: ECRFForm,
        study_metadata: StudyMetadata,
    ) -> None:
        output = builder.build_prompt(
            domain="DM",
            source_profiles=[dm_source_profile],
            ecrf_forms=[dm_ecrf_form],
            study_metadata=study_metadata,
        )
        size_bytes = len(output.encode("utf-8"))
        assert size_bytes < 20480, f"Context output is {size_bytes} bytes, exceeds 20KB limit"


class TestBuildPromptUnknownDomain:
    """Test error handling for unknown domains."""

    def test_build_prompt_raises_for_unknown_domain(
        self,
        builder: MappingContextBuilder,
        dm_source_profile: DatasetProfile,
        dm_ecrf_form: ECRFForm,
        study_metadata: StudyMetadata,
    ) -> None:
        with pytest.raises(ValueError, match="Unknown SDTM domain"):
            builder.build_prompt(
                domain="ZZ",
                source_profiles=[dm_source_profile],
                ecrf_forms=[dm_ecrf_form],
                study_metadata=study_metadata,
            )


class TestBuildPromptEmptyInputs:
    """Test handling of empty source profiles and eCRF forms."""

    def test_build_prompt_empty_profiles(
        self,
        builder: MappingContextBuilder,
        dm_ecrf_form: ECRFForm,
        study_metadata: StudyMetadata,
    ) -> None:
        output = builder.build_prompt(
            domain="DM",
            source_profiles=[],
            ecrf_forms=[dm_ecrf_form],
            study_metadata=study_metadata,
        )
        assert "No source profiles provided." in output

    def test_build_prompt_empty_ecrf(
        self,
        builder: MappingContextBuilder,
        dm_source_profile: DatasetProfile,
        study_metadata: StudyMetadata,
    ) -> None:
        output = builder.build_prompt(
            domain="DM",
            source_profiles=[dm_source_profile],
            ecrf_forms=[],
            study_metadata=study_metadata,
        )
        assert "No eCRF forms provided." in output
