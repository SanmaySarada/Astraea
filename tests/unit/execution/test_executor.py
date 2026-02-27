"""Tests for DatasetExecutor class."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from astraea.execution.executor import (
    CrossDomainContext,
    DatasetExecutor,
    ExecutionError,
)
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation


def _make_mapping(
    *,
    sdtm_variable: str,
    pattern: MappingPattern,
    source_variable: str | None = None,
    assigned_value: str | None = None,
    derivation_rule: str | None = None,
    codelist_code: str | None = None,
    order: int = 0,
) -> VariableMapping:
    """Helper to create a VariableMapping with minimal boilerplate."""
    return VariableMapping(
        sdtm_variable=sdtm_variable,
        sdtm_label=f"{sdtm_variable} label",
        sdtm_data_type="Char",
        core=CoreDesignation.REQ,
        source_variable=source_variable,
        mapping_pattern=pattern,
        mapping_logic="test mapping",
        assigned_value=assigned_value,
        derivation_rule=derivation_rule,
        codelist_code=codelist_code,
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="test",
        order=order,
    )


def _make_dm_spec() -> DomainMappingSpec:
    """Create a minimal DM domain mapping spec for testing."""
    return DomainMappingSpec(
        domain="DM",
        domain_label="Demographics",
        domain_class="Special Purpose",
        structure="One record per subject",
        study_id="TEST-001",
        source_datasets=["dm.sas7bdat"],
        variable_mappings=[
            _make_mapping(
                sdtm_variable="STUDYID",
                pattern=MappingPattern.ASSIGN,
                assigned_value="TEST-001",
                order=1,
            ),
            _make_mapping(
                sdtm_variable="DOMAIN",
                pattern=MappingPattern.ASSIGN,
                assigned_value="DM",
                order=2,
            ),
            _make_mapping(
                sdtm_variable="USUBJID",
                pattern=MappingPattern.DERIVATION,
                derivation_rule="generate_usubjid",
                order=3,
            ),
            _make_mapping(
                sdtm_variable="SUBJID",
                pattern=MappingPattern.DIRECT,
                source_variable="Subject",
                order=4,
            ),
            _make_mapping(
                sdtm_variable="SEX",
                pattern=MappingPattern.LOOKUP_RECODE,
                source_variable="Gender",
                codelist_code="C66731",
                order=5,
            ),
        ],
        total_variables=5,
        required_mapped=5,
        expected_mapped=0,
        high_confidence_count=5,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


def _make_ae_spec() -> DomainMappingSpec:
    """Create a minimal AE domain mapping spec for --DY testing."""
    return DomainMappingSpec(
        domain="AE",
        domain_label="Adverse Events",
        domain_class="Events",
        structure="One record per adverse event",
        study_id="TEST-001",
        source_datasets=["ae.sas7bdat"],
        variable_mappings=[
            _make_mapping(
                sdtm_variable="STUDYID",
                pattern=MappingPattern.ASSIGN,
                assigned_value="TEST-001",
                order=1,
            ),
            _make_mapping(
                sdtm_variable="DOMAIN",
                pattern=MappingPattern.ASSIGN,
                assigned_value="AE",
                order=2,
            ),
            _make_mapping(
                sdtm_variable="USUBJID",
                pattern=MappingPattern.DIRECT,
                source_variable="USUBJID",
                order=3,
            ),
            _make_mapping(
                sdtm_variable="AESEQ",
                pattern=MappingPattern.DERIVATION,
                derivation_rule="generate_seq",
                order=4,
            ),
            _make_mapping(
                sdtm_variable="AETERM",
                pattern=MappingPattern.DIRECT,
                source_variable="AETERM",
                order=5,
            ),
            _make_mapping(
                sdtm_variable="AESTDTC",
                pattern=MappingPattern.DIRECT,
                source_variable="AESTDTC",
                order=6,
            ),
            _make_mapping(
                sdtm_variable="AESTDY",
                pattern=MappingPattern.DERIVATION,
                derivation_rule="calculate_study_day",
                order=7,
            ),
        ],
        total_variables=7,
        required_mapped=7,
        expected_mapped=0,
        high_confidence_count=7,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def raw_dm_df() -> pd.DataFrame:
    """Raw DM data for testing."""
    return pd.DataFrame(
        {
            "Subject": ["001", "002"],
            "Gender": ["Male", "Female"],
            "SiteNumber": ["101", "102"],
        }
    )


@pytest.fixture()
def raw_ae_df() -> pd.DataFrame:
    """Raw AE data for testing."""
    return pd.DataFrame(
        {
            "USUBJID": ["TEST-001-101-001", "TEST-001-101-001", "TEST-001-102-002"],
            "AETERM": ["Headache", "Nausea", "Fatigue"],
            "AESTDTC": ["2022-04-01", "2022-04-05", "2022-03-30"],
        }
    )


@pytest.fixture()
def mock_ct() -> MagicMock:
    """Mock CTReference with SEX codelist."""
    mock = MagicMock(spec=["lookup_codelist"])
    mock_codelist = MagicMock()
    mock_codelist.terms = {
        "M": MagicMock(preferred_term="Male"),
        "F": MagicMock(preferred_term="Female"),
    }
    mock.lookup_codelist.return_value = mock_codelist
    return mock


class TestExecutorBasic:
    def test_executor_basic_dm(
        self, raw_dm_df: pd.DataFrame, mock_ct: MagicMock
    ) -> None:
        """Execute DM spec and verify output columns."""
        executor = DatasetExecutor(ct_ref=mock_ct)
        spec = _make_dm_spec()
        result = executor.execute(
            spec,
            {"dm": raw_dm_df},
            study_id="TEST-001",
        )
        assert "STUDYID" in result.columns
        assert "DOMAIN" in result.columns
        assert "SUBJID" in result.columns
        assert "SEX" in result.columns
        assert len(result) == 2

    def test_executor_assign_pattern(
        self, raw_dm_df: pd.DataFrame, mock_ct: MagicMock
    ) -> None:
        """STUDYID column should be constant 'TEST-001' for all rows."""
        executor = DatasetExecutor(ct_ref=mock_ct)
        spec = _make_dm_spec()
        result = executor.execute(spec, {"dm": raw_dm_df}, study_id="TEST-001")
        assert all(result["STUDYID"] == "TEST-001")

    def test_executor_direct_pattern(
        self, raw_dm_df: pd.DataFrame, mock_ct: MagicMock
    ) -> None:
        """SUBJID should match raw Subject column."""
        executor = DatasetExecutor(ct_ref=mock_ct)
        spec = _make_dm_spec()
        result = executor.execute(spec, {"dm": raw_dm_df}, study_id="TEST-001")
        assert list(result["SUBJID"]) == ["001", "002"]


class TestExecutorColumnOrder:
    def test_executor_variable_order(
        self, raw_dm_df: pd.DataFrame, mock_ct: MagicMock
    ) -> None:
        """Columns should be ordered by mapping order field."""
        executor = DatasetExecutor(ct_ref=mock_ct)
        spec = _make_dm_spec()
        result = executor.execute(spec, {"dm": raw_dm_df}, study_id="TEST-001")
        cols = list(result.columns)
        assert cols.index("STUDYID") < cols.index("DOMAIN")
        assert cols.index("DOMAIN") < cols.index("SUBJID")
        assert cols.index("SUBJID") < cols.index("SEX")

    def test_executor_drops_unmapped(
        self, raw_dm_df: pd.DataFrame, mock_ct: MagicMock
    ) -> None:
        """Raw columns not in spec should not appear in output."""
        executor = DatasetExecutor(ct_ref=mock_ct)
        spec = _make_dm_spec()
        result = executor.execute(spec, {"dm": raw_dm_df}, study_id="TEST-001")
        assert "Subject" not in result.columns
        assert "Gender" not in result.columns
        assert "SiteNumber" not in result.columns


class TestExecutorSeq:
    def test_executor_seq_not_in_dm(
        self, raw_dm_df: pd.DataFrame, mock_ct: MagicMock
    ) -> None:
        """DM domain should NOT have DMSEQ."""
        executor = DatasetExecutor(ct_ref=mock_ct)
        spec = _make_dm_spec()
        result = executor.execute(spec, {"dm": raw_dm_df}, study_id="TEST-001")
        assert "DMSEQ" not in result.columns


class TestExecutorCrossDomain:
    def test_executor_with_cross_domain_dy(
        self, raw_ae_df: pd.DataFrame
    ) -> None:
        """Verify --DY derivation with RFSTDTC lookup for AE domain."""
        executor = DatasetExecutor()
        spec = _make_ae_spec()
        cross_domain = CrossDomainContext(
            rfstdtc_lookup={
                "TEST-001-101-001": "2022-03-30",
                "TEST-001-102-002": "2022-03-30",
            }
        )
        result = executor.execute(
            spec,
            {"ae": raw_ae_df},
            cross_domain=cross_domain,
        )
        assert "AESTDY" in result.columns
        # AESTDTC="2022-03-30" with RFSTDTC="2022-03-30" -> DY=1
        # AESTDTC="2022-04-01" with RFSTDTC="2022-03-30" -> DY=3
        dy_values = result.set_index("AETERM")["AESTDY"]
        assert dy_values["Fatigue"] == 1
        assert dy_values["Headache"] == 3
        assert dy_values["Nausea"] == 7


class TestExecutorErrorHandling:
    def test_executor_noncritical_failure_continues(self) -> None:
        """Mapping referencing nonexistent source should log warning, not crash."""
        spec = DomainMappingSpec(
            domain="AE",
            domain_label="Adverse Events",
            domain_class="Events",
            structure="One record per AE",
            study_id="TEST-001",
            source_datasets=["ae.sas7bdat"],
            variable_mappings=[
                _make_mapping(
                    sdtm_variable="STUDYID",
                    pattern=MappingPattern.ASSIGN,
                    assigned_value="TEST-001",
                    order=1,
                ),
                _make_mapping(
                    sdtm_variable="DOMAIN",
                    pattern=MappingPattern.ASSIGN,
                    assigned_value="AE",
                    order=2,
                ),
                _make_mapping(
                    sdtm_variable="USUBJID",
                    pattern=MappingPattern.DIRECT,
                    source_variable="USUBJID",
                    order=3,
                ),
                _make_mapping(
                    sdtm_variable="BADVAR",
                    pattern=MappingPattern.DIRECT,
                    source_variable="NONEXISTENT",
                    order=4,
                ),
            ],
            total_variables=4,
            required_mapped=3,
            expected_mapped=0,
            high_confidence_count=4,
            medium_confidence_count=0,
            low_confidence_count=0,
            mapping_timestamp="2026-02-27T00:00:00",
            model_used="test",
        )
        df = pd.DataFrame({"USUBJID": ["S001"]})
        executor = DatasetExecutor()
        # Should NOT raise despite NONEXISTENT column
        result = executor.execute(spec, {"ae": df})
        assert "STUDYID" in result.columns
        assert "BADVAR" in result.columns
        assert pd.isna(result["BADVAR"].iloc[0])

    def test_executor_critical_failure_raises(self) -> None:
        """STUDYID failing should raise ExecutionError."""
        spec = DomainMappingSpec(
            domain="AE",
            domain_label="Adverse Events",
            domain_class="Events",
            structure="One record per AE",
            study_id="TEST-001",
            source_datasets=["ae.sas7bdat"],
            variable_mappings=[
                _make_mapping(
                    sdtm_variable="STUDYID",
                    pattern=MappingPattern.DIRECT,
                    source_variable="NONEXISTENT",
                    order=1,
                ),
            ],
            total_variables=1,
            required_mapped=1,
            expected_mapped=0,
            high_confidence_count=1,
            medium_confidence_count=0,
            low_confidence_count=0,
            mapping_timestamp="2026-02-27T00:00:00",
            model_used="test",
        )
        df = pd.DataFrame({"USUBJID": ["S001"]})
        executor = DatasetExecutor()
        with pytest.raises(ExecutionError, match="STUDYID"):
            executor.execute(spec, {"ae": df})
