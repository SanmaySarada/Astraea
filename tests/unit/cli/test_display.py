"""Tests for CLI display_mapping_spec function.

Verifies that display_mapping_spec produces output containing the
domain name, variable names, and confidence information without errors.
"""

from __future__ import annotations

import re
from io import StringIO

import pytest
from rich.console import Console

from astraea.cli.display import display_mapping_spec
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


@pytest.fixture()
def sample_spec() -> DomainMappingSpec:
    """Minimal DomainMappingSpec for display testing."""
    mappings = [
        VariableMapping(
            sdtm_variable="STUDYID",
            sdtm_label="Study Identifier",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            mapping_pattern=MappingPattern.ASSIGN,
            mapping_logic="Assign constant study ID",
            assigned_value="PHA022121-C301",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Standard assignment",
        ),
        VariableMapping(
            sdtm_variable="USUBJID",
            sdtm_label="Unique Subject Identifier",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            source_dataset="dm.sas7bdat",
            source_variable="Subject",
            source_label="Subject Number",
            mapping_pattern=MappingPattern.DERIVATION,
            mapping_logic="STUDYID || '-' || SiteNumber || '-' || Subject",
            confidence=0.90,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Standard derivation",
        ),
        VariableMapping(
            sdtm_variable="SEX",
            sdtm_label="Sex",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            source_dataset="dm.sas7bdat",
            source_variable="SEX",
            source_label="Gender",
            mapping_pattern=MappingPattern.LOOKUP_RECODE,
            mapping_logic="Map via CT codelist C66731",
            codelist_code="C66731",
            confidence=0.50,
            confidence_level=ConfidenceLevel.LOW,
            confidence_rationale="CT lookup needed",
            notes="Review values",
        ),
    ]

    return DomainMappingSpec(
        domain="DM",
        domain_label="Demographics",
        domain_class="Special Purpose",
        structure="One record per subject",
        study_id="PHA022121-C301",
        source_datasets=["dm.sas7bdat"],
        cross_domain_sources=[],
        variable_mappings=mappings,
        total_variables=3,
        required_mapped=3,
        expected_mapped=0,
        high_confidence_count=2,
        medium_confidence_count=0,
        low_confidence_count=1,
        mapping_timestamp="2026-02-27T12:00:00Z",
        model_used="claude-sonnet-4-20250514",
        unmapped_source_variables=["SCREENED"],
        suppqual_candidates=["ETHNGRP"],
    )


class TestDisplayMappingSpec:
    """Tests for display_mapping_spec Rich output."""

    def test_display_mapping_spec_no_error(
        self, sample_spec: DomainMappingSpec
    ) -> None:
        """display_mapping_spec runs without exception and produces output."""
        buf = StringIO()
        cons = Console(file=buf, force_terminal=True, no_color=True, width=120)
        display_mapping_spec(sample_spec, cons)
        output = buf.getvalue()
        assert len(output) > 0

    def test_display_mapping_spec_contains_domain(
        self, sample_spec: DomainMappingSpec
    ) -> None:
        """Output contains the domain name."""
        buf = StringIO()
        cons = Console(file=buf, force_terminal=True, no_color=True, width=120)
        display_mapping_spec(sample_spec, cons)
        output = buf.getvalue()
        assert "DM" in output
        assert "Demographics" in output

    def test_display_mapping_spec_contains_variables(
        self, sample_spec: DomainMappingSpec
    ) -> None:
        """Output contains SDTM variable names from the fixture."""
        buf = StringIO()
        cons = Console(file=buf, force_terminal=True, no_color=True, width=120)
        display_mapping_spec(sample_spec, cons)
        output = buf.getvalue()
        assert "STUDYID" in output
        assert "USUBJID" in output
        assert "SEX" in output

    def test_display_mapping_spec_contains_confidence_counts(
        self, sample_spec: DomainMappingSpec
    ) -> None:
        """Output contains confidence level summary counts."""
        buf = StringIO()
        cons = Console(file=buf, force_terminal=True, no_color=True, width=120)
        display_mapping_spec(sample_spec, cons)
        output = _strip_ansi(buf.getvalue())
        assert "HIGH: 2" in output
        assert "LOW: 1" in output

    def test_display_mapping_spec_contains_unmapped(
        self, sample_spec: DomainMappingSpec
    ) -> None:
        """Output contains unmapped and SUPPQUAL candidate information."""
        buf = StringIO()
        cons = Console(file=buf, force_terminal=True, no_color=True, width=120)
        display_mapping_spec(sample_spec, cons)
        output = buf.getvalue()
        assert "SCREENED" in output
        assert "ETHNGRP" in output
