"""End-to-end DM domain execution integration test.

Creates a synthetic DM mapping scenario (no real Fakedata dependency)
and verifies the full pipeline: spec + raw data -> SDTM DataFrame
with correct columns, order, and optimized character lengths.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.executor import DatasetExecutor
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
def dm_spec() -> DomainMappingSpec:
    """Minimal DM domain spec with 8 variables."""
    mappings = [
        _mapping(
            var="STUDYID",
            pattern=MappingPattern.ASSIGN,
            label="Study Identifier",
            assigned="TEST-STUDY-001",
            order=1,
        ),
        _mapping(
            var="DOMAIN",
            pattern=MappingPattern.ASSIGN,
            label="Domain Abbreviation",
            assigned="DM",
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
            var="SUBJID",
            pattern=MappingPattern.DIRECT,
            label="Subject Identifier for the Study",
            source="Subject",
            order=4,
        ),
        _mapping(
            var="SITEID",
            pattern=MappingPattern.DIRECT,
            label="Study Site Identifier",
            source="SiteNumber",
            order=5,
        ),
        _mapping(
            var="SEX",
            pattern=MappingPattern.LOOKUP_RECODE,
            label="Sex",
            source="Gender",
            codelist="C66731",
            order=6,
        ),
        _mapping(
            var="AGE",
            pattern=MappingPattern.DIRECT,
            label="Age",
            source="Age",
            order=7,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="ARMCD",
            pattern=MappingPattern.DIRECT,
            label="Planned Arm Code",
            source="ArmCode",
            order=8,
            core=CoreDesignation.REQ,
        ),
    ]
    return DomainMappingSpec(
        domain="DM",
        domain_label="Demographics",
        domain_class="Special Purpose",
        structure="One record per subject",
        study_id="TEST-STUDY-001",
        source_datasets=["dm.sas7bdat"],
        variable_mappings=mappings,
        total_variables=8,
        required_mapped=6,
        expected_mapped=1,
        high_confidence_count=8,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_dm_df() -> pd.DataFrame:
    """Raw DM data with 5 synthetic subjects."""
    return pd.DataFrame(
        {
            "Subject": ["005", "002", "001", "004", "003"],
            "SiteNumber": ["101", "101", "102", "102", "103"],
            "Gender": ["Male", "Female", "Male", "Female", "Male"],
            "Age": [45, 32, 58, 41, 67],
            "ArmCode": ["TRT", "PBO", "TRT", "TRT", "PBO"],
            # EDC system columns that should be filtered out
            "projectid": [1, 1, 1, 1, 1],
            "instanceId": [10, 20, 30, 40, 50],
        }
    )


class TestDMEndToEnd:
    def test_output_has_exactly_mapped_columns(
        self, dm_spec: DomainMappingSpec, raw_dm_df: pd.DataFrame
    ) -> None:
        """Output should have exactly the 8 mapped columns, no extras."""
        sdtm_ref = load_sdtm_reference()
        ct_ref = load_ct_reference()
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec,
            {"dm": raw_dm_df},
            study_id="TEST-STUDY-001",
        )
        expected_cols = {
            "STUDYID", "DOMAIN", "USUBJID", "SUBJID",
            "SITEID", "SEX", "AGE", "ARMCD",
        }
        assert set(result.columns) == expected_cols

    def test_studyid_is_constant(
        self, dm_spec: DomainMappingSpec, raw_dm_df: pd.DataFrame
    ) -> None:
        """STUDYID should be the same constant for all rows."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dm_spec,
            {"dm": raw_dm_df},
            study_id="TEST-STUDY-001",
        )
        assert all(result["STUDYID"] == "TEST-STUDY-001")

    def test_domain_is_dm(
        self, dm_spec: DomainMappingSpec, raw_dm_df: pd.DataFrame
    ) -> None:
        """DOMAIN should be 'DM' for all rows."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dm_spec,
            {"dm": raw_dm_df},
            study_id="TEST-STUDY-001",
        )
        assert all(result["DOMAIN"] == "DM")

    def test_columns_in_sdtm_order(
        self, dm_spec: DomainMappingSpec, raw_dm_df: pd.DataFrame
    ) -> None:
        """Columns should be in SDTM-IG order (by mapping order field)."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dm_spec,
            {"dm": raw_dm_df},
            study_id="TEST-STUDY-001",
        )
        cols = list(result.columns)
        # Verify ordering
        assert cols.index("STUDYID") < cols.index("DOMAIN")
        assert cols.index("DOMAIN") < cols.index("USUBJID")
        assert cols.index("USUBJID") < cols.index("SUBJID")
        assert cols.index("SUBJID") < cols.index("SITEID")
        assert cols.index("SITEID") < cols.index("SEX")

    def test_no_unmapped_raw_columns(
        self, dm_spec: DomainMappingSpec, raw_dm_df: pd.DataFrame
    ) -> None:
        """Raw columns like projectid, instanceId should NOT leak through."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dm_spec,
            {"dm": raw_dm_df},
            study_id="TEST-STUDY-001",
        )
        assert "projectid" not in result.columns
        assert "instanceId" not in result.columns
        assert "Gender" not in result.columns

    def test_char_lengths_optimized(
        self, dm_spec: DomainMappingSpec, raw_dm_df: pd.DataFrame
    ) -> None:
        """Character column lengths should be optimized (not 200)."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        executor.execute(
            dm_spec,
            {"dm": raw_dm_df},
            study_id="TEST-STUDY-001",
        )
        widths = executor._last_char_widths
        assert len(widths) > 0
        # All widths should be reasonable (not 200 default)
        for col, width in widths.items():
            assert width < 200, f"Column {col} has width {width}, should be optimized"

    def test_five_subjects_preserved(
        self, dm_spec: DomainMappingSpec, raw_dm_df: pd.DataFrame
    ) -> None:
        """All 5 subjects from raw data should be in output."""
        executor = DatasetExecutor(ct_ref=load_ct_reference())
        result = executor.execute(
            dm_spec,
            {"dm": raw_dm_df},
            study_id="TEST-STUDY-001",
        )
        assert len(result) == 5

    def test_sex_recoded(
        self, dm_spec: DomainMappingSpec, raw_dm_df: pd.DataFrame
    ) -> None:
        """SEX should be recoded via C66731 codelist (Male -> M, Female -> F)."""
        ct_ref = load_ct_reference()
        executor = DatasetExecutor(ct_ref=ct_ref)
        result = executor.execute(
            dm_spec,
            {"dm": raw_dm_df},
            study_id="TEST-STUDY-001",
        )
        sex_values = set(result["SEX"].dropna().unique())
        # Should contain submission values (M, F), not display terms (Male, Female)
        assert sex_values <= {"M", "F"}
