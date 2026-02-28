"""Tests for Phase 14 reference data fixes.

Validates C66738 addition, C66789 fix, C66742 expansion,
PE/QS VISITNUM additions, and collision-safe reverse lookup.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from astraea.reference.controlled_terms import CTReference


@pytest.fixture()
def ct() -> CTReference:
    """Create CTReference from production data."""
    return CTReference()


class TestC66738TrialSummaryParameterCode:
    """Validate the C66738 codelist was added correctly."""

    def test_c66738_exists(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66738")
        assert cl is not None
        assert cl.name == "Trial Summary Parameter Code"

    def test_c66738_extensible(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66738") is True

    def test_c66738_has_28_terms(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66738")
        assert cl is not None
        assert len(cl.terms) >= 28

    def test_c66738_maps_to_tsparmcd(self, ct: CTReference) -> None:
        cl = ct.get_codelist_for_variable("TSPARMCD")
        assert cl is not None
        assert cl.code == "C66738"

    def test_c66738_fda_required_terms(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66738")
        assert cl is not None
        required = [
            "SSTDTC", "SENDTC", "SPONSOR", "TITLE", "INDIC",
            "TRT", "SDTMVER", "TTYPE", "STYPE", "RANDOM",
        ]
        for term in required:
            assert term in cl.terms, f"{term} missing from C66738"


class TestC66789Fix:
    """Validate C66789 maps to LBSPCND not LBSPEC."""

    def test_lbspcnd_returns_c66789(self, ct: CTReference) -> None:
        cl = ct.get_codelist_for_variable("LBSPCND")
        assert cl is not None
        assert cl.code == "C66789"

    def test_lbspec_not_c66789(self, ct: CTReference) -> None:
        """LBSPEC should map to C78734 (Specimen Type), not C66789."""
        cl = ct.get_codelist_for_variable("LBSPEC")
        if cl is not None:
            assert cl.code != "C66789"


class TestC66742Expansion:
    """Validate C66742 expanded with additional variable mappings."""

    @pytest.mark.parametrize(
        "variable",
        ["CEOCCUR", "CEPRESP", "LBBLFL", "VSBLFL", "EGBLFL", "DVBLFL", "PEBLFL", "IESTRESC"],
    )
    def test_variable_maps_to_c66742(self, ct: CTReference, variable: str) -> None:
        codelists = ct.get_codelists_for_variable(variable)
        codes = [cl.code for cl in codelists]
        assert "C66742" in codes, f"{variable} does not map to C66742"

    def test_existing_mappings_preserved(self, ct: CTReference) -> None:
        """Original variable mappings should still be present."""
        codelists = ct.get_codelists_for_variable("AESER")
        codes = [cl.code for cl in codelists]
        assert "C66742" in codes


class TestCollisionSafeReverseLookup:
    """Validate that reverse lookup handles multiple codelists per variable."""

    def test_get_codelists_for_variable_returns_list(self, ct: CTReference) -> None:
        result = ct.get_codelists_for_variable("SEX")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_get_codelist_for_variable_returns_first(self, ct: CTReference) -> None:
        """Backward-compatible single-result method still works."""
        cl = ct.get_codelist_for_variable("SEX")
        assert cl is not None
        assert cl.code == "C66731"

    def test_nonexistent_variable_returns_none(self, ct: CTReference) -> None:
        assert ct.get_codelist_for_variable("NONEXISTENT") is None

    def test_nonexistent_variable_returns_empty_list(self, ct: CTReference) -> None:
        assert ct.get_codelists_for_variable("NONEXISTENT") == []

    def test_collision_warning_logged(self, ct: CTReference) -> None:
        """When a variable maps to multiple codelists, a warning should be logged."""
        # DTHFL maps to C66742 (No Yes Response) -- add a second mapping to simulate collision
        ct._variable_to_codelist["DTHFL"] = ["C66742", "C66731"]
        with patch("astraea.reference.controlled_terms.logger") as mock_logger:
            result = ct.get_codelist_for_variable("DTHFL")
            assert result is not None
            mock_logger.warning.assert_called_once()

    def test_collision_returns_all(self, ct: CTReference) -> None:
        """get_codelists_for_variable returns all matching codelists."""
        ct._variable_to_codelist["DTHFL"] = ["C66742", "C66731"]
        results = ct.get_codelists_for_variable("DTHFL")
        assert len(results) == 2
        codes = {cl.code for cl in results}
        assert codes == {"C66742", "C66731"}


class TestDomainsVisitnum:
    """Validate PE and QS domains have VISITNUM and VISIT."""

    @pytest.fixture()
    def domains(self) -> dict:
        path = Path(__file__).resolve().parent.parent.parent.parent / "src" / "astraea" / "data" / "sdtm_ig" / "domains.json"
        with open(path) as f:
            return json.load(f)

    @pytest.mark.parametrize("domain", ["PE", "QS"])
    def test_visitnum_present(self, domains: dict, domain: str) -> None:
        var_names = [v["name"] for v in domains[domain]["variables"]]
        assert "VISITNUM" in var_names, f"VISITNUM missing from {domain}"

    @pytest.mark.parametrize("domain", ["PE", "QS"])
    def test_visit_present(self, domains: dict, domain: str) -> None:
        var_names = [v["name"] for v in domains[domain]["variables"]]
        assert "VISIT" in var_names, f"VISIT missing from {domain}"

    @pytest.mark.parametrize("domain", ["PE", "QS"])
    def test_visitnum_is_numeric(self, domains: dict, domain: str) -> None:
        for v in domains[domain]["variables"]:
            if v["name"] == "VISITNUM":
                assert v["data_type"] == "Num"
                break
