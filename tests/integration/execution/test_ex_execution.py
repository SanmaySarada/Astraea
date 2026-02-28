"""End-to-end EX domain execution integration test.

Creates a synthetic EX mapping scenario with multi-source merge (ex + ex_ole)
and row filtering (EXYN=N exclusion). Verifies the full pipeline: filter ->
merge -> execute -> SDTM DataFrame with correct columns, CT recodes, and
sequence numbering.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.executor import DatasetExecutor
from astraea.execution.preprocessing import filter_rows
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
def ex_spec() -> DomainMappingSpec:
    """EX domain spec with 11 variables covering ASSIGN, DIRECT, DERIVATION,
    LOOKUP_RECODE, and REFORMAT patterns."""
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
            assigned="EX",
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
            var="EXSEQ",
            pattern=MappingPattern.DERIVATION,
            label="Sequence Number",
            derivation="generate_seq",
            order=4,
        ),
        _mapping(
            var="EXTRT",
            pattern=MappingPattern.DIRECT,
            label="Name of Treatment",
            source="EXTRT",
            order=5,
        ),
        _mapping(
            var="EXDOSE",
            pattern=MappingPattern.DIRECT,
            label="Dose per Administration",
            source="EXDOSE",
            order=6,
        ),
        _mapping(
            var="EXDOSU",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Dose Units",
            source="EXDOSU_STD",
            codelist="C71620",
            order=7,
        ),
        _mapping(
            var="EXDOSFRM",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Dose Form",
            source="EXDOSFRM_STD",
            codelist="C66726",
            order=8,
        ),
        _mapping(
            var="EXROUTE",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Route of Administration",
            source="EXROUTE_STD",
            codelist="C66729",
            order=9,
        ),
        _mapping(
            var="EXSTDTC",
            pattern=MappingPattern.REFORMAT,
            label="Start Date/Time of Treatment",
            source="EXSTDAT_RAW",
            derivation="parse_string_date_to_iso",
            order=10,
        ),
        _mapping(
            var="EXENDTC",
            pattern=MappingPattern.REFORMAT,
            label="End Date/Time of Treatment",
            source="EXENDAT_RAW",
            derivation="parse_string_date_to_iso",
            order=11,
        ),
    ]
    return DomainMappingSpec(
        domain="EX",
        domain_label="Exposure",
        domain_class="Interventions",
        structure="One record per constant-dosing interval per subject",
        study_id="PHA022121-C301",
        source_datasets=["ex.sas7bdat", "ex_ole.sas7bdat"],
        variable_mappings=mappings,
        total_variables=11,
        required_mapped=4,
        expected_mapped=0,
        high_confidence_count=11,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_ex_df() -> pd.DataFrame:
    """Main study EX data with 4 rows, 1 with EXYN=N (not administered)."""
    return pd.DataFrame(
        {
            "Subject": ["001", "001", "002", "003"],
            "SiteNumber": ["101", "101", "101", "102"],
            "EXTRT": ["C1-INH", "C1-INH", "C1-INH", "C1-INH"],
            "EXDOSE": ["50", "50", "50", "50"],
            "EXDOSU_STD": ["IU/kg", "IU/kg", "IU/kg", "IU/kg"],
            "EXDOSFRM_STD": ["INJECTION", "INJECTION", "INJECTION", "INJECTION"],
            "EXROUTE_STD": ["INTRAVENOUS", "INTRAVENOUS", "INTRAVENOUS", "INTRAVENOUS"],
            "EXSTDAT_RAW": ["01 Jan 2022", "15 Jan 2022", "01 Jan 2022", "05 Jan 2022"],
            "EXENDAT_RAW": ["01 Jan 2022", "15 Jan 2022", "01 Jan 2022", "05 Jan 2022"],
            "EXYN_STD": ["Y", "N", "Y", "Y"],
            "projectid": [1, 1, 1, 1],
        }
    )


@pytest.fixture()
def raw_ex_ole_df() -> pd.DataFrame:
    """OLE extension EX data with 2 rows, all administered."""
    return pd.DataFrame(
        {
            "Subject": ["001", "002"],
            "SiteNumber": ["101", "101"],
            "EXTRT": ["C1-INH", "C1-INH"],
            "EXDOSE": ["50", "50"],
            "EXDOSU_STD": ["IU/kg", "IU/kg"],
            "EXDOSFRM_STD": ["INJECTION", "INJECTION"],
            "EXROUTE_STD": ["INTRAVENOUS", "INTRAVENOUS"],
            "EXSTDAT_RAW": ["01 Jul 2022", "01 Jul 2022"],
            "EXENDAT_RAW": ["01 Jul 2022", "01 Jul 2022"],
            "EXYN_STD": ["Y", "Y"],
            "projectid": [1, 1],
        }
    )


class TestEXEndToEnd:
    """Integration tests for EX domain execution with row filtering and multi-source merge."""

    def _execute(
        self,
        ex_spec: DomainMappingSpec,
        raw_ex_df: pd.DataFrame,
        raw_ex_ole_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Helper: filter rows, merge sources, execute."""
        # Step 1: Filter out EXYN_STD=N rows from both DataFrames
        filtered_ex = filter_rows(raw_ex_df, column="EXYN_STD", keep_values={"Y"})
        filtered_ole = filter_rows(raw_ex_ole_df, column="EXYN_STD", keep_values={"Y"})

        # Step 2: Execute with multi-source
        sdtm_ref = load_sdtm_reference()
        ct_ref = load_ct_reference()
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        return executor.execute(
            ex_spec,
            {"ex": filtered_ex, "ex_ole": filtered_ole},
            study_id="PHA022121-C301",
        )

    def test_output_has_correct_columns(
        self,
        ex_spec: DomainMappingSpec,
        raw_ex_df: pd.DataFrame,
        raw_ex_ole_df: pd.DataFrame,
    ) -> None:
        """Output should have exactly the 11 mapped columns."""
        result = self._execute(ex_spec, raw_ex_df, raw_ex_ole_df)
        expected_cols = {
            "STUDYID",
            "DOMAIN",
            "USUBJID",
            "EXSEQ",
            "EXTRT",
            "EXDOSE",
            "EXDOSU",
            "EXDOSFRM",
            "EXROUTE",
            "EXSTDTC",
            "EXENDTC",
        }
        assert set(result.columns) == expected_cols

    def test_non_administered_filtered_out(
        self,
        ex_spec: DomainMappingSpec,
        raw_ex_df: pd.DataFrame,
        raw_ex_ole_df: pd.DataFrame,
    ) -> None:
        """EXYN=N row should be excluded. Result should have 5 rows (3 from ex + 2 from ole)."""
        result = self._execute(ex_spec, raw_ex_df, raw_ex_ole_df)
        assert len(result) == 5

    def test_extrt_direct_copy(
        self,
        ex_spec: DomainMappingSpec,
        raw_ex_df: pd.DataFrame,
        raw_ex_ole_df: pd.DataFrame,
    ) -> None:
        """All EXTRT values should be 'C1-INH'."""
        result = self._execute(ex_spec, raw_ex_df, raw_ex_ole_df)
        assert all(result["EXTRT"] == "C1-INH")

    def test_multi_source_merged(
        self,
        ex_spec: DomainMappingSpec,
        raw_ex_df: pd.DataFrame,
        raw_ex_ole_df: pd.DataFrame,
    ) -> None:
        """Result should contain records from both main study and OLE extension.
        Main study contributes 3 rows (after filtering), OLE contributes 2 = 5 total."""
        result = self._execute(ex_spec, raw_ex_df, raw_ex_ole_df)
        # Check that we have both Jan 2022 (main study) and Jul 2022 (OLE) dates
        dates = result["EXSTDTC"].tolist()
        has_jan = any("2022-01" in d for d in dates)
        has_jul = any("2022-07" in d for d in dates)
        assert has_jan, "Expected main study dates (Jan 2022)"
        assert has_jul, "Expected OLE extension dates (Jul 2022)"

    def test_dosage_form_recoded(
        self,
        ex_spec: DomainMappingSpec,
        raw_ex_df: pd.DataFrame,
        raw_ex_ole_df: pd.DataFrame,
    ) -> None:
        """EXDOSFRM values should match C66726 (INJECTION -> INJECTION)."""
        result = self._execute(ex_spec, raw_ex_df, raw_ex_ole_df)
        dosfrm_values = set(result["EXDOSFRM"].dropna().unique())
        assert "INJECTION" in dosfrm_values

    def test_route_recoded(
        self,
        ex_spec: DomainMappingSpec,
        raw_ex_df: pd.DataFrame,
        raw_ex_ole_df: pd.DataFrame,
    ) -> None:
        """EXROUTE values should match C66729 (INTRAVENOUS -> INTRAVENOUS)."""
        result = self._execute(ex_spec, raw_ex_df, raw_ex_ole_df)
        route_values = set(result["EXROUTE"].dropna().unique())
        assert "INTRAVENOUS" in route_values

    def test_dates_converted(
        self,
        ex_spec: DomainMappingSpec,
        raw_ex_df: pd.DataFrame,
        raw_ex_ole_df: pd.DataFrame,
    ) -> None:
        """EXSTDTC should be in ISO 8601 format (YYYY-MM-DD)."""
        result = self._execute(ex_spec, raw_ex_df, raw_ex_ole_df)
        for dtc in result["EXSTDTC"]:
            assert len(dtc) == 10, f"Expected YYYY-MM-DD format, got '{dtc}'"
            assert dtc[4] == "-" and dtc[7] == "-", f"Expected ISO format, got '{dtc}'"

    def test_exseq_generated(
        self,
        ex_spec: DomainMappingSpec,
        raw_ex_df: pd.DataFrame,
        raw_ex_ole_df: pd.DataFrame,
    ) -> None:
        """EXSEQ should be generated per USUBJID."""
        result = self._execute(ex_spec, raw_ex_df, raw_ex_ole_df)
        assert "EXSEQ" in result.columns
        # Subject 001 has 1 from main + 1 from OLE = 2 records -> seq 1, 2
        subj_001 = result[result["USUBJID"].str.endswith("001")]
        assert len(subj_001) == 2
        seq_values = sorted(subj_001["EXSEQ"].tolist())
        assert seq_values == [1, 2]

    def test_no_exyn_column_in_output(
        self,
        ex_spec: DomainMappingSpec,
        raw_ex_df: pd.DataFrame,
        raw_ex_ole_df: pd.DataFrame,
    ) -> None:
        """EXYN_STD should not appear in output (not mapped, should be dropped)."""
        result = self._execute(ex_spec, raw_ex_df, raw_ex_ole_df)
        assert "EXYN_STD" not in result.columns
        assert "projectid" not in result.columns
