"""eCRF PDF extraction and parsing pipeline.

Provides deterministic PDF-to-Markdown extraction (pdf_extractor) and
LLM-based structured field extraction (ecrf_parser).
"""

from astraea.parsing.pdf_extractor import (
    extract_ecrf_pages,
    get_form_names,
    group_pages_by_form,
)

__all__ = [
    "extract_ecrf_pages",
    "get_form_names",
    "group_pages_by_form",
]


def __getattr__(name: str):  # noqa: ANN001
    """Lazy import ecrf_parser symbols to avoid import errors before it exists."""
    _ecrf_exports = {"load_extraction", "parse_ecrf", "save_extraction"}
    if name in _ecrf_exports:
        from astraea.parsing import ecrf_parser  # noqa: WPS433

        return getattr(ecrf_parser, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
