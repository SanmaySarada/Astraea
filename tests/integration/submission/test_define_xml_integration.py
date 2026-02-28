"""define.xml generation integration tests.

Creates realistic DomainMappingSpec objects and verifies that
generate_define_xml produces valid, well-structured XML with
correct element counts, namespace handling, and OID consistency.
"""

from __future__ import annotations

import pandas as pd
import pytest
from lxml import etree

from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)
from astraea.models.sdtm import CoreDesignation
from astraea.reference import load_ct_reference
from astraea.submission.define_xml import (
    DEFINE_NS,
    ODM_NS,
    XLINK_NS,
    generate_define_xml,
)

# ── Helper ──────────────────────────────────────────────────────────


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
    """Create a VariableMapping with minimal boilerplate."""
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


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def dm_spec() -> DomainMappingSpec:
    """DM spec -- simple, non-repeating domain."""
    mappings = [
        _mapping(
            var="STUDYID",
            label="Study Identifier",
            pattern=MappingPattern.ASSIGN,
            assigned="TEST-001",
            order=1,
            origin=VariableOrigin.ASSIGNED,
        ),
        _mapping(
            var="DOMAIN",
            label="Domain Abbreviation",
            pattern=MappingPattern.ASSIGN,
            assigned="DM",
            order=2,
            origin=VariableOrigin.ASSIGNED,
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
            origin=VariableOrigin.CRF,
        ),
        _mapping(
            var="SEX",
            label="Sex",
            source="SEX",
            order=5,
            codelist="C66731",
            origin=VariableOrigin.CRF,
        ),
        _mapping(
            var="AGE",
            label="Age",
            dtype="Num",
            pattern=MappingPattern.DERIVATION,
            order=6,
            core=CoreDesignation.EXP,
            origin=VariableOrigin.DERIVED,
            computational_method="RFSTDTC - BRTHDTC in years",
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
        required_mapped=4,
        expected_mapped=1,
        high_confidence_count=len(mappings),
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


@pytest.fixture
def lb_spec() -> DomainMappingSpec:
    """LB spec -- Findings domain with TRANSPOSE pattern."""
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
            label="Lab Test Short Name",
            pattern=MappingPattern.TRANSPOSE,
            source="columns",
            order=5,
        ),
        _mapping(
            var="LBTEST",
            label="Lab Test or Examination Name",
            pattern=MappingPattern.TRANSPOSE,
            source="columns",
            order=6,
        ),
        _mapping(
            var="LBORRES",
            label="Result or Finding in Original Units",
            pattern=MappingPattern.TRANSPOSE,
            source="values",
            order=7,
            core=CoreDesignation.EXP,
        ),
        _mapping(
            var="LBSPEC",
            label="Specimen Type",
            source="LBSPEC",
            order=8,
            core=CoreDesignation.EXP,
            codelist="C78734",
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
        required_mapped=4,
        expected_mapped=2,
        high_confidence_count=len(mappings),
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
    )


@pytest.fixture
def lb_data() -> pd.DataFrame:
    """Synthetic LB data for ValueListDef test code extraction."""
    return pd.DataFrame(
        {
            "STUDYID": ["TEST-001"] * 4,
            "DOMAIN": ["LB"] * 4,
            "USUBJID": ["TEST-001-001-001"] * 4,
            "LBSEQ": [1, 2, 3, 4],
            "LBTESTCD": ["ALB", "ALT", "AST", "WBC"],
            "LBTEST": [
                "Albumin",
                "Alanine Aminotransferase",
                "Aspartate Aminotransferase",
                "White Blood Cells",
            ],
            "LBORRES": ["4.2", "25", "18", "5.5"],
            "LBSPEC": ["BLOOD"] * 4,
        }
    )


# ── Tests ───────────────────────────────────────────────────────────


@pytest.mark.integration
class TestDefineXmlGeneration:
    """Integration tests for define.xml generation."""

    def test_define_xml_multi_domain(self, tmp_path, dm_spec, lb_spec, lb_data):
        """Generate define.xml with DM + LB and verify structure."""
        output_path = tmp_path / "define.xml"
        ct_ref = load_ct_reference()

        generate_define_xml(
            specs=[dm_spec, lb_spec],
            ct_ref=ct_ref,
            study_id="TEST-001",
            study_name="Test Clinical Study",
            output_path=output_path,
            generated_dfs={"LB": lb_data},
        )

        assert output_path.exists()

        tree = etree.parse(str(output_path))
        root = tree.getroot()

        # Verify ItemGroupDefs
        igs = root.findall(f".//{{{ODM_NS}}}ItemGroupDef")
        assert len(igs) == 2

        ig_names = {ig.get("Name") for ig in igs}
        assert "DM" in ig_names
        assert "LB" in ig_names

        # Verify ItemDefs
        ids = root.findall(f".//{{{ODM_NS}}}ItemDef")
        total_vars = len(dm_spec.variable_mappings) + len(lb_spec.variable_mappings)
        assert len(ids) == total_vars

        # Verify CodeLists exist for referenced codelists
        cls = root.findall(f".//{{{ODM_NS}}}CodeList")
        assert len(cls) >= 1  # At least C66731 (SEX)

        # Verify MethodDefs for derived variables
        mds = root.findall(f".//{{{ODM_NS}}}MethodDef")
        assert len(mds) >= 2  # USUBJID and AGE derivations

    def test_define_xml_namespaces(self, tmp_path, dm_spec):
        """Verify correct namespace handling in root element."""
        output_path = tmp_path / "define.xml"
        ct_ref = load_ct_reference()

        generate_define_xml(
            specs=[dm_spec],
            ct_ref=ct_ref,
            study_id="TEST-001",
            study_name="Test Study",
            output_path=output_path,
        )

        tree = etree.parse(str(output_path))
        root = tree.getroot()

        # Root should be in ODM namespace
        assert root.tag == f"{{{ODM_NS}}}ODM"

        # nsmap should contain def: and xlink: prefixes
        nsmap = root.nsmap
        assert nsmap.get("def") == DEFINE_NS
        assert nsmap.get("xlink") == XLINK_NS

        # def: namespace elements should resolve
        mdv = root.find(f".//{{{ODM_NS}}}MetaDataVersion")
        assert mdv is not None
        assert mdv.get(f"{{{DEFINE_NS}}}DefineVersion") == "2.0.0"

    def test_define_xml_findings_value_list(self, tmp_path, lb_spec, lb_data):
        """Verify ValueListDef for Findings domain with TRANSPOSE."""
        output_path = tmp_path / "define.xml"
        ct_ref = load_ct_reference()

        generate_define_xml(
            specs=[lb_spec],
            ct_ref=ct_ref,
            study_id="TEST-001",
            study_name="Test Study",
            output_path=output_path,
            generated_dfs={"LB": lb_data},
        )

        tree = etree.parse(str(output_path))
        root = tree.getroot()

        # ValueListDef should be present for LB
        vlds = root.findall(f".//{{{DEFINE_NS}}}ValueListDef")
        assert len(vlds) >= 1

        vld = vlds[0]
        assert "LB" in vld.get("OID", "")

        # Should have ItemRef elements for each test code
        item_refs = vld.findall(f"{{{ODM_NS}}}ItemRef")
        assert len(item_refs) == 4  # ALB, ALT, AST, WBC

        # WhereClauseDef should exist for each test code
        wcs = root.findall(f".//{{{DEFINE_NS}}}WhereClauseDef")
        assert len(wcs) == 4

    def test_define_xml_roundtrip(self, tmp_path, dm_spec, lb_spec):
        """Write define.xml, read back, verify OID consistency."""
        output_path = tmp_path / "define.xml"
        ct_ref = load_ct_reference()

        generate_define_xml(
            specs=[dm_spec, lb_spec],
            ct_ref=ct_ref,
            study_id="TEST-001",
            study_name="Test Study",
            output_path=output_path,
        )

        tree = etree.parse(str(output_path))
        root = tree.getroot()

        # Collect all ItemDef OIDs
        item_def_oids = {id_el.get("OID") for id_el in root.findall(f".//{{{ODM_NS}}}ItemDef")}
        assert len(item_def_oids) > 0

        # Collect all ItemRef ItemOIDs
        item_ref_oids = {
            ir.get("ItemOID")
            for ir in root.findall(f".//{{{ODM_NS}}}ItemRef")
            if ir.getparent().tag == f"{{{ODM_NS}}}ItemGroupDef"
        }
        assert len(item_ref_oids) > 0

        # Every ItemRef should point to an existing ItemDef
        missing_refs = item_ref_oids - item_def_oids
        assert len(missing_refs) == 0, f"ItemRef OIDs without matching ItemDef: {missing_refs}"

        # Collect MethodDef OIDs
        method_oids = {md.get("OID") for md in root.findall(f".//{{{ODM_NS}}}MethodDef")}

        # All MethodOID references should point to existing MethodDefs
        method_refs = {
            ir.get("MethodOID")
            for ir in root.findall(f".//{{{ODM_NS}}}ItemRef")
            if ir.get("MethodOID") is not None
        }
        missing_methods = method_refs - method_oids
        assert len(missing_methods) == 0, (
            f"MethodOID refs without matching MethodDef: {missing_methods}"
        )
