"""Tests for define.xml 2.0 generator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
from lxml import etree

from astraea.models.controlled_terms import Codelist, CodelistTerm
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)
from astraea.models.sdtm import CoreDesignation
from astraea.submission.define_xml import (
    DEFINE_NS,
    ODM_NS,
    XLINK_NS,
    generate_define_xml,
)

# ── Namespace map for XPath ──────────────────────────────────────────
NS = {"odm": ODM_NS, "def": DEFINE_NS, "xlink": XLINK_NS}

STUDY_ID = "TEST-001"
STUDY_NAME = "Test Study"


# ── Helper factories ─────────────────────────────────────────────────


def _make_vm(
    name: str,
    label: str,
    dtype: str = "Char",
    core: CoreDesignation = CoreDesignation.REQ,
    pattern: MappingPattern = MappingPattern.ASSIGN,
    *,
    codelist_code: str | None = None,
    origin: VariableOrigin | None = None,
    computational_method: str | None = None,
    notes: str = "",
    source_variable: str | None = None,
    length: int | None = None,
) -> VariableMapping:
    """Create a VariableMapping with sensible defaults."""
    return VariableMapping(
        sdtm_variable=name,
        sdtm_label=label,
        sdtm_data_type=dtype,
        core=core,
        mapping_pattern=pattern,
        mapping_logic="test logic",
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="test",
        codelist_code=codelist_code,
        origin=origin,
        computational_method=computational_method,
        notes=notes,
        source_variable=source_variable,
        length=length,
    )


def _make_spec(
    domain: str = "DM",
    label: str = "Demographics",
    domain_class: str = "Special-Purpose",
    structure: str = "One record per subject",
    mappings: list[VariableMapping] | None = None,
    suppqual_candidates: list[str] | None = None,
) -> DomainMappingSpec:
    """Create a DomainMappingSpec with sensible defaults."""
    vms = mappings or [
        _make_vm("STUDYID", "Study Identifier"),
        _make_vm("DOMAIN", "Domain Abbreviation"),
        _make_vm("USUBJID", "Unique Subject Identifier"),
    ]
    return DomainMappingSpec(
        domain=domain,
        domain_label=label,
        domain_class=domain_class,
        structure=structure,
        study_id=STUDY_ID,
        variable_mappings=vms,
        total_variables=len(vms),
        required_mapped=sum(1 for v in vms if v.core == CoreDesignation.REQ),
        expected_mapped=sum(1 for v in vms if v.core == CoreDesignation.EXP),
        high_confidence_count=len(vms),
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test",
        suppqual_candidates=suppqual_candidates or [],
    )


def _mock_ct_ref() -> MagicMock:
    """Create a mock CTReference that returns None for all lookups."""
    ct = MagicMock()
    ct.lookup_codelist.return_value = None
    return ct


def _mock_ct_ref_with_sex() -> MagicMock:
    """Create a mock CTReference with SEX codelist (C66731)."""
    ct = MagicMock()
    sex_cl = Codelist(
        code="C66731",
        name="Sex",
        extensible=False,
        variable_mappings=["SEX"],
        terms={
            "M": CodelistTerm(submission_value="M", nci_preferred_term="Male", definition="Male"),
            "F": CodelistTerm(
                submission_value="F", nci_preferred_term="Female", definition="Female"
            ),
        },
    )

    def lookup(code: str) -> Codelist | None:
        if code == "C66731":
            return sex_cl
        return None

    ct.lookup_codelist.side_effect = lookup
    return ct


def _parse(path: Path) -> etree._ElementTree:
    """Parse a generated define.xml file."""
    return etree.parse(str(path))  # noqa: S320


# ── Tests ────────────────────────────────────────────────────────────


def test_basic_structure(tmp_path: Path) -> None:
    """define.xml has ODM root, Study, MetaDataVersion, ItemGroupDef, ItemDefs."""
    out = tmp_path / "define.xml"
    spec = _make_spec()
    generate_define_xml([spec], _mock_ct_ref(), STUDY_ID, STUDY_NAME, out)

    tree = _parse(out)
    root = tree.getroot()

    # ODM root
    assert root.tag == f"{{{ODM_NS}}}ODM"
    assert root.get("FileType") == "Snapshot"
    assert root.get("ODMVersion") == "1.3.2"

    # Study
    studies = root.findall("odm:Study", NS)
    assert len(studies) == 1

    # MetaDataVersion
    mdv = root.findall(".//odm:MetaDataVersion", NS)
    assert len(mdv) == 1
    assert mdv[0].get(f"{{{DEFINE_NS}}}DefineVersion") == "2.0.0"

    # 1 ItemGroupDef (DM)
    igs = root.findall(".//odm:ItemGroupDef", NS)
    assert len(igs) == 1

    # 3 ItemDefs (STUDYID, DOMAIN, USUBJID)
    ids = root.findall(".//odm:ItemDef", NS)
    assert len(ids) == 3


def test_item_group_attributes(tmp_path: Path) -> None:
    """ItemGroupDef has correct OID, Name, Repeating, structure, class attributes."""
    out = tmp_path / "define.xml"
    spec = _make_spec()
    generate_define_xml([spec], _mock_ct_ref(), STUDY_ID, STUDY_NAME, out)

    tree = _parse(out)
    ig = tree.getroot().find(".//odm:ItemGroupDef", NS)
    assert ig is not None

    assert ig.get("OID") == "IG.DM"
    assert ig.get("Name") == "DM"
    assert ig.get("Repeating") == "No"  # DM is non-repeating
    assert ig.get("SASDatasetName") == "DM"
    assert ig.get("Purpose") == "Tabulation"
    assert ig.get(f"{{{DEFINE_NS}}}Structure") == "One record per subject"
    assert ig.get(f"{{{DEFINE_NS}}}Class") == "Special-Purpose"
    assert ig.get(f"{{{DEFINE_NS}}}ArchiveLocationID") == "LF.DM"


def test_item_def_attributes(tmp_path: Path) -> None:
    """ItemDef has correct OID, Name, DataType, Description, Origin."""
    out = tmp_path / "define.xml"
    vms = [
        _make_vm("STUDYID", "Study Identifier", origin=VariableOrigin.ASSIGNED),
        _make_vm("AGE", "Age", dtype="Num", core=CoreDesignation.EXP, length=8),
    ]
    spec = _make_spec(mappings=vms)
    generate_define_xml([spec], _mock_ct_ref(), STUDY_ID, STUDY_NAME, out)

    tree = _parse(out)
    items = tree.getroot().findall(".//odm:ItemDef", NS)
    assert len(items) == 2

    # STUDYID -- Char type
    studyid = items[0]
    assert studyid.get("OID") == "IT.DM.STUDYID"
    assert studyid.get("Name") == "STUDYID"
    assert studyid.get("DataType") == "text"
    assert studyid.get("SASFieldName") == "STUDYID"

    # Check Description
    desc = studyid.find("odm:Description/odm:TranslatedText", NS)
    assert desc is not None
    assert desc.text == "Study Identifier"

    # Check Origin
    origin_el = studyid.find("def:Origin", NS)
    assert origin_el is not None
    assert origin_el.get("Type") == "Assigned"

    # AGE -- Num type
    age = items[1]
    assert age.get("DataType") == "float"
    assert age.get("Length") == "8"


def test_codelist_generation(tmp_path: Path) -> None:
    """CodeList element generated for referenced codelist with CodeListItems."""
    out = tmp_path / "define.xml"
    vms = [
        _make_vm(
            "SEX",
            "Sex",
            codelist_code="C66731",
            core=CoreDesignation.EXP,
            pattern=MappingPattern.LOOKUP_RECODE,
        ),
    ]
    spec = _make_spec(mappings=vms)
    ct = _mock_ct_ref_with_sex()
    generate_define_xml([spec], ct, STUDY_ID, STUDY_NAME, out)

    tree = _parse(out)
    root = tree.getroot()

    # CodeList element
    cls = root.findall(".//odm:CodeList", NS)
    assert len(cls) == 1
    cl = cls[0]
    assert cl.get("OID") == "CL.C66731"
    assert cl.get("Name") == "Sex"
    assert cl.get(f"{{{DEFINE_NS}}}Extensible") == "No"

    # CodeListItems
    items = cl.findall("odm:CodeListItem", NS)
    assert len(items) == 2
    coded_values = {it.get("CodedValue") for it in items}
    assert coded_values == {"M", "F"}

    # ItemDef should reference the CodeList
    item_def = root.find(".//odm:ItemDef", NS)
    assert item_def is not None
    cl_ref = item_def.find("odm:CodeListRef", NS)
    assert cl_ref is not None
    assert cl_ref.get("CodeListOID") == "CL.C66731"


def test_method_def(tmp_path: Path) -> None:
    """MethodDef generated for derived variables with Description and FormalExpression."""
    out = tmp_path / "define.xml"
    vms = [
        _make_vm(
            "AGE",
            "Age",
            dtype="Num",
            core=CoreDesignation.EXP,
            pattern=MappingPattern.DERIVATION,
            computational_method="AGE = floor((RFSTDTC - BRTHDTC) / 365.25)",
        ),
    ]
    spec = _make_spec(mappings=vms)
    generate_define_xml([spec], _mock_ct_ref(), STUDY_ID, STUDY_NAME, out)

    tree = _parse(out)
    root = tree.getroot()

    # MethodDef
    methods = root.findall(".//odm:MethodDef", NS)
    assert len(methods) == 1
    md = methods[0]
    assert md.get("OID") == "MT.DM.AGE"
    assert md.get("Type") == "Computation"

    # Description
    desc = md.find("odm:Description/odm:TranslatedText", NS)
    assert desc is not None
    assert "AGE = floor" in desc.text

    # FormalExpression
    fe = md.find("odm:FormalExpression", NS)
    assert fe is not None
    assert fe.get("Context") == "Python"
    assert "AGE = floor" in fe.text

    # ItemRef should reference the MethodDef
    ir = root.find(".//odm:ItemGroupDef/odm:ItemRef", NS)
    assert ir is not None
    assert ir.get("MethodOID") == "MT.DM.AGE"


def test_comment_def_nonstandard(tmp_path: Path) -> None:
    """CommentDef generated for non-standard variables with def:CommentOID reference."""
    out = tmp_path / "define.xml"
    vms = [
        _make_vm(
            "STUDYID",
            "Study Identifier",
        ),
        _make_vm(
            "XFIELD",
            "Extra Field",
            core=CoreDesignation.PERM,
            notes="Non-standard variable added for sponsor requirements",
        ),
    ]
    spec = _make_spec(mappings=vms)
    generate_define_xml([spec], _mock_ct_ref(), STUDY_ID, STUDY_NAME, out)

    tree = _parse(out)
    root = tree.getroot()

    # CommentDef
    comments = root.findall(".//odm:CommentDef", NS)
    assert len(comments) == 1
    cd = comments[0]
    assert cd.get("OID") == "COM.DM.XFIELD"

    desc = cd.find("odm:Description/odm:TranslatedText", NS)
    assert desc is not None
    assert "Non-standard variable" in desc.text

    # ItemRef should reference CommentOID
    item_refs = root.findall(".//odm:ItemGroupDef/odm:ItemRef", NS)
    xfield_ref = [ir for ir in item_refs if ir.get("ItemOID") == "IT.DM.XFIELD"]
    assert len(xfield_ref) == 1
    assert xfield_ref[0].get(f"{{{DEFINE_NS}}}CommentOID") == "COM.DM.XFIELD"


def test_comment_def_suppqual(tmp_path: Path) -> None:
    """CommentDef generated for SUPPQUAL candidates with appropriate description."""
    out = tmp_path / "define.xml"
    vms = [
        _make_vm("STUDYID", "Study Identifier"),
        _make_vm(
            "AESSION",
            "AE Session",
            core=CoreDesignation.PERM,
            source_variable="AESESSION",
        ),
    ]
    spec = _make_spec(
        domain="AE",
        label="Adverse Events",
        domain_class="Events",
        mappings=vms,
        suppqual_candidates=["AESSION"],
    )
    generate_define_xml([spec], _mock_ct_ref(), STUDY_ID, STUDY_NAME, out)

    tree = _parse(out)
    root = tree.getroot()

    # CommentDef
    comments = root.findall(".//odm:CommentDef", NS)
    assert len(comments) == 1
    cd = comments[0]
    assert cd.get("OID") == "COM.AE.AESSION"

    desc = cd.find("odm:Description/odm:TranslatedText", NS)
    assert desc is not None
    assert "Candidate for SUPPQUAL" in desc.text
    assert "AESESSION" in desc.text

    # ItemRef should reference CommentOID
    item_refs = root.findall(".//odm:ItemGroupDef/odm:ItemRef", NS)
    aession_ref = [ir for ir in item_refs if ir.get("ItemOID") == "IT.AE.AESSION"]
    assert len(aession_ref) == 1
    assert aession_ref[0].get(f"{{{DEFINE_NS}}}CommentOID") == "COM.AE.AESSION"


def test_multiple_domains(tmp_path: Path) -> None:
    """Multiple domains produce separate ItemGroupDefs with no duplicate OIDs."""
    out = tmp_path / "define.xml"
    dm = _make_spec()
    ae_vms = [
        _make_vm("STUDYID", "Study Identifier"),
        _make_vm("DOMAIN", "Domain Abbreviation"),
        _make_vm("USUBJID", "Unique Subject Identifier"),
        _make_vm("AETERM", "Reported Term for the Adverse Event"),
    ]
    ae = _make_spec(
        domain="AE",
        label="Adverse Events",
        domain_class="Events",
        structure="One record per adverse event per subject",
        mappings=ae_vms,
    )
    generate_define_xml([dm, ae], _mock_ct_ref(), STUDY_ID, STUDY_NAME, out)

    tree = _parse(out)
    root = tree.getroot()

    # 2 ItemGroupDefs
    igs = root.findall(".//odm:ItemGroupDef", NS)
    assert len(igs) == 2

    # AE should be Repeating=Yes
    ae_ig = [ig for ig in igs if ig.get("Name") == "AE"][0]
    assert ae_ig.get("Repeating") == "Yes"

    # Total ItemDefs: 3 (DM) + 4 (AE) = 7
    ids = root.findall(".//odm:ItemDef", NS)
    assert len(ids) == 7

    # No duplicate OIDs
    oids = [it.get("OID") for it in ids]
    assert len(oids) == len(set(oids))


def test_findings_value_list(tmp_path: Path) -> None:
    """ValueListDef generated for Findings domains with TRANSPOSE pattern."""
    out = tmp_path / "define.xml"
    vms = [
        _make_vm("STUDYID", "Study Identifier"),
        _make_vm(
            "LBTESTCD",
            "Lab Test Code",
            pattern=MappingPattern.TRANSPOSE,
        ),
        _make_vm(
            "LBORRES",
            "Result",
            pattern=MappingPattern.TRANSPOSE,
        ),
    ]
    spec = _make_spec(
        domain="LB",
        label="Laboratory Test Results",
        domain_class="Findings",
        structure="One record per test per visit per subject",
        mappings=vms,
    )
    dfs = {
        "LB": pd.DataFrame({"LBTESTCD": ["ALT", "AST", "WBC", "ALT", "AST"]}),
    }
    generate_define_xml([spec], _mock_ct_ref(), STUDY_ID, STUDY_NAME, out, generated_dfs=dfs)

    tree = _parse(out)
    root = tree.getroot()

    # ValueListDef
    vlds = root.findall(".//def:ValueListDef", NS)
    assert len(vlds) == 1
    assert vlds[0].get("OID") == "VL.LB.LBTESTCD"

    # 3 unique test codes -> 3 ItemRef entries
    item_refs = vlds[0].findall("odm:ItemRef", NS)
    assert len(item_refs) == 3

    # WhereClauseDef elements
    wcs = root.findall(".//def:WhereClauseDef", NS)
    assert len(wcs) == 3


def test_leaf_elements(tmp_path: Path) -> None:
    """def:leaf elements generated with correct xlink:href for each domain."""
    out = tmp_path / "define.xml"
    dm = _make_spec()
    ae = _make_spec(
        domain="AE",
        label="Adverse Events",
        domain_class="Events",
        structure="One record per AE per subject",
    )
    generate_define_xml([dm, ae], _mock_ct_ref(), STUDY_ID, STUDY_NAME, out)

    tree = _parse(out)
    root = tree.getroot()

    leaves = root.findall(".//def:leaf", NS)
    assert len(leaves) == 2

    hrefs = {leaf.get(f"{{{XLINK_NS}}}href") for leaf in leaves}
    assert hrefs == {"dm.xpt", "ae.xpt"}

    # Each leaf has a title
    for leaf in leaves:
        title = leaf.find("def:title", NS)
        assert title is not None
        assert title.text.endswith(".xpt")


def test_output_file_written(tmp_path: Path) -> None:
    """Generated file exists, starts with XML declaration, and is valid XML."""
    out = tmp_path / "subdir" / "define.xml"
    spec = _make_spec()
    result = generate_define_xml([spec], _mock_ct_ref(), STUDY_ID, STUDY_NAME, out)

    assert result == out
    assert out.exists()

    content = out.read_bytes()
    assert content.startswith(b"<?xml")

    # Should parse without error
    tree = etree.parse(str(out))  # noqa: S320
    assert tree.getroot() is not None
