"""Tests for the LearningRetriever class."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from astraea.learning.retriever import LearningRetriever
from astraea.models.profiling import DatasetProfile, VariableProfile


@pytest.fixture()
def mock_vector_store() -> MagicMock:
    """Create a mock LearningVectorStore."""
    store = MagicMock()
    store.query_similar_corrections.return_value = []
    store.query_similar_mappings.return_value = []
    return store


@pytest.fixture()
def retriever(mock_vector_store: MagicMock) -> LearningRetriever:
    """Create a LearningRetriever with mock store."""
    return LearningRetriever(mock_vector_store)


@pytest.fixture()
def sample_profiles() -> list[DatasetProfile]:
    """Create sample DatasetProfile list for testing."""
    return [
        DatasetProfile(
            filename="ae.sas7bdat",
            row_count=100,
            col_count=3,
            variables=[
                VariableProfile(
                    name="AETERM",
                    dtype="character",
                    label="Reported Term for the Adverse Event",
                    n_total=100,
                    n_unique=50,
                    n_missing=0,
                    missing_pct=0.0,
                    sample_values=["Headache", "Nausea"],
                    is_edc_column=False,
                ),
                VariableProfile(
                    name="AESTDT",
                    dtype="numeric",
                    label="Start Date",
                    n_total=100,
                    n_unique=80,
                    n_missing=5,
                    missing_pct=5.0,
                    sample_values=["22738"],
                    is_edc_column=False,
                ),
                VariableProfile(
                    name="projectid",
                    dtype="character",
                    label="Project ID",
                    n_total=100,
                    n_unique=1,
                    n_missing=0,
                    missing_pct=0.0,
                    sample_values=["PRJ001"],
                    is_edc_column=True,
                ),
            ],
        )
    ]


@pytest.fixture()
def sample_corrections() -> list[dict]:
    """Sample correction results from vector store."""
    return [
        {
            "document": (
                "SDTM domain AE variable AEDECOD. "
                "original pattern: direct. "
                "original logic: Direct carry from AETERM. "
                "corrected pattern: derivation. "
                "corrected logic: Derive via MedDRA coding lookup. "
                "reason: AEDECOD requires dictionary-derived preferred term"
            ),
            "metadata": {
                "study_id": "STUDY001",
                "domain": "AE",
                "sdtm_variable": "AEDECOD",
                "correction_type": "logic_change",
                "original_pattern": "direct",
                "corrected_pattern": "derivation",
                "invalidated": "false",
            },
            "distance": 0.3,
        },
    ]


@pytest.fixture()
def sample_approved() -> list[dict]:
    """Sample approved mapping results from vector store."""
    return [
        {
            "document": (
                "SDTM domain AE variable AETERM. "
                "mapping pattern: direct. "
                "logic: Direct carry from source ae.AETERM. "
                "source variable: AETERM"
            ),
            "metadata": {
                "study_id": "STUDY001",
                "domain": "AE",
                "sdtm_variable": "AETERM",
                "mapping_pattern": "direct",
                "was_corrected": "false",
                "confidence": 0.95,
            },
            "distance": 0.2,
        },
        {
            "document": (
                "SDTM domain AE variable AESTDTC. "
                "mapping pattern: reformat. "
                "logic: Convert SAS datetime to ISO 8601. "
                "source variable: AESTDT"
            ),
            "metadata": {
                "study_id": "STUDY001",
                "domain": "AE",
                "sdtm_variable": "AESTDTC",
                "mapping_pattern": "reformat",
                "was_corrected": "false",
                "confidence": 0.90,
            },
            "distance": 0.25,
        },
    ]


class TestColdStart:
    """Tests for cold start behavior (no learning data)."""

    def test_returns_none_when_both_empty(
        self,
        retriever: LearningRetriever,
        sample_profiles: list[DatasetProfile],
    ) -> None:
        """get_examples_section returns None when no data exists."""
        result = retriever.get_examples_section(
            domain="AE",
            source_profiles=sample_profiles,
        )
        assert result is None

    def test_store_queried_with_correct_domain(
        self,
        retriever: LearningRetriever,
        mock_vector_store: MagicMock,
        sample_profiles: list[DatasetProfile],
    ) -> None:
        """Both corrections and mappings queries use the correct domain."""
        retriever.get_examples_section(
            domain="AE",
            source_profiles=sample_profiles,
        )
        mock_vector_store.query_similar_corrections.assert_called_once()
        call_kwargs = mock_vector_store.query_similar_corrections.call_args
        assert call_kwargs.kwargs.get("domain") == "AE" or call_kwargs[1].get("domain") == "AE"


class TestWithCorrections:
    """Tests for behavior when corrections exist."""

    def test_returns_formatted_string_with_corrections(
        self,
        retriever: LearningRetriever,
        mock_vector_store: MagicMock,
        sample_profiles: list[DatasetProfile],
        sample_corrections: list[dict],
    ) -> None:
        """Returns formatted string when corrections exist."""
        mock_vector_store.query_similar_corrections.return_value = sample_corrections
        result = retriever.get_examples_section(
            domain="AE",
            source_profiles=sample_profiles,
        )
        assert result is not None
        assert "Relevant Past Mapping Examples" in result
        assert "Correction Example 1" in result
        assert "AEDECOD" in result

    def test_corrections_appear_before_approved(
        self,
        retriever: LearningRetriever,
        mock_vector_store: MagicMock,
        sample_profiles: list[DatasetProfile],
        sample_corrections: list[dict],
        sample_approved: list[dict],
    ) -> None:
        """Corrections are listed before approved examples."""
        mock_vector_store.query_similar_corrections.return_value = sample_corrections
        mock_vector_store.query_similar_mappings.return_value = sample_approved
        result = retriever.get_examples_section(
            domain="AE",
            source_profiles=sample_profiles,
        )
        assert result is not None
        correction_pos = result.index("Correction Example 1")
        approved_pos = result.index("Approved Example 1")
        assert correction_pos < approved_pos


class TestWithApprovedOnly:
    """Tests for behavior with approved examples but no corrections."""

    def test_returns_formatted_string_approved_only(
        self,
        retriever: LearningRetriever,
        mock_vector_store: MagicMock,
        sample_profiles: list[DatasetProfile],
        sample_approved: list[dict],
    ) -> None:
        """Returns formatted string with only approved examples."""
        mock_vector_store.query_similar_mappings.return_value = sample_approved
        result = retriever.get_examples_section(
            domain="AE",
            source_profiles=sample_profiles,
        )
        assert result is not None
        assert "Approved Example 1" in result
        assert "Correction Example" not in result


class TestMaxTotal:
    """Tests for max_total limit enforcement."""

    def test_max_total_respected(
        self,
        retriever: LearningRetriever,
        mock_vector_store: MagicMock,
        sample_profiles: list[DatasetProfile],
    ) -> None:
        """3 corrections + approved fills to max_total=5."""
        corrections = [
            {
                "document": f"SDTM domain AE variable VAR{i}. original logic: logic{i}. corrected logic: fixed{i}. reason: reason{i}",
                "metadata": {
                    "sdtm_variable": f"VAR{i}",
                    "original_pattern": "direct",
                    "corrected_pattern": "derivation",
                },
                "distance": 0.1 * i,
            }
            for i in range(3)
        ]
        approved = [
            {
                "document": f"SDTM domain AE variable APP{i}. mapping pattern: direct. logic: carry. source variable: SRC{i}",
                "metadata": {
                    "sdtm_variable": f"APP{i}",
                    "domain": "AE",
                    "mapping_pattern": "direct",
                },
                "distance": 0.1 * i,
            }
            for i in range(5)
        ]
        mock_vector_store.query_similar_corrections.return_value = corrections
        mock_vector_store.query_similar_mappings.return_value = approved

        result = retriever.get_examples_section(
            domain="AE",
            source_profiles=sample_profiles,
            max_examples=5,
        )
        assert result is not None
        # 3 corrections + 2 approved = 5 total
        assert result.count("Correction Example") == 3
        assert result.count("Approved Example") == 2


class TestBuildQueryText:
    """Tests for build_query_text method."""

    def test_includes_domain(
        self,
        retriever: LearningRetriever,
        sample_profiles: list[DatasetProfile],
    ) -> None:
        """Query text includes the domain name."""
        text = retriever.build_query_text("AE", sample_profiles)
        assert "AE" in text

    def test_includes_variable_names_and_labels(
        self,
        retriever: LearningRetriever,
        sample_profiles: list[DatasetProfile],
    ) -> None:
        """Query text includes non-EDC variable names and labels."""
        text = retriever.build_query_text("AE", sample_profiles)
        assert "AETERM" in text
        assert "Reported Term" in text
        assert "AESTDT" in text

    def test_excludes_edc_columns(
        self,
        retriever: LearningRetriever,
        sample_profiles: list[DatasetProfile],
    ) -> None:
        """EDC columns are excluded from the query text."""
        text = retriever.build_query_text("AE", sample_profiles)
        assert "projectid" not in text

    def test_limits_to_10_variables(
        self,
        retriever: LearningRetriever,
    ) -> None:
        """Only first 10 clinical variables are included."""
        variables = [
            VariableProfile(
                name=f"VAR{i:02d}",
                dtype="character",
                label=f"Variable {i}",
                n_total=100,
                n_unique=10,
                n_missing=0,
                missing_pct=0.0,
                sample_values=[],
                is_edc_column=False,
            )
            for i in range(15)
        ]
        profile = DatasetProfile(
            filename="test.sas7bdat",
            row_count=100,
            col_count=15,
            variables=variables,
        )
        text = retriever.build_query_text("AE", [profile])
        assert "VAR09" in text
        assert "VAR10" not in text


class TestFormatExamplesSection:
    """Tests for format_examples_section output format."""

    def test_header_present(
        self,
        retriever: LearningRetriever,
        sample_approved: list[dict],
    ) -> None:
        """Output includes the header and guidance text."""
        result = retriever.format_examples_section(
            approved=sample_approved,
            corrections=[],
        )
        assert "## Relevant Past Mapping Examples" in result
        assert "Use them as reference" in result

    def test_correction_format_includes_wrong_correct(
        self,
        retriever: LearningRetriever,
        sample_corrections: list[dict],
    ) -> None:
        """Correction examples include WRONG and CORRECT approach."""
        result = retriever.format_examples_section(
            approved=[],
            corrections=sample_corrections,
        )
        assert "WRONG approach:" in result
        assert "CORRECT approach:" in result

    def test_approved_format_includes_pattern_and_logic(
        self,
        retriever: LearningRetriever,
        sample_approved: list[dict],
    ) -> None:
        """Approved examples include Pattern and Logic."""
        result = retriever.format_examples_section(
            approved=sample_approved,
            corrections=[],
        )
        assert "Pattern:" in result
        assert "Logic:" in result
