"""Tests for DatasetExecutor XPT compliance: ASCII fix, char lengths, sort, cross-domain."""

from __future__ import annotations

import pandas as pd

from astraea.execution.executor import DatasetExecutor
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
    label: str | None = None,
) -> VariableMapping:
    """Helper to create a VariableMapping with minimal boilerplate."""
    return VariableMapping(
        sdtm_variable=sdtm_variable,
        sdtm_label=label or f"{sdtm_variable} label",
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


def _make_simple_spec() -> DomainMappingSpec:
    """Create a minimal AE spec for XPT compliance testing."""
    return DomainMappingSpec(
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
                sdtm_variable="AETERM",
                pattern=MappingPattern.DIRECT,
                source_variable="AETERM",
                order=4,
            ),
        ],
        total_variables=4,
        required_mapped=4,
        expected_mapped=0,
        high_confidence_count=4,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


class TestAsciiFixApplied:
    def test_curly_quotes_replaced(self) -> None:
        """Input DataFrame with curly quotes should have straight quotes in output."""
        spec = _make_simple_spec()
        raw_df = pd.DataFrame(
            {
                "USUBJID": ["S001", "S002"],
                "AETERM": ["\u201cHeadache\u201d", "Nausea"],
            }
        )
        executor = DatasetExecutor()
        result = executor.execute(spec, {"ae": raw_df})
        # Curly quotes should be replaced with straight quotes
        assert result["AETERM"].iloc[0] == '"Headache"'
        assert result["AETERM"].iloc[1] == "Nausea"


class TestCharLengthsComputed:
    def test_char_widths_populated(self) -> None:
        """_last_char_widths should be populated after execute()."""
        spec = _make_simple_spec()
        raw_df = pd.DataFrame(
            {
                "USUBJID": ["S001", "S002"],
                "AETERM": ["Headache", "Nausea"],
            }
        )
        executor = DatasetExecutor()
        # Before execute, char widths should be empty
        assert executor._last_char_widths == {}
        executor.execute(spec, {"ae": raw_df})
        # After execute, should have widths for string columns
        assert len(executor._last_char_widths) > 0
        # AETERM max is "Headache" (8 chars), not default 200
        assert executor._last_char_widths["AETERM"] == 8


class TestSortOrderApplied:
    def test_rows_sorted_by_key_variables(self) -> None:
        """Output rows should be sorted by STUDYID, USUBJID (fallback)."""
        spec = _make_simple_spec()
        raw_df = pd.DataFrame(
            {
                "USUBJID": ["S003", "S001", "S002"],
                "AETERM": ["Fatigue", "Headache", "Nausea"],
            }
        )
        executor = DatasetExecutor()
        result = executor.execute(spec, {"ae": raw_df})
        # Should be sorted by USUBJID (fallback since no sdtm_ref)
        assert list(result["USUBJID"]) == ["S001", "S002", "S003"]


class TestCrossDomainValidation:
    def test_pass_all_subjects_in_dm(self) -> None:
        """No errors when all domain USUBJIDs exist in DM."""
        dm_df = pd.DataFrame({"USUBJID": ["S001", "S002"]})
        ae_df = pd.DataFrame({"USUBJID": ["S001", "S002"]})
        errors = DatasetExecutor.validate_cross_domain_usubjid(
            dm_df, {"AE": ae_df}
        )
        assert errors == []

    def test_fail_orphan_subject(self) -> None:
        """Error when a domain has a USUBJID not in DM."""
        dm_df = pd.DataFrame({"USUBJID": ["S001", "S002"]})
        ae_df = pd.DataFrame({"USUBJID": ["S001", "S002", "S003"]})
        errors = DatasetExecutor.validate_cross_domain_usubjid(
            dm_df, {"AE": ae_df}
        )
        assert len(errors) == 1
        assert "S003" in errors[0]
        assert "AE" in errors[0]

    def test_fail_missing_dm_column(self) -> None:
        """Error when DM lacks USUBJID column."""
        dm_df = pd.DataFrame({"SUBJID": ["001"]})
        ae_df = pd.DataFrame({"USUBJID": ["S001"]})
        errors = DatasetExecutor.validate_cross_domain_usubjid(
            dm_df, {"AE": ae_df}
        )
        assert len(errors) == 1
        assert "missing USUBJID" in errors[0]

    def test_multiple_domains(self) -> None:
        """Check across multiple domains at once."""
        dm_df = pd.DataFrame({"USUBJID": ["S001", "S002"]})
        ae_df = pd.DataFrame({"USUBJID": ["S001", "S002"]})
        cm_df = pd.DataFrame({"USUBJID": ["S001", "S003"]})
        errors = DatasetExecutor.validate_cross_domain_usubjid(
            dm_df, {"AE": ae_df, "CM": cm_df}
        )
        assert len(errors) == 1
        assert "S003" in errors[0]
        assert "CM" in errors[0]
