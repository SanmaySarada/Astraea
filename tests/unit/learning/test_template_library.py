"""Tests for the cross-study domain template library.

Verifies template building from DomainMappingSpecs, SQLite persistence,
pattern distribution computation, keyword extraction, and incremental
template updates from new studies.
"""

from __future__ import annotations

import pytest

from astraea.learning.models import StudyMetrics
from astraea.learning.template_library import (
    DomainTemplate,
    TemplateLibrary,
    VariablePattern,
    _extract_keywords,
)
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)
from astraea.models.sdtm import CoreDesignation


def _make_variable_mapping(
    sdtm_variable: str = "AETERM",
    mapping_pattern: MappingPattern = MappingPattern.DIRECT,
    source_variable: str | None = "AETERM",
    source_dataset: str | None = "ae",
    mapping_logic: str = "Direct carry from source ae.AETERM",
    derivation_rule: str | None = None,
    confidence: float = 0.95,
) -> VariableMapping:
    """Create a minimal VariableMapping for testing."""
    return VariableMapping(
        sdtm_variable=sdtm_variable,
        sdtm_label=f"Label for {sdtm_variable}",
        sdtm_data_type="Char",
        core=CoreDesignation.REQ,
        source_dataset=source_dataset,
        source_variable=source_variable,
        source_label=f"SAS label for {source_variable or sdtm_variable}",
        mapping_pattern=mapping_pattern,
        mapping_logic=mapping_logic,
        derivation_rule=derivation_rule,
        confidence=confidence,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="Test rationale",
        origin=VariableOrigin.CRF,
    )


def _make_spec(
    domain: str = "AE",
    study_id: str = "STUDY-001",
    variable_mappings: list[VariableMapping] | None = None,
) -> DomainMappingSpec:
    """Create a minimal DomainMappingSpec for testing."""
    if variable_mappings is None:
        variable_mappings = [
            _make_variable_mapping(
                "STUDYID", MappingPattern.ASSIGN, None, None, "Assign constant study ID"
            ),
            _make_variable_mapping(
                "DOMAIN", MappingPattern.ASSIGN, None, None, "Assign constant domain code"
            ),
            _make_variable_mapping(
                "USUBJID",
                MappingPattern.DERIVATION,
                "Subject",
                "ae",
                "Derive from STUDYID + SITEID + SUBJID",
                derivation_rule="CONCAT(STUDYID, '-', SITEID, '-', SUBJID)",
            ),
            _make_variable_mapping(
                "AETERM",
                MappingPattern.DIRECT,
                "AETERM",
                "ae",
                "Direct carry from source ae.AETERM",
            ),
            _make_variable_mapping(
                "AEDECOD",
                MappingPattern.LOOKUP_RECODE,
                "AETERM",
                "ae",
                "MedDRA preferred term lookup",
            ),
            _make_variable_mapping(
                "AESTDTC", MappingPattern.REFORMAT, "AESTDT", "ae", "Convert SAS date to ISO 8601"
            ),
            _make_variable_mapping(
                "AEENDTC", MappingPattern.REFORMAT, "AEENDT", "ae", "Convert SAS date to ISO 8601"
            ),
            _make_variable_mapping(
                "AESEQ",
                MappingPattern.DERIVATION,
                None,
                None,
                "Sequence number within subject",
                derivation_rule="SEQ_BY(USUBJID)",
            ),
        ]
    total = len(variable_mappings)
    req = sum(1 for v in variable_mappings if v.core == CoreDesignation.REQ)
    return DomainMappingSpec(
        domain=domain,
        domain_label="Adverse Events",
        domain_class="Events",
        structure="One record per adverse event per subject",
        study_id=study_id,
        source_datasets=["ae"],
        variable_mappings=variable_mappings,
        total_variables=total,
        required_mapped=req,
        expected_mapped=0,
        high_confidence_count=total,
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00+00:00",
        model_used="claude-sonnet-4-20250514",
    )


