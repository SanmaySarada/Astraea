"""Tests for VariableOrigin enum and origin/computational_method fields on mapping models."""

from __future__ import annotations

import pytest

from astraea.models.mapping import (
    ConfidenceLevel,
    MappingPattern,
    VariableMapping,
    VariableMappingProposal,
    VariableOrigin,
)
from astraea.models.sdtm import CoreDesignation


class TestVariableOriginEnum:
    """Tests for the VariableOrigin StrEnum."""

    def test_variable_origin_enum_values(self) -> None:
        """All 6 define.xml 2.0 origin types exist."""
        assert VariableOrigin.CRF == "CRF"
        assert VariableOrigin.DERIVED == "Derived"
        assert VariableOrigin.ASSIGNED == "Assigned"
        assert VariableOrigin.PROTOCOL == "Protocol"
        assert VariableOrigin.EDT == "eDT"
        assert VariableOrigin.PREDECESSOR == "Predecessor"

    def test_variable_origin_has_six_members(self) -> None:
        """Exactly 6 origin types defined."""
        assert len(VariableOrigin) == 6


class TestVariableMappingOriginFields:
    """Tests for origin and computational_method on VariableMapping."""

    @pytest.fixture()
    def base_mapping_kwargs(self) -> dict:
        """Minimal kwargs for constructing a VariableMapping."""
        return {
            "sdtm_variable": "AGE",
            "sdtm_label": "Age",
            "sdtm_data_type": "Num",
            "core": CoreDesignation.EXP,
            "mapping_pattern": MappingPattern.DERIVATION,
            "mapping_logic": "Age derived from BRTHDAT and RFSTDTC",
            "confidence": 0.9,
            "confidence_level": ConfidenceLevel.HIGH,
            "confidence_rationale": "Standard derivation",
        }

    def test_variable_mapping_with_origin(self, base_mapping_kwargs: dict) -> None:
        """VariableMapping accepts origin=CRF."""
        m = VariableMapping(**base_mapping_kwargs, origin=VariableOrigin.CRF)
        assert m.origin == VariableOrigin.CRF

    def test_variable_mapping_origin_default_none(self, base_mapping_kwargs: dict) -> None:
        """VariableMapping origin defaults to None when not specified."""
        m = VariableMapping(**base_mapping_kwargs)
        assert m.origin is None

    def test_variable_mapping_with_computational_method(self, base_mapping_kwargs: dict) -> None:
        """VariableMapping accepts computational_method string."""
        method = "AGE = floor((RFSTDTC - BRTHDTC) / 365.25)"
        m = VariableMapping(
            **base_mapping_kwargs,
            origin=VariableOrigin.DERIVED,
            computational_method=method,
        )
        assert m.computational_method == method

    def test_variable_mapping_computational_method_default_none(
        self, base_mapping_kwargs: dict
    ) -> None:
        """computational_method defaults to None."""
        m = VariableMapping(**base_mapping_kwargs)
        assert m.computational_method is None

    def test_variable_mapping_serialization(self, base_mapping_kwargs: dict) -> None:
        """model_dump() includes origin and computational_method."""
        m = VariableMapping(
            **base_mapping_kwargs,
            origin=VariableOrigin.DERIVED,
            computational_method="AGE = floor((RFSTDTC - BRTHDTC) / 365.25)",
        )
        data = m.model_dump()
        assert "origin" in data
        assert data["origin"] == "Derived"
        assert "computational_method" in data
        assert "RFSTDTC" in data["computational_method"]

    def test_variable_mapping_origin_from_string(self, base_mapping_kwargs: dict) -> None:
        """VariableMapping origin can be set from a string value."""
        m = VariableMapping(**base_mapping_kwargs, origin="Assigned")
        assert m.origin == VariableOrigin.ASSIGNED


class TestVariableMappingProposalOrigin:
    """Tests for origin field on VariableMappingProposal."""

    def test_proposal_with_origin(self) -> None:
        """VariableMappingProposal accepts origin string."""
        p = VariableMappingProposal(
            sdtm_variable="AGE",
            mapping_pattern=MappingPattern.DERIVATION,
            mapping_logic="Derived from BRTHDAT",
            confidence=0.85,
            rationale="Standard derivation",
            origin="Derived",
        )
        assert p.origin == "Derived"

    def test_proposal_origin_default_none(self) -> None:
        """VariableMappingProposal origin defaults to None."""
        p = VariableMappingProposal(
            sdtm_variable="AETERM",
            mapping_pattern=MappingPattern.DIRECT,
            mapping_logic="Direct carry",
            confidence=0.95,
            rationale="Exact match",
        )
        assert p.origin is None
