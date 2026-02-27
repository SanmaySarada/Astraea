"""Tests for the eCRF parser module.

All tests use mocked LLM clients -- no ANTHROPIC_API_KEY required.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from astraea.models.ecrf import ECRFExtractionResult, ECRFField, ECRFForm
from astraea.parsing.ecrf_parser import (
    extract_form_fields,
    load_extraction,
    parse_ecrf,
    save_extraction,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_ecrf_form() -> ECRFForm:
    """A realistic ECRFForm fixture for Demographics."""
    return ECRFForm(
        form_name="Demographics",
        fields=[
            ECRFField(
                field_number=1,
                field_name="BRTHDAT",
                data_type="dd MMM yyyy",
                sas_label="Date of Birth",
                units=None,
                coded_values=None,
                field_oid="BRTHDAT",
            ),
            ECRFField(
                field_number=2,
                field_name="SEX",
                data_type="$1",
                sas_label="Sex",
                units=None,
                coded_values={"M": "Male", "F": "Female"},
                field_oid="SEX",
            ),
            ECRFField(
                field_number=3,
                field_name="RACE",
                data_type="$25",
                sas_label="Race",
                units=None,
                coded_values=None,
                field_oid="RACE",
            ),
        ],
        page_numbers=[5, 6],
    )


@pytest.fixture()
def sample_extraction_result(sample_ecrf_form: ECRFForm) -> ECRFExtractionResult:
    """A complete extraction result fixture."""
    ae_form = ECRFForm(
        form_name="Adverse Events",
        fields=[
            ECRFField(
                field_number=1,
                field_name="AETERM",
                data_type="$200",
                sas_label="Reported Term for the Adverse Event",
                units=None,
                coded_values=None,
                field_oid="AETERM",
            ),
        ],
        page_numbers=[10, 11, 12],
    )
    return ECRFExtractionResult(
        forms=[sample_ecrf_form, ae_form],
        source_pdf="ECRF.pdf",
        extraction_timestamp="2026-02-26T12:00:00+00:00",
    )


@pytest.fixture()
def mock_client(sample_ecrf_form: ECRFForm) -> MagicMock:
    """A mocked AstraeaLLMClient whose parse() returns sample_ecrf_form."""
    client = MagicMock()
    client.parse.return_value = sample_ecrf_form
    return client


# ---------------------------------------------------------------------------
# extract_form_fields tests
# ---------------------------------------------------------------------------


class TestExtractFormFields:
    def test_returns_ecrf_form(self, mock_client: MagicMock) -> None:
        """extract_form_fields should return the ECRFForm from the LLM."""
        result = extract_form_fields(
            client=mock_client,
            form_name="Demographics",
            form_text="Field Name Data Type SAS Label\n1 BRTHDAT dd MMM yyyy Date of Birth",
            page_numbers=[5, 6],
        )
        assert isinstance(result, ECRFForm)
        assert result.form_name == "Demographics"
        assert len(result.fields) == 3

    def test_calls_client_parse(self, mock_client: MagicMock) -> None:
        """Should call client.parse with correct model and parameters."""
        extract_form_fields(
            client=mock_client,
            form_name="Demographics",
            form_text="Field Name Data Type SAS Label Units Values Include Field OID -- enough text to pass minimum",
            page_numbers=[5],
        )
        mock_client.parse.assert_called_once()
        call_kwargs = mock_client.parse.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["temperature"] == 0.2
        assert call_kwargs["max_tokens"] == 4096
        assert call_kwargs["output_format"] is ECRFForm

    def test_short_text_returns_empty_fields(self, mock_client: MagicMock) -> None:
        """Form text shorter than 50 chars should return empty fields without LLM call."""
        result = extract_form_fields(
            client=mock_client,
            form_name="Tiny Form",
            form_text="Short",
            page_numbers=[1],
        )
        assert result.form_name == "Tiny Form"
        assert result.fields == []
        assert result.page_numbers == [1]
        mock_client.parse.assert_not_called()

    def test_default_page_numbers(self, mock_client: MagicMock) -> None:
        """page_numbers defaults to empty list when not provided."""
        result = extract_form_fields(
            client=mock_client,
            form_name="Test",
            form_text="x" * 5,  # short -> skip LLM
        )
        assert result.page_numbers == []


# ---------------------------------------------------------------------------
# parse_ecrf tests
# ---------------------------------------------------------------------------


class TestParseECRF:
    def test_orchestrator_skips_header(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """parse_ecrf should skip HEADER and UNKNOWN groups."""
        # Create a tiny fake PDF that pymupdf4llm can process
        # Instead, mock the two deterministic functions
        mock_pages = [
            {"text": "Cover page"},
            {"text": "Form: Demographics\nField table data here with enough text to pass minimum"},
        ]
        mock_forms = {
            "HEADER": [(1, "Cover page")],
            "Demographics": [(2, "Form: Demographics\nField table data here with enough text to pass minimum")],
        }

        with (
            patch("astraea.parsing.ecrf_parser.extract_ecrf_pages", return_value=mock_pages),
            patch("astraea.parsing.ecrf_parser.group_pages_by_form", return_value=mock_forms),
        ):
            result = parse_ecrf(pdf_path="/fake/path.pdf", client=mock_client)

        assert len(result.forms) == 1
        assert result.forms[0].form_name == "Demographics"

    def test_orchestrator_concatenates_pages(
        self, mock_client: MagicMock,
    ) -> None:
        """Multi-page forms should have their text concatenated."""
        mock_pages = [
            {"text": "Form: AE\nPage 1 text with enough characters to pass the minimum length check"},
            {"text": "Form: AE\nPage 2 text with enough characters to pass the minimum length check"},
        ]
        mock_forms = {
            "AE": [
                (1, "Form: AE\nPage 1 text with enough characters to pass the minimum length check"),
                (2, "Form: AE\nPage 2 text with enough characters to pass the minimum length check"),
            ],
        }

        with (
            patch("astraea.parsing.ecrf_parser.extract_ecrf_pages", return_value=mock_pages),
            patch("astraea.parsing.ecrf_parser.group_pages_by_form", return_value=mock_forms),
        ):
            parse_ecrf(pdf_path="/fake/path.pdf", client=mock_client)

        # Verify the LLM was called with concatenated text
        call_kwargs = mock_client.parse.call_args.kwargs
        user_msg = call_kwargs["messages"][0]["content"]
        assert "Page 1 text" in user_msg
        assert "Page 2 text" in user_msg

    def test_creates_client_when_none(self) -> None:
        """parse_ecrf creates a new client when None is passed."""
        mock_pages = []
        mock_forms: dict = {}

        with (
            patch("astraea.parsing.ecrf_parser.extract_ecrf_pages", return_value=mock_pages),
            patch("astraea.parsing.ecrf_parser.group_pages_by_form", return_value=mock_forms),
            patch("astraea.parsing.ecrf_parser.AstraeaLLMClient") as mock_cls,
        ):
            parse_ecrf(pdf_path="/fake/path.pdf", client=None)

        mock_cls.assert_called_once()

    def test_result_has_metadata(self, mock_client: MagicMock) -> None:
        """Result should include source_pdf and timestamp."""
        with (
            patch("astraea.parsing.ecrf_parser.extract_ecrf_pages", return_value=[]),
            patch("astraea.parsing.ecrf_parser.group_pages_by_form", return_value={}),
        ):
            result = parse_ecrf(pdf_path="/some/ecrf.pdf", client=mock_client)

        assert result.source_pdf == "/some/ecrf.pdf"
        assert result.extraction_timestamp  # non-empty

    def test_single_form_failure_does_not_crash_pipeline(self) -> None:
        """When extract_form_fields raises for one form, others still parse."""
        dm_form_result = ECRFForm(
            form_name="Demographics",
            fields=[
                ECRFField(
                    field_number=1,
                    field_name="SEX",
                    data_type="$1",
                    sas_label="Sex",
                    units=None,
                    coded_values=None,
                    field_oid="SEX",
                ),
            ],
            page_numbers=[5],
        )

        # Mock extract_form_fields directly: succeed for Demographics, fail for AE
        def _mock_extract_form_fields(
            client: object,
            form_name: str,
            form_text: str,
            page_numbers: list[int] | None = None,
        ) -> ECRFForm:
            if form_name == "AE":
                raise RuntimeError("LLM timeout for AE form")
            return dm_form_result

        mock_forms = {
            "Demographics": [(5, "Form: Demographics\n" + "x" * 60)],
            "AE": [(10, "Form: AE\n" + "x" * 60)],
        }

        client = MagicMock()

        with (
            patch("astraea.parsing.ecrf_parser.extract_ecrf_pages", return_value=[]),
            patch("astraea.parsing.ecrf_parser.group_pages_by_form", return_value=mock_forms),
            patch("astraea.parsing.ecrf_parser.extract_form_fields", side_effect=_mock_extract_form_fields),
        ):
            result = parse_ecrf(pdf_path="/fake/path.pdf", client=client)

        # Both forms should be in results
        assert len(result.forms) == 2
        names = [f.form_name for f in result.forms]
        assert "Demographics" in names
        assert "AE" in names

        # Demographics should have fields; AE should be empty (failed)
        dm_form = next(f for f in result.forms if f.form_name == "Demographics")
        ae_form = next(f for f in result.forms if f.form_name == "AE")
        assert len(dm_form.fields) == 1
        assert len(ae_form.fields) == 0
        assert ae_form.page_numbers == [10]

    def test_pre_extracted_pages_skips_pdf_extraction(
        self, mock_client: MagicMock,
    ) -> None:
        """When pre_extracted_pages is provided, extract_ecrf_pages is not called."""
        pre_pages = [
            {"text": "Form: Demographics\nField table data with enough text to pass minimum length"},
        ]
        mock_forms = {
            "Demographics": [
                (1, "Form: Demographics\nField table data with enough text to pass minimum length"),
            ],
        }

        with (
            patch("astraea.parsing.ecrf_parser.extract_ecrf_pages") as mock_extract,
            patch("astraea.parsing.ecrf_parser.group_pages_by_form", return_value=mock_forms),
        ):
            result = parse_ecrf(
                pdf_path="/fake/path.pdf",
                client=mock_client,
                pre_extracted_pages=pre_pages,
            )

        mock_extract.assert_not_called()
        assert len(result.forms) == 1


# ---------------------------------------------------------------------------
# save_extraction / load_extraction round-trip tests
# ---------------------------------------------------------------------------


class TestCacheRoundTrip:
    def test_save_and_load(
        self, sample_extraction_result: ECRFExtractionResult, tmp_path: Path
    ) -> None:
        """Save then load should reproduce the same result."""
        cache_path = tmp_path / "ecrf_cache.json"
        save_extraction(sample_extraction_result, cache_path)

        loaded = load_extraction(cache_path)

        assert loaded.source_pdf == sample_extraction_result.source_pdf
        assert loaded.extraction_timestamp == sample_extraction_result.extraction_timestamp
        assert len(loaded.forms) == len(sample_extraction_result.forms)
        assert loaded.total_fields == sample_extraction_result.total_fields

    def test_save_creates_directories(
        self, sample_extraction_result: ECRFExtractionResult, tmp_path: Path
    ) -> None:
        """save_extraction should create parent directories if needed."""
        cache_path = tmp_path / "nested" / "dir" / "cache.json"
        save_extraction(sample_extraction_result, cache_path)
        assert cache_path.exists()

    def test_load_preserves_fields(
        self, sample_extraction_result: ECRFExtractionResult, tmp_path: Path
    ) -> None:
        """Loaded result should preserve all field details."""
        cache_path = tmp_path / "cache.json"
        save_extraction(sample_extraction_result, cache_path)
        loaded = load_extraction(cache_path)

        dm_form = loaded.forms[0]
        assert dm_form.form_name == "Demographics"
        sex_field = dm_form.fields[1]
        assert sex_field.field_name == "SEX"
        assert sex_field.coded_values == {"M": "Male", "F": "Female"}
        assert sex_field.data_type == "$1"

    def test_load_file_not_found(self, tmp_path: Path) -> None:
        """load_extraction raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="Extraction cache not found"):
            load_extraction(tmp_path / "nonexistent.json")

    def test_total_fields_computed(
        self, sample_extraction_result: ECRFExtractionResult, tmp_path: Path
    ) -> None:
        """total_fields property should compute correctly after round-trip."""
        cache_path = tmp_path / "cache.json"
        save_extraction(sample_extraction_result, cache_path)
        loaded = load_extraction(cache_path)
        # Demographics has 3 fields, AE has 1 = 4 total
        assert loaded.total_fields == 4
