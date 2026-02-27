"""XPT v5 file writer with pre-write validation.

Writes SDTM-compliant XPT (SAS Transport v5) files using pyreadstat,
with comprehensive pre-write validation to catch constraint violations
that pyreadstat would silently truncate.

XPT v5 constraints:
- Variable names: <= 8 characters, alphanumeric + underscore, starts with letter
- Variable labels: <= 40 characters
- Dataset (table) name: <= 8 characters, starts with letter, alphanumeric only
- Character variable values: <= 200 bytes
- ASCII only in character columns
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pyreadstat
from loguru import logger


class XPTValidationError(Exception):
    """Raised when data violates XPT v5 format constraints.

    Contains a list of all validation errors found, not just the first.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        msg = f"XPT v5 validation failed with {len(errors)} error(s):\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        super().__init__(msg)


_TABLE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_COLUMN_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def validate_for_xpt_v5(
    df: pd.DataFrame,
    column_labels: dict[str, str],
    table_name: str,
    table_label: str | None = None,
) -> list[str]:
    """Validate a DataFrame against XPT v5 constraints.

    Checks table name, column names, column labels, table label,
    character value lengths, and ASCII compliance. Returns a list of
    error strings (empty list means valid).

    Args:
        df: DataFrame to validate.
        column_labels: Mapping of column name -> label string.
        table_name: XPT dataset name.
        table_label: Optional dataset label (max 40 characters).

    Returns:
        List of validation error messages. Empty if valid.
    """
    errors: list[str] = []

    # Table label validation
    if table_label is not None and len(table_label) > 40:
        errors.append(
            f"Table label exceeds 40 characters ({len(table_label)} chars): "
            f"'{table_label[:50]}...'"
        )

    # Unlabeled column warning
    upper_label_keys = {k.upper() for k in column_labels}
    for col in df.columns:
        col_str = str(col)
        if col_str not in column_labels and col_str.upper() not in upper_label_keys:
            errors.append(
                f"Column '{col_str}' has no label defined -- "
                f"every SDTM variable must have a label"
            )

    # Table name validation
    if len(table_name) > 8:
        errors.append(
            f"Table name '{table_name}' exceeds 8 characters ({len(table_name)} chars)"
        )
    if not _TABLE_NAME_RE.match(table_name):
        errors.append(
            f"Table name '{table_name}' must start with a letter and contain only "
            f"alphanumeric characters"
        )

    # Column name validation
    for col in df.columns:
        col_str = str(col)
        if len(col_str) > 8:
            errors.append(
                f"Column name '{col_str}' exceeds 8 characters ({len(col_str)} chars)"
            )
        if not _COLUMN_NAME_RE.match(col_str):
            errors.append(
                f"Column name '{col_str}' must start with a letter and contain only "
                f"alphanumeric characters or underscores"
            )

    # Label validation
    for col, label in column_labels.items():
        if len(label) > 40:
            errors.append(
                f"Label for '{col}' exceeds 40 characters ({len(label)} chars): "
                f"'{label[:50]}...'"
            )

    # Character column value validation
    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]):
            non_null = df[col].dropna()
            if non_null.empty:
                continue

            # Check value byte length (XPT v5 max 200 bytes)
            max_bytes = non_null.astype(str).apply(lambda x: len(x.encode("utf-8"))).max()
            if max_bytes > 200:
                errors.append(
                    f"Column '{col}' has character values exceeding 200 bytes "
                    f"(max: {max_bytes} bytes)"
                )

            # Check ASCII compliance
            non_ascii = non_null.astype(str).apply(
                lambda x: not x.isascii()
            )
            if non_ascii.any():
                n_bad = int(non_ascii.sum())
                errors.append(
                    f"Column '{col}' contains {n_bad} non-ASCII value(s)"
                )

    return errors


def write_xpt_v5(
    df: pd.DataFrame,
    path: str | Path,
    table_name: str,
    column_labels: dict[str, str],
    table_label: str | None = None,
) -> None:
    """Write a DataFrame as an XPT v5 (SAS Transport) file with validation.

    Validates all XPT v5 constraints before writing. After writing,
    performs a read-back verification to catch any silent corruption.

    Args:
        df: DataFrame to write.
        path: Output file path.
        table_name: XPT dataset name (max 8 chars, alphanumeric).
        column_labels: Mapping of column name -> label string.
        table_label: Optional dataset label (max 40 characters).

    Raises:
        XPTValidationError: If data violates XPT v5 constraints.
        RuntimeError: If read-back verification fails.
    """
    path = Path(path)

    # Step 1: Validate
    errors = validate_for_xpt_v5(df, column_labels, table_name, table_label=table_label)
    if errors:
        raise XPTValidationError(errors)

    # Step 2: Uppercase column names (SDTM convention)
    df_out = df.copy()
    rename_map = {col: str(col).upper() for col in df_out.columns}
    df_out = df_out.rename(columns=rename_map)

    # Uppercase column labels keys
    upper_labels = {k.upper(): v for k, v in column_labels.items()}

    # Uppercase table name
    upper_table = table_name.upper()

    logger.info(
        "Writing XPT v5: {} ({} rows x {} cols) -> {}",
        upper_table,
        len(df_out),
        len(df_out.columns),
        path,
    )

    # Step 3: Write using pyreadstat
    write_kwargs: dict[str, object] = dict(
        table_name=upper_table,
        column_labels=upper_labels,
        file_format_version=5,
    )
    if table_label is not None:
        write_kwargs["file_label"] = table_label
    pyreadstat.write_xport(df_out, str(path), **write_kwargs)

    # Step 4: Read-back verification
    df_readback, meta_readback = pyreadstat.read_xport(str(path))

    # Verify column names match
    written_cols = set(df_out.columns)
    readback_cols = set(df_readback.columns)
    if written_cols != readback_cols:
        missing = written_cols - readback_cols
        extra = readback_cols - written_cols
        msg = f"Read-back column mismatch: missing={missing}, extra={extra}"
        raise RuntimeError(msg)

    # Verify row count matches
    if len(df_readback) != len(df_out):
        msg = (
            f"Read-back row count mismatch: "
            f"wrote {len(df_out)}, read back {len(df_readback)}"
        )
        raise RuntimeError(msg)

    logger.info(
        "XPT v5 write verified: {} rows x {} cols in {}",
        len(df_readback),
        len(df_readback.columns),
        path.name,
    )
