"""Dataset profiler for raw SAS files.

Produces rich statistical summaries of each variable, detects EDC system
columns, and identifies date variables from both SAS format metadata and
string pattern analysis.
"""

from __future__ import annotations

import re

import pandas as pd
from loguru import logger

from astraea.models.metadata import DatasetMetadata
from astraea.models.profiling import DatasetProfile, ValueDistribution, VariableProfile

# EDC system column names (lowercase for case-insensitive matching).
# These are standard Rave/EDC columns present in every dataset.
EDC_SYSTEM_COLUMNS: frozenset[str] = frozenset(
    {
        "projectid",
        "project",
        "studyid",
        "environmentname",
        "subjectid",
        "studysiteid",
        "siteid",
        "instanceid",
        "instancename",
        "instancerepeatnumber",
        "folderid",
        "folder",
        "foldername",
        "folderseq",
        "targetdays",
        "datapageid",
        "datapagename",
        "pagerepeatnumber",
        "recorddate",
        "recordid",
        "recordposition",
        "mincreated",
        "maxupdated",
        "savets",
        "studyenvsitenumber",
        "subject",
        "sitenumber",
        "site",
        "sitegroup",
    }
)

# SAS formats that indicate date/time variables.
SAS_DATE_FORMATS: frozenset[str] = frozenset(
    {
        "DATETIME",
        "DATE",
        "TIME",
        "DDMMYY",
        "MMDDYY",
        "YYMMDD",
        "DTDATE",
        "DATETIME22.3",
        "DATETIME20.",
        "DATE9.",
        "DATETIME.",
        "MMDDYY10.",
        "DDMMYY10.",
        "YYMMDD10.",
    }
)

