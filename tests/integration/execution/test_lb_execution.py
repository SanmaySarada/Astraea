"""End-to-end LB domain execution integration test.

Creates synthetic lab data (no real Fakedata dependency) and verifies the
full Findings pipeline: multi-source normalization, merging, spec execution,
LBSEQ generation, column order, date imputation flags, and LBNRIND passthrough.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.executor import DatasetExecutor
from astraea.execution.findings import (
    FindingsExecutor,
    normalize_lab_columns,
)
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
def lb_spec() -> DomainMappingSpec:
    """LB domain spec with Findings-class mappings."""
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
            assigned="LB",
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
            var="LBSEQ",
            pattern=MappingPattern.DERIVATION,
            label="Sequence Number",
            derivation="generate_seq",
            order=4,
        ),
        _mapping(
            var="LBTESTCD",
            pattern=MappingPattern.DIRECT,
            label="Lab Test or Examination Short Name",
            source="LBTESTCD",
            order=5,
        ),
        _mapping(
            var="LBTEST",
            pattern=MappingPattern.DIRECT,
            label="Lab Test or Examination Name",
            source="LBTEST",
            order=6,
        ),
        _mapping(
            var="LBCAT",
            pattern=MappingPattern.DIRECT,
            label="Category for Lab Test",
            source="LBCAT",
            order=7,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBORRES",
            pattern=MappingPattern.DIRECT,
            label="Result or Finding in Original Units",
            source="LBORRES",
            order=8,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBORRESU",
            pattern=MappingPattern.DIRECT,
            label="Original Units",
            source="LBORRESU",
            order=9,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBSTRESC",
            pattern=MappingPattern.DIRECT,
            label="Character Result/Finding in Std Format",
            source="LBSTRESC",
            order=10,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBSTRESN",
            pattern=MappingPattern.DIRECT,
            label="Numeric Result/Finding in Std Units",
            source="LBSTRESN",
            order=11,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBSTRESU",
            pattern=MappingPattern.DIRECT,
            label="Standard Units",
            source="LBSTRESU",
            order=12,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBSTNRLO",
            pattern=MappingPattern.DIRECT,
            label="Reference Range Lower Limit-Std Units",
            source="LBSTNRLO",
            order=13,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBSTNRHI",
            pattern=MappingPattern.DIRECT,
            label="Reference Range Upper Limit-Std Units",
            source="LBSTNRHI",
            order=14,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBNRIND",
            pattern=MappingPattern.DIRECT,
            label="Reference Range Indicator",
            source="LBNRIND",
            order=15,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBSPEC",
            pattern=MappingPattern.DIRECT,
            label="Specimen Type",
            source="LBSPEC",
            order=16,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBMETHOD",
            pattern=MappingPattern.DIRECT,
            label="Method of Test or Examination",
            source="LBMETHOD",
            order=17,
            core=CoreDesignation.PERM,
        ),
        _mapping(
            var="LBBLFL",
            pattern=MappingPattern.DIRECT,
            label="Baseline Flag",
            source="LBBLFL",
            order=18,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBFAST",
            pattern=MappingPattern.DIRECT,
            label="Fasting Status",
            source="LBFAST",
            order=19,
            core=CoreDesignation.PERM,
        ),
        _mapping(
            var="LBDTC",
            pattern=MappingPattern.DIRECT,
            label="Date/Time of Specimen Collection",
            source="LBDTC",
            order=20,
        ),
        _mapping(
            var="LBDTF",
            pattern=MappingPattern.DIRECT,
            label="Date Imputation Flag",
            source="LBDTF",
            order=21,
            core=CoreDesignation.PERM,
        ),
    ]
    return DomainMappingSpec(
        domain="LB",
        domain_label="Laboratory Test Results",
        domain_class="Findings",
        structure="One record per lab test per visit per subject",
        study_id="PHA022121-C301",
        source_datasets=["lab_results.sas7bdat", "llb.sas7bdat"],
        variable_mappings=mappings,
        total_variables=21,
        required_mapped=4,
        expected_mapped=12,
        high_confidence_count=21,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_lab_results() -> pd.DataFrame:
    """Synthetic lab_results data: 10 rows, 3 subjects, SDTM-like columns."""
    return pd.DataFrame(
        {
            "Subject": ["001", "001", "001", "001", "002", "002", "002", "003", "003", "003"],
            "SiteNumber": ["101"] * 10,
            "LBTESTCD": ["ALT", "WBC", "HGB", "ALT", "ALT", "WBC", "HGB", "ALT", "WBC", "HGB"],
            "LBTEST": [
                "Alanine Aminotransferase",
                "White Blood Cell",
                "Hemoglobin",
                "Alanine Aminotransferase",
                "Alanine Aminotransferase",
                "White Blood Cell",
                "Hemoglobin",
                "Alanine Aminotransferase",
                "White Blood Cell",
                "Hemoglobin",
            ],
            "LBCAT": [
                "CHEMISTRY",
                "HEMATOLOGY",
                "HEMATOLOGY",
                "CHEMISTRY",
                "CHEMISTRY",
                "HEMATOLOGY",
                "HEMATOLOGY",
                "CHEMISTRY",
                "HEMATOLOGY",
                "HEMATOLOGY",
            ],
            "LBORRES": ["25", "5.2", "14.1", "30", "22", "6.0", "13.5", "28", "4.8", "15.0"],
            "LBORRESU": [
                "U/L",
                "10^3/uL",
                "g/dL",
                "U/L",
                "U/L",
                "10^3/uL",
                "g/dL",
                "U/L",
                "10^3/uL",
                "g/dL",
            ],
            "LBSTRESC": ["25", "5.2", "14.1", "30", "22", "6.0", "13.5", "28", "4.8", "15.0"],
            "LBSTRESN": [25.0, 5.2, 14.1, 30.0, 22.0, 6.0, 13.5, 28.0, 4.8, 15.0],
            "LBSTRESU": [
                "U/L",
                "10^9/L",
                "g/L",
                "U/L",
                "U/L",
                "10^9/L",
                "g/L",
                "U/L",
                "10^9/L",
                "g/L",
            ],
            "LBSTNRLO": [7.0, 4.0, 12.0, 7.0, 7.0, 4.0, 12.0, 7.0, 4.0, 12.0],
            "LBSTNRHI": [56.0, 11.0, 18.0, 56.0, 56.0, 11.0, 18.0, 56.0, 11.0, 18.0],
            "LBNRIND": [
                "NORMAL",
                "NORMAL",
                "NORMAL",
                "NORMAL",
                "NORMAL",
                "NORMAL",
                "LOW",
                "NORMAL",
                "NORMAL",
                "NORMAL",
            ],
            "LBSPEC": [
                "BLOOD",
                "BLOOD",
                "BLOOD",
                "BLOOD",
                "BLOOD",
                "BLOOD",
                "BLOOD",
                "BLOOD",
                "BLOOD",
                "BLOOD",
            ],
            "LBMETHOD": [
                "Photometry",
                "Flow Cytometry",
                "Photometry",
                "Photometry",
                "Photometry",
                "Flow Cytometry",
                "Photometry",
                "Photometry",
                "Flow Cytometry",
                "Photometry",
            ],
            "LBBLFL": ["Y", "", "", "", "Y", "", "", "Y", "", ""],
            "LBFAST": ["Y", "Y", "Y", "Y", "Y", "Y", "Y", "Y", "Y", "Y"],
            "LBDTC": [
                "2022-01-15",
                "2022-01-15",
                "2022-01-15",
                "2022-02-15",
                "2022-01-20",
                "2022-01-20",
                "2022-01-20",
                "2022-01-25",
                "2022-01-25",
                "2022-01-25",
            ],
            "LBDTF": [
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ],
        }
    )


@pytest.fixture()
def raw_llb() -> pd.DataFrame:
    """Synthetic llb (local lab) data: 3 rows with CRF-style column names."""
    return pd.DataFrame(
        {
            "Subject": ["001", "002", "003"],
            "SiteNumber": ["101", "101", "101"],
            "LBTEST2": ["Glucose", "Glucose", "Glucose"],
            "LBORRES": ["95", "110", "88"],
            "LBORRESU": ["mg/dL", "mg/dL", "mg/dL"],
            "LBORNRLO": [70.0, 70.0, 70.0],
            "LBORNRHI": [100.0, 100.0, 100.0],
            "LBNAM": ["Local Lab A", "Local Lab A", "Local Lab A"],
            "LBCAT": ["CHEMISTRY", "CHEMISTRY", "CHEMISTRY"],
            "LBSPEC": ["BLOOD", "BLOOD", "BLOOD"],
            "LBMETHOD": ["Enzymatic", "Enzymatic", "Enzymatic"],
            "LBBLFL": ["Y", "Y", "Y"],
            "LBFAST": ["Y", "Y", "Y"],
            "LBDTC": ["2022-01-15", "2022-01-20", "2022-01-25"],
            "LBDTF": ["", "", ""],
        }
    )


@pytest.fixture()
def raw_lab_with_partial_dates() -> pd.DataFrame:
    """Lab data with partial dates to test date imputation flags."""
    return pd.DataFrame(
        {
            "Subject": ["001", "001", "002"],
            "SiteNumber": ["101", "101", "101"],
            "LBTESTCD": ["ALT", "WBC", "ALT"],
            "LBTEST": ["Alanine Aminotransferase", "White Blood Cell", "Alanine Aminotransferase"],
            "LBCAT": ["CHEMISTRY", "HEMATOLOGY", "CHEMISTRY"],
            "LBORRES": ["25", "5.2", "30"],
            "LBORRESU": ["U/L", "10^3/uL", "U/L"],
            "LBSTRESC": ["25", "5.2", "30"],
            "LBSTRESN": [25.0, 5.2, 30.0],
            "LBSTRESU": ["U/L", "10^9/L", "U/L"],
            "LBSTNRLO": [7.0, 4.0, 7.0],
            "LBSTNRHI": [56.0, 11.0, 56.0],
            "LBNRIND": ["NORMAL", "NORMAL", "NORMAL"],
            "LBSPEC": ["BLOOD", "BLOOD", "BLOOD"],
            "LBMETHOD": ["Photometry", "Flow Cytometry", "Photometry"],
            "LBBLFL": ["Y", "", "Y"],
            "LBFAST": ["Y", "Y", "Y"],
            "LBDTC": ["2022-03", "2022-01-15", "2022-03"],
            "LBDTF": ["D", "", "D"],
        }
    )


@pytest.fixture()
def lb_executor() -> FindingsExecutor:
    """FindingsExecutor with both SDTM and CT references loaded."""
    return FindingsExecutor(
        sdtm_ref=load_sdtm_reference(),
        ct_ref=load_ct_reference(),
    )


@pytest.fixture()
def lb_basic_executor() -> DatasetExecutor:
    """DatasetExecutor for basic LB tests."""
    return DatasetExecutor(
        sdtm_ref=load_sdtm_reference(),
        ct_ref=load_ct_reference(),
    )


class TestLBExecution:
    def test_lb_basic_execution(
        self,
        lb_spec: DomainMappingSpec,
        raw_lab_results: pd.DataFrame,
        lb_basic_executor: DatasetExecutor,
    ) -> None:
        """Execute spec on lab_results only, verify SDTM columns present and row count."""
        result = lb_basic_executor.execute(
            lb_spec, {"lab_results": raw_lab_results}, study_id="PHA022121-C301"
        )
        assert len(result) == 10
        assert "STUDYID" in result.columns
        assert "DOMAIN" in result.columns
        assert "USUBJID" in result.columns
        assert "LBTESTCD" in result.columns
        assert "LBTEST" in result.columns
        assert "LBORRES" in result.columns
        assert "LBDTC" in result.columns

    def test_lb_multi_source_merge(
        self,
        lb_spec: DomainMappingSpec,
        raw_lab_results: pd.DataFrame,
        raw_llb: pd.DataFrame,
        lb_executor: FindingsExecutor,
    ) -> None:
        """Merge lab_results + normalized llb, verify combined row count = 13."""
        lb_df, _ = lb_executor.execute_lb(
            lb_spec,
            {"lab_results": raw_lab_results, "llb": raw_llb},
            study_id="PHA022121-C301",
        )
        assert len(lb_df) == 13

    def test_lb_seq_generation(
        self,
        lb_spec: DomainMappingSpec,
        raw_lab_results: pd.DataFrame,
        lb_basic_executor: DatasetExecutor,
    ) -> None:
        """Verify LBSEQ is unique per USUBJID and monotonically increasing."""
        result = lb_basic_executor.execute(
            lb_spec, {"lab_results": raw_lab_results}, study_id="PHA022121-C301"
        )
        assert "LBSEQ" in result.columns
        # Check per-subject monotonicity
        for _, group in result.groupby("USUBJID"):
            seq_values = list(group["LBSEQ"])
            assert seq_values == sorted(seq_values), (
                f"LBSEQ not monotonic for {group['USUBJID'].iloc[0]}"
            )
            assert seq_values[0] == 1, "LBSEQ should start at 1"
            # Verify uniqueness within subject
            assert len(seq_values) == len(set(seq_values)), "LBSEQ should be unique per subject"

    def test_lb_column_order(
        self,
        lb_spec: DomainMappingSpec,
        raw_lab_results: pd.DataFrame,
        lb_basic_executor: DatasetExecutor,
    ) -> None:
        """Verify columns appear in spec order."""
        result = lb_basic_executor.execute(
            lb_spec, {"lab_results": raw_lab_results}, study_id="PHA022121-C301"
        )
        cols = list(result.columns)
        assert cols.index("STUDYID") < cols.index("DOMAIN")
        assert cols.index("DOMAIN") < cols.index("USUBJID")
        assert cols.index("USUBJID") < cols.index("LBSEQ")
        assert cols.index("LBSEQ") < cols.index("LBTESTCD")
        assert cols.index("LBTESTCD") < cols.index("LBTEST")
        assert cols.index("LBORRES") < cols.index("LBDTC")

    def test_lb_domain_class_findings(
        self,
        lb_spec: DomainMappingSpec,
    ) -> None:
        """Verify domain_class is 'Findings' in spec."""
        assert lb_spec.domain_class == "Findings"

    def test_lb_nrind_passthrough(
        self,
        lb_spec: DomainMappingSpec,
        raw_lab_results: pd.DataFrame,
        lb_basic_executor: DatasetExecutor,
    ) -> None:
        """Verify LBNRIND values from source are preserved."""
        result = lb_basic_executor.execute(
            lb_spec, {"lab_results": raw_lab_results}, study_id="PHA022121-C301"
        )
        assert "LBNRIND" in result.columns
        nrind_values = set(result["LBNRIND"].dropna().unique())
        assert "NORMAL" in nrind_values
        assert "LOW" in nrind_values

    def test_lb_normalize_llb_columns(
        self,
        raw_llb: pd.DataFrame,
    ) -> None:
        """Test normalize_lab_columns on llb-style data."""
        normalized = normalize_lab_columns(raw_llb, "llb")
        # LBTEST2 should be renamed to LBTEST
        assert "LBTEST" in normalized.columns
        assert "LBTEST2" not in normalized.columns
        # LBTESTCD should be derived from LBTEST
        assert "LBTESTCD" in normalized.columns
        assert normalized["LBTESTCD"].iloc[0] == "GLUCOSE"
        # LBORNRLO -> LBSTNRLO
        assert "LBSTNRLO" in normalized.columns

    def test_lb_date_imputation_flag(
        self,
        lb_spec: DomainMappingSpec,
        raw_lab_with_partial_dates: pd.DataFrame,
        lb_basic_executor: DatasetExecutor,
    ) -> None:
        """Verify LBDTF column is present and contains 'D' for day-imputed dates."""
        result = lb_basic_executor.execute(
            lb_spec, {"lab": raw_lab_with_partial_dates}, study_id="PHA022121-C301"
        )
        assert "LBDTF" in result.columns
        dtf_values = list(result["LBDTF"])
        # Rows with partial dates (2022-03) should have "D" flag
        assert "D" in dtf_values
        # Row with full date should have empty flag
        assert "" in dtf_values
