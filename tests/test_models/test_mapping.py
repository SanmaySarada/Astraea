"""Unit tests for mapping specification Pydantic models."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingProposal,
    DomainMappingSpec,
    MappingPattern,
    StudyMetadata,
    VariableMapping,
    VariableMappingProposal,
    confidence_level_from_score,
)
from astraea.models.sdtm import CoreDesignation

# ---------------------------------------------------------------------------
# MappingPattern enum
# ---------------------------------------------------------------------------


class TestMappingPattern:
    """Tests for the MappingPattern enum."""

    def test_all_nine_values_exist(self) -> None:
        """All 9 mapping patterns must be defined."""
        expected = {
            "ASSIGN",
            "DIRECT",
            "RENAME",
            "REFORMAT",
            "SPLIT",
            "COMBINE",
            "DERIVATION",
            "LOOKUP_RECODE",
            "TRANSPOSE",
        }
        actual = {m.name for m in MappingPattern}
        assert actual == expected

    def test_string_values_lowercase(self) -> None:
        """String values should be lowercase."""
        assert MappingPattern.ASSIGN == "assign"
        assert MappingPattern.DIRECT == "direct"
        assert MappingPattern.RENAME == "rename"
        assert MappingPattern.REFORMAT == "reformat"
        assert MappingPattern.SPLIT == "split"
        assert MappingPattern.COMBINE == "combine"
        assert MappingPattern.DERIVATION == "derivation"
        assert MappingPattern.LOOKUP_RECODE == "lookup_recode"
        assert MappingPattern.TRANSPOSE == "transpose"

    def test_enum_count(self) -> None:
        """Exactly 9 mapping patterns."""
        assert len(MappingPattern) == 9


# ---------------------------------------------------------------------------
# ConfidenceLevel enum
# ---------------------------------------------------------------------------


class TestConfidenceLevel:
    """Tests for the ConfidenceLevel enum."""

    def test_all_three_values_exist(self) -> None:
        """All 3 confidence levels must be defined."""
        expected = {"HIGH", "MEDIUM", "LOW"}
        actual = {c.name for c in ConfidenceLevel}
        assert actual == expected

    def test_string_values(self) -> None:
        """String values should be lowercase."""
        assert ConfidenceLevel.HIGH == "high"
        assert ConfidenceLevel.MEDIUM == "medium"
        assert ConfidenceLevel.LOW == "low"


# ---------------------------------------------------------------------------
# confidence_level_from_score
# ---------------------------------------------------------------------------


class TestConfidenceLevelFromScore:
    """Tests for the confidence_level_from_score helper function."""

    def test_high_at_boundary(self) -> None:
        """Score of exactly 0.85 should be HIGH."""
        assert confidence_level_from_score(0.85) == ConfidenceLevel.HIGH

    def test_high_above_boundary(self) -> None:
        """Score of 1.0 should be HIGH."""
        assert confidence_level_from_score(1.0) == ConfidenceLevel.HIGH

    def test_medium_just_below_high(self) -> None:
        """Score of 0.84 should be MEDIUM."""
        assert confidence_level_from_score(0.84) == ConfidenceLevel.MEDIUM

    def test_medium_at_boundary(self) -> None:
        """Score of exactly 0.60 should be MEDIUM."""
        assert confidence_level_from_score(0.60) == ConfidenceLevel.MEDIUM

    def test_low_just_below_medium(self) -> None:
        """Score of 0.59 should be LOW."""
        assert confidence_level_from_score(0.59) == ConfidenceLevel.LOW

    def test_low_at_zero(self) -> None:
        """Score of 0.0 should be LOW."""
        assert confidence_level_from_score(0.0) == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# VariableMappingProposal
# ---------------------------------------------------------------------------


class TestVariableMappingProposal:
    """Tests for the VariableMappingProposal model."""

    def test_valid_construction(self) -> None:
        """Construct a valid proposal with all required fields."""
        proposal = VariableMappingProposal(
            sdtm_variable="AETERM",
            source_dataset="ae.sas7bdat",
            source_variable="AETERM",
            mapping_pattern=MappingPattern.DIRECT,
            mapping_logic="Direct carry from source AETERM",
            confidence=0.95,
            rationale="Exact variable name match",
        )
        assert proposal.sdtm_variable == "AETERM"
        assert proposal.mapping_pattern == MappingPattern.DIRECT
        assert proposal.confidence == 0.95
        assert proposal.derivation_rule is None
        assert proposal.assigned_value is None
        assert proposal.codelist_code is None

    def test_assign_pattern(self) -> None:
        """ASSIGN pattern with constant value and no source."""
        proposal = VariableMappingProposal(
            sdtm_variable="STUDYID",
            mapping_pattern=MappingPattern.ASSIGN,
            mapping_logic="Assign constant study identifier",
            assigned_value="PHA022121-C301",
            confidence=1.0,
            rationale="Study ID is a constant",
        )
        assert proposal.source_dataset is None
        assert proposal.source_variable is None
        assert proposal.assigned_value == "PHA022121-C301"

    def test_confidence_rejects_above_one(self) -> None:
        """Confidence > 1.0 should be rejected."""
        with pytest.raises(ValidationError, match="less than or equal to 1"):
            VariableMappingProposal(
                sdtm_variable="AETERM",
                mapping_pattern=MappingPattern.DIRECT,
                mapping_logic="test",
                confidence=1.1,
                rationale="test",
            )

    def test_confidence_rejects_below_zero(self) -> None:
        """Confidence < 0.0 should be rejected."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            VariableMappingProposal(
                sdtm_variable="AETERM",
                mapping_pattern=MappingPattern.DIRECT,
                mapping_logic="test",
                confidence=-0.1,
                rationale="test",
            )

    def test_derivation_with_rule(self) -> None:
        """DERIVATION pattern with derivation_rule set."""
        proposal = VariableMappingProposal(
            sdtm_variable="AGE",
            source_dataset="dm.sas7bdat",
            source_variable="BRTHDAT",
            mapping_pattern=MappingPattern.DERIVATION,
            mapping_logic="Calculate age from birth date and reference start date",
            derivation_rule="floor((RFSTDTC - BRTHDAT) / 365.25)",
            confidence=0.80,
            rationale="Standard age derivation",
        )
        assert proposal.derivation_rule is not None


