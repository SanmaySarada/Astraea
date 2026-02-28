"""Per-pattern handler functions for the dataset execution pipeline.

Each handler takes a DataFrame and a VariableMapping and returns a pd.Series
containing the transformed values for that SDTM variable. Handlers are
registered in the PATTERN_HANDLERS dispatch dictionary, keyed by MappingPattern.

All handlers share the signature:
    (df: pd.DataFrame, mapping: VariableMapping, **kwargs) -> pd.Series

The kwargs allow passing extra context (ct_reference, transform registry)
without changing the handler signature.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pandas as pd
from loguru import logger

from astraea.execution.transpose import handle_transpose
from astraea.mapping.transform_registry import get_transform
from astraea.models.mapping import MappingPattern, VariableMapping
from astraea.reference.controlled_terms import CTReference

# ---------------------------------------------------------------------------
# Derivation rule parser and column resolution helpers
# ---------------------------------------------------------------------------

_RULE_RE = re.compile(r"^(\w+)\s*\((.*)\)$", re.DOTALL)

# EDC alias map: eCRF/IRT field names -> common SAS column names
_EDC_ALIASES: dict[str, str] = {
    "SSUBJID": "Subject",
    "SSITENUM": "SiteNumber",
    "SSITE": "Site",
    "SSITEGROUP": "SiteGroup",
}

# Race checkbox column-name -> CDISC CT race value (C74457)
_RACE_COL_MAP: dict[str, str] = {
    "RACEAME": "AMERICAN INDIAN OR ALASKA NATIVE",
    "RACEASI": "ASIAN",
    "RACEBLA": "BLACK OR AFRICAN AMERICAN",
    "RACENAT": "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
    "RACEWHI": "WHITE",
    "RACEOTH": "OTHER",
    "RACENR": "NOT REPORTED",
}


def parse_derivation_rule(rule: str) -> tuple[str, list[str]]:
    """Parse ``KEYWORD(arg1, arg2, ...)`` into ``(KEYWORD, [arg1, arg2, ...])``.

    - Keyword is upper-cased.
    - Arguments are split on commas, stripped of surrounding quotes/whitespace.
    - Dataset prefixes (e.g. ``dm.COL``) are stripped: ``dm.AGE`` becomes ``AGE``.
    - If the string has no parentheses the bare keyword is returned with an
      empty argument list.
    """
    rule = rule.strip()
    m = _RULE_RE.match(rule)
    if m:
        keyword = m.group(1).upper()
        raw_args = m.group(2)
        args: list[str] = []
        for arg in raw_args.split(","):
            arg = arg.strip().strip("'\"")
            if not arg:
                continue
            # Strip dataset prefix (dm.COL -> COL) but NOT numeric literals (3.14)
            if "." in arg and not arg.replace(".", "").replace("-", "").isdigit():
                arg = arg.split(".")[-1]
            args.append(arg)
        return keyword, args
    # Bare keyword (no parentheses)
    return rule.strip().upper(), []


def _resolve_column(
    df: pd.DataFrame, name: str, kwargs: dict[str, object]
) -> str | None:
    """Resolve a column name against a DataFrame, with alias fallbacks.

    Resolution order:
    1. Strip dataset prefix (dm.COL -> COL)
    2. Exact match in ``df.columns``
    3. Custom aliases from ``kwargs["column_aliases"]``
    4. Hardcoded EDC aliases (``_EDC_ALIASES``)
    5. Case-insensitive fallback
    """
    # Strip dataset prefix
    if "." in name and not name.replace(".", "").replace("-", "").isdigit():
        name = name.split(".")[-1]

    # 1. Exact match
    if name in df.columns:
        return name

    # 2. Custom aliases
    aliases: dict[str, str] = kwargs.get("column_aliases", {})  # type: ignore[assignment]
    if name in aliases and aliases[name] in df.columns:
        return aliases[name]

    # 3. EDC aliases
    if name in _EDC_ALIASES and _EDC_ALIASES[name] in df.columns:
        return _EDC_ALIASES[name]

    # 4. Case-insensitive fallback
    lower_map = {c.lower(): c for c in df.columns}
    if name.lower() in lower_map:
        return lower_map[name.lower()]

    return None


def _extract_race_from_col(col_name: str, df: pd.DataFrame) -> str | None:
    """Extract the race category name for a checkbox column.

    Checks the column label first (from ``df.attrs``), then falls back to
    well-known column name prefixes.
    """
    # Try column label
    labels: dict[str, str] = df.attrs.get("column_labels", {})
    label = labels.get(col_name)
    if label:
        return label.upper()

    # Fallback: column name pattern
    upper = col_name.upper()
    for prefix, race in _RACE_COL_MAP.items():
        if upper.startswith(prefix):
            return race

    return None


def handle_assign(df: pd.DataFrame, mapping: VariableMapping, **kwargs: object) -> pd.Series:
    """Return a Series filled with the mapping's assigned_value for all rows.

    Raises:
        ValueError: If mapping.assigned_value is None.
    """
    if mapping.assigned_value is None:
        msg = f"ASSIGN pattern for {mapping.sdtm_variable} has no assigned_value"
        raise ValueError(msg)

    return pd.Series(mapping.assigned_value, index=df.index, dtype="object")


def handle_direct(df: pd.DataFrame, mapping: VariableMapping, **kwargs: object) -> pd.Series:
    """Copy the source column directly (no transformation).

    Raises:
        ValueError: If mapping.source_variable is None.
        KeyError: If source_variable not found in df.columns.
    """
    if mapping.source_variable is None:
        msg = f"DIRECT pattern for {mapping.sdtm_variable} has no source_variable"
        raise ValueError(msg)

    if mapping.source_variable not in df.columns:
        msg = f"Source variable '{mapping.source_variable}' not found in DataFrame columns"
        raise KeyError(msg)

    return df[mapping.source_variable].copy()


def handle_rename(df: pd.DataFrame, mapping: VariableMapping, **kwargs: object) -> pd.Series:
    """Copy the source column (it gets a new name at assignment time).

    Functionally identical to handle_direct -- the rename happens when
    the executor assigns the Series to result_df[mapping.sdtm_variable].

    Raises:
        ValueError: If mapping.source_variable is None.
        KeyError: If source_variable not found in df.columns.
    """
    return handle_direct(df, mapping, **kwargs)


def handle_reformat(df: pd.DataFrame, mapping: VariableMapping, **kwargs: object) -> pd.Series:
    """Apply a registered transform function to the source column.

    Looks up the transform by mapping.derivation_rule name. If found, applies
    it element-wise via .map(). If not found, passes through the source column
    unchanged with a warning.

    Raises:
        ValueError: If mapping.source_variable is None.
        KeyError: If source_variable not found in df.columns.
    """
    if mapping.source_variable is None:
        msg = f"REFORMAT pattern for {mapping.sdtm_variable} has no source_variable"
        raise ValueError(msg)

    if mapping.source_variable not in df.columns:
        msg = f"Source variable '{mapping.source_variable}' not found in DataFrame columns"
        raise KeyError(msg)

    transform_fn = get_transform(mapping.derivation_rule) if mapping.derivation_rule else None

    if transform_fn is not None:
        return df[mapping.source_variable].map(transform_fn)

    logger.warning(
        "No transform found for derivation_rule='{}' on {}; passing through source column",
        mapping.derivation_rule,
        mapping.sdtm_variable,
    )
    return df[mapping.source_variable].copy()


def handle_lookup_recode(df: pd.DataFrame, mapping: VariableMapping, **kwargs: object) -> pd.Series:
    """Map source values through a codelist lookup table.

    If mapping.codelist_code and a CTReference are available, builds a recode
    dictionary from codelist terms and applies it. Non-matching values are
    kept as-is (important for extensible codelists).

    Args:
        df: Source DataFrame.
        mapping: Variable mapping with optional codelist_code.
        **kwargs: Must include 'ct_reference' (CTReference) for codelist lookup.

    Raises:
        ValueError: If mapping.source_variable is None.
        KeyError: If source_variable not found in df.columns.
    """
    if mapping.source_variable is None:
        msg = f"LOOKUP_RECODE pattern for {mapping.sdtm_variable} has no source_variable"
        raise ValueError(msg)

    if mapping.source_variable not in df.columns:
        msg = f"Source variable '{mapping.source_variable}' not found in DataFrame columns"
        raise KeyError(msg)

    ct_reference: CTReference | None = kwargs.get("ct_reference")  # type: ignore[assignment]

    if mapping.codelist_code and ct_reference is not None:
        codelist = ct_reference.lookup_codelist(mapping.codelist_code)
        if codelist is not None:
            # Build recode dict: submission_value -> submission_value
            # (CT terms are keyed by submission value, we map raw values to submission values)
            recode_dict: dict[str, str] = {}
            for submission_value, term in codelist.terms.items():
                # Map the nci_preferred_term (display name) to submission_value
                if term.nci_preferred_term:
                    recode_dict[term.nci_preferred_term] = submission_value
                # Also map submission_value to itself (identity)
                recode_dict[submission_value] = submission_value

            source_col = df[mapping.source_variable]
            return source_col.map(lambda v: recode_dict.get(str(v), v) if pd.notna(v) else v)

    logger.warning(
        "No codelist available for LOOKUP_RECODE on {} (code={}); passing through source column",
        mapping.sdtm_variable,
        mapping.codelist_code,
    )
    return df[mapping.source_variable].copy()


def handle_derivation(df: pd.DataFrame, mapping: VariableMapping, **kwargs: object) -> pd.Series:
    """Apply a derivation rule to produce computed values.

    Checks mapping.derivation_rule for known transform names. If found,
    applies the transform to the source column. For USUBJID generation,
    delegates to generate_usubjid_column.

    For unrecognized derivation rules, returns a Series of None with a warning.
    This is intentionally conservative -- unknown derivations are flagged, not guessed.
    """
    rule = mapping.derivation_rule or ""

    # Check for USUBJID generation
    if "USUBJID" in rule.upper() or "generate_usubjid" in rule:
        from astraea.transforms.usubjid import generate_usubjid_column

        study_id: str | None = kwargs.get("study_id")  # type: ignore[assignment]
        site_col: str = kwargs.get("site_col", "SiteNumber")  # type: ignore[assignment]
        subject_col: str = kwargs.get("subject_col", "Subject")  # type: ignore[assignment]

        if study_id is not None:
            return generate_usubjid_column(
                df,
                studyid_value=study_id,
                siteid_col=site_col,
                subjid_col=subject_col,
            )

    # Check for registered transforms
    transform_fn = get_transform(rule)
    has_transform = (
        transform_fn is not None
        and mapping.source_variable is not None
        and mapping.source_variable in df.columns
    )
    if has_transform:
        return df[mapping.source_variable].map(transform_fn)

    logger.warning(
        "Unrecognized derivation rule '{}' for {}; returning None series",
        rule,
        mapping.sdtm_variable,
    )
    return pd.Series(None, index=df.index, dtype="object")


def handle_combine(df: pd.DataFrame, mapping: VariableMapping, **kwargs: object) -> pd.Series:
    """Combine multiple source columns into one target.

    Parses mapping.derivation_rule to identify the combination strategy.
    Currently supports USUBJID concatenation; other combine patterns
    return Series of None with a warning.
    """
    rule = mapping.derivation_rule or ""

    # USUBJID is the primary COMBINE use case
    if "USUBJID" in rule.upper() or "generate_usubjid" in rule:
        return handle_derivation(df, mapping, **kwargs)

    logger.warning(
        "Unrecognized combine rule '{}' for {}; returning None series",
        rule,
        mapping.sdtm_variable,
    )
    return pd.Series(None, index=df.index, dtype="object")


def handle_split(df: pd.DataFrame, mapping: VariableMapping, **kwargs: object) -> pd.Series:
    """Stub for SPLIT pattern -- complex domain-specific implementation deferred to Phase 5/6.

    Returns a Series of None with a warning.
    """
    logger.warning(
        "SPLIT pattern not yet implemented for {}; returning None series",
        mapping.sdtm_variable,
    )
    return pd.Series(None, index=df.index, dtype="object")


PATTERN_HANDLERS: dict[MappingPattern, Callable[..., pd.Series]] = {
    MappingPattern.ASSIGN: handle_assign,
    MappingPattern.DIRECT: handle_direct,
    MappingPattern.RENAME: handle_rename,
    MappingPattern.REFORMAT: handle_reformat,
    MappingPattern.LOOKUP_RECODE: handle_lookup_recode,
    MappingPattern.DERIVATION: handle_derivation,
    MappingPattern.COMBINE: handle_combine,
    MappingPattern.SPLIT: handle_split,
    MappingPattern.TRANSPOSE: handle_transpose,
}
