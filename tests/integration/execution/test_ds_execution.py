"""End-to-end DS domain execution integration test.

Creates a synthetic DS (Disposition) mapping scenario with two source
datasets (ds + ds2) requiring column alignment before merge. Verifies
the full pipeline: multi-source merge -> SDTM DataFrame with correct
columns, DSCAT differentiation, CT codelist recodes, and --SEQ generation.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.executor import DatasetExecutor
from astraea.execution.preprocessing import align_multi_source_columns
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation
from astraea.reference import load_ct_reference, load_sdtm_reference


def _mapping(
    *,
    var: str,
    pattern: MappingPattern,
    label: str,
    source: str | None = None,
    assigned: str | None = None,
    derivation: str | None = None,
    codelist: str | None = None,
    order: int,
    core: CoreDesignation = CoreDesignation.REQ,
) -> VariableMapping:
    return VariableMapping(
        sdtm_variable=var,
        sdtm_label=label,
        sdtm_data_type="Char",
        core=core,
        source_variable=source,
        mapping_pattern=pattern,
        mapping_logic="test",
        assigned_value=assigned,
        derivation_rule=derivation,
        codelist_code=codelist,
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="test",
        order=order,
    )


@pytest.fixture()
def ds_spec() -> DomainMappingSpec:
    """DS domain spec with 8 variables for disposition events."""
    mappings = [
        _mapping(
            var="STUDYID",
            pattern=MappingPattern.ASSIGN,
            label="Study Identifier",
            assigned="PHA022121-C301",
            order=1,
        ),
        _mapping(
            var="DOMAIN",
            pattern=MappingPattern.ASSIGN,
            label="Domain Abbreviation",
            assigned="DS",
            order=2,
        ),
        _mapping(
            var="USUBJID",
            pattern=MappingPattern.DERIVATION,
            label="Unique Subject Identifier",
            derivation="generate_usubjid",
            order=3,
        ),
        _mapping(
            var="DSSEQ",
            pattern=MappingPattern.DERIVATION,
            label="Sequence Number",
            derivation="generate_seq",
            order=4,
        ),
        _mapping(
            var="DSTERM",
            pattern=MappingPattern.DIRECT,
            label="Reported Term for the Disposition Event",
            source="DSDECOD",
            order=5,
        ),
        _mapping(
            var="DSDECOD",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Standardized Disposition Term",
            source="DSDECOD_STD",
            codelist="C66727",
            order=6,
        ),
        _mapping(
            var="DSCAT",
            pattern=MappingPattern.DIRECT,
            label="Category for Disposition Event",
            source="DSCAT",
            order=7,
        ),
        _mapping(
            var="DSSTDTC",
            pattern=MappingPattern.REFORMAT,
            label="Start Date/Time of Disposition Event",
            source="DSSTDAT_RAW",
            derivation="parse_string_date_to_iso",
            order=8,
        ),
    ]
    return DomainMappingSpec(
        domain="DS",
        domain_label="Disposition",
        domain_class="Events",
        structure="One record per disposition status or protocol milestone per subject",
        study_id="PHA022121-C301",
        source_datasets=["ds.sas7bdat", "ds2.sas7bdat"],
        variable_mappings=mappings,
        total_variables=8,
        required_mapped=6,
        expected_mapped=0,
        high_confidence_count=8,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_ds_dfs() -> dict[str, pd.DataFrame]:
    """Two raw DS DataFrames simulating EOT and EOS sources with aligned columns."""
    ds_df = pd.DataFrame(
        {
            "Subject": ["001", "002", "003"],
            "SiteNumber": ["101", "101", "102"],
            "DSDECOD": ["Completed", "Adverse Event", "Completed"],
            "DSDECOD_STD": ["COMPLETED", "ADVERSE EVENT", "COMPLETED"],
            "DSSTDAT_RAW": ["30 Jun 2022", "15 May 2022", "30 Jun 2022"],
            "DSCAT": ["DISPOSITION EVENT", "DISPOSITION EVENT", "DISPOSITION EVENT"],
            "projectid": [1, 1, 1],
        }
    )

    ds2_df = pd.DataFrame(
        {
            "Subject": ["001", "002", "003"],
            "SiteNumber": ["101", "101", "102"],
            "DSDECOD2": ["Completed", "Adverse Event", "Completed"],
            "DSDECOD2_STD": ["COMPLETED", "ADVERSE EVENT", "COMPLETED"],
            "DSENDAT2_RAW": ["15 Jul 2022", "30 May 2022", "15 Jul 2022"],
            "DSCAT": ["PROTOCOL MILESTONE", "PROTOCOL MILESTONE", "PROTOCOL MILESTONE"],
            "projectid": [1, 1, 1],
        }
    )

    # Align ds2 columns to match ds column names before merge
    aligned = align_multi_source_columns(
        {"ds": ds_df, "ds2": ds2_df},
        rename_maps={
            "ds2": {
                "DSDECOD2": "DSDECOD",
                "DSDECOD2_STD": "DSDECOD_STD",
                "DSENDAT2_RAW": "DSSTDAT_RAW",
            }
        },
    )
    return aligned


@pytest.fixture()
def ds_executor() -> DatasetExecutor:
    """Executor with both SDTM and CT references loaded."""
    return DatasetExecutor(
        sdtm_ref=load_sdtm_reference(),
        ct_ref=load_ct_reference(),
    )


class TestDSEndToEnd:
    def test_output_has_correct_columns(
        self,
        ds_spec: DomainMappingSpec,
        raw_ds_dfs: dict[str, pd.DataFrame],
        ds_executor: DatasetExecutor,
    ) -> None:
        """Output should have exactly the 8 mapped SDTM variables."""
        result = ds_executor.execute(ds_spec, raw_ds_dfs, study_id="PHA022121-C301")
        expected_cols = {
            "STUDYID",
            "DOMAIN",
            "USUBJID",
            "DSSEQ",
            "DSTERM",
            "DSDECOD",
            "DSCAT",
            "DSSTDTC",
        }
        assert set(result.columns) == expected_cols

    def test_six_rows_from_two_sources(
        self,
        ds_spec: DomainMappingSpec,
        raw_ds_dfs: dict[str, pd.DataFrame],
        ds_executor: DatasetExecutor,
    ) -> None:
        """Merged output should have 6 rows (3 from ds + 3 from ds2)."""
        result = ds_executor.execute(ds_spec, raw_ds_dfs, study_id="PHA022121-C301")
        assert len(result) == 6

    def test_dscat_differentiates_sources(
        self,
        ds_spec: DomainMappingSpec,
        raw_ds_dfs: dict[str, pd.DataFrame],
        ds_executor: DatasetExecutor,
    ) -> None:
        """DSCAT should contain both 'DISPOSITION EVENT' and 'PROTOCOL MILESTONE'."""
        result = ds_executor.execute(ds_spec, raw_ds_dfs, study_id="PHA022121-C301")
        dscat_values = set(result["DSCAT"].unique())
        assert "DISPOSITION EVENT" in dscat_values
        assert "PROTOCOL MILESTONE" in dscat_values

    def test_dsdecod_recoded(
        self,
        ds_spec: DomainMappingSpec,
        raw_ds_dfs: dict[str, pd.DataFrame],
        ds_executor: DatasetExecutor,
    ) -> None:
        """DSDECOD should contain valid C66727 submission values."""
        result = ds_executor.execute(ds_spec, raw_ds_dfs, study_id="PHA022121-C301")
        dsdecod_values = set(result["DSDECOD"].dropna().unique())
        assert dsdecod_values == {"COMPLETED", "ADVERSE EVENT"}

    def test_dates_converted(
        self,
        ds_spec: DomainMappingSpec,
        raw_ds_dfs: dict[str, pd.DataFrame],
        ds_executor: DatasetExecutor,
    ) -> None:
        """DSSTDTC should be in ISO 8601 format."""
        result = ds_executor.execute(ds_spec, raw_ds_dfs, study_id="PHA022121-C301")
        # Check all dates are ISO format (YYYY-MM-DD)
        for val in result["DSSTDTC"].dropna():
            assert len(str(val)) == 10, f"Expected ISO date, got: {val}"
            assert str(val)[4] == "-" and str(val)[7] == "-"

    def test_dsseq_generated(
        self,
        ds_spec: DomainMappingSpec,
        raw_ds_dfs: dict[str, pd.DataFrame],
        ds_executor: DatasetExecutor,
    ) -> None:
        """DSSEQ should be present with correct per-subject sequencing."""
        result = ds_executor.execute(ds_spec, raw_ds_dfs, study_id="PHA022121-C301")
        assert "DSSEQ" in result.columns
        # Each subject has 2 records (1 from ds, 1 from ds2) -> seq 1, 2
        for usubjid in result["USUBJID"].unique():
            subj_rows = result[result["USUBJID"] == usubjid]
            assert len(subj_rows) == 2
            seq_values = sorted(subj_rows["DSSEQ"].tolist())
            assert seq_values == [1, 2]

    def test_multi_source_alignment_works(
        self,
        ds_spec: DomainMappingSpec,
        raw_ds_dfs: dict[str, pd.DataFrame],
        ds_executor: DatasetExecutor,
    ) -> None:
        """No NaN columns from mismatched names after alignment."""
        result = ds_executor.execute(ds_spec, raw_ds_dfs, study_id="PHA022121-C301")
        # DSTERM comes from DSDECOD column -- should have no NaN
        assert result["DSTERM"].notna().all()
        # DSDECOD comes from DSDECOD_STD via lookup -- should have no NaN
        assert result["DSDECOD"].notna().all()

    def test_columns_in_order(
        self,
        ds_spec: DomainMappingSpec,
        raw_ds_dfs: dict[str, pd.DataFrame],
        ds_executor: DatasetExecutor,
    ) -> None:
        """Columns should follow SDTM-IG order."""
        result = ds_executor.execute(ds_spec, raw_ds_dfs, study_id="PHA022121-C301")
        cols = list(result.columns)
        assert cols.index("STUDYID") < cols.index("DOMAIN")
        assert cols.index("DOMAIN") < cols.index("USUBJID")
        assert cols.index("USUBJID") < cols.index("DSSEQ")

    def test_no_edc_columns_leak(
        self,
        ds_spec: DomainMappingSpec,
        raw_ds_dfs: dict[str, pd.DataFrame],
        ds_executor: DatasetExecutor,
    ) -> None:
        """EDC system columns should not appear in output."""
        result = ds_executor.execute(ds_spec, raw_ds_dfs, study_id="PHA022121-C301")
        assert "projectid" not in result.columns