# ---------------------------------------------------------------------------
# DomainMappingProposal
# ---------------------------------------------------------------------------


class TestDomainMappingProposal:
    """Tests for the DomainMappingProposal model."""

    def test_valid_construction(self) -> None:
        """Construct a valid domain proposal with variable list."""
        proposal = DomainMappingProposal(
            domain="AE",
            variable_proposals=[
                VariableMappingProposal(
                    sdtm_variable="STUDYID",
                    mapping_pattern=MappingPattern.ASSIGN,
                    mapping_logic="Assign study ID",
                    assigned_value="PHA022121-C301",
                    confidence=1.0,
                    rationale="Constant",
                ),
                VariableMappingProposal(
                    sdtm_variable="AETERM",
                    source_dataset="ae.sas7bdat",
                    source_variable="AETERM",
                    mapping_pattern=MappingPattern.DIRECT,
                    mapping_logic="Direct carry",
                    confidence=0.95,
                    rationale="Name match",
                ),
            ],
            unmapped_source_variables=["CUSTOM_VAR1"],
            suppqual_candidates=["CUSTOM_VAR2"],
            mapping_notes="Standard AE mapping",
        )
        assert proposal.domain == "AE"
        assert len(proposal.variable_proposals) == 2
        assert len(proposal.unmapped_source_variables) == 1
        assert len(proposal.suppqual_candidates) == 1

    def test_empty_defaults(self) -> None:
        """Default lists should be empty."""
        proposal = DomainMappingProposal(domain="DM")
        assert proposal.variable_proposals == []
        assert proposal.unmapped_source_variables == []
        assert proposal.suppqual_candidates == []
        assert proposal.mapping_notes == ""


# ---------------------------------------------------------------------------
# VariableMapping (enriched)
# ---------------------------------------------------------------------------


