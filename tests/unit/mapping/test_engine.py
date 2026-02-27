"""Tests for MappingEngine orchestrator.

Uses a mock LLM client to verify the full mapping flow without API calls.
Real SDTMReference and CTReference are used for realistic enrichment.
"""

from __future__ import annotations

import re
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from astraea.mapping.engine import MappingEngine
from astraea.models.ecrf import ECRFField, ECRFForm
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingProposal,
    MappingPattern,
    StudyMetadata,
    VariableMappingProposal,
)
from astraea.models.profiling import DatasetProfile, VariableProfile
from astraea.models.sdtm import CoreDesignation
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference


@pytest.fixture()
def sdtm_ref() -> SDTMReference:
    """Real SDTM-IG reference from bundled data."""
    return SDTMReference()


@pytest.fixture()
def ct_ref() -> CTReference:
    """Real CT reference from bundled data."""
    return CTReference()


@pytest.fixture()
def study_metadata() -> StudyMetadata:
    """Study metadata for test mapping."""
    return StudyMetadata(
        study_id="PHA022121-C301",
        site_id_variable="SiteNumber",
        subject_id_variable="Subject",
    )


@pytest.fixture()
def dm_profile() -> DatasetProfile:
    """Minimal DM dataset profile with clinical and EDC columns."""
    return DatasetProfile(
        filename="dm.sas7bdat",
        row_count=3,
        col_count=10,
        variables=[
            VariableProfile(
                name="projectid",
                label="Project ID",
                dtype="character",
                n_total=3,
                n_missing=0,
                n_unique=1,
                missing_pct=0.0,
                sample_values=["PHA022121"],
                is_edc_column=True,
            ),
            VariableProfile(
                name="AGE",
                label="Age",
                dtype="numeric",
                n_total=3,
                n_missing=0,
                n_unique=3,
                missing_pct=0.0,
                sample_values=["61", "46", "40"],
            ),
            VariableProfile(
                name="SEX_STD",
                label="Sex (coded)",
                dtype="character",
                n_total=3,
                n_missing=0,
                n_unique=2,
                missing_pct=0.0,
                sample_values=["F", "M"],
            ),
            VariableProfile(
                name="ETHNIC_STD",
                label="Ethnicity (coded)",
                dtype="character",
                n_total=3,
                n_missing=0,
                n_unique=1,
                missing_pct=0.0,
                sample_values=["NOT HISPANIC OR LATINO"],
            ),
        ],
    )


@pytest.fixture()
def demographics_form() -> ECRFForm:
    """Minimal demographics eCRF form."""
    return ECRFForm(
        form_name="Demographics",
        fields=[
            ECRFField(
                field_number=1,
                field_name="AGE",
                data_type="1",
                sas_label="Age",
            ),
            ECRFField(
                field_number=2,
                field_name="SEX",
                data_type="$25",
                sas_label="Sex",
                coded_values={"F": "Female", "M": "Male"},
            ),
        ],
    )


def _build_mock_dm_proposal() -> DomainMappingProposal:
    """Build a realistic DM mapping proposal that a mock LLM would return."""
    return DomainMappingProposal(
        domain="DM",
        variable_proposals=[
            VariableMappingProposal(
                sdtm_variable="STUDYID",
                source_dataset=None,
                source_variable=None,
                mapping_pattern=MappingPattern.ASSIGN,
                mapping_logic="Assign constant study identifier",
                assigned_value="PHA022121-C301",
                confidence=0.99,
                rationale="Standard constant assignment for STUDYID",
            ),
            VariableMappingProposal(
                sdtm_variable="DOMAIN",
                source_dataset=None,
                source_variable=None,
                mapping_pattern=MappingPattern.ASSIGN,
                mapping_logic="Assign constant domain code",
                assigned_value="DM",
                codelist_code="C66734",
                confidence=0.99,
                rationale="Standard constant assignment for DOMAIN",
            ),
            VariableMappingProposal(
                sdtm_variable="USUBJID",
                source_dataset="dm.sas7bdat",
                source_variable="Subject",
                mapping_pattern=MappingPattern.COMBINE,
                mapping_logic="Concatenate STUDYID + SITEID + SUBJID",
                derivation_rule='CONCAT(STUDYID, "-", SITEID, "-", Subject)',
                confidence=0.92,
                rationale="Standard USUBJID derivation",
            ),
            VariableMappingProposal(
                sdtm_variable="AGE",
                source_dataset="dm.sas7bdat",
                source_variable="AGE",
                mapping_pattern=MappingPattern.DIRECT,
                mapping_logic="Direct carry from source AGE",
                confidence=0.95,
                rationale="Same variable name and content, numeric age",
            ),
            VariableMappingProposal(
                sdtm_variable="SEX",
                source_dataset="dm.sas7bdat",
                source_variable="SEX_STD",
                mapping_pattern=MappingPattern.RENAME,
                mapping_logic="Rename SEX_STD to SEX; values are CT submission values",
                codelist_code="C66731",
                confidence=0.93,
                rationale="_STD column contains valid CT terms F, M",
            ),
            VariableMappingProposal(
                sdtm_variable="ETHNIC",
                source_dataset="dm.sas7bdat",
                source_variable="ETHNIC_STD",
                mapping_pattern=MappingPattern.LOOKUP_RECODE,
                mapping_logic="Map through ethnicity codelist",
                codelist_code="C66790",
                confidence=0.85,
                rationale="ETHNIC_STD contains coded values matching CT",
            ),
            VariableMappingProposal(
                sdtm_variable="RFSTDTC",
                source_dataset="ex.sas7bdat",
                source_variable="EXDAT",
                mapping_pattern=MappingPattern.DERIVATION,
                mapping_logic="ISO 8601 of min EX dose date per subject",
                derivation_rule="ISO8601(MIN(ex.EXDAT WHERE ex.EXYN == 'Yes'))",
                confidence=0.78,
                rationale="Cross-domain derivation from EX dataset",
            ),
        ],
        unmapped_source_variables=["DMCBP", "HEIGHT", "HEIGHT_UNITS"],
        suppqual_candidates=["DMCBP"],
        mapping_notes="DM mapping for study PHA022121-C301",
    )


