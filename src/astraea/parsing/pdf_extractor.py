"""Deterministic PDF-to-Markdown extraction for eCRF documents.

Wraps pymupdf4llm to extract pages from an eCRF PDF, then groups them
by form name using the "Form: <name>" header pattern found on every page.
No LLM calls -- this module is purely deterministic.
"""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf4llm
from loguru import logger

# Regex to detect the "Form: <name>" header present on every eCRF page
_FORM_HEADER_RE = re.compile(r"Form:\s*(.+?)(?:\n|$)")


def extract_ecrf_pages(pdf_path: str | Path) -> list[dict]:
    """Extract eCRF PDF to page-level Markdown chunks.

    Uses pymupdf4llm with ``page_chunks=True`` and strict table detection
    to produce structured page-level output.

    Args:
        pdf_path: Path to the eCRF PDF file.

    Returns:
        List of dicts from pymupdf4llm, each containing page metadata and text.

    Raises:
        FileNotFoundError: If pdf_path does not exist.
    """
    path = Path(pdf_path)
    if not path.exists():
        msg = f"PDF file not found: {path}"
        raise FileNotFoundError(msg)

    pages = pymupdf4llm.to_markdown(
        str(path),
        page_chunks=True,
        table_strategy="lines_strict",
        show_progress=False,
    )

    logger.info("Extracted {n} pages from {pdf}", n=len(pages), pdf=path.name)
    return pages


def group_pages_by_form(
    pages: list[dict],
) -> dict[str, list[tuple[int, str]]]:
    """Group extracted pages by eCRF form name.

    Scans each page for the ``Form: <name>`` header and groups pages
    belonging to the same form together. Multi-page forms are correctly
    grouped by their shared form name.

    Pages appearing before any form header are placed in the ``"HEADER"`` group.

    Args:
        pages: List of page dicts from :func:`extract_ecrf_pages`.

    Returns:
        Dict mapping form name to a list of ``(page_number, page_text)`` tuples.
        Page numbers are 1-based.
    """
    forms: dict[str, list[tuple[int, str]]] = {}
    current_form = "HEADER"

    for idx, page in enumerate(pages):
        text = page.get("text", "")
        page_number = idx + 1  # 1-based page numbers

        # Check for form header on this page
        match = _FORM_HEADER_RE.search(text)
        if match:
            current_form = match.group(1).strip()

        if current_form not in forms:
            forms[current_form] = []
        forms[current_form].append((page_number, text))

    # Log summary
    form_count = len(forms)
    header_excluded = form_count - (1 if "HEADER" in forms else 0)
    logger.info(
        "Grouped {total} pages into {forms} forms",
        total=len(pages),
        forms=header_excluded,
    )
    for name, page_list in forms.items():
        logger.debug(
            "  Form '{name}': {n} page(s)", name=name, n=len(page_list)
        )

    return forms


def get_form_names(pages: list[dict]) -> list[str]:
    """Return ordered unique form names found in the pages.

    Preserves the order of first appearance. Excludes the ``"HEADER"``
    pseudo-form.

    Args:
        pages: List of page dicts from :func:`extract_ecrf_pages`.

    Returns:
        List of unique form names in order of first appearance.
    """
    seen: set[str] = set()
    names: list[str] = []

    for page in pages:
        text = page.get("text", "")
        match = _FORM_HEADER_RE.search(text)
        if match:
            name = match.group(1).strip()
            if name not in seen:
                seen.add(name)
                names.append(name)

    return names