class TestVariableMapping:
    """Tests for the enriched VariableMapping model."""

    def test_valid_construction(self) -> None:
        """Construct a fully populated variable mapping."""
        mapping = VariableMapping(
            sdtm_variable="AETERM",
            sdtm_label="Reported Term for the Adverse Event",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            source_dataset="ae.sas7bdat",
            source_variable="AETERM",
            source_label="Adverse Event Term",
            mapping_pattern=MappingPattern.DIRECT,
            mapping_logic="Direct carry from source AETERM",
            codelist_code=None,
            codelist_name=None,
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Exact variable name and label match",
        )
        assert mapping.sdtm_variable == "AETERM"
        assert mapping.core == CoreDesignation.REQ
        assert mapping.sdtm_data_type == "Char"
        assert mapping.confidence_level == ConfidenceLevel.HIGH
        assert mapping.notes == ""

    def test_core_uses_enum(self) -> None:
        """Core field must use CoreDesignation enum values."""
        mapping = VariableMapping(
            sdtm_variable="DOMAIN",
            sdtm_label="Domain Abbreviation",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            mapping_pattern=MappingPattern.ASSIGN,
            mapping_logic="Assign domain code",
            assigned_value="AE",
            confidence=1.0,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Constant assignment",
        )
        assert mapping.core == CoreDesignation.REQ
        assert mapping.core.value == "Req"

    def test_order_and_length_defaults(self) -> None:
        """VariableMapping defaults: order=0, length=None."""
        mapping = VariableMapping(
            sdtm_variable="AETERM",
            sdtm_label="Reported Term for the Adverse Event",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            mapping_pattern=MappingPattern.DIRECT,
            mapping_logic="Direct carry",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Test",
        )
        assert mapping.order == 0
        assert mapping.length is None

    def test_order_and_length_explicit(self) -> None:
        """VariableMapping accepts explicit order and length values."""
        mapping = VariableMapping(
            sdtm_variable="AETERM",
            sdtm_label="Reported Term for the Adverse Event",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            mapping_pattern=MappingPattern.DIRECT,
            mapping_logic="Direct carry",
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_rationale="Test",
            order=5,
            length=200,
        )
        assert mapping.order == 5
        assert mapping.length == 200

    def test_order_negative_rejected(self) -> None:
        """order < 0 should be rejected by ge=0 constraint."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            VariableMapping(
                sdtm_variable="AETERM",
                sdtm_label="Test",
                sdtm_data_type="Char",
                core=CoreDesignation.REQ,
                mapping_pattern=MappingPattern.DIRECT,
                mapping_logic="test",
                confidence=0.5,
                confidence_level=ConfidenceLevel.LOW,
                confidence_rationale="test",
                order=-1,
            )

    def test_order_length_json_roundtrip(self) -> None:
        """order and length survive JSON round-trip."""
        mapping = VariableMapping(
            sdtm_variable="AETERM",
            sdtm_label="Test",
            sdtm_data_type="Char",
            core=CoreDesignation.REQ,
            mapping_pattern=MappingPattern.DIRECT,
            mapping_logic="test",
            confidence=0.5,
            confidence_level=ConfidenceLevel.LOW,
            confidence_rationale="test",
            order=7,
            length=100,
        )
        json_str = mapping.model_dump_json()
        restored = VariableMapping.model_validate_json(json_str)
        assert restored.order == 7
        assert restored.length == 100

    def test_data_type_literal(self) -> None:
        """sdtm_data_type must be Char or Num."""
        with pytest.raises(ValidationError, match="sdtm_data_type"):
            VariableMapping(
                sdtm_variable="TEST",
                sdtm_label="Test",
                sdtm_data_type="Integer",  # type: ignore[arg-type]
                core=CoreDesignation.PERM,
                mapping_pattern=MappingPattern.DIRECT,
                mapping_logic="test",
                confidence=0.5,
                confidence_level=ConfidenceLevel.LOW,
                confidence_rationale="test",
            )


# ---------------------------------------------------------------------------
# DomainMappingSpec
# ---------------------------------------------------------------------------


class TestDomainMappingSpec:
    """Tests for the DomainMappingSpec model."""

    def test_valid_construction(self) -> None:
        """Construct a valid domain mapping spec with summary counts."""
        spec = DomainMappingSpec(
            domain="DM",
            domain_label="Demographics",
            domain_class="Special-Purpose",
            structure="One record per subject",
            study_id="PHA022121-C301",
            source_datasets=["dm.sas7bdat"],
            variable_mappings=[],
            total_variables=20,
            required_mapped=5,
            expected_mapped=10,
            high_confidence_count=15,
            medium_confidence_count=3,
            low_confidence_count=2,
            mapping_timestamp="2026-02-27T10:00:00Z",
            model_used="claude-sonnet-4-20250514",
        )
        assert spec.domain == "DM"
        assert spec.total_variables == 20
        assert spec.cross_domain_sources == []
        assert spec.unmapped_source_variables == []
        assert spec.suppqual_candidates == []

    def test_missing_required_variables_default(self) -> None:
        """missing_required_variables defaults to empty list."""
        spec = DomainMappingSpec(
            domain="DM",
            domain_label="Demographics",
            domain_class="Special-Purpose",
            structure="One record per subject",
            study_id="PHA022121-C301",
            source_datasets=["dm.sas7bdat"],
            variable_mappings=[],
            total_variables=0,
            required_mapped=0,
            expected_mapped=0,
            high_confidence_count=0,
            medium_confidence_count=0,
            low_confidence_count=0,
            mapping_timestamp="2026-02-27T10:00:00Z",
            model_used="claude-sonnet-4-20250514",
        )
        assert spec.missing_required_variables == []

    def test_missing_required_variables_explicit(self) -> None:
        """Explicit missing_required_variables serializes correctly."""
        spec = DomainMappingSpec(
            domain="DM",
            domain_label="Demographics",
            domain_class="Special-Purpose",
            structure="One record per subject",
            study_id="PHA022121-C301",
            source_datasets=["dm.sas7bdat"],
            variable_mappings=[],
            total_variables=0,
            required_mapped=0,
            expected_mapped=0,
            high_confidence_count=0,
            medium_confidence_count=0,
            low_confidence_count=0,
            mapping_timestamp="2026-02-27T10:00:00Z",
            model_used="claude-sonnet-4-20250514",
            missing_required_variables=["STUDYID", "DOMAIN"],
        )
        assert spec.missing_required_variables == ["STUDYID", "DOMAIN"]

        # JSON round-trip
        restored = DomainMappingSpec.model_validate_json(spec.model_dump_json())
        assert restored.missing_required_variables == ["STUDYID", "DOMAIN"]

    def test_summary_counts_non_negative(self) -> None:
        """Summary count fields must be >= 0."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            DomainMappingSpec(
                domain="AE",
                domain_label="Adverse Events",
                domain_class="Events",
                structure="One record per AE per subject",
                study_id="TEST",
                total_variables=-1,
                required_mapped=0,
                expected_mapped=0,
                high_confidence_count=0,
                medium_confidence_count=0,
                low_confidence_count=0,
                mapping_timestamp="2026-02-27T10:00:00Z",
                model_used="test",
            )


