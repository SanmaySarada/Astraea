"""SAS file reader with metadata extraction using pyreadstat.

Reads .sas7bdat files and extracts rich metadata including variable names,
labels, SAS formats, data types, encoding, and row/column counts.

IMPORTANT: Uses disable_datetime_conversion=True to preserve raw numeric
date values (SAS DATETIME = seconds since 1960-01-01). Date conversion
is handled separately by the transforms layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
import pyreadstat
from loguru import logger

from astraea.models.metadata import DatasetMetadata, VariableMetadata


def read_sas_with_metadata(
    filepath: str | Path,
) -> tuple[pd.DataFrame, DatasetMetadata]:
    """Read a SAS .sas7bdat file, returning a DataFrame and structured metadata.

    Args:
        filepath: Path to a .sas7bdat file.

    Returns:
        Tuple of (DataFrame with raw data, DatasetMetadata with variable info).

    Raises:
        FileNotFoundError: If the file does not exist.
        pyreadstat.ReadstatError: If the file cannot be read as SAS data.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"SAS file not found: {filepath}")
    if not filepath.suffix == ".sas7bdat":
        raise ValueError(f"Expected .sas7bdat file, got: {filepath.suffix}")

    logger.info("Reading SAS file: {}", filepath.name)

    df, meta = pyreadstat.read_sas7bdat(
        str(filepath),
        disable_datetime_conversion=True,
    )

    # Build variable metadata from pyreadstat meta object
    variables: list[VariableMetadata] = []
    for col_name in meta.column_names:
        sas_format = meta.original_variable_types.get(col_name)
        # pyreadstat: "$" prefix = character, None or other = numeric
        dtype: Literal["numeric", "character"] = (
            "character" if sas_format is not None and sas_format.startswith("$") else "numeric"
        )

        label = meta.column_names_to_labels.get(col_name) or ""

        variables.append(
            VariableMetadata(
                name=col_name,
                label=label,
                sas_format=sas_format,
                dtype=dtype,
            )
        )

    dataset_meta = DatasetMetadata(
        filename=filepath.name,
        row_count=meta.number_rows,
        col_count=meta.number_columns,
        variables=variables,
        file_encoding=meta.file_encoding,
    )

    logger.info(
        "Read {}: {} rows x {} cols (encoding: {})",
        filepath.name,
        dataset_meta.row_count,
        dataset_meta.col_count,
        dataset_meta.file_encoding,
    )

    return df, dataset_meta


def read_all_sas_files(
    data_dir: str | Path,
) -> dict[str, tuple[pd.DataFrame, DatasetMetadata]]:
    """Read all .sas7bdat files in a directory.

    Args:
        data_dir: Path to directory containing .sas7bdat files.

    Returns:
        Dict keyed by filename stem (e.g., "dm", "ae") with
        (DataFrame, DatasetMetadata) tuple values.

    Raises:
        FileNotFoundError: If the directory does not exist.
        ValueError: If no .sas7bdat files are found.
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    sas_files = sorted(data_dir.glob("*.sas7bdat"))
    if not sas_files:
        raise ValueError(f"No .sas7bdat files found in: {data_dir}")

    logger.info("Found {} SAS files in {}", len(sas_files), data_dir)

    results: dict[str, tuple[pd.DataFrame, DatasetMetadata]] = {}
    for sas_file in sas_files:
        try:
            df, meta = read_sas_with_metadata(sas_file)
            results[sas_file.stem] = (df, meta)
        except Exception:
            logger.exception("Failed to read SAS file: {}", sas_file.name)
            raise

    logger.info("Successfully read {} SAS files", len(results))
    return results