class TestMappingEngine:
    """Tests for MappingEngine.map_domain()."""

    def test_map_domain_returns_spec(
        self,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
        study_metadata: StudyMetadata,
        dm_profile: DatasetProfile,
        demographics_form: ECRFForm,
    ) -> None:
        """map_domain returns a DomainMappingSpec with correct domain and study_id."""
        mock_llm = MagicMock()
        mock_llm.parse.return_value = _build_mock_dm_proposal()

        engine = MappingEngine(mock_llm, sdtm_ref, ct_ref)
        spec = engine.map_domain(
            domain="DM",
            source_profiles=[dm_profile],
            ecrf_forms=[demographics_form],
            study_metadata=study_metadata,
        )

        assert spec.domain == "DM"
        assert spec.study_id == "PHA022121-C301"
        assert spec.domain_label == "Demographics"
        assert spec.domain_class == "Special-Purpose"
        assert len(spec.variable_mappings) == 7

    def test_enriched_mappings_have_labels(
        self,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
        study_metadata: StudyMetadata,
        dm_profile: DatasetProfile,
        demographics_form: ECRFForm,
    ) -> None:
        """Enriched mappings include SDTM-IG labels and core designations."""
        mock_llm = MagicMock()
        mock_llm.parse.return_value = _build_mock_dm_proposal()

        engine = MappingEngine(mock_llm, sdtm_ref, ct_ref)
        spec = engine.map_domain(
            domain="DM",
            source_profiles=[dm_profile],
            ecrf_forms=[demographics_form],
            study_metadata=study_metadata,
        )

        # Find STUDYID mapping
        studyid = next(m for m in spec.variable_mappings if m.sdtm_variable == "STUDYID")
        assert studyid.sdtm_label == "Study Identifier"
        assert studyid.core == CoreDesignation.REQ

        # Find AGE mapping
        age = next(m for m in spec.variable_mappings if m.sdtm_variable == "AGE")
        assert age.sdtm_data_type == "Num"
        assert age.core == CoreDesignation.EXP

    def test_summary_counts_correct(
        self,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
        study_metadata: StudyMetadata,
        dm_profile: DatasetProfile,
        demographics_form: ECRFForm,
    ) -> None:
        """Summary counts (high/medium/low) are computed correctly."""
        mock_llm = MagicMock()
        mock_llm.parse.return_value = _build_mock_dm_proposal()

        engine = MappingEngine(mock_llm, sdtm_ref, ct_ref)
        spec = engine.map_domain(
            domain="DM",
            source_profiles=[dm_profile],
            ecrf_forms=[demographics_form],
            study_metadata=study_metadata,
        )

        assert spec.total_variables == 7
        assert spec.high_confidence_count + spec.medium_confidence_count + spec.low_confidence_count == 7
        assert spec.high_confidence_count >= 1  # At least STUDYID, AGE, SEX are high
        assert spec.required_mapped >= 1  # At least STUDYID is required

    def test_mapping_timestamp_valid_iso(
        self,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
        study_metadata: StudyMetadata,
        dm_profile: DatasetProfile,
        demographics_form: ECRFForm,
    ) -> None:
        """mapping_timestamp is a valid ISO 8601 string."""
        mock_llm = MagicMock()
        mock_llm.parse.return_value = _build_mock_dm_proposal()

        engine = MappingEngine(mock_llm, sdtm_ref, ct_ref)
        spec = engine.map_domain(
            domain="DM",
            source_profiles=[dm_profile],
            ecrf_forms=[demographics_form],
            study_metadata=study_metadata,
        )

        # Verify ISO 8601 format
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", spec.mapping_timestamp)
        # Parse it to confirm validity
        datetime.fromisoformat(spec.mapping_timestamp.replace("Z", "+00:00"))

    def test_model_used_is_set(
        self,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
        study_metadata: StudyMetadata,
        dm_profile: DatasetProfile,
        demographics_form: ECRFForm,
    ) -> None:
        """model_used is set to the model passed to map_domain."""
        mock_llm = MagicMock()
        mock_llm.parse.return_value = _build_mock_dm_proposal()

        engine = MappingEngine(mock_llm, sdtm_ref, ct_ref)
        spec = engine.map_domain(
            domain="DM",
            source_profiles=[dm_profile],
            ecrf_forms=[demographics_form],
            study_metadata=study_metadata,
        )

        assert spec.model_used == "claude-sonnet-4-20250514"

    def test_custom_model(
        self,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
        study_metadata: StudyMetadata,
        dm_profile: DatasetProfile,
        demographics_form: ECRFForm,
    ) -> None:
        """Custom model name is passed through."""
        mock_llm = MagicMock()
        mock_llm.parse.return_value = _build_mock_dm_proposal()

        engine = MappingEngine(mock_llm, sdtm_ref, ct_ref)
        spec = engine.map_domain(
            domain="DM",
            source_profiles=[dm_profile],
            ecrf_forms=[demographics_form],
            study_metadata=study_metadata,
            model="claude-opus-4-20250514",
        )

        assert spec.model_used == "claude-opus-4-20250514"

    def test_unmapped_and_suppqual_forwarded(
        self,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
        study_metadata: StudyMetadata,
        dm_profile: DatasetProfile,
        demographics_form: ECRFForm,
    ) -> None:
        """Unmapped variables and suppqual candidates are forwarded from proposal."""
        mock_llm = MagicMock()
        mock_llm.parse.return_value = _build_mock_dm_proposal()

        engine = MappingEngine(mock_llm, sdtm_ref, ct_ref)
        spec = engine.map_domain(
            domain="DM",
            source_profiles=[dm_profile],
            ecrf_forms=[demographics_form],
            study_metadata=study_metadata,
        )

        assert "DMCBP" in spec.unmapped_source_variables
        assert "DMCBP" in spec.suppqual_candidates

    def test_confidence_boost_applied(
        self,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
        study_metadata: StudyMetadata,
        dm_profile: DatasetProfile,
        demographics_form: ECRFForm,
    ) -> None:
        """ETHNIC lookup_recode gets +0.05 confidence boost."""
        mock_llm = MagicMock()
        mock_llm.parse.return_value = _build_mock_dm_proposal()

        engine = MappingEngine(mock_llm, sdtm_ref, ct_ref)
        spec = engine.map_domain(
            domain="DM",
            source_profiles=[dm_profile],
            ecrf_forms=[demographics_form],
            study_metadata=study_metadata,
        )

        ethnic = next(m for m in spec.variable_mappings if m.sdtm_variable == "ETHNIC")
        # Original confidence 0.85 + 0.05 boost = 0.90
        assert ethnic.confidence == pytest.approx(0.90, abs=0.001)
        assert ethnic.confidence_level == ConfidenceLevel.HIGH

    def test_unknown_domain_raises(
        self,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
        study_metadata: StudyMetadata,
        dm_profile: DatasetProfile,
        demographics_form: ECRFForm,
    ) -> None:
        """Unknown domain raises ValueError."""
        mock_llm = MagicMock()
        engine = MappingEngine(mock_llm, sdtm_ref, ct_ref)

        with pytest.raises(ValueError, match="not found"):
            engine.map_domain(
                domain="ZZFAKE",
                source_profiles=[dm_profile],
                ecrf_forms=[demographics_form],
                study_metadata=study_metadata,
            )

    def test_llm_called_with_correct_params(
        self,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
        study_metadata: StudyMetadata,
        dm_profile: DatasetProfile,
        demographics_form: ECRFForm,
    ) -> None:
        """Verify the LLM client is called with expected parameters."""
        mock_llm = MagicMock()
        mock_llm.parse.return_value = _build_mock_dm_proposal()

        engine = MappingEngine(mock_llm, sdtm_ref, ct_ref)
        engine.map_domain(
            domain="DM",
            source_profiles=[dm_profile],
            ecrf_forms=[demographics_form],
            study_metadata=study_metadata,
        )

        mock_llm.parse.assert_called_once()
        call_kwargs = mock_llm.parse.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs.kwargs["temperature"] == 0.1
        assert call_kwargs.kwargs["output_format"] is DomainMappingProposal
        assert "SDTM Domain: DM" in call_kwargs.kwargs["messages"][0]["content"]