# ---------------------------------------------------------------------------
# StudyMetadata
# ---------------------------------------------------------------------------


class TestStudyMetadata:
    """Tests for the StudyMetadata model."""

    def test_valid_construction_with_defaults(self) -> None:
        """Construct with only required field; defaults populate."""
        meta = StudyMetadata(study_id="PHA022121-C301")
        assert meta.study_id == "PHA022121-C301"
        assert meta.site_id_variable == "SiteNumber"
        assert meta.subject_id_variable == "Subject"
        assert meta.study_env_site_variable == "StudyEnvSiteNumber"

    def test_override_defaults(self) -> None:
        """Override default variable names."""
        meta = StudyMetadata(
            study_id="STUDY-001",
            site_id_variable="SITEID",
            subject_id_variable="SUBJID",
            study_env_site_variable="ENVSITE",
        )
        assert meta.site_id_variable == "SITEID"
        assert meta.subject_id_variable == "SUBJID"
        assert meta.study_env_site_variable == "ENVSITE"


# ---------------------------------------------------------------------------
# JSON round-trip (critical for LLM tool use)
# ---------------------------------------------------------------------------


class TestJSONRoundTrip:
    """Test JSON serialization/deserialization for LLM tool use compatibility."""

    def test_domain_mapping_proposal_round_trip(self) -> None:
        """DomainMappingProposal must survive JSON round-trip."""
        original = DomainMappingProposal(
            domain="AE",
            variable_proposals=[
                VariableMappingProposal(
                    sdtm_variable="STUDYID",
                    mapping_pattern=MappingPattern.ASSIGN,
                    mapping_logic="Assign study ID",
                    assigned_value="PHA022121-C301",
                    confidence=1.0,
                    rationale="Constant",
                ),
                VariableMappingProposal(
                    sdtm_variable="AETERM",
                    source_dataset="ae.sas7bdat",
                    source_variable="AETERM",
                    mapping_pattern=MappingPattern.DIRECT,
                    mapping_logic="Direct carry",
                    confidence=0.95,
                    rationale="Name match",
                ),
            ],
            unmapped_source_variables=["EXTRA_COL"],
            suppqual_candidates=["AEMOD"],
            mapping_notes="Standard mapping",
        )
        json_str = original.model_dump_json()
        restored = DomainMappingProposal.model_validate_json(json_str)
        assert restored.domain == original.domain
        assert len(restored.variable_proposals) == len(original.variable_proposals)
        assert (
            restored.variable_proposals[0].sdtm_variable
            == original.variable_proposals[0].sdtm_variable
        )
        assert (
            restored.variable_proposals[1].confidence
            == original.variable_proposals[1].confidence
        )
        assert restored.unmapped_source_variables == original.unmapped_source_variables
        assert restored.suppqual_candidates == original.suppqual_candidates
        # Full equality via model_dump
        assert original.model_dump() == restored.model_dump()

    def test_variable_mapping_proposal_round_trip(self) -> None:
        """VariableMappingProposal round-trip through JSON."""
        original = VariableMappingProposal(
            sdtm_variable="AESTDTC",
            source_dataset="ae.sas7bdat",
            source_variable="AESTDT",
            mapping_pattern=MappingPattern.REFORMAT,
            mapping_logic="Convert SAS datetime to ISO 8601",
            derivation_rule="sas_datetime_to_iso(AESTDT)",
            codelist_code=None,
            confidence=0.88,
            rationale="Known date variable with SAS datetime format",
        )
        json_str = original.model_dump_json()
        restored = VariableMappingProposal.model_validate_json(json_str)
        assert original.model_dump() == restored.model_dump()


