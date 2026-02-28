"""Tests for the parse-ecrf CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from astraea.cli.app import app
from astraea.models.ecrf import ECRFExtractionResult, ECRFField, ECRFForm

runner = CliRunner()


def _make_extraction_result() -> ECRFExtractionResult:
    """Create a sample extraction result for testing."""
    return ECRFExtractionResult(
        forms=[
            ECRFForm(
                form_name="Adverse Events",
                fields=[
                    ECRFField(
                        field_number=1,
                        field_name="AETERM",
                        data_type="$200",
                        sas_label="Reported Term for the Adverse Event",
                        coded_values=None,
                    ),
                    ECRFField(
                        field_number=2,
                        field_name="AESER",
                        data_type="1",
                        sas_label="Serious Event",
                        coded_values={"Y": "Yes", "N": "No"},
                    ),
                ],
                page_numbers=[10, 11],
            ),
            ECRFForm(
                form_name="Demographics",
                fields=[
                    ECRFField(
                        field_number=1,
                        field_name="SEX",
                        data_type="1",
                        sas_label="Sex",
                        coded_values={"M": "Male", "F": "Female"},
                    ),
                ],
                page_numbers=[5],
            ),
        ],
        source_pdf="ECRF.pdf",
        extraction_timestamp="2026-02-26T00:00:00+00:00",
    )


class TestParseEcrfCommand:
    def test_help_shows_description(self) -> None:
        result = runner.invoke(app, ["parse-ecrf", "--help"])
        assert result.exit_code == 0
        assert "eCRF" in result.output or "ecrf" in result.output.lower()

    def test_missing_file_exits_nonzero(self) -> None:
        result = runner.invoke(app, ["parse-ecrf", "/nonexistent/ecrf.pdf"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_non_pdf_file_exits_nonzero(self, tmp_path: Path) -> None:
        txt_file = tmp_path / "ecrf.txt"
        txt_file.write_text("not a pdf")
        result = runner.invoke(app, ["parse-ecrf", str(txt_file)])
        assert result.exit_code != 0
        assert "PDF" in result.output or "pdf" in result.output.lower()

    def test_no_api_key_exits_nonzero(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "ecrf.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        import os

        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(app, ["parse-ecrf", str(pdf_file)])
            assert result.exit_code != 0
            assert "ANTHROPIC_API_KEY" in result.output

    @patch("astraea.parsing.ecrf_parser.parse_ecrf")
    @patch("astraea.parsing.pdf_extractor.group_pages_by_form")
    @patch("astraea.parsing.pdf_extractor.extract_ecrf_pages")
    def test_successful_parse_shows_summary(
        self,
        mock_extract: MagicMock,
        mock_group: MagicMock,
        mock_parse: MagicMock,
        tmp_path: Path,
    ) -> None:
        pdf_file = tmp_path / "ecrf.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_extract.return_value = []
        mock_group.return_value = {"Form1": []}
        mock_parse.return_value = _make_extraction_result()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            result = runner.invoke(app, ["parse-ecrf", str(pdf_file)])

        assert result.exit_code == 0
        assert "Adverse Events" in result.output
        assert "Demographics" in result.output
        assert "2 forms" in result.output
        assert "3 fields" in result.output

    @patch("astraea.parsing.ecrf_parser.parse_ecrf")
    @patch("astraea.parsing.pdf_extractor.group_pages_by_form")
    @patch("astraea.parsing.pdf_extractor.extract_ecrf_pages")
    def test_detail_flag_shows_fields(
        self,
        mock_extract: MagicMock,
        mock_group: MagicMock,
        mock_parse: MagicMock,
        tmp_path: Path,
    ) -> None:
        pdf_file = tmp_path / "ecrf.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_extract.return_value = []
        mock_group.return_value = {"Form1": []}
        mock_parse.return_value = _make_extraction_result()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            result = runner.invoke(app, ["parse-ecrf", str(pdf_file), "--detail"])

        assert result.exit_code == 0
        assert "AETERM" in result.output
        assert "AESER" in result.output
        assert "SEX" in result.output

    @patch("astraea.parsing.ecrf_parser.parse_ecrf")
    @patch("astraea.parsing.pdf_extractor.group_pages_by_form")
    @patch("astraea.parsing.pdf_extractor.extract_ecrf_pages")
    def test_output_flag_writes_json(
        self,
        mock_extract: MagicMock,
        mock_group: MagicMock,
        mock_parse: MagicMock,
        tmp_path: Path,
    ) -> None:
        pdf_file = tmp_path / "ecrf.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        output_file = tmp_path / "result.json"
        mock_extract.return_value = []
        mock_group.return_value = {"Form1": []}
        mock_parse.return_value = _make_extraction_result()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            result = runner.invoke(
                app,
                ["parse-ecrf", str(pdf_file), "--output", str(output_file)],
            )

        assert result.exit_code == 0
        assert output_file.exists()
        assert "Adverse Events" in output_file.read_text()

    @patch("astraea.parsing.ecrf_parser.parse_ecrf")
    @patch("astraea.parsing.pdf_extractor.group_pages_by_form")
    @patch("astraea.parsing.pdf_extractor.extract_ecrf_pages")
    def test_single_pdf_extraction(
        self,
        mock_extract: MagicMock,
        mock_group: MagicMock,
        mock_parse: MagicMock,
        tmp_path: Path,
    ) -> None:
        """PDF extraction should happen only once (via CLI), not again inside parse_ecrf."""
        pdf_file = tmp_path / "ecrf.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_pages = [{"text": "page 1"}]
        mock_extract.return_value = mock_pages
        mock_group.return_value = {"Form1": []}
        mock_parse.return_value = _make_extraction_result()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            result = runner.invoke(app, ["parse-ecrf", str(pdf_file)])

        assert result.exit_code == 0
        # extract_ecrf_pages called exactly once (by CLI), not twice
        mock_extract.assert_called_once()
        # parse_ecrf receives pre_extracted_pages so it skips its own extraction
        mock_parse.assert_called_once()
        call_kwargs = mock_parse.call_args
        assert call_kwargs.kwargs.get("pre_extracted_pages") == mock_pages

    def test_cache_dir_loads_cached(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "ecrf.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        # Create a cached extraction
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "ecrf_extraction.json"
        extraction = _make_extraction_result()
        cache_file.write_text(extraction.model_dump_json(indent=2))

        result = runner.invoke(app, ["parse-ecrf", str(pdf_file), "--cache-dir", str(cache_dir)])

        assert result.exit_code == 0
        assert "cached" in result.output.lower() or "Loading" in result.output
        assert "Adverse Events" in result.output
