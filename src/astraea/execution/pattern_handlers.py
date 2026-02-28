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
    lower_map: dict[str, str] = {str(c).lower(): str(c) for c in df.columns}
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


# ---------------------------------------------------------------------------
# Derivation rule handler functions
# ---------------------------------------------------------------------------


def _handle_generate_usubjid(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series:
    """Generate USUBJID from study_id, site column, and subject column."""
    from astraea.transforms.usubjid import generate_usubjid_column

    study_id: str | None = kwargs.get("study_id")  # type: ignore[assignment]
    if args:
        # First arg can override study_id literal
        study_id = args[0]

    site_hint = str(kwargs.get("site_col", "SiteNumber"))
    subject_hint = str(kwargs.get("subject_col", "Subject"))
    site_col = _resolve_column(df, site_hint, kwargs) or "SiteNumber"
    subject_col = _resolve_column(df, subject_hint, kwargs) or "Subject"

    if study_id is not None:
        return generate_usubjid_column(
            df,
            studyid_value=study_id,
            siteid_col=site_col,
            subjid_col=subject_col,
        )
    logger.warning("GENERATE_USUBJID: no study_id available for {}", mapping.sdtm_variable)
    return pd.Series(None, index=df.index, dtype="object")


def _handle_concat(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series:
    """Concatenate column values and literal strings element-wise."""
    parts: list[pd.Series] = []
    for arg in args:
        resolved = _resolve_column(df, arg, kwargs)
        if resolved is not None:
            parts.append(df[resolved].astype(str).fillna(""))
        else:
            # Treat as literal string
            parts.append(pd.Series(arg, index=df.index, dtype="object"))
    if not parts:
        return pd.Series("", index=df.index, dtype="object")
    result = parts[0]
    for p in parts[1:]:
        result = result + p
    return result


def _handle_iso8601_date(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series:
    """Convert SAS numeric DATE values to ISO 8601."""
    from astraea.transforms.dates import sas_date_to_iso

    col_hint = args[0] if args else (mapping.source_variable or "")
    if not col_hint:
        logger.warning("ISO8601_DATE: no source column specified for {}", mapping.sdtm_variable)
        return pd.Series(None, index=df.index, dtype="object")
    col = _resolve_column(df, col_hint, kwargs) or col_hint
    if col not in df.columns:
        logger.warning("ISO8601_DATE: column '{}' not found for {}", col, mapping.sdtm_variable)
        return pd.Series(None, index=df.index, dtype="object")
    return df[col].map(sas_date_to_iso)


def _handle_iso8601_datetime(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series:
    """Convert SAS numeric DATETIME values to ISO 8601."""
    from astraea.transforms.dates import sas_datetime_to_iso

    col_hint = args[0] if args else (mapping.source_variable or "")
    if not col_hint:
        logger.warning("ISO8601_DATETIME: no source column for {}", mapping.sdtm_variable)
        return pd.Series(None, index=df.index, dtype="object")
    col = _resolve_column(df, col_hint, kwargs) or col_hint
    if col not in df.columns:
        logger.warning("ISO8601_DATETIME: column '{}' not found for {}", col, mapping.sdtm_variable)
        return pd.Series(None, index=df.index, dtype="object")
    return df[col].map(sas_datetime_to_iso)


def _handle_iso8601_partial_date(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series:
    """Build partial ISO 8601 from year/month/day component columns."""
    from astraea.transforms.dates import format_partial_iso8601

    if not args:
        return pd.Series(None, index=df.index, dtype="object")

    # Resolve up to 3 columns: year, month, day
    year_col = _resolve_column(df, args[0], kwargs)
    month_col = _resolve_column(df, args[1], kwargs) if len(args) > 1 else None
    day_col = _resolve_column(df, args[2], kwargs) if len(args) > 2 else None

    def _row_to_iso(row: pd.Series) -> str:
        year_val = row.get(year_col) if year_col else None
        month_val = row.get(month_col) if month_col else None
        day_val = row.get(day_col) if day_col else None

        year = int(float(year_val)) if pd.notna(year_val) and year_val is not None else None
        month = int(float(month_val)) if pd.notna(month_val) and month_val is not None else None
        day = int(float(day_val)) if pd.notna(day_val) and day_val is not None else None

        return format_partial_iso8601(year=year, month=month, day=day)

    return df.apply(_row_to_iso, axis=1)


def _handle_parse_string_date(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series:
    """Parse string dates (DD Mon YYYY, etc.) to ISO 8601."""
    from astraea.transforms.dates import parse_string_date_to_iso

    col_hint = args[0] if args else (mapping.source_variable or "")
    if not col_hint:
        return pd.Series(None, index=df.index, dtype="object")
    col = _resolve_column(df, col_hint, kwargs) or col_hint
    if col not in df.columns:
        logger.warning(
            "PARSE_STRING_DATE: column '{}' not found for {}", col, mapping.sdtm_variable,
        )
        return pd.Series(None, index=df.index, dtype="object")
    return df[col].map(parse_string_date_to_iso)


def _handle_min_date_per_subject(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series:
    """Find the minimum date per USUBJID and map back to all rows."""
    return _handle_date_agg_per_subject(df, args, mapping, agg="min", **kwargs)


def _handle_max_date_per_subject(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series:
    """Find the maximum date per USUBJID and map back to all rows."""
    return _handle_date_agg_per_subject(df, args, mapping, agg="max", **kwargs)


def _handle_date_agg_per_subject(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    *,
    agg: str,
    **kwargs: object,
) -> pd.Series:
    """Aggregate a date column per USUBJID and broadcast back.

    If the source column is in a cross-domain DataFrame, look it up from
    ``kwargs["cross_domain_dfs"]``.
    """
    from astraea.transforms.dates import sas_date_to_iso

    if not args:
        return pd.Series(None, index=df.index, dtype="object")

    source_col_name = args[0]
    work_df = df

    # Check cross-domain DataFrames
    cross_dfs: dict[str, pd.DataFrame] = kwargs.get("cross_domain_dfs", {})  # type: ignore[assignment]
    for _name, cdf in cross_dfs.items():
        resolved = _resolve_column(cdf, source_col_name, kwargs)
        if resolved is not None:
            work_df = cdf
            source_col_name = resolved
            break
    else:
        resolved_local = _resolve_column(df, source_col_name, kwargs)
        if resolved_local:
            source_col_name = resolved_local

    if source_col_name not in work_df.columns:
        logger.warning(
            "{}: column '{}' not found for {}",
            agg.upper() + "_DATE_PER_SUBJECT",
            source_col_name,
            mapping.sdtm_variable,
        )
        return pd.Series(None, index=df.index, dtype="object")

    # Find USUBJID column in the work DataFrame
    usubjid_col = _resolve_column(work_df, "USUBJID", kwargs) or "USUBJID"
    if usubjid_col not in work_df.columns:
        logger.warning(
            "{}: USUBJID column not found in DataFrame for {}",
            agg.upper() + "_DATE_PER_SUBJECT",
            mapping.sdtm_variable,
        )
        return pd.Series(None, index=df.index, dtype="object")

    # Aggregate: group by USUBJID, get min/max of the date column
    grouped = work_df.groupby(usubjid_col)[source_col_name]
    agg_dates = grouped.min() if agg == "min" else grouped.max()

    # Map back to original df's USUBJID
    df_usubjid_col = _resolve_column(df, "USUBJID", kwargs) or "USUBJID"
    if df_usubjid_col not in df.columns:
        return pd.Series(None, index=df.index, dtype="object")

    mapped_numeric = df[df_usubjid_col].map(agg_dates)

    # Convert to ISO 8601
    return mapped_numeric.map(sas_date_to_iso)


def _handle_race_checkbox(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series:
    """Derive RACE from checkbox columns (0/1 values).

    Returns single race name if exactly 1 checked, "MULTIPLE" if >1, None if 0.
    """
    # Resolve checkbox column names
    resolved_cols: list[tuple[str, str]] = []  # (resolved_col, race_name)
    for arg in args:
        col = _resolve_column(df, arg, kwargs)
        if col is not None and col in df.columns:
            race = _extract_race_from_col(col, df)
            if race:
                resolved_cols.append((col, race))

    if not resolved_cols:
        logger.warning(
            "RACE_CHECKBOX: no valid checkbox columns found for {}", mapping.sdtm_variable,
        )
        return pd.Series(None, index=df.index, dtype="object")

    def _derive_race(row: pd.Series) -> str | None:
        checked = []
        for col, race in resolved_cols:
            val = row.get(col)
            if pd.notna(val) and float(val) == 1:
                checked.append(race)
        if len(checked) == 0:
            return None
        if len(checked) == 1:
            return checked[0]
        return "MULTIPLE"

    return df.apply(_derive_race, axis=1)


def _handle_numeric_to_yn(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series:
    """Convert 0/1 values to Y/N using numeric_to_yn."""
    from astraea.transforms.recoding import numeric_to_yn

    # Use args[0] if available, else fall back to mapping.source_variable
    col_hint = args[0] if args else (mapping.source_variable or "")
    if not col_hint:
        return pd.Series(None, index=df.index, dtype="object")
    col = _resolve_column(df, col_hint, kwargs) or col_hint
    if col not in df.columns:
        logger.warning("NUMERIC_TO_YN: column '{}' not found for {}", col, mapping.sdtm_variable)
        return pd.Series(None, index=df.index, dtype="object")
    return df[col].map(numeric_to_yn)


# ---------------------------------------------------------------------------
# Derivation dispatch table
# ---------------------------------------------------------------------------

_DERIVATION_DISPATCH: dict[str, Callable[..., pd.Series]] = {
    "GENERATE_USUBJID": _handle_generate_usubjid,
    "CONCAT": _handle_concat,
    "ISO8601_DATE": _handle_iso8601_date,
    "ISO8601_DATETIME": _handle_iso8601_datetime,
    "ISO8601_PARTIAL_DATE": _handle_iso8601_partial_date,
    "PARSE_STRING_DATE": _handle_parse_string_date,
    "MIN_DATE_PER_SUBJECT": _handle_min_date_per_subject,
    "MAX_DATE_PER_SUBJECT": _handle_max_date_per_subject,
    "RACE_CHECKBOX": _handle_race_checkbox,
    "RACE_FROM_CHECKBOXES": _handle_race_checkbox,  # alias
    "NUMERIC_TO_YN": _handle_numeric_to_yn,
    "LAST_DISPOSITION_DATE": _handle_max_date_per_subject,  # alias
    "LAST_DISPOSITION_DATE_PER_SUBJECT": _handle_max_date_per_subject,  # alias
}


def _dispatch_derivation_rule(
    df: pd.DataFrame,
    rule: str,
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series | None:
    """Parse a derivation rule and dispatch to the appropriate handler.

    Returns None if the keyword is not recognized.
    """
    keyword, args = parse_derivation_rule(rule)
    handler = _DERIVATION_DISPATCH.get(keyword)
    if handler is not None:
        return handler(df, args, mapping, **kwargs)
    return None


# ---------------------------------------------------------------------------
# Pattern handler functions (public API)
# ---------------------------------------------------------------------------


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

    If the source variable is not found in the DataFrame, checks for a
    ``resolved_source`` in kwargs (set by the executor via column alias
    resolution).

    Raises:
        ValueError: If mapping.source_variable is None.
        KeyError: If source_variable not found in df.columns (even after alias resolution).
    """
    if mapping.source_variable is None:
        msg = f"DIRECT pattern for {mapping.sdtm_variable} has no source_variable"
        raise ValueError(msg)

    col = mapping.source_variable
    if col not in df.columns:
        # Try resolved alias from executor
        resolved: str | None = kwargs.get("resolved_source")  # type: ignore[assignment]
        if resolved and resolved in df.columns:
            col = resolved
        else:
            msg = f"Source variable '{mapping.source_variable}' not found in DataFrame columns"
            raise KeyError(msg)

    return df[col].copy()


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

    First tries derivation rule dispatch (e.g. ISO8601_DATE(COL)). If the
    rule keyword is not recognized, falls back to the transform registry.
    If neither matches, passes through unchanged with a warning.

    Raises:
        ValueError: If mapping.source_variable is None.
        KeyError: If source_variable not found in df.columns.
    """
    # Try derivation rule dispatch first
    if mapping.derivation_rule:
        result = _dispatch_derivation_rule(df, mapping.derivation_rule, mapping, **kwargs)
        if result is not None:
            return result

    if mapping.source_variable is None:
        msg = f"REFORMAT pattern for {mapping.sdtm_variable} has no source_variable"
        raise ValueError(msg)

    col = mapping.source_variable
    if col not in df.columns:
        # Try resolved alias from executor
        resolved: str | None = kwargs.get("resolved_source")  # type: ignore[assignment]
        if resolved and resolved in df.columns:
            col = resolved
        else:
            msg = f"Source variable '{mapping.source_variable}' not found in DataFrame columns"
            raise KeyError(msg)

    transform_fn = get_transform(mapping.derivation_rule) if mapping.derivation_rule else None

    if transform_fn is not None:
        return df[col].map(transform_fn)

    logger.warning(
        "No transform found for derivation_rule='{}' on {}; passing through source column",
        mapping.derivation_rule,
        mapping.sdtm_variable,
    )
    return df[col].copy()


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

    col = mapping.source_variable
    if col not in df.columns:
        # Try resolved alias from executor
        resolved: str | None = kwargs.get("resolved_source")  # type: ignore[assignment]
        if resolved and resolved in df.columns:
            col = resolved
        else:
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

            source_col = df[col]
            return source_col.map(lambda v: recode_dict.get(str(v), v) if pd.notna(v) else v)

    logger.warning(
        "No codelist available for LOOKUP_RECODE on {} (code={}); passing through source column",
        mapping.sdtm_variable,
        mapping.codelist_code,
    )
    return df[col].copy()


def handle_derivation(df: pd.DataFrame, mapping: VariableMapping, **kwargs: object) -> pd.Series:
    """Apply a derivation rule to produce computed values.

    Dispatches through the derivation rule parser first. Falls back to the
    legacy USUBJID special-case and then the transform registry. For
    unrecognized derivation rules, returns a Series of None with a warning.
    """
    rule = mapping.derivation_rule or ""

    # 1. Try formal derivation rule dispatch
    if rule:
        result = _dispatch_derivation_rule(df, rule, mapping, **kwargs)
        if result is not None:
            return result

    # 2. Legacy USUBJID fallback (bare "USUBJID" in rule text)
    if "USUBJID" in rule.upper() or "generate_usubjid" in rule:
        from astraea.transforms.usubjid import generate_usubjid_column

        study_id: str | None = kwargs.get("study_id")  # type: ignore[assignment]
        site_col_name: str = kwargs.get("site_col", "SiteNumber")  # type: ignore[assignment]
        subject_col_name: str = kwargs.get("subject_col", "Subject")  # type: ignore[assignment]

        if study_id is not None:
            return generate_usubjid_column(
                df,
                studyid_value=study_id,
                siteid_col=site_col_name,
                subjid_col=subject_col_name,
            )

    # 3. Check for registered transforms
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

    Dispatches through the derivation rule parser. Falls back to the legacy
    USUBJID special-case. Other unrecognized combine patterns return None.
    """
    rule = mapping.derivation_rule or ""

    # 1. Try formal derivation rule dispatch (CONCAT, GENERATE_USUBJID, etc.)
    if rule:
        result = _dispatch_derivation_rule(df, rule, mapping, **kwargs)
        if result is not None:
            return result

    # 2. Legacy USUBJID fallback
    if "USUBJID" in rule.upper() or "generate_usubjid" in rule:
        return handle_derivation(df, mapping, **kwargs)

    logger.warning(
        "Unrecognized combine rule '{}' for {}; returning None series",
        rule,
        mapping.sdtm_variable,
    )
    return pd.Series(None, index=df.index, dtype="object")


def handle_split(df: pd.DataFrame, mapping: VariableMapping, **kwargs: object) -> pd.Series:
    """Extract part of a source column using SUBSTRING, DELIMITER_PART, or REGEX_GROUP.

    Derivation rule keywords:
    - ``SUBSTRING(column, start, end)`` -- ``df[col].str[start:end]``
    - ``DELIMITER_PART(column, delimiter, index)`` -- ``df[col].str.split(delim).str[index]``
    - ``REGEX_GROUP(column, pattern, group_index)`` -- ``df[col].str.extract(pattern)[group]``

    Fallback behaviour:
    - No derivation_rule but source_variable exists: return source column copy.
    - Unrecognized derivation_rule: log warning, return source column unchanged.
    - No source data at all: return None series.
    """
    rule = mapping.derivation_rule or ""

    if rule:
        keyword, args = parse_derivation_rule(rule)

        if keyword == "SUBSTRING" and len(args) >= 3:
            col = _resolve_column(df, args[0], kwargs)
            if col is None:
                logger.warning(
                    "SPLIT/SUBSTRING: column '{}' not found for {}",
                    args[0], mapping.sdtm_variable,
                )
                return pd.Series(None, index=df.index, dtype="object")
            start = int(args[1])
            end = int(args[2])
            return df[col].astype(str).str[start:end]

        if keyword == "DELIMITER_PART" and len(args) >= 3:
            col = _resolve_column(df, args[0], kwargs)
            if col is None:
                logger.warning(
                    "SPLIT/DELIMITER_PART: column '{}' not found for {}",
                    args[0], mapping.sdtm_variable,
                )
                return pd.Series(None, index=df.index, dtype="object")
            delimiter = args[1]
            index = int(args[2])
            return df[col].astype(str).str.split(delimiter).str[index]

        if keyword == "REGEX_GROUP" and len(args) >= 2:
            col = _resolve_column(df, args[0], kwargs)
            if col is None:
                logger.warning(
                    "SPLIT/REGEX_GROUP: column '{}' not found for {}",
                    args[0], mapping.sdtm_variable,
                )
                return pd.Series(None, index=df.index, dtype="object")
            pattern = args[1]
            group_index = int(args[2]) if len(args) >= 3 else 0
            extracted = df[col].astype(str).str.extract(pattern)
            if group_index < len(extracted.columns):
                return extracted.iloc[:, group_index]
            logger.warning(
                "SPLIT/REGEX_GROUP: group_index {} out of range for {}",
                group_index, mapping.sdtm_variable,
            )
            return pd.Series(None, index=df.index, dtype="object")

        # Unrecognized rule -- fall through to source column fallback.
        # This is expected for simple splits that don't need a derivation rule;
        # copying the source column is the correct default behaviour.
        logger.info(
            "SPLIT: unrecognized derivation rule '{}' for {}; falling back to source column",
            rule,
            mapping.sdtm_variable,
        )

    # Fallback: copy source column if available
    src = mapping.source_variable
    if src:
        col = _resolve_column(df, src, kwargs)
        if col is not None:
            return df[col].copy()
        # Try resolved alias from executor
        resolved: str | None = kwargs.get("resolved_source")  # type: ignore[assignment]
        if resolved and resolved in df.columns:
            return df[resolved].copy()

    # No source data at all
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