# ---------------------------------------------------------------------------
# JSON schema generation (for LLM tool definitions)
# ---------------------------------------------------------------------------


class TestJSONSchema:
    """Test JSON schema generation for Claude tool definitions."""

    def test_domain_mapping_proposal_schema(self) -> None:
        """DomainMappingProposal.model_json_schema() produces valid schema."""
        schema = DomainMappingProposal.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "domain" in schema["properties"]
        assert "variable_proposals" in schema["properties"]
        # Schema should be JSON-serializable
        json_str = json.dumps(schema)
        assert len(json_str) > 0

    def test_variable_mapping_proposal_schema(self) -> None:
        """VariableMappingProposal schema has all fields."""
        schema = VariableMappingProposal.model_json_schema()
        props = schema["properties"]
        expected_fields = {
            "sdtm_variable",
            "source_dataset",
            "source_variable",
            "mapping_pattern",
            "mapping_logic",
            "derivation_rule",
            "assigned_value",
            "codelist_code",
            "confidence",
            "rationale",
        }
        assert expected_fields.issubset(set(props.keys()))

    def test_mapping_pattern_in_schema(self) -> None:
        """MappingPattern enum values should appear in the schema."""
        schema = DomainMappingProposal.model_json_schema()
        # The schema should reference MappingPattern somewhere in $defs
        schema_str = json.dumps(schema)
        assert "assign" in schema_str
        assert "transpose" in schema_str
        assert "lookup_recode" in schema_str