def _make_metrics(
    study_id: str = "STUDY-001",
    domain: str = "AE",
    accuracy_rate: float = 0.80,
) -> StudyMetrics:
    """Create a minimal StudyMetrics for testing."""
    total = 10
    approved = int(total * accuracy_rate)
    return StudyMetrics(
        study_id=study_id,
        domain=domain,
        total_proposed=total,
        approved_unchanged=approved,
        corrected=total - approved,
        rejected=0,
        added_by_reviewer=0,
        accuracy_rate=accuracy_rate,
        correction_rate=1.0 - accuracy_rate,
        completed_at="2026-02-28T00:00:00+00:00",
    )


class TestExtractKeywords:
    """Tests for the _extract_keywords helper."""

    def test_simple_variable_name(self) -> None:
        result = _extract_keywords("AETERM")
        assert result == ["aeterm"]

    def test_underscore_separated(self) -> None:
        result = _extract_keywords("AE_START_DATE")
        assert "ae" in result
        assert "start" in result
        assert "date" in result

    def test_mapping_logic_string(self) -> None:
        result = _extract_keywords("Direct carry from source ae.AETERM")
        assert "direct" in result
        assert "carry" in result
        assert "source" in result  # "source" is domain-meaningful, not a stop word
        assert "ae" in result
        assert "aeterm" in result

    def test_deduplication(self) -> None:
        result = _extract_keywords("ae ae ae")
        assert result == ["ae"]

    def test_filters_short_tokens(self) -> None:
        result = _extract_keywords("a b cc dd")
        # 'a' and 'b' are < 2 chars, filtered out
        assert "cc" in result
        assert "dd" in result
        assert "a" not in result
        assert "b" not in result


