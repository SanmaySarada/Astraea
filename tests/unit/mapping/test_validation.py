"""Tests for mapping validation and enrichment.

Tests validate_and_enrich and check_required_coverage using real bundled
SDTM-IG and CT reference data for realistic validation behavior.
"""

from __future__ import annotations

import pytest

from astraea.mapping.validation import check_required_coverage, validate_and_enrich
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingProposal,
    MappingPattern,
    VariableMapping,
    VariableMappingProposal,
)
from astraea.models.sdtm import CoreDesignation
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference


@pytest.fixture()
def sdtm_ref() -> SDTMReference:
    """Real SDTM-IG reference from bundled data."""
    return SDTMReference()


@pytest.fixture()
def ct_ref() -> CTReference:
    """Real CT reference from bundled data."""
    return CTReference()


def _make_proposal(
    variable_proposals: list[VariableMappingProposal],
) -> DomainMappingProposal:
    """Helper to build a DomainMappingProposal."""
    return DomainMappingProposal(
        domain="DM",
        variable_proposals=variable_proposals,
        unmapped_source_variables=[],
        suppqual_candidates=[],
        mapping_notes="Test proposal",
    )


class TestValidateAndEnrich:
    """Tests for validate_and_enrich function."""

    def test_valid_dm_proposal(self, sdtm_ref: SDTMReference, ct_ref: CTReference) -> None:
        """A valid DM proposal enriches correctly with labels and core."""
        proposal = _make_proposal(
            [
                VariableMappingProposal(
                    sdtm_variable="STUDYID",
                    source_dataset=None,
                    source_variable=None,
                    mapping_pattern=MappingPattern.ASSIGN,
                    mapping_logic="Assign constant study ID",
                    assigned_value="PHA022121-C301",
                    confidence=0.99,
                    rationale="Standard constant assignment",
                ),
                VariableMappingProposal(
                    sdtm_variable="AGE",
                    source_dataset="dm.sas7bdat",
                    source_variable="AGE",
                    mapping_pattern=MappingPattern.DIRECT,
                    mapping_logic="Direct carry from source AGE",
                    confidence=0.95,
                    rationale="Same variable name and content",
                ),
            ]
        )

        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        mappings, issues = validate_and_enrich(proposal, domain_spec, ct_ref)

        assert len(mappings) == 2
        assert len(issues) == 0

        # STUDYID should be enriched with IG data
        studyid = mappings[0]
        assert studyid.sdtm_variable == "STUDYID"
        assert studyid.sdtm_label == "Study Identifier"
        assert studyid.sdtm_data_type == "Char"
        assert studyid.core == CoreDesignation.REQ

        # AGE should be enriched
        age = mappings[1]
        assert age.sdtm_variable == "AGE"
        assert age.sdtm_data_type == "Num"
        assert age.core == CoreDesignation.EXP

    def test_ct_validation_valid_term(self, sdtm_ref: SDTMReference, ct_ref: CTReference) -> None:
        """Valid CT term on non-extensible codelist passes without issue."""
        proposal = _make_proposal(
            [
                VariableMappingProposal(
                    sdtm_variable="SEX",
                    source_dataset="dm.sas7bdat",
                    source_variable="SEX_STD",
                    mapping_pattern=MappingPattern.RENAME,
                    mapping_logic="Rename SEX_STD to SEX",
                    codelist_code="C66731",
                    assigned_value="F",
                    confidence=0.90,
                    rationale="SEX_STD contains CT submission values",
                ),
            ]
        )

        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        mappings, issues = validate_and_enrich(proposal, domain_spec, ct_ref)

        assert len(mappings) == 1
        assert len(issues) == 0
        assert mappings[0].codelist_name is not None
        assert "Sex" in mappings[0].codelist_name or "SEX" in mappings[0].codelist_name.upper()

    def test_ct_validation_invalid_term_nonextensible(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Invalid CT term on non-extensible codelist flags issue, caps confidence."""
        proposal = _make_proposal(
            [
                VariableMappingProposal(
                    sdtm_variable="SEX",
                    source_dataset="dm.sas7bdat",
                    source_variable="SEX",
                    mapping_pattern=MappingPattern.RENAME,
                    mapping_logic="Map display value",
                    codelist_code="C66731",
                    assigned_value="Female",  # Not a valid submission value
                    confidence=0.90,
                    rationale="Using display value incorrectly",
                ),
            ]
        )

        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        mappings, issues = validate_and_enrich(proposal, domain_spec, ct_ref)

        assert len(issues) >= 1
        assert any("Female" in issue for issue in issues)
        # Confidence should be capped at 0.4
        assert mappings[0].confidence <= 0.4

    def test_ct_codelist_not_found(self, sdtm_ref: SDTMReference, ct_ref: CTReference) -> None:
        """Non-existent codelist code flags issue and caps confidence."""
        proposal = _make_proposal(
            [
                VariableMappingProposal(
                    sdtm_variable="SEX",
                    source_dataset="dm.sas7bdat",
                    source_variable="SEX_STD",
                    mapping_pattern=MappingPattern.RENAME,
                    mapping_logic="Rename with bad codelist",
                    codelist_code="C99999",  # Does not exist
                    confidence=0.85,
                    rationale="Testing missing codelist",
                ),
            ]
        )

        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        mappings, issues = validate_and_enrich(proposal, domain_spec, ct_ref)

        assert len(issues) >= 1
        assert any("C99999" in issue for issue in issues)
        assert mappings[0].confidence <= 0.4
        assert mappings[0].codelist_name is None

    def test_confidence_boost_lookup_recode(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Successful CT validation on lookup_recode boosts confidence by 0.05."""
        proposal = _make_proposal(
            [
                VariableMappingProposal(
                    sdtm_variable="ETHNIC",
                    source_dataset="dm.sas7bdat",
                    source_variable="ETHNIC_STD",
                    mapping_pattern=MappingPattern.LOOKUP_RECODE,
                    mapping_logic="Map through ethnicity codelist",
                    codelist_code="C66790",
                    confidence=0.85,
                    rationale="ETHNIC_STD contains coded values",
                ),
            ]
        )

        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        mappings, issues = validate_and_enrich(proposal, domain_spec, ct_ref)

        # Should get +0.05 boost: 0.85 -> 0.90
        assert mappings[0].confidence == pytest.approx(0.90, abs=0.001)
        assert mappings[0].confidence_level == ConfidenceLevel.HIGH

    def test_unknown_variable_confidence_capped(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Variable not in SDTM-IG gets confidence capped at 0.3."""
        proposal = _make_proposal(
            [
                VariableMappingProposal(
                    sdtm_variable="FAKEVAR",
                    source_dataset="dm.sas7bdat",
                    source_variable="SOMETHING",
                    mapping_pattern=MappingPattern.DIRECT,
                    mapping_logic="Non-existent variable",
                    confidence=0.90,
                    rationale="Testing unknown variable",
                ),
            ]
        )

        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        mappings, issues = validate_and_enrich(proposal, domain_spec, ct_ref)

        assert len(issues) >= 1
        assert any("FAKEVAR" in issue for issue in issues)
        assert mappings[0].confidence <= 0.3
        assert mappings[0].confidence_level == ConfidenceLevel.LOW

    def test_order_enrichment_from_domain_spec(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Enrichment populates order from VariableSpec.order."""
        proposal = _make_proposal(
            [
                VariableMappingProposal(
                    sdtm_variable="STUDYID",
                    source_dataset=None,
                    source_variable=None,
                    mapping_pattern=MappingPattern.ASSIGN,
                    mapping_logic="Assign constant study ID",
                    assigned_value="PHA022121-C301",
                    confidence=0.99,
                    rationale="Standard constant assignment",
                ),
            ]
        )

        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        mappings, _issues = validate_and_enrich(proposal, domain_spec, ct_ref)

        # STUDYID should have a positive order from the IG spec
        assert mappings[0].order > 0

        # Verify it matches the actual spec order
        studyid_spec = next(v for v in domain_spec.variables if v.name == "STUDYID")
        assert mappings[0].order == studyid_spec.order

    def test_order_defaults_to_zero_for_unknown_variable(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """Unknown variable (not in domain spec) gets order=0."""
        proposal = _make_proposal(
            [
                VariableMappingProposal(
                    sdtm_variable="FAKEVAR",
                    source_dataset="dm.sas7bdat",
                    source_variable="SOMETHING",
                    mapping_pattern=MappingPattern.DIRECT,
                    mapping_logic="Non-existent variable",
                    confidence=0.90,
                    rationale="Testing unknown variable",
                ),
            ]
        )

        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        mappings, _issues = validate_and_enrich(proposal, domain_spec, ct_ref)
        assert mappings[0].order == 0

    def test_lookup_recode_nonextensible_codelist_warning(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """LOOKUP_RECODE with non-extensible codelist (no assigned_value) produces warning."""
        # C66731 is Sex -- non-extensible
        proposal = _make_proposal(
            [
                VariableMappingProposal(
                    sdtm_variable="SEX",
                    source_dataset="dm.sas7bdat",
                    source_variable="SEX_RAW",
                    mapping_pattern=MappingPattern.LOOKUP_RECODE,
                    mapping_logic="Recode raw sex values via CT",
                    codelist_code="C66731",
                    assigned_value=None,
                    confidence=0.85,
                    rationale="Lookup recode for sex",
                ),
            ]
        )

        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        mappings, issues = validate_and_enrich(proposal, domain_spec, ct_ref)

        # Should have warning about non-extensible codelist with lookup_recode
        assert any(
            "non-extensible" in i and "lookup_recode" in i and "runtime" in i for i in issues
        ), f"Expected non-extensible lookup_recode warning, got: {issues}"

        # Confidence should NOT be penalized (still gets +0.05 boost)
        assert mappings[0].confidence == pytest.approx(0.90, abs=0.001)

    def test_lookup_recode_extensible_codelist_no_warning(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """LOOKUP_RECODE with extensible codelist should NOT produce the non-extensible warning."""
        # C74457 is Race -- extensible
        proposal = _make_proposal(
            [
                VariableMappingProposal(
                    sdtm_variable="RACE",
                    source_dataset="dm.sas7bdat",
                    source_variable="RACE_RAW",
                    mapping_pattern=MappingPattern.LOOKUP_RECODE,
                    mapping_logic="Recode raw race values via CT",
                    codelist_code="C74457",
                    assigned_value=None,
                    confidence=0.85,
                    rationale="Lookup recode for race",
                ),
            ]
        )

        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        mappings, issues = validate_and_enrich(proposal, domain_spec, ct_ref)

        # Should NOT have the non-extensible warning
        assert not any("non-extensible" in i and "lookup_recode" in i for i in issues), (
            f"Should not warn for extensible codelist, got: {issues}"
        )

    def test_lookup_recode_nonextensible_with_assigned_value_uses_existing_check(
        self, sdtm_ref: SDTMReference, ct_ref: CTReference
    ) -> None:
        """LOOKUP_RECODE with non-extensible codelist AND assigned_value uses existing check."""
        # C66731 is Sex -- non-extensible; "Female" is NOT a valid submission value
        proposal = _make_proposal(
            [
                VariableMappingProposal(
                    sdtm_variable="SEX",
                    source_dataset="dm.sas7bdat",
                    source_variable="SEX_RAW",
                    mapping_pattern=MappingPattern.LOOKUP_RECODE,
                    mapping_logic="Recode raw sex values via CT",
                    codelist_code="C66731",
                    assigned_value="Female",  # Invalid submission value
                    confidence=0.85,
                    rationale="Lookup recode for sex",
                ),
            ]
        )

        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        mappings, issues = validate_and_enrich(proposal, domain_spec, ct_ref)

        # Should have the existing "value not in codelist" error, NOT the new warning
        assert any("Female" in i and "not in non-extensible" in i for i in issues)
        # Should NOT have the new lookup_recode warning (assigned_value is present)
        assert not any("runtime" in i and "lookup_recode" in i for i in issues)


class TestCheckRequiredCoverage:
    """Tests for check_required_coverage function."""

    def test_missing_studyid(self, sdtm_ref: SDTMReference) -> None:
        """Missing STUDYID (a Required variable) is flagged."""
        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        # Empty mapping list -- all required vars missing
        missing = check_required_coverage([], domain_spec)

        assert "STUDYID" in missing
        assert "USUBJID" in missing
        assert "DOMAIN" in missing

    def test_all_required_present(self, sdtm_ref: SDTMReference, ct_ref: CTReference) -> None:
        """All Required variables present returns empty list."""
        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        # Create mappings for all Required variables
        required_vars = [v.name for v in domain_spec.variables if v.core == CoreDesignation.REQ]
        mappings = [
            VariableMapping(
                sdtm_variable=name,
                sdtm_label=name,
                sdtm_data_type="Char",
                core=CoreDesignation.REQ,
                mapping_pattern=MappingPattern.ASSIGN,
                mapping_logic="Test",
                confidence=0.95,
                confidence_level=ConfidenceLevel.HIGH,
                confidence_rationale="Test",
            )
            for name in required_vars
        ]

        missing = check_required_coverage(mappings, domain_spec)
        assert missing == []

    def test_partial_coverage(self, sdtm_ref: SDTMReference) -> None:
        """Partial coverage returns only the missing required variables."""
        domain_spec = sdtm_ref.get_domain_spec("DM")
        assert domain_spec is not None

        # Provide only STUDYID and DOMAIN
        mappings = [
            VariableMapping(
                sdtm_variable="STUDYID",
                sdtm_label="Study Identifier",
                sdtm_data_type="Char",
                core=CoreDesignation.REQ,
                mapping_pattern=MappingPattern.ASSIGN,
                mapping_logic="Test",
                confidence=0.95,
                confidence_level=ConfidenceLevel.HIGH,
                confidence_rationale="Test",
            ),
            VariableMapping(
                sdtm_variable="DOMAIN",
                sdtm_label="Domain Abbreviation",
                sdtm_data_type="Char",
                core=CoreDesignation.REQ,
                mapping_pattern=MappingPattern.ASSIGN,
                mapping_logic="Test",
                confidence=0.95,
                confidence_level=ConfidenceLevel.HIGH,
                confidence_rationale="Test",
            ),
        ]

        missing = check_required_coverage(mappings, domain_spec)

        # STUDYID and DOMAIN covered; USUBJID, SUBJID, SITEID, SEX, COUNTRY missing
        assert "STUDYID" not in missing
        assert "DOMAIN" not in missing
        assert "USUBJID" in missing
