"""Registry of available deterministic transforms for mapping specs.

Makes transform function signatures discoverable by the mapping engine
so that derivation_rule references can be validated against actual
available transforms. This module is the production code import path
for the transforms/ package.
"""

from __future__ import annotations

from collections.abc import Callable

from astraea.transforms.dates import (
    format_partial_iso8601,
    parse_string_date_to_iso,
    sas_date_to_iso,
    sas_datetime_to_iso,
)
from astraea.transforms.usubjid import (
    generate_usubjid,
    generate_usubjid_column,
)

AVAILABLE_TRANSFORMS: dict[str, Callable] = {
    "sas_date_to_iso": sas_date_to_iso,
    "sas_datetime_to_iso": sas_datetime_to_iso,
    "parse_string_date_to_iso": parse_string_date_to_iso,
    "format_partial_iso8601": format_partial_iso8601,
    "generate_usubjid": generate_usubjid,
    "generate_usubjid_column": generate_usubjid_column,
}


def get_transform(name: str) -> Callable | None:
    """Look up a transform function by name.

    Args:
        name: Transform function name (e.g., "sas_date_to_iso").

    Returns:
        The callable transform function, or None if not found.
    """
    return AVAILABLE_TRANSFORMS.get(name)


def list_transforms() -> list[str]:
    """Return names of all registered transforms.

    Returns:
        Sorted list of transform function names.
    """
    return sorted(AVAILABLE_TRANSFORMS.keys())
