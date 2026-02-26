"""Tests for the PDF extractor module.

Unit tests use mock page data. Integration test extracts from the real
ECRF.pdf if present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astraea.parsing.pdf_extractor import (
    extract_ecrf_pages,
    get_form_names,
    group_pages_by_form,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ECRF_PDF_PATH = Path(__file__).resolve().parents[2] / "ECRF.pdf"


def _make_page(text: str) -> dict:
    """Create a mock page dict matching pymupdf4llm output structure."""
    return {"text": text, "metadata": {}, "tables": []}


@pytest.fixture()
def mock_pages() -> list[dict]:
    """Multi-form mock pages including header, single-page, and multi-page forms."""
    return [
        _make_page("Cover page with study info\nNo form header here"),
        _make_page("Form: Demographics\nField table for demographics page 1"),
        _make_page("Form: Demographics\nField table for demographics page 2"),
        _make_page("Form: Adverse Events\nField table for AE page 1"),
        _make_page("Form: Adverse Events\nField table for AE page 2"),
        _make_page("Form: Adverse Events\nField table for AE page 3"),
        _make_page("Form: Vital Signs\nField table for VS page 1"),
    ]


# ---------------------------------------------------------------------------
# group_pages_by_form tests
# ---------------------------------------------------------------------------


class TestGroupPagesByForm:
    def test_header_pages_grouped(self, mock_pages: list[dict]) -> None:
        """Pages before any form header go to 'HEADER' group."""
        forms = group_pages_by_form(mock_pages)
        assert "HEADER" in forms
        assert len(forms["HEADER"]) == 1
        assert forms["HEADER"][0][0] == 1  # page number 1-based

    def test_single_page_form(self, mock_pages: list[dict]) -> None:
        """Vital Signs has only one page."""
        forms = group_pages_by_form(mock_pages)
        assert "Vital Signs" in forms
        assert len(forms["Vital Signs"]) == 1
        assert forms["Vital Signs"][0][0] == 7

    def test_multi_page_form(self, mock_pages: list[dict]) -> None:
        """Adverse Events spans 3 pages, all grouped together."""
        forms = group_pages_by_form(mock_pages)
        assert "Adverse Events" in forms
        ae_pages = forms["Adverse Events"]
        assert len(ae_pages) == 3
        assert [p[0] for p in ae_pages] == [4, 5, 6]

    def test_demographics_two_pages(self, mock_pages: list[dict]) -> None:
        """Demographics spans 2 pages."""
        forms = group_pages_by_form(mock_pages)
        assert "Demographics" in forms
        assert len(forms["Demographics"]) == 2
        assert [p[0] for p in forms["Demographics"]] == [2, 3]

    def test_form_count(self, mock_pages: list[dict]) -> None:
        """Should have 4 groups: HEADER + 3 forms."""
        forms = group_pages_by_form(mock_pages)
        assert len(forms) == 4

    def test_page_text_preserved(self, mock_pages: list[dict]) -> None:
        """Page text content should be passed through unchanged."""
        forms = group_pages_by_form(mock_pages)
        _, text = forms["Vital Signs"][0]
        assert "Field table for VS page 1" in text

    def test_empty_pages(self) -> None:
        """Empty page list returns empty dict."""
        forms = group_pages_by_form([])
        assert forms == {}

    def test_no_form_headers(self) -> None:
        """Pages with no form headers all go to HEADER."""
        pages = [
            _make_page("Just some text"),
            _make_page("More text without form header"),
        ]
        forms = group_pages_by_form(pages)
        assert len(forms) == 1
        assert "HEADER" in forms
        assert len(forms["HEADER"]) == 2


# ---------------------------------------------------------------------------
# get_form_names tests
# ---------------------------------------------------------------------------


class TestGetFormNames:
    def test_returns_unique_ordered_names(self, mock_pages: list[dict]) -> None:
        """Form names should be unique and in order of first appearance."""
        names = get_form_names(mock_pages)
        assert names == ["Demographics", "Adverse Events", "Vital Signs"]

    def test_no_header_in_names(self, mock_pages: list[dict]) -> None:
        """HEADER pseudo-form should not appear in form names."""
        names = get_form_names(mock_pages)
        assert "HEADER" not in names

    def test_empty_pages(self) -> None:
        """Empty page list returns empty names."""
        assert get_form_names([]) == []


# ---------------------------------------------------------------------------
# extract_ecrf_pages tests
# ---------------------------------------------------------------------------


class TestExtractECRFPages:
    def test_file_not_found(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError for non-existent PDF."""
        with pytest.raises(FileNotFoundError, match="PDF file not found"):
            extract_ecrf_pages(tmp_path / "nonexistent.pdf")


# ---------------------------------------------------------------------------
# Integration test (requires real ECRF.pdf)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not ECRF_PDF_PATH.exists(),
    reason="ECRF.pdf not found -- skipping integration test",
)
class TestIntegrationECRFPDF:
    def test_extract_real_ecrf(self) -> None:
        """Extract pages from real ECRF.pdf and verify basic structure."""
        pages = extract_ecrf_pages(ECRF_PDF_PATH)
        # The eCRF is 188-189 pages
        assert len(pages) > 100, f"Expected >100 pages, got {len(pages)}"

    def test_group_real_ecrf_forms(self) -> None:
        """Group real ECRF.pdf pages by form and verify form detection."""
        pages = extract_ecrf_pages(ECRF_PDF_PATH)
        forms = group_pages_by_form(pages)
        # Should find multiple forms
        form_names = [k for k in forms if k != "HEADER"]
        assert len(form_names) > 10, f"Expected >10 forms, got {len(form_names)}"

    def test_get_real_form_names(self) -> None:
        """Get form names from real ECRF.pdf."""
        pages = extract_ecrf_pages(ECRF_PDF_PATH)
        names = get_form_names(pages)
        assert len(names) > 10
