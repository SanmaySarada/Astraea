"""Registry of available deterministic transforms for mapping specs.

Makes transform function signatures discoverable by the mapping engine
so that derivation_rule references can be validated against actual
available transforms. This module is the production code import path
for the transforms/ package.
"""

from __future__ import annotations

from collections.abc import Callable

from astraea.transforms.ascii_validation import fix_common_non_ascii, validate_ascii
from astraea.transforms.char_length import optimize_char_lengths
from astraea.transforms.dates import (
    format_partial_iso8601,
    parse_string_date_to_iso,
    sas_date_to_iso,
    sas_datetime_to_iso,
)
from astraea.transforms.epoch import assign_epoch
from astraea.transforms.recoding import numeric_to_yn
from astraea.transforms.imputation import (
    get_date_imputation_flag,
    get_time_imputation_flag,
)
from astraea.transforms.sequence import generate_seq
from astraea.transforms.study_day import calculate_study_day
from astraea.transforms.usubjid import (
    generate_usubjid,
    generate_usubjid_column,
)
from astraea.transforms.visit import assign_visit

AVAILABLE_TRANSFORMS: dict[str, Callable] = {
    # date transforms
    "sas_date_to_iso": sas_date_to_iso,
    "sas_datetime_to_iso": sas_datetime_to_iso,
    "parse_string_date_to_iso": parse_string_date_to_iso,
    "format_partial_iso8601": format_partial_iso8601,
    # usubjid transforms
    "generate_usubjid": generate_usubjid,
    "generate_usubjid_column": generate_usubjid_column,
    # study day
    "calculate_study_day": calculate_study_day,
    # sequence
    "generate_seq": generate_seq,
    # epoch
    "assign_epoch": assign_epoch,
    # visit
    "assign_visit": assign_visit,
    # imputation flags
    "get_date_imputation_flag": get_date_imputation_flag,
    "get_time_imputation_flag": get_time_imputation_flag,
    # ascii validation
    "validate_ascii": validate_ascii,
    "fix_common_non_ascii": fix_common_non_ascii,
    # char length optimization
    "optimize_char_lengths": optimize_char_lengths,
    # recoding transforms
    "numeric_to_yn": numeric_to_yn,
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
