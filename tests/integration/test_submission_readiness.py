"""Integration tests for Phase 15 submission readiness features.

Verifies that key Phase 15 deliverables work together:
SPLIT pattern, LC domain, cSDRG content, FDA business rules, SDTM detection.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from astraea.models.mapping import (
    ConfidenceLevel,
    CoreDesignation,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)


def _make_mapping(
    variable: str,
    label: str,
    pattern: MappingPattern = MappingPattern.DIRECT,
    source_var: str | None = None,
    derivation_rule: str | None = None,
    assigned_value: str | None = None,
    data_type: str = "Char",
) -> VariableMapping:
    """Helper to create a VariableMapping with required fields."""
    return VariableMapping(
        sdtm_variable=variable,
        sdtm_label=label,
        sdtm_data_type=data_type,
        core=CoreDesignation.REQ,
        source_dataset="test.sas7bdat",
        source_variable=source_var,
        mapping_pattern=pattern,
        mapping_logic="Test mapping",
        derivation_rule=derivation_rule,
        assigned_value=assigned_value,
        confidence=0.95,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="Test",
        notes="",
        order=0,
        origin=VariableOrigin.CRF,
    )


def _make_spec(
    domain: str, domain_label: str, mappings: list[VariableMapping],
) -> DomainMappingSpec:
    """Helper to create a DomainMappingSpec with required fields."""
    return DomainMappingSpec(
        domain=domain,
        domain_label=domain_label,
        domain_class="Events",
        structure="One record per event per subject",
        study_id="TEST-001",
        source_datasets=["test.sas7bdat"],
        variable_mappings=mappings,
        total_variables=len(mappings),
        required_mapped=len(mappings),
        expected_mapped=0,
        high_confidence_count=len(mappings),
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


class TestSplitPatternIntegration:
    """Test SPLIT pattern handler with DELIMITER_PART rule."""

    def test_split_delimiter_part(self) -> None:
        """SPLIT pattern with DELIMITER_PART correctly splits a delimited column."""
        from astraea.execution.pattern_handlers import handle_split

        df = pd.DataFrame({
            "SITEID_SUBJID": ["SITE01-SUBJ001", "SITE02-SUBJ002", "SITE03-SUBJ003"],
        })

        mapping = _make_mapping(
            variable="SITEID",
            label="Site Identifier",
            pattern=MappingPattern.SPLIT,
            source_var="SITEID_SUBJID",
            derivation_rule="DELIMITER_PART(SITEID_SUBJID, -, 0)",
        )

        result = handle_split(df, mapping)
        assert list(result) == ["SITE01", "SITE02", "SITE03"]


class TestLCDomainIntegration:
    """Test LC domain generation from LB data."""

    def test_generate_lc_from_lb(self) -> None:
        """LC domain is correctly generated from LB with column renaming."""
        from astraea.execution.lc_domain import generate_lc_from_lb

        lb_df = pd.DataFrame({
            "STUDYID": ["S1", "S1"],
            "DOMAIN": ["LB", "LB"],
            "USUBJID": ["S1-001", "S1-002"],
            "LBSEQ": [1, 2],
            "LBTESTCD": ["ALB", "ALP"],
            "LBTEST": ["Albumin", "Alkaline Phosphatase"],
            "LBORRES": ["4.2", "85"],
            "LBORRESU": ["g/dL", "U/L"],
            "LBSTRESC": ["4.2", "85"],
            "LBSTRESN": [4.2, 85.0],
        })

        lc_df, warnings = generate_lc_from_lb(lb_df, "TEST-001")

        # Verify domain set to LC
        assert all(lc_df["DOMAIN"] == "LC")

        # Verify LB columns renamed to LC
        assert "LCTESTCD" in lc_df.columns
        assert "LCTEST" in lc_df.columns
        assert "LCORRES" in lc_df.columns

        # Verify LB columns removed
        assert "LBTESTCD" not in lc_df.columns

        # Verify row count preserved
        assert len(lc_df) == len(lb_df)


class TestCSDRGContentIntegration:
    """Test cSDRG generation with populated sections."""

    def test_csdrg_with_ts_params(self, tmp_path: Path) -> None:
        """cSDRG Section 2 is populated (not placeholder) when ts_params provided."""
        from astraea.submission.csdrg import generate_csdrg
        from astraea.validation.report import ValidationReport

        mappings = [
            _make_mapping(
                "STUDYID", "Study Identifier",
                MappingPattern.ASSIGN, assigned_value="S1",
            ),
            _make_mapping(
                "DOMAIN", "Domain Abbreviation",
                MappingPattern.ASSIGN, assigned_value="AE",
            ),
            _make_mapping("AETERM", "Reported Term for AE", source_var="AETERM"),
        ]
        spec = _make_spec("AE", "Adverse Events", mappings)

        validation_report = ValidationReport.from_results(
            study_id="TEST-001",
            results=[],
            domains=["AE"],
        )

        ts_params = {
            "TITLE": "A Phase 3 Study of Drug X",
            "TPHASE": "PHASE III TRIAL",
            "INDIC": "Hereditary Angioedema",
        }

        output_path = tmp_path / "csdrg.md"
        result_path = generate_csdrg(
            specs=[spec],
            validation_report=validation_report,
            study_id="TEST-001",
            output_path=output_path,
            ts_params=ts_params,
        )

        content = result_path.read_text()

        # Section 2 should be populated, not placeholder
        assert "Placeholder" not in content or "Study Description" in content
        # ts_params title should appear
        assert "Phase 3 Study of Drug X" in content

        # Section 6 should have content (even if empty issues)
        assert "Known Data Issues" in content or "Data Issues" in content

        # Section 8 should mention SUPPQUAL
        assert "SUPPQUAL" in content or "Supplemental" in content


class TestFDABusinessRuleCount:
    """Test that sufficient FDA business rules are registered."""

    def test_fda_business_rules_count(self) -> None:
        """At least 20 FDA business rules are registered."""
        from astraea.validation.rules.fda_business import get_fda_business_rules

        rules = get_fda_business_rules()
        assert len(rules) >= 20, f"Expected >= 20 FDA business rules, got {len(rules)}"


class TestPreMappedSDTMDetection:
    """Test detection of pre-mapped SDTM datasets."""

    def test_detect_sdtm_findings_format(self) -> None:
        """Dataset with SDTM Findings columns is detected as pre-mapped."""
        from astraea.models.profiling import DatasetProfile, VariableProfile
        from astraea.profiling.profiler import detect_sdtm_format

        variables = [
            VariableProfile(
                name="LBTESTCD", dtype="character", sas_format="",
                label="Lab Test Short Name", n_total=100, n_unique=5,
                n_missing=0, missing_pct=0.0, sample_values=["ALB", "ALP", "ALT"],
            ),
            VariableProfile(
                name="LBTEST", dtype="character", sas_format="",
                label="Lab Test Name", n_total=100, n_unique=5,
                n_missing=0, missing_pct=0.0, sample_values=["Albumin"],
            ),
            VariableProfile(
                name="LBORRES", dtype="character", sas_format="",
                label="Result", n_total=100, n_unique=10,
                n_missing=0, missing_pct=0.0, sample_values=["4.2"],
            ),
            VariableProfile(
                name="LBORRESU", dtype="character", sas_format="",
                label="Unit", n_total=100, n_unique=3,
                n_missing=0, missing_pct=0.0, sample_values=["g/dL"],
            ),
            VariableProfile(
                name="DOMAIN", dtype="character", sas_format="",
                label="Domain", n_total=100, n_unique=1,
                n_missing=0, missing_pct=0.0, sample_values=["LB"],
            ),
        ]

        profile = DatasetProfile(
            filename="lb.sas7bdat",
            row_count=100,
            col_count=5,
            variables=variables,
        )

        assert detect_sdtm_format(profile) is True

    def test_non_sdtm_not_detected(self) -> None:
        """Regular raw dataset is not detected as pre-mapped SDTM."""
        from astraea.models.profiling import DatasetProfile, VariableProfile
        from astraea.profiling.profiler import detect_sdtm_format

        variables = [
            VariableProfile(
                name="SUBJID", dtype="character", sas_format="",
                label="Subject ID", n_total=50, n_unique=10,
                n_missing=0, missing_pct=0.0, sample_values=["001"],
            ),
            VariableProfile(
                name="VISIT_DATE", dtype="numeric", sas_format="DATE9.",
                label="Visit Date", n_total=50, n_unique=5,
                n_missing=0, missing_pct=0.0, sample_values=["2022-01-01"],
            ),
        ]

        profile = DatasetProfile(
            filename="raw_data.sas7bdat",
            row_count=50,
            col_count=2,
            variables=variables,
        )

        assert detect_sdtm_format(profile) is False
