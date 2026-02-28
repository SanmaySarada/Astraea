"""TRANSPOSE pattern handler for wide-to-tall SDTM Findings conversion.

Provides TransposeSpec (configuration model) and execute_transpose() which
uses pandas.melt() to convert horizontal raw data (one column per test) into
vertical SDTM Findings format (one row per test per subject per visit).

The handle_transpose() stub is registered in PATTERN_HANDLERS but logs a
warning -- actual transpose is handled at the DataFrame level by
execute_transpose(), not per-variable.
"""

from __future__ import annotations

import pandas as pd
from loguru import logger
from pydantic import BaseModel, Field

from astraea.models.mapping import VariableMapping


class TransposeSpec(BaseModel):
    """Configuration for a wide-to-tall transpose operation.

    Defines which columns to keep as identifiers, which to unpivot,
    and how to map source column names to SDTM TESTCD, TEST, and unit values.
    """

    id_vars: list[str] = Field(
        ..., description="Columns to keep as-is (e.g., USUBJID, VISITNUM, date cols)"
    )
    value_vars: list[str] = Field(..., description="Columns to unpivot (test result columns)")
    testcd_mapping: dict[str, str] = Field(
        ..., description="Source column name -> TESTCD value (e.g., 'SYSBP' -> 'SYSBP')"
    )
    test_mapping: dict[str, str] = Field(
        ...,
        description="Source column name -> TEST label (e.g., 'SYSBP' -> 'Systolic Blood Pressure')",
    )
    unit_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="Source column name -> unit string. Missing keys = no unit.",
    )
    result_var: str = Field(
        ..., description="Target column for original result (e.g., 'VSORRES', 'LBORRES')"
    )
    testcd_var: str = Field(
        ..., description="Target column for test code (e.g., 'VSTESTCD', 'LBTESTCD')"
    )
    test_var: str = Field(..., description="Target column for test name (e.g., 'VSTEST', 'LBTEST')")
    unit_var: str = Field(
        ..., description="Target column for original unit (e.g., 'VSORRESU', 'LBORRESU')"
    )


def execute_transpose(df: pd.DataFrame, spec: TransposeSpec) -> pd.DataFrame:
    """Convert a wide DataFrame to tall SDTM Findings format via pandas.melt().

    Args:
        df: Wide-format DataFrame with one column per test result.
        spec: TransposeSpec defining the transpose configuration.

    Returns:
        Tall DataFrame with one row per test per subject, with TESTCD, TEST,
        result, and unit columns. Rows with NaN/None results are dropped.
    """
    if df.empty:
        # Return empty DataFrame with expected columns
        cols = spec.id_vars + [spec.testcd_var, spec.test_var, spec.result_var, spec.unit_var]
        return pd.DataFrame(columns=cols)

    # Filter id_vars to only those present in df
    available_id_vars = [v for v in spec.id_vars if v in df.columns]

    # Filter value_vars to only those present in df
    available_value_vars = [v for v in spec.value_vars if v in df.columns]

    if not available_value_vars:
        logger.warning("No value_vars found in DataFrame columns; returning empty DataFrame")
        cols = spec.id_vars + [spec.testcd_var, spec.test_var, spec.result_var, spec.unit_var]
        return pd.DataFrame(columns=cols)

    # Melt: wide -> tall
    melted = pd.melt(
        df,
        id_vars=available_id_vars,
        value_vars=available_value_vars,
        var_name="_source_col",
        value_name=spec.result_var,
    )

    # Map source column names to TESTCD values
    melted[spec.testcd_var] = melted["_source_col"].map(spec.testcd_mapping)

    # Map source column names to TEST labels
    melted[spec.test_var] = melted["_source_col"].map(spec.test_mapping)

    # Map source column names to unit values (may be partial/empty)
    if spec.unit_mapping:
        melted[spec.unit_var] = melted["_source_col"].map(spec.unit_mapping)
    else:
        melted[spec.unit_var] = None

    # Drop the intermediate _source_col
    melted = melted.drop(columns=["_source_col"])

    # Drop rows where the result value is NaN/None (test not performed)
    melted = melted.dropna(subset=[spec.result_var]).reset_index(drop=True)

    return melted


def handle_transpose(df: pd.DataFrame, mapping: VariableMapping, **kwargs: object) -> pd.Series:
    """Stub handler for TRANSPOSE pattern in PATTERN_HANDLERS.

    TRANSPOSE mappings are handled at the DataFrame level by execute_transpose(),
    not per-variable. This handler exists only to satisfy the dispatch registry
    and logs a warning if called directly.

    Returns:
        Empty Series -- the actual transpose is done by execute_transpose().
    """
    logger.warning(
        "TRANSPOSE mappings are handled at the DataFrame level by execute_transpose(), "
        "not per-variable. Variable: {}",
        mapping.sdtm_variable,
    )
    return pd.Series(dtype="object")
