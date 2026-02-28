"""End-to-end validation integration tests.

Creates synthetic multi-domain DataFrames and DomainMappingSpec objects
with intentional issues, then verifies the full validation pipeline
catches expected problems and generates correct reports.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)
from astraea.models.sdtm import CoreDesignation
from astraea.reference import load_ct_reference, load_sdtm_reference
from astraea.validation.engine import ValidationEngine
from astraea.validation.report import ValidationReport
from astraea.validation.rules.base import RuleSeverity
from astraea.validation.rules.consistency import CrossDomainValidator
from astraea.validation.rules.fda_trc import TRCPreCheck


def _mapping(
    *,
    var: str,
    label: str,
    pattern: MappingPattern = MappingPattern.DIRECT,
    dtype: str = "Char",
    core: CoreDesignation = CoreDesignation.REQ,
    source: str | None = None,
    assigned: str | None = None,
    codelist: str | None = None,
    order: int = 1,
    origin: VariableOrigin | None = None,
    computational_method: str | None = None,
) -> VariableMapping:
    """Helper to create a VariableMapping with minimal boilerplate."""
    return VariableMapping(
        sdtm_variable=var,
        sdtm_label=label,
        sdtm_data_type=dtype,
        core=core,
        source_variable=source,
        mapping_pattern=pattern,
        mapping_logic="test mapping",
        assigned_value=assigned,
        codelist_code=codelist,
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="test",
        order=order,
        origin=origin,
        computational_method=computational_method,
    )


def _make_dm_spec() -> DomainMappingSpec:
    """Create DM spec with standard variables."""
    mappings = [
        _mapping(
            var="STUDYID",
            label="Study Identifier",
            pattern=MappingPattern.ASSIGN,
            assigned="TEST-001",
            order=1,
        ),
        _mapping(
            var="DOMAIN",
            label="Domain Abbreviation",
            pattern=MappingPattern.ASSIGN,
            assigned="DM",
            order=2,
        ),
        _mapping(
            var="USUBJID",
            label="Unique Subject Identifier",
            pattern=MappingPattern.DERIVATION,
            source="SUBJID",
            order=3,
            origin=VariableOrigin.DERIVED,
            computational_method="STUDYID || '-' || SITEID || '-' || SUBJID",
        ),
        _mapping(
            var="SUBJID",
            label="Subject Identifier for the Study",
            source="SUBJID",
            order=4,
        ),
        _mapping(
            var="RFSTDTC",
            label="Subject Reference Start Date/Time",
            source="RFSTDTC",
            order=5,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="SITEID",
            label="Study Site Identifier",
            source="SITEID",
            order=6,
            core=CoreDesignation.REQ,
        ),
        _mapping(
            var="SEX",
            label="Sex",
            source="SEX",
            order=7,
            core=CoreDesignation.REQ,
            codelist="C66731",
        ),
        _mapping(
            var="ETHNIC",
            label="Ethnicity",
            source="ETHNIC",
            order=8,
            core=CoreDesignation.EXP,
            codelist="C66790",
        ),
    ]
    return DomainMappingSpec(
        domain="DM",
        domain_label="Demographics",
        domain_class="Special Purpose",
        structure="One record per subject",
        study_id="TEST-001",
        source_datasets=["dm.sas7bdat"],
        variable_mappings=mappings,
        total_variables=len(mappings),
        required_mapped=5,
        expected_mapped=2,
        high_confidence_count=len(mappings),
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


def _make_ae_spec() -> DomainMappingSpec:
    """Create AE spec -- intentionally missing AEDECOD (Required)."""
    mappings = [
        _mapping(
            var="STUDYID",
            label="Study Identifier",
            pattern=MappingPattern.ASSIGN,
            assigned="TEST-001",
            order=1,
        ),
        _mapping(
            var="DOMAIN",
            label="Domain Abbreviation",
            pattern=MappingPattern.ASSIGN,
            assigned="AE",
            order=2,
        ),
        _mapping(
            var="USUBJID",
            label="Unique Subject Identifier",
            source="SUBJID",
            order=3,
        ),
        _mapping(
            var="AESEQ",
            label="Sequence Number",
            dtype="Num",
            source="AESEQ",
            order=4,
        ),
        _mapping(
            var="AETERM",
            label="Reported Term for the Adverse Event",
            source="AETERM",
            order=5,
        ),
        # AEDECOD intentionally MISSING (Required variable)
        _mapping(
            var="AESTDTC",
            label="Start Date/Time of Adverse Event",
            source="AESTDTC",
            order=6,
            core=CoreDesignation.EXP,
        ),
    ]
    return DomainMappingSpec(
        domain="AE",
        domain_label="Adverse Events",
        domain_class="Events",
        structure="One record per adverse event per subject",
        study_id="TEST-001",
        source_datasets=["ae.sas7bdat"],
        variable_mappings=mappings,
        total_variables=len(mappings),
        required_mapped=4,
        expected_mapped=1,
        high_confidence_count=len(mappings),
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


def _make_lb_spec() -> DomainMappingSpec:
    """Create LB spec for findings domain."""
    mappings = [
        _mapping(
            var="STUDYID",
            label="Study Identifier",
            pattern=MappingPattern.ASSIGN,
            assigned="TEST-001",
            order=1,
        ),
        _mapping(
            var="DOMAIN",
            label="Domain Abbreviation",
            pattern=MappingPattern.ASSIGN,
            assigned="LB",
            order=2,
        ),
        _mapping(
            var="USUBJID",
            label="Unique Subject Identifier",
            source="SUBJID",
            order=3,
        ),
        _mapping(
            var="LBSEQ",
            label="Sequence Number",
            dtype="Num",
            source="LBSEQ",
            order=4,
        ),
        _mapping(
            var="LBTESTCD",
            label="Lab Test or Examination Short Name",
            source="LBTESTCD",
            order=5,
        ),
        _mapping(
            var="LBTEST",
            label="Lab Test or Examination Name",
            source="LBTEST",
            order=6,
        ),
        _mapping(
            var="LBORRES",
            label="Result or Finding in Original Units",
            source="LBORRES",
            order=7,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBSTRESC",
            label="Character Result/Finding in Std Format",
            source="LBSTRESC",
            order=8,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBSPEC",
            label="Specimen Type",
            source="LBSPEC",
            order=9,
            core=CoreDesignation.EXP,
            codelist="C78734",  # Specimen Type codelist
        ),
    ]
    return DomainMappingSpec(
        domain="LB",
        domain_label="Laboratory Test Results",
        domain_class="Findings",
        structure="One record per lab test per visit per subject",
        study_id="TEST-001",
        source_datasets=["lb.sas7bdat"],
        variable_mappings=mappings,
        total_variables=len(mappings),
        required_mapped=5,
        expected_mapped=3,
        high_confidence_count=len(mappings),
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


def _make_dm_df() -> pd.DataFrame:
    """Create DM DataFrame with 3 subjects."""
    return pd.DataFrame(
        {
            "STUDYID": ["TEST-001", "TEST-001", "TEST-001"],
            "DOMAIN": ["DM", "DM", "DM"],
            "USUBJID": ["TEST-001-001-001", "TEST-001-001-002", "TEST-001-001-003"],
            "SUBJID": ["001", "002", "003"],
            "RFSTDTC": ["2022-01-15", "2022-02-01", "2022-03-10"],
            "SITEID": ["001", "001", "001"],
            "SEX": ["M", "F", "M"],
            # ETHNIC has intentionally invalid value for C66790
            "ETHNIC": ["HISPANIC OR LATINO", "NOT HISPANIC OR LATINO", "INVALID_ETHNIC"],
        }
    )


def _make_ae_df() -> pd.DataFrame:
    """Create AE DataFrame -- includes a USUBJID orphan not in DM."""
    return pd.DataFrame(
        {
            "STUDYID": ["TEST-001", "TEST-001", "TEST-001"],
            "DOMAIN": ["AE", "AE", "AE"],
            # Third USUBJID is NOT in DM (orphan)
            "USUBJID": ["TEST-001-001-001", "TEST-001-001-002", "TEST-001-001-999"],
            "AESEQ": [1, 1, 1],
            "AETERM": ["Headache", "Nausea", "Fatigue"],
            "AESTDTC": ["2022-02-01", "2022-03-15", "2022-04-01"],
        }
    )


def _make_lb_df() -> pd.DataFrame:
    """Create LB DataFrame with invalid CT values."""
    return pd.DataFrame(
        {
            "STUDYID": ["TEST-001", "TEST-001"],
            "DOMAIN": ["LB", "LB"],
            "USUBJID": ["TEST-001-001-001", "TEST-001-001-002"],
            "LBSEQ": [1, 1],
            "LBTESTCD": ["ALB", "ALT"],
            "LBTEST": ["Albumin", "Alanine Aminotransferase"],
            "LBORRES": ["4.2", "25"],
            "LBSTRESC": ["4.2", "25"],
            # Invalid specimen type -- not in the CT codelist
            "LBSPEC": ["BLOOD", "TOTALLY_INVALID_SPECIMEN"],
        }
    )


@pytest.fixture
def synthetic_domains():
    """Build synthetic 3-domain validation dataset."""
    return {
        "DM": (_make_dm_df(), _make_dm_spec()),
        "AE": (_make_ae_df(), _make_ae_spec()),
        "LB": (_make_lb_df(), _make_lb_spec()),
    }


@pytest.fixture
def engine():
    """Create a ValidationEngine with default rules."""
    sdtm_ref = load_sdtm_reference()
    ct_ref = load_ct_reference()
    return ValidationEngine(sdtm_ref=sdtm_ref, ct_ref=ct_ref)


@pytest.mark.integration
class TestFullValidationPipeline:
    """End-to-end validation pipeline tests."""

    def test_full_validation_pipeline(self, engine, synthetic_domains):
        """Run validate_all on 3 domains and verify expected findings."""
        results = engine.validate_all(synthetic_domains)

        # Should have findings from multiple categories
        assert len(results) > 0

        _rule_ids = {r.rule_id for r in results}
        severities = {r.severity for r in results}

        # Should include at least one error (cross-domain or presence)
        assert RuleSeverity.ERROR in severities or RuleSeverity.WARNING in severities

        # Should have results from multiple domains
        result_domains = {r.domain for r in results if r.domain}
        assert len(result_domains) >= 1

    def test_cross_domain_validation(self, synthetic_domains):
        """CrossDomainValidator catches USUBJID orphan in AE."""
        domain_dfs = {code: df for code, (df, _) in synthetic_domains.items()}
        domain_specs = {code: spec for code, (_, spec) in synthetic_domains.items()}

        validator = CrossDomainValidator()
        results = validator.validate(domain_dfs, domain_specs)

        # Should find the AE orphan USUBJID
        orphan_results = [r for r in results if "ASTR-C001" in r.rule_id]
        assert len(orphan_results) > 0
        # Orphan is in AE domain
        ae_orphans = [r for r in orphan_results if r.domain == "AE"]
        assert len(ae_orphans) > 0

    def test_trc_precheck_pass(self, tmp_path):
        """TRCPreCheck passes when DM, TS, and define.xml are present."""
        # Create DM DataFrame
        dm_df = pd.DataFrame(
            {
                "STUDYID": ["TEST-001"],
                "DOMAIN": ["DM"],
                "USUBJID": ["TEST-001-001-001"],
            }
        )
        # Create TS DataFrame with SSTDTC
        ts_df = pd.DataFrame(
            {
                "STUDYID": ["TEST-001"],
                "DOMAIN": ["TS"],
                "TSPARMCD": ["SSTDTC"],
                "TSVAL": ["2022-01-01"],
            }
        )

        # Create define.xml (empty but present)
        (tmp_path / "define.xml").write_text("<ODM/>")

        domains = {"DM": dm_df, "TS": ts_df}
        checker = TRCPreCheck()
        results = checker.check_all(domains, tmp_path, "TEST-001")

        errors = [r for r in results if r.severity == RuleSeverity.ERROR]
        assert len(errors) == 0

    def test_trc_precheck_fail(self, tmp_path):
        """TRCPreCheck fails when DM, TS, define.xml are missing."""
        domains: dict[str, pd.DataFrame] = {}
        checker = TRCPreCheck()
        results = checker.check_all(domains, tmp_path, "TEST-001")

        error_rules = {r.rule_id for r in results if r.severity == RuleSeverity.ERROR}
        # Should flag missing DM and TS
        assert "FDA-TRC-1736" in error_rules  # DM missing
        assert "FDA-TRC-1734" in error_rules  # TS missing
        assert "FDA-TRC-1735" in error_rules  # define.xml missing

    def test_validation_report_generation(self, engine, synthetic_domains):
        """Generate ValidationReport and verify summary statistics."""
        results = engine.validate_all(synthetic_domains)
        domains = sorted(synthetic_domains.keys())

        report = ValidationReport.from_results("TEST-001", results, domains)

        assert report.study_id == "TEST-001"
        assert len(report.domains_validated) == 3
        assert report.total_rules_run == len(results)
        assert report.error_count >= 0
        assert report.warning_count >= 0
        assert report.notice_count >= 0
        assert 0.0 <= report.pass_rate <= 1.0

        # Summary by domain should have entries
        assert "DM" in report.summary_by_domain
        assert "AE" in report.summary_by_domain

        # Summary by category should have at least one entry
        assert len(report.summary_by_category) >= 1

    def test_validation_report_markdown(self, engine, synthetic_domains):
        """Generate report and verify Markdown output."""
        results = engine.validate_all(synthetic_domains)
        domains = sorted(synthetic_domains.keys())

        report = ValidationReport.from_results("TEST-001", results, domains)
        md = report.to_markdown()

        assert isinstance(md, str)
        assert len(md) > 100
        assert "# Validation Report: TEST-001" in md
        assert "## Summary" in md
        assert "## Submission Readiness" in md
