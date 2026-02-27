"""LLM-based eCRF parsing that converts Markdown form text to structured models.

Orchestrates the end-to-end eCRF extraction pipeline: PDF extraction via
:mod:`astraea.parsing.pdf_extractor`, then Claude structured output to parse
each form into :class:`~astraea.models.ecrf.ECRFForm` / :class:`~astraea.models.ecrf.ECRFField`
Pydantic models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from astraea.llm.client import AstraeaLLMClient
from astraea.models.ecrf import ECRFExtractionResult, ECRFForm
from astraea.parsing.pdf_extractor import extract_ecrf_pages, group_pages_by_form

# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

ECRF_EXTRACTION_PROMPT = """\
You are extracting structured metadata from a clinical trial eCRF \
(electronic Case Report Form).

The text below contains pages from a single eCRF form. Each form has:
1. A human-readable description section (questions, response options)
2. A FIELD TABLE section with headers: \
"Field Name  Data Type  SAS Label  Units  Values  Include  Field OID"

Extract ONLY from the FIELD TABLE section. For each field row, extract:
- field_number: The sequence number (leftmost column, starting at 1)
- field_name: The SAS variable name (e.g., AETERM, VSDAT). \
Must be uppercase, no spaces, typically max 8 characters.
- data_type: The data type/format (e.g., $25, 1, dd MMM yyyy, HH:nn, 5.2)
- sas_label: The human-readable label
- units: Measurement units if specified, otherwise null
- coded_values: Code-to-decode mappings as a JSON object \
(e.g., {{"Y": "Yes", "N": "No"}}) if present, otherwise null
- field_oid: The Field OID (rightmost column, often same as field_name)

IMPORTANT:
- Field names are SAS variable names: UPPERCASE, no spaces.
- If a field name appears split across lines, join the parts.
- The form_name in your response must match: {form_name}
- Include page_numbers: {page_numbers}
- If no field table is found, return an empty fields list.

Form text:

{form_text}
"""

# Minimum characters for a form page to be worth sending to the LLM
_MIN_FORM_TEXT_LENGTH = 50


def extract_form_fields(
    client: AstraeaLLMClient,
    form_name: str,
    form_text: str,
    page_numbers: list[int] | None = None,
) -> ECRFForm:
    """Extract structured fields from a single eCRF form using Claude.

    Sends the concatenated Markdown text for one form to the LLM and
    receives a structured :class:`ECRFForm` with all fields.

    Args:
        client: Configured LLM client.
        form_name: Name of the form as detected from the PDF header.
        form_text: Concatenated Markdown text for all pages of this form.
        page_numbers: 1-based page numbers where this form appears.

    Returns:
        Parsed :class:`ECRFForm` instance.
    """
    if page_numbers is None:
        page_numbers = []

    # Skip trivially short pages (e.g., blank pages, page-break artifacts)
    if len(form_text.strip()) < _MIN_FORM_TEXT_LENGTH:
        logger.debug(
            "Skipping short form text for '{name}' ({n} chars)",
            name=form_name,
            n=len(form_text.strip()),
        )
        return ECRFForm(
            form_name=form_name,
            fields=[],
            page_numbers=page_numbers,
        )

    user_message = ECRF_EXTRACTION_PROMPT.format(
        form_name=form_name,
        page_numbers=page_numbers,
        form_text=form_text,
    )

    result: ECRFForm = client.parse(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": user_message}],
        output_format=ECRFForm,
        temperature=0.2,
        max_tokens=4096,
    )

    logger.debug(
        "Extracted {n} fields from form '{name}'",
        n=len(result.fields),
        name=form_name,
    )
    return result


def parse_ecrf(
    pdf_path: str | Path,
    client: AstraeaLLMClient | None = None,
    pre_extracted_pages: list[dict[str, str]] | None = None,
) -> ECRFExtractionResult:
    """Parse an eCRF PDF into structured form and field metadata.

    Orchestrates the full pipeline:

    1. Extract PDF pages to Markdown via :func:`extract_ecrf_pages`.
    2. Group pages by form name via :func:`group_pages_by_form`.
    3. For each form, concatenate page texts and call :func:`extract_form_fields`.
    4. Collect results into an :class:`ECRFExtractionResult`.

    Args:
        pdf_path: Path to the eCRF PDF file.
        client: Optional pre-configured LLM client.
            If *None*, a new :class:`AstraeaLLMClient` is created.
        pre_extracted_pages: Optional list of already-extracted pages (each a
            dict with a ``"text"`` key). When provided, PDF extraction is
            skipped and these pages are used directly.

    Returns:
        :class:`ECRFExtractionResult` with all extracted forms.
    """
    if client is None:
        client = AstraeaLLMClient()

    path = Path(pdf_path)

    # Step 1: Extract pages (or use pre-extracted ones)
    if pre_extracted_pages is not None:
        pages = pre_extracted_pages
    else:
        pages = extract_ecrf_pages(path)

    # Step 2: Group by form
    form_groups = group_pages_by_form(pages)

    # Step 3: Parse each form
    forms: list[ECRFForm] = []
    # Exclude pseudo-groups
    skip_groups = {"HEADER", "UNKNOWN"}
    processable = {k: v for k, v in form_groups.items() if k not in skip_groups}
    total = len(processable)

    for idx, (form_name, page_list) in enumerate(processable.items(), start=1):
        logger.info(
            "Parsing form {idx} of {total}: {name}",
            idx=idx,
            total=total,
            name=form_name,
        )

        # Concatenate all page texts for this form
        page_numbers = [pn for pn, _ in page_list]
        combined_text = "\n\n---\n\n".join(text for _, text in page_list)

        try:
            form = extract_form_fields(
                client=client,
                form_name=form_name,
                form_text=combined_text,
                page_numbers=page_numbers,
            )
            forms.append(form)
        except Exception as e:
            logger.warning(
                "Failed to extract form '{name}' (pages {pages}): {error}. Skipping.",
                name=form_name,
                pages=page_numbers,
                error=str(e),
            )
            # Create empty form placeholder so we know it was attempted
            forms.append(ECRFForm(
                form_name=form_name,
                fields=[],
                page_numbers=page_numbers,
            ))

    result = ECRFExtractionResult(
        forms=forms,
        source_pdf=str(path),
        extraction_timestamp=datetime.now(tz=UTC).isoformat(),
    )

    logger.info(
        "eCRF parsing complete: {n_forms} forms, {n_fields} total fields",
        n_forms=len(result.forms),
        n_fields=result.total_fields,
    )
    return result


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def save_extraction(
    result: ECRFExtractionResult,
    output_path: str | Path,
) -> None:
    """Save an extraction result to JSON for caching.

    Args:
        result: The extraction result to persist.
        output_path: File path to write the JSON to.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2))
    logger.info("Saved extraction to {path}", path=path)


def load_extraction(path: str | Path) -> ECRFExtractionResult:
    """Load a cached extraction result from JSON.

    Args:
        path: File path to read the JSON from.

    Returns:
        Validated :class:`ECRFExtractionResult`.

    Raises:
        FileNotFoundError: If *path* does not exist.
    """
    p = Path(path)
    if not p.exists():
        msg = f"Extraction cache not found: {p}"
        raise FileNotFoundError(msg)

    raw = p.read_text()
    result = ECRFExtractionResult.model_validate_json(raw)
    logger.info(
        "Loaded extraction from {path}: {n} forms",
        path=p,
        n=len(result.forms),
    )
    return result
