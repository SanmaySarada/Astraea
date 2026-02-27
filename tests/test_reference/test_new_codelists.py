"""Tests for newly added CT codelists: C66785 (Laterality) and C66789 (Specimen Condition)."""

from __future__ import annotations

import pytest

from astraea.reference import CTReference


@pytest.fixture()
def ct() -> CTReference:
    """CTReference instance with default bundled data."""
    return CTReference()


class TestLateralityCodelist:
    """Tests for C66785 (Laterality) codelist."""

    def test_laterality_codelist_exists(self, ct: CTReference) -> None:
        """C66785 Laterality codelist loads successfully."""
        cl = ct.lookup_codelist("C66785")
        assert cl is not None
        assert cl.name == "Laterality"

    def test_laterality_terms(self, ct: CTReference) -> None:
        """Laterality has LEFT, RIGHT, BILATERAL terms."""
        cl = ct.lookup_codelist("C66785")
        assert cl is not None
        assert "LEFT" in cl.terms
        assert "RIGHT" in cl.terms
        assert "BILATERAL" in cl.terms
        assert len(cl.terms) == 3

    def test_laterality_non_extensible(self, ct: CTReference) -> None:
        """Laterality is non-extensible -- unknown terms are invalid."""
        assert ct.validate_term("C66785", "LEFT") is True
        assert ct.validate_term("C66785", "RIGHT") is True
        assert ct.validate_term("C66785", "BILATERAL") is True
        assert ct.validate_term("C66785", "UNILATERAL") is False

    def test_laterality_not_extensible_flag(self, ct: CTReference) -> None:
        """C66785 extensible flag is False."""
        assert ct.is_extensible("C66785") is False


class TestSpecimenConditionCodelist:
    """Tests for C66789 (Specimen Condition) codelist."""

    def test_specimen_condition_codelist_exists(self, ct: CTReference) -> None:
        """C66789 Specimen Condition codelist loads successfully."""
        cl = ct.lookup_codelist("C66789")
        assert cl is not None
        assert cl.name == "Specimen Condition"

    def test_specimen_condition_terms(self, ct: CTReference) -> None:
        """Specimen Condition has the expected terms."""
        cl = ct.lookup_codelist("C66789")
        assert cl is not None
        assert "HEMOLYZED" in cl.terms
        assert "LIPEMIC" in cl.terms
        assert "ICTERIC" in cl.terms
        assert "CLOTTED" in cl.terms
        assert "INSUFFICIENT QUANTITY" in cl.terms
        assert "NOT APPLICABLE" in cl.terms
        assert len(cl.terms) == 6

    def test_specimen_condition_extensible(self, ct: CTReference) -> None:
        """Specimen Condition is extensible -- unknown terms are valid."""
        assert ct.validate_term("C66789", "HEMOLYZED") is True
        assert ct.validate_term("C66789", "FROZEN") is True  # Extensible allows anything

    def test_specimen_condition_extensible_flag(self, ct: CTReference) -> None:
        """C66789 extensible flag is True."""
        assert ct.is_extensible("C66789") is True
