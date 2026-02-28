"""Tests for MappingEngine learning retriever integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from astraea.mapping.engine import MappingEngine
from astraea.models.ecrf import ECRFForm
from astraea.models.mapping import (
    DomainMappingProposal,
    StudyMetadata,
    VariableMappingProposal,
)
from astraea.models.profiling import DatasetProfile, VariableProfile


@pytest.fixture()
def mock_llm() -> MagicMock:
    """Create a mock LLM client."""
    client = MagicMock()
    # Return a minimal valid proposal
    client.parse.return_value = DomainMappingProposal(
        domain="DM",
        variable_mappings=[
            VariableMappingProposal(
                sdtm_variable="STUDYID",
                source_dataset=None,
                source_variable=None,
                mapping_pattern="assign",
                mapping_logic="Constant assignment",
                assigned_value="TEST-001",
                confidence=1.0,
                rationale="Study identifier constant",
            ),
            VariableMappingProposal(
                sdtm_variable="DOMAIN",
                source_dataset=None,
                source_variable=None,
                mapping_pattern="assign",
                mapping_logic="Domain constant",
                assigned_value="DM",
                confidence=1.0,
                rationale="Domain constant",
            ),
            VariableMappingProposal(
                sdtm_variable="USUBJID",
                source_dataset="dm.sas7bdat",
                source_variable="SUBJID",
                mapping_pattern="combine",
                mapping_logic="STUDYID + SITEID + SUBJID",
                confidence=0.95,
                rationale="Standard USUBJID derivation",
            ),
        ],
        unmapped_source_variables=[],
        suppqual_candidates=[],
    )
    return client


@pytest.fixture()
def mock_sdtm_ref() -> MagicMock:
    """Create a mock SDTMReference."""
    ref = MagicMock()
    spec = MagicMock()
    spec.domain = "DM"
    spec.description = "Demographics"
    spec.domain_class.value = "Special Purpose"
    spec.structure = "One record per subject"
    spec.key_variables = ["STUDYID", "USUBJID"]
    spec.variables = []
    ref.get_domain_spec.return_value = spec
    return ref


@pytest.fixture()
def mock_ct_ref() -> MagicMock:
    """Create a mock CTReference."""
    return MagicMock()


@pytest.fixture()
def study_metadata() -> StudyMetadata:
    """Create sample study metadata."""
    return StudyMetadata(
        study_id="TEST-001",
        site_id_variable="SiteNumber",
        subject_id_variable="Subject",
    )


@pytest.fixture()
def source_profiles() -> list[DatasetProfile]:
    """Create sample source profiles."""
    return [
        DatasetProfile(
            filename="dm.sas7bdat",
            row_count=50,
            col_count=5,
            variables=[
                VariableProfile(
                    name="SUBJID",
                    dtype="character",
                    label="Subject ID",
                    n_total=50,
                    n_unique=50,
                    n_missing=0,
                    missing_pct=0.0,
                    sample_values=["001", "002"],
                    is_edc_column=False,
                ),
            ],
        )
    ]


@pytest.fixture()
def ecrf_forms() -> list[ECRFForm]:
    """Create empty eCRF forms list."""
    return []


class TestBackwardCompatibility:
    """Tests that MappingEngine works without learning_retriever."""

    def test_init_accepts_none(
        self,
        mock_llm: MagicMock,
        mock_sdtm_ref: MagicMock,
        mock_ct_ref: MagicMock,
    ) -> None:
        """MappingEngine.__init__ accepts learning_retriever=None."""
        engine = MappingEngine(mock_llm, mock_sdtm_ref, mock_ct_ref)
        assert engine._learning is None

    def test_init_default_is_none(
        self,
        mock_llm: MagicMock,
        mock_sdtm_ref: MagicMock,
        mock_ct_ref: MagicMock,
    ) -> None:
        """Default learning_retriever is None."""
        engine = MappingEngine(mock_llm, mock_sdtm_ref, mock_ct_ref)
        assert engine._learning is None

    @patch("astraea.mapping.engine.validate_and_enrich")
    @patch("astraea.mapping.engine.check_required_coverage")
    def test_map_domain_without_learning_no_examples_in_prompt(
        self,
        mock_coverage: MagicMock,
        mock_validate: MagicMock,
        mock_llm: MagicMock,
        mock_sdtm_ref: MagicMock,
        mock_ct_ref: MagicMock,
        source_profiles: list[DatasetProfile],
        ecrf_forms: list[ECRFForm],
        study_metadata: StudyMetadata,
    ) -> None:
        """Without learning_retriever, prompt does not contain examples header."""
        mock_validate.return_value = ([], [])
        mock_coverage.return_value = []
        engine = MappingEngine(mock_llm, mock_sdtm_ref, mock_ct_ref)

        engine.map_domain(
            domain="DM",
            source_profiles=source_profiles,
            ecrf_forms=ecrf_forms,
            study_metadata=study_metadata,
        )

        # Capture the prompt sent to LLM
        call_args = mock_llm.parse.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        prompt_text = messages[0]["content"]
        assert "Relevant Past Mapping Examples" not in prompt_text


class TestWithLearningRetriever:
    """Tests that learning examples are injected when retriever is provided."""

    def test_init_accepts_mock_retriever(
        self,
        mock_llm: MagicMock,
        mock_sdtm_ref: MagicMock,
        mock_ct_ref: MagicMock,
    ) -> None:
        """MappingEngine.__init__ accepts a mock LearningRetriever."""
        mock_retriever = MagicMock()
        engine = MappingEngine(
            mock_llm, mock_sdtm_ref, mock_ct_ref, learning_retriever=mock_retriever
        )
        assert engine._learning is mock_retriever

    @patch("astraea.mapping.engine.validate_and_enrich")
    @patch("astraea.mapping.engine.check_required_coverage")
    def test_examples_injected_into_prompt(
        self,
        mock_coverage: MagicMock,
        mock_validate: MagicMock,
        mock_llm: MagicMock,
        mock_sdtm_ref: MagicMock,
        mock_ct_ref: MagicMock,
        source_profiles: list[DatasetProfile],
        ecrf_forms: list[ECRFForm],
        study_metadata: StudyMetadata,
    ) -> None:
        """When retriever returns examples, they appear in the LLM prompt."""
        mock_validate.return_value = ([], [])
        mock_coverage.return_value = []

        mock_retriever = MagicMock()
        mock_retriever.get_examples_section.return_value = (
            "## Relevant Past Mapping Examples\n\n"
            "### Approved Example 1\n"
            "Variable: AETERM (AE)\n"
            "Pattern: direct\n"
        )
        engine = MappingEngine(
            mock_llm, mock_sdtm_ref, mock_ct_ref, learning_retriever=mock_retriever
        )

        engine.map_domain(
            domain="DM",
            source_profiles=source_profiles,
            ecrf_forms=ecrf_forms,
            study_metadata=study_metadata,
        )

        # Capture the prompt sent to LLM
        call_args = mock_llm.parse.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        prompt_text = messages[0]["content"]
        assert "Relevant Past Mapping Examples" in prompt_text

    @patch("astraea.mapping.engine.validate_and_enrich")
    @patch("astraea.mapping.engine.check_required_coverage")
    def test_cold_start_prompt_unchanged(
        self,
        mock_coverage: MagicMock,
        mock_validate: MagicMock,
        mock_llm: MagicMock,
        mock_sdtm_ref: MagicMock,
        mock_ct_ref: MagicMock,
        source_profiles: list[DatasetProfile],
        ecrf_forms: list[ECRFForm],
        study_metadata: StudyMetadata,
    ) -> None:
        """When retriever returns None (cold start), prompt is unchanged."""
        mock_validate.return_value = ([], [])
        mock_coverage.return_value = []

        mock_retriever = MagicMock()
        mock_retriever.get_examples_section.return_value = None
        engine = MappingEngine(
            mock_llm, mock_sdtm_ref, mock_ct_ref, learning_retriever=mock_retriever
        )

        engine.map_domain(
            domain="DM",
            source_profiles=source_profiles,
            ecrf_forms=ecrf_forms,
            study_metadata=study_metadata,
        )

        # Capture the prompt sent to LLM
        call_args = mock_llm.parse.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        prompt_text = messages[0]["content"]
        assert "Relevant Past Mapping Examples" not in prompt_text