class TestBuildTemplate:
    """Tests for TemplateLibrary.build_template."""

    def test_build_from_single_spec(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec = _make_spec()

        template = lib.build_template("AE", [spec])

        assert template.domain == "AE"
        assert template.domain_class == "Events"
        assert template.source_study_ids == ["STUDY-001"]
        assert len(template.variable_patterns) == 8
        lib.close()

    def test_pattern_distribution(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec = _make_spec()

        template = lib.build_template("AE", [spec])

        # 2 ASSIGN, 1 DIRECT, 1 LOOKUP_RECODE, 2 REFORMAT, 2 DERIVATION
        assert template.pattern_distribution["assign"] == 2
        assert template.pattern_distribution["direct"] == 1
        assert template.pattern_distribution["lookup_recode"] == 1
        assert template.pattern_distribution["reformat"] == 2
        assert template.pattern_distribution["derivation"] == 2
        lib.close()

    def test_variable_patterns_typical_pattern(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec = _make_spec()

        template = lib.build_template("AE", [spec])

        patterns_by_var = {vp.sdtm_variable: vp for vp in template.variable_patterns}
        assert patterns_by_var["STUDYID"].typical_pattern == "assign"
        assert patterns_by_var["AETERM"].typical_pattern == "direct"
        assert patterns_by_var["AEDECOD"].typical_pattern == "lookup_recode"
        assert patterns_by_var["USUBJID"].typical_pattern == "derivation"
        lib.close()

    def test_source_keywords_extraction(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec = _make_spec()

        template = lib.build_template("AE", [spec])

        patterns_by_var = {vp.sdtm_variable: vp for vp in template.variable_patterns}
        aeterm_kw = patterns_by_var["AETERM"].typical_source_keywords
        assert "aeterm" in aeterm_kw
        assert "direct" in aeterm_kw
        assert "carry" in aeterm_kw
        lib.close()

    def test_derivation_template_captured(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec = _make_spec()

        template = lib.build_template("AE", [spec])

        patterns_by_var = {vp.sdtm_variable: vp for vp in template.variable_patterns}
        assert patterns_by_var["USUBJID"].derivation_template == (
            "CONCAT(STUDYID, '-', SITEID, '-', SUBJID)"
        )
        assert patterns_by_var["AESEQ"].derivation_template == "SEQ_BY(USUBJID)"
        # Non-derivation variables have no template
        assert patterns_by_var["AETERM"].derivation_template is None
        lib.close()

    def test_accuracy_rate_from_metrics(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec = _make_spec()
        metrics = [_make_metrics(accuracy_rate=0.85)]

        template = lib.build_template("AE", [spec], metrics)

        assert template.accuracy_rate == pytest.approx(0.85)
        lib.close()

    def test_accuracy_rate_zero_without_metrics(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec = _make_spec()

        template = lib.build_template("AE", [spec])

        assert template.accuracy_rate == 0.0
        lib.close()

    def test_accuracy_rate_filters_to_domain(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec = _make_spec()
        metrics = [
            _make_metrics(domain="AE", accuracy_rate=0.90),
            _make_metrics(domain="DM", accuracy_rate=0.50),
        ]

        template = lib.build_template("AE", [spec], metrics)

        # Only AE metrics should be used
        assert template.accuracy_rate == pytest.approx(0.90)
        lib.close()


class TestSaveAndRetrieve:
    """Tests for save_template, get_template, get_all_templates."""

    def test_save_and_get_roundtrip(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec = _make_spec()
        template = lib.build_template("AE", [spec])

        lib.save_template(template)
        retrieved = lib.get_template("AE")

        assert retrieved is not None
        assert retrieved.domain == "AE"
        assert retrieved.domain_class == "Events"
        assert retrieved.source_study_ids == ["STUDY-001"]
        assert retrieved.template_id == template.template_id
        assert len(retrieved.variable_patterns) == 8
        assert retrieved.pattern_distribution == template.pattern_distribution
        lib.close()

    def test_get_template_returns_none_for_missing(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")

        result = lib.get_template("XX")

        assert result is None
        lib.close()

    def test_get_all_templates(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")

        ae_spec = _make_spec(domain="AE")
        dm_mappings = [
            _make_variable_mapping("STUDYID", MappingPattern.ASSIGN, None, None, "Assign study ID"),
            _make_variable_mapping(
                "USUBJID",
                MappingPattern.DERIVATION,
                "Subject",
                "dm",
                "Derive USUBJID",
                "CONCAT(STUDYID, '-', SUBJID)",
            ),
        ]
        dm_spec = _make_spec(domain="DM", variable_mappings=dm_mappings)

        ae_template = lib.build_template("AE", [ae_spec])
        dm_template = lib.build_template("DM", [dm_spec])
        lib.save_template(ae_template)
        lib.save_template(dm_template)

        all_templates = lib.get_all_templates()

        assert len(all_templates) == 2
        domains = [t.domain for t in all_templates]
        assert "AE" in domains
        assert "DM" in domains
        lib.close()

    def test_save_replaces_existing(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec = _make_spec()
        template = lib.build_template("AE", [spec])
        lib.save_template(template)

        # Save again with different template_id (same domain)
        template2 = lib.build_template("AE", [spec])
        lib.save_template(template2)

        all_templates = lib.get_all_templates()
        assert len(all_templates) == 1
        assert all_templates[0].template_id == template2.template_id
        lib.close()


class TestUpdateTemplate:
    """Tests for incremental template updates."""

    def test_update_adds_study_id(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec1 = _make_spec(study_id="STUDY-001")
        template = lib.build_template("AE", [spec1])
        lib.save_template(template)

        spec2 = _make_spec(study_id="STUDY-002")
        updated = lib.update_template("AE", spec2)

        assert "STUDY-001" in updated.source_study_ids
        assert "STUDY-002" in updated.source_study_ids
        lib.close()

    def test_update_merges_pattern_distribution(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec1 = _make_spec(study_id="STUDY-001")
        template = lib.build_template("AE", [spec1])
        lib.save_template(template)

        # spec1 has 2 assign, 1 direct, etc.
        orig_assign = template.pattern_distribution.get("assign", 0)

        spec2 = _make_spec(study_id="STUDY-002")
        updated = lib.update_template("AE", spec2)

        # Pattern counts should increase
        assert updated.pattern_distribution["assign"] > orig_assign
        lib.close()

    def test_update_adds_new_variables(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec1 = _make_spec(study_id="STUDY-001")
        template = lib.build_template("AE", [spec1])
        lib.save_template(template)

        # Create spec2 with a new variable not in spec1
        new_mapping = _make_variable_mapping(
            "AESEV",
            MappingPattern.LOOKUP_RECODE,
            "AESEV",
            "ae",
            "Severity lookup recode",
        )
        spec2 = _make_spec(
            study_id="STUDY-002",
            variable_mappings=[new_mapping],
        )
        updated = lib.update_template("AE", spec2)

        var_names = [vp.sdtm_variable for vp in updated.variable_patterns]
        assert "AESEV" in var_names
        assert "AETERM" in var_names  # original still present
        lib.close()

    def test_update_recalculates_accuracy(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec1 = _make_spec(study_id="STUDY-001")
        metrics1 = _make_metrics(study_id="STUDY-001", accuracy_rate=0.80)
        template = lib.build_template("AE", [spec1], [metrics1])
        lib.save_template(template)

        spec2 = _make_spec(study_id="STUDY-002")
        metrics2 = _make_metrics(study_id="STUDY-002", accuracy_rate=0.90)
        updated = lib.update_template("AE", spec2, metrics2)

        # Weighted average: (0.80 * 1 + 0.90) / 2 = 0.85
        assert updated.accuracy_rate == pytest.approx(0.85)
        lib.close()

    def test_update_creates_if_not_exists(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec = _make_spec(study_id="STUDY-001")

        # No existing template -- should create one
        template = lib.update_template("AE", spec)

        assert template.domain == "AE"
        assert template.source_study_ids == ["STUDY-001"]

        # Verify persisted
        retrieved = lib.get_template("AE")
        assert retrieved is not None
        lib.close()

    def test_update_does_not_duplicate_study_id(self, tmp_path) -> None:
        lib = TemplateLibrary(tmp_path / "test.db")
        spec1 = _make_spec(study_id="STUDY-001")
        template = lib.build_template("AE", [spec1])
        lib.save_template(template)

        # Update with same study_id
        spec2 = _make_spec(study_id="STUDY-001")
        updated = lib.update_template("AE", spec2)

        assert updated.source_study_ids.count("STUDY-001") == 1
        lib.close()


class TestVariablePatternModel:
    """Tests for VariablePattern Pydantic model."""

    def test_minimal_creation(self) -> None:
        vp = VariablePattern(
            sdtm_variable="AETERM",
            typical_pattern="direct",
        )
        assert vp.sdtm_variable == "AETERM"
        assert vp.typical_source_keywords == []
        assert vp.derivation_template is None
        assert vp.common_issues == []

    def test_full_creation(self) -> None:
        vp = VariablePattern(
            sdtm_variable="USUBJID",
            typical_pattern="derivation",
            typical_source_keywords=["subject", "subjid"],
            derivation_template="CONCAT(STUDYID, '-', SUBJID)",
            common_issues=["Missing SITEID component"],
        )
        assert vp.derivation_template is not None
        assert len(vp.common_issues) == 1


class TestDomainTemplateModel:
    """Tests for DomainTemplate Pydantic model."""

    def test_default_factory_fields(self) -> None:
        dt = DomainTemplate(
            domain="AE",
            domain_class="Events",
        )
        assert dt.template_id  # UUID generated
        assert dt.source_study_ids == []
        assert dt.pattern_distribution == {}
        assert dt.variable_patterns == []
        assert dt.accuracy_rate == 0.0
        assert dt.created_at  # timestamp generated
        assert dt.updated_at  # timestamp generated
