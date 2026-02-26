"""Tests for NCI Controlled Terminology reference data lookup."""

import pytest

from astraea.models.controlled_terms import Codelist
from astraea.reference import CTReference, load_ct_reference


@pytest.fixture
def ct() -> CTReference:
    """Load CT reference from default bundled data."""
    return load_ct_reference()


class TestCTReference:
    """Tests for CTReference lookup class."""

    def test_version(self, ct: CTReference) -> None:
        assert ct.version == "2025-09-26"

    def test_ig_version(self, ct: CTReference) -> None:
        assert ct.ig_version == "3.4"

    def test_list_codelists_at_least_10(self, ct: CTReference) -> None:
        codes = ct.list_codelists()
        assert len(codes) >= 10

    def test_lookup_codelist_sex(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66731")
        assert cl is not None
        assert isinstance(cl, Codelist)
        assert cl.name == "Sex"
        assert "M" in cl.terms
        assert "F" in cl.terms
        assert "U" in cl.terms
        assert "UNDIFFERENTIATED" in cl.terms

    def test_lookup_codelist_nonexistent(self, ct: CTReference) -> None:
        assert ct.lookup_codelist("C99999") is None

    def test_validate_term_sex_valid(self, ct: CTReference) -> None:
        assert ct.validate_term("C66731", "M") is True
        assert ct.validate_term("C66731", "F") is True

    def test_validate_term_sex_invalid(self, ct: CTReference) -> None:
        assert ct.validate_term("C66731", "INVALID") is False
        assert ct.validate_term("C66731", "Male") is False  # must be submission value
        assert ct.validate_term("C66731", "m") is False  # case-sensitive

    def test_validate_term_nonexistent_codelist(self, ct: CTReference) -> None:
        assert ct.validate_term("C99999", "M") is False

    def test_is_extensible_sex_false(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66731") is False

    def test_is_extensible_race_false(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66767") is False

    def test_is_extensible_ethnicity_false(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66728") is False

    def test_is_extensible_severity_false(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66734") is False

    def test_is_extensible_route_true(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66769") is True

    def test_is_extensible_unit_true(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66781") is True

    def test_is_extensible_frequency_true(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66770") is True

    def test_is_extensible_country_true(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66742") is True

    def test_is_extensible_nonexistent_returns_false(self, ct: CTReference) -> None:
        assert ct.is_extensible("C99999") is False

    def test_validate_term_extensible_always_true(self, ct: CTReference) -> None:
        """Extensible codelists accept any value."""
        assert ct.validate_term("C66769", "ORAL") is True
        assert ct.validate_term("C66769", "CUSTOM_ROUTE") is True

    def test_get_codelist_for_variable_sex(self, ct: CTReference) -> None:
        cl = ct.get_codelist_for_variable("SEX")
        assert cl is not None
        assert cl.code == "C66731"

    def test_get_codelist_for_variable_case_insensitive(self, ct: CTReference) -> None:
        cl = ct.get_codelist_for_variable("sex")
        assert cl is not None
        assert cl.code == "C66731"

    def test_get_codelist_for_variable_race(self, ct: CTReference) -> None:
        cl = ct.get_codelist_for_variable("RACE")
        assert cl is not None
        assert cl.code == "C66767"

    def test_get_codelist_for_variable_ageu(self, ct: CTReference) -> None:
        cl = ct.get_codelist_for_variable("AGEU")
        assert cl is not None
        assert cl.code == "C66726"

    def test_get_codelist_for_variable_no_codelist(self, ct: CTReference) -> None:
        assert ct.get_codelist_for_variable("AETERM") is None

    def test_race_codelist_terms(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66767")
        assert cl is not None
        assert "WHITE" in cl.terms
        assert "ASIAN" in cl.terms
        assert "BLACK OR AFRICAN AMERICAN" in cl.terms

    def test_ethnicity_codelist_terms(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66728")
        assert cl is not None
        assert "HISPANIC OR LATINO" in cl.terms
        assert "NOT HISPANIC OR LATINO" in cl.terms

    def test_no_yes_response_terms(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66790")
        assert cl is not None
        assert "Y" in cl.terms
        assert "N" in cl.terms
        assert cl.extensible is False