# Regex patterns for string date detection.
_DATE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("DD Mon YYYY", re.compile(r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$")),
    ("YYYY-MM-DD", re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")),
    ("DD-Mon-YYYY", re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{4}$")),
    ("YYYY-MM-DDTHH:MM:SS", re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")),
    ("SLASH_DATE", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")),
]


def detect_date_format(samples: list[str]) -> str | None:
    """Examine sample string values and return the likely date format.

    Args:
        samples: List of non-null, non-empty string values to check.

    Returns:
        Detected date format string (e.g., "DD Mon YYYY") or None.
    """
    if not samples:
        return None

    # Try each pattern against the samples
    for format_name, pattern in _DATE_PATTERNS:
        matches = sum(1 for s in samples if pattern.match(s.strip()))
        # If >50% of samples match, we have a date pattern
        if matches > len(samples) * 0.5:
            if format_name == "SLASH_DATE":
                # Disambiguate DD/MM/YYYY vs MM/DD/YYYY by checking field values
                for s in samples:
                    s = s.strip()
                    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
                    if m:
                        first, second = int(m.group(1)), int(m.group(2))
                        if first > 12:
                            return "DD/MM/YYYY"
                        if second > 12:
                            return "MM/DD/YYYY"
                # All ambiguous -- default to DD/MM/YYYY per project convention (D-0104-01)
                return "DD/MM/YYYY"
            return format_name

    return None


def _is_edc_column(name: str) -> bool:
    """Check if a column name matches a known EDC system column."""
    return name.lower() in EDC_SYSTEM_COLUMNS


def _is_sas_date_format(sas_format: str | None) -> bool:
    """Check if a SAS format indicates a date/time variable."""
    if sas_format is None:
        return False
    # Strip trailing digits and periods for flexible matching
    # e.g., "DATETIME22.3" -> check against set
    clean = sas_format.rstrip("0123456789.")
    return sas_format in SAS_DATE_FORMATS or clean in SAS_DATE_FORMATS


def _is_potential_string_date_column(name: str) -> bool:
    """Check if column name suggests it might contain string dates.

    Looks for _RAW columns (case insensitive). All _RAW columns are
    candidates for string date detection because EDC systems store
    human-entered dates in _RAW variants. The detect_date_format
    function will return None if the values don't match any date pattern,
    so false positives are harmless.
    """
    return "_RAW" in name.upper()


def _compute_sample_values(series: pd.Series, max_samples: int = 10) -> list[str]:
    """Get first N unique non-null values as strings."""
    non_null = series.dropna()
    if non_null.empty:
        return []
    unique = non_null.unique()[:max_samples]
    return [str(v) for v in unique]


def _compute_top_values(
    series: pd.Series, n_total: int, max_top: int = 5, max_unique: int = 100
) -> list[ValueDistribution]:
    """Compute top N value frequencies for low-cardinality variables."""
    non_null = series.dropna()
    if non_null.empty:
        return []
    n_unique = non_null.nunique()
    if n_unique > max_unique:
        return []

    counts = non_null.value_counts().head(max_top)
    return [
        ValueDistribution(
            value=str(val),
            count=int(cnt),
            percentage=round(float(cnt) / n_total * 100, 2) if n_total > 0 else 0.0,
        )
        for val, cnt in counts.items()
    ]


# SDTM Findings domain prefixes and their characteristic variable suffixes.
_FINDINGS_PREFIXES: tuple[str, ...] = ("LB", "EG", "VS", "PE", "QS")
_FINDINGS_SUFFIXES: frozenset[str] = frozenset({"TESTCD", "TEST", "ORRES", "STRESC", "STRESN"})

# Valid SDTM domain codes for DOMAIN column detection.
_VALID_SDTM_DOMAINS: frozenset[str] = frozenset(
    {
        "DM", "AE", "CE", "DS", "DV", "MH",
        "CM", "EX", "SU", "EC",
        "LB", "VS", "EG", "PE", "QS", "SC", "FA", "IE", "RS", "TR", "TU",
        "SV", "SE", "TV", "TA", "TE", "TI", "TS",
    }
)


def detect_sdtm_format(profile: DatasetProfile) -> bool:
    """Detect if a profiled dataset is already in SDTM Findings format.

    Checks for characteristic Findings domain variable patterns
    (e.g., LBTESTCD, LBTEST, LBORRES) and the presence of a DOMAIN
    column with a valid SDTM domain code.

    Args:
        profile: A profiled dataset.

    Returns:
        True if the dataset appears to be pre-mapped SDTM data.
    """
    # Get non-EDC column names in uppercase
    col_names = {
        v.name.upper() for v in profile.variables if not v.is_edc_column
    }

    # Check for Findings domain patterns
    for prefix in _FINDINGS_PREFIXES:
        matches = sum(
            1 for suffix in _FINDINGS_SUFFIXES
            if f"{prefix}{suffix}" in col_names
        )
        if matches >= 3:
            return True

    # Check for DOMAIN column with valid SDTM code
    if "DOMAIN" in col_names:
        for v in profile.variables:
            if (
                v.name.upper() == "DOMAIN"
                and v.sample_values
                and any(sv.strip().upper() in _VALID_SDTM_DOMAINS for sv in v.sample_values)
            ):
                return True

    return False


def profile_dataset(df: pd.DataFrame, meta: DatasetMetadata) -> DatasetProfile:
    """Profile a raw SAS dataset, producing rich statistical summaries.

    Args:
        df: DataFrame with raw data (from read_sas_with_metadata).
        meta: DatasetMetadata extracted by the SAS reader.

    Returns:
        DatasetProfile with per-variable statistics, EDC column detection,
        and date format detection.
    """
    logger.info(
        "Profiling dataset: {} ({} rows x {} cols)", meta.filename, meta.row_count, meta.col_count
    )

    n_total = len(df)
    variable_profiles: list[VariableProfile] = []
    date_variables: list[str] = []
    edc_columns: list[str] = []

    # Build a quick lookup from variable name to metadata
    var_meta_map = {v.name: v for v in meta.variables}

    for col_name in df.columns:
        series = df[col_name]
        var_meta = var_meta_map.get(col_name)

        # Basic stats
        n_missing = int(series.isna().sum())
        n_unique = int(series.dropna().nunique())
        missing_pct = round(float(n_missing) / n_total * 100, 2) if n_total > 0 else 0.0

        # Variable metadata
        label = var_meta.label if var_meta else ""
        dtype = var_meta.dtype if var_meta else "numeric"
        sas_format = var_meta.sas_format if var_meta else None

        # Sample and top values
        sample_values = _compute_sample_values(series)
        top_values = _compute_top_values(series, n_total)

        # EDC column detection
        is_edc = _is_edc_column(col_name)

        # Date detection from SAS format
        is_date = _is_sas_date_format(sas_format)
        detected_format: str | None = None

        if is_date:
            detected_format = (
                "SAS_DATETIME" if sas_format and "DATETIME" in sas_format else "SAS_DATE"
            )

        # String date detection for _RAW columns
        if not is_date and _is_potential_string_date_column(col_name):
            non_empty = [str(v) for v in series.dropna().head(20).tolist() if str(v).strip()]
            fmt = detect_date_format(non_empty)
            if fmt is not None:
                is_date = True
                detected_format = fmt

        # Track aggregates
        if is_edc:
            edc_columns.append(col_name)
        if is_date:
            date_variables.append(col_name)

        variable_profiles.append(
            VariableProfile(
                name=col_name,
                label=label,
                dtype=dtype,
                sas_format=sas_format,
                n_total=n_total,
                n_missing=n_missing,
                n_unique=n_unique,
                missing_pct=missing_pct,
                sample_values=sample_values,
                top_values=top_values,
                is_date=is_date,
                detected_date_format=detected_format,
                is_edc_column=is_edc,
            )
        )

    profile = DatasetProfile(
        filename=meta.filename,
        row_count=n_total,
        col_count=meta.col_count,
        variables=variable_profiles,
        date_variables=date_variables,
        edc_columns=edc_columns,
    )

    # Detect pre-mapped SDTM Findings datasets (MED-29)
    profile.is_sdtm_preformatted = detect_sdtm_format(profile)

    logger.info(
        "Profiled {}: {} EDC columns, {} date variables, sdtm_preformatted={}",
        meta.filename,
        len(edc_columns),
        len(date_variables),
        profile.is_sdtm_preformatted,
    )

    return profile
