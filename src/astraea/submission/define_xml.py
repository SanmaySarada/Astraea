"""Define.xml 2.0 generator for FDA SDTM submissions.

Produces a standards-compliant define.xml from DomainMappingSpec objects,
containing ItemGroupDef, ItemDef, CodeList, MethodDef, ValueListDef,
and CommentDef elements. Uses lxml for proper namespace handling.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from lxml import etree

from astraea.models.mapping import (
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)
from astraea.models.sdtm import CoreDesignation
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference

# -- XML namespace constants --------------------------------------------------
ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
DEFINE_NS = "http://www.cdisc.org/ns/def/v2.0"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"

NSMAP = {None: ODM_NS, "def": DEFINE_NS, "xlink": XLINK_NS}

# Domain classes considered "reference data"
_TRIAL_DESIGN_CLASSES = {"Trial Design"}

# Domain classes considered "Findings" (need ValueListDef)
_FINDINGS_CLASSES = {"Findings"}

# DM is the only non-repeating domain
_NON_REPEATING_DOMAINS = {"DM"}

# Result variable suffixes that get ValueListDef in Findings domains
_RESULT_SUFFIXES = ("ORRES", "STRESC", "STRESN")


def generate_define_xml(
    specs: list[DomainMappingSpec],
    ct_ref: CTReference,
    study_id: str,
    study_name: str,
    output_path: Path,
    *,
    sdtm_ig_version: str = "3.4",
    generated_dfs: dict[str, pd.DataFrame] | None = None,
    sdtm_ref: SDTMReference | None = None,
) -> Path:
    """Generate a define.xml 2.0 file from domain mapping specifications.

    Args:
        specs: Mapping specifications for all domains.
        ct_ref: Controlled terminology reference for CodeList elements.
        study_id: Study identifier (e.g., 'PHA022121-C301').
        study_name: Human-readable study name.
        output_path: File path where define.xml will be written.
        sdtm_ig_version: SDTM-IG version string (default '3.4').
        generated_dfs: Optional dict of domain -> DataFrame for ValueListDef
            test code extraction.
        sdtm_ref: Optional SDTM-IG reference for key_variables lookup.

    Returns:
        Path to the generated define.xml file.
    """
    root = _create_odm_root(study_id)
    study_el = _add_study(root, study_id, study_name)
    mdv = _add_metadata_version(study_el, study_id, sdtm_ig_version)

    # Collect method and comment OIDs for cross-referencing
    method_oids: dict[tuple[str, str], str] = {}
    comment_oids: dict[tuple[str, str], str] = {}

    # Pre-compute methods and comments so ItemGroupDef can reference them
    for spec in specs:
        for vm in spec.variable_mappings:
            if vm.computational_method:
                oid = f"MT.{spec.domain}.{vm.sdtm_variable}"
                method_oids[(spec.domain, vm.sdtm_variable)] = oid
            comment_text = _get_comment_text(spec, vm)
            if comment_text:
                oid = f"COM.{spec.domain}.{vm.sdtm_variable}"
                comment_oids[(spec.domain, vm.sdtm_variable)] = oid

    # Pre-compute VLD variables for ValueListRef on ItemRef
    vld_by_domain = _get_vld_variables(specs)

    # 1. ItemGroupDef per domain
    for spec in specs:
        # Look up key_variables from SDTM-IG reference if available
        key_variables: list[str] | None = None
        if sdtm_ref:
            domain_spec = sdtm_ref.get_domain_spec(spec.domain)
            if domain_spec and domain_spec.key_variables:
                key_variables = domain_spec.key_variables
        _add_item_group(
            mdv,
            spec,
            method_oids,
            comment_oids,
            key_variables=key_variables,
            vld_variables=vld_by_domain.get(spec.domain),
        )

    # 2. ItemDef per variable (all domains)
    for spec in specs:
        for vm in spec.variable_mappings:
            _add_item_def(mdv, spec.domain, vm)

    # 3. CodeLists from CT reference
    _add_codelists(mdv, specs, ct_ref)

    # 4. MethodDef for derived variables
    _add_methods(mdv, specs)

    # 5. CommentDef for non-standard / SUPPQUAL candidates
    _add_comments(mdv, specs)

    # 6. ValueListDef for Findings domains
    _add_value_lists(mdv, specs, generated_dfs)

    # 7. def:leaf elements for dataset file locations
    _add_leaf_elements(mdv, specs)

    # Write XML
    tree = etree.ElementTree(root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(
        str(output_path),
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )
    return output_path


# -- Root structure helpers ---------------------------------------------------


def _create_odm_root(study_id: str) -> etree._Element:
    """Create the ODM root element with required attributes."""
    root = etree.Element(f"{{{ODM_NS}}}ODM", nsmap=NSMAP)
    root.set("FileType", "Snapshot")
    root.set("FileOID", f"DEFINE.{study_id}")
    root.set("CreationDateTime", datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S"))
    root.set("ODMVersion", "1.3.2")
    root.set("Originator", "Astraea-SDTM")
    root.set("AsOfDateTime", datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S"))
    return root


def _add_study(root: etree._Element, study_id: str, study_name: str) -> etree._Element:
    """Add Study element with GlobalVariables."""
    study = etree.SubElement(root, f"{{{ODM_NS}}}Study")
    study.set("OID", f"STUDY.{study_id}")

    gv = etree.SubElement(study, f"{{{ODM_NS}}}GlobalVariables")

    sn = etree.SubElement(gv, f"{{{ODM_NS}}}StudyName")
    sn.text = study_name

    sd = etree.SubElement(gv, f"{{{ODM_NS}}}StudyDescription")
    sd.text = study_name

    pn = etree.SubElement(gv, f"{{{ODM_NS}}}ProtocolName")
    pn.text = study_id

    return study


def _add_metadata_version(
    study: etree._Element, study_id: str, ig_version: str
) -> etree._Element:
    """Add MetaDataVersion element with define.xml attributes."""
    mdv = etree.SubElement(study, f"{{{ODM_NS}}}MetaDataVersion")
    mdv.set("OID", f"MDV.{study_id}")
    mdv.set("Name", f"Study {study_id}, SDTM Data Definitions")
    mdv.set(f"{{{DEFINE_NS}}}DefineVersion", "2.0.0")
    mdv.set(f"{{{DEFINE_NS}}}StandardName", "CDISC SDTM")
    mdv.set(f"{{{DEFINE_NS}}}StandardVersion", ig_version)
    return mdv


# -- ItemGroupDef -------------------------------------------------------------


def _add_item_group(
    mdv: etree._Element,
    spec: DomainMappingSpec,
    method_oids: dict[tuple[str, str], str],
    comment_oids: dict[tuple[str, str], str],
    *,
    key_variables: list[str] | None = None,
    vld_variables: set[str] | None = None,
) -> None:
    """Add an ItemGroupDef element for one domain.

    Args:
        mdv: MetaDataVersion parent element.
        spec: Domain mapping specification.
        method_oids: Pre-computed MethodDef OID lookup.
        comment_oids: Pre-computed CommentDef OID lookup.
        key_variables: Ordered list of key variables for KeySequence attribute.
        vld_variables: Set of variable names that have ValueListDef references.
    """
    ig = etree.SubElement(mdv, f"{{{ODM_NS}}}ItemGroupDef")
    ig.set("OID", f"IG.{spec.domain}")
    ig.set("Name", spec.domain)
    ig.set("Repeating", "No" if spec.domain in _NON_REPEATING_DOMAINS else "Yes")
    is_ref = "Yes" if spec.domain_class in _TRIAL_DESIGN_CLASSES else "No"
    ig.set("IsReferenceData", is_ref)
    ig.set("SASDatasetName", spec.domain)
    ig.set("Purpose", "Tabulation")
    ig.set(f"{{{DEFINE_NS}}}Structure", spec.structure)
    ig.set(f"{{{DEFINE_NS}}}Class", spec.domain_class)
    ig.set(f"{{{DEFINE_NS}}}Label", spec.domain_label)
    ig.set(f"{{{DEFINE_NS}}}ArchiveLocationID", f"LF.{spec.domain}")

    # Description
    desc = etree.SubElement(ig, f"{{{ODM_NS}}}Description")
    tt = etree.SubElement(desc, f"{{{ODM_NS}}}TranslatedText")
    tt.set(f"{{{XML_NS}}}lang", "en")
    tt.text = spec.domain_label

    # ItemRef for each variable
    for idx, vm in enumerate(spec.variable_mappings, start=1):
        ir = etree.SubElement(ig, f"{{{ODM_NS}}}ItemRef")
        ir.set("ItemOID", f"IT.{spec.domain}.{vm.sdtm_variable}")
        ir.set("OrderNumber", str(idx))
        ir.set("Mandatory", "Yes" if vm.core == CoreDesignation.REQ else "No")

        # KeySequence for key variables (independent of OrderNumber)
        if key_variables and vm.sdtm_variable in key_variables:
            key_seq = key_variables.index(vm.sdtm_variable) + 1
            ir.set("KeySequence", str(key_seq))

        key = (spec.domain, vm.sdtm_variable)
        if key in method_oids:
            ir.set("MethodOID", method_oids[key])
        if key in comment_oids:
            ir.set(f"{{{DEFINE_NS}}}CommentOID", comment_oids[key])

        # ValueListRef for Findings result variables with VLDs
        if vld_variables and vm.sdtm_variable in vld_variables:
            ir.set(
                f"{{{DEFINE_NS}}}ValueListOID",
                f"VL.{spec.domain}.{vm.sdtm_variable}",
            )


# -- ItemDef ------------------------------------------------------------------


def _add_item_def(mdv: etree._Element, domain: str, vm: VariableMapping) -> None:
    """Add an ItemDef element for one variable."""
    it = etree.SubElement(mdv, f"{{{ODM_NS}}}ItemDef")
    it.set("OID", f"IT.{domain}.{vm.sdtm_variable}")
    it.set("Name", vm.sdtm_variable)
    it.set("SASFieldName", vm.sdtm_variable)

    # Data type mapping
    if vm.sdtm_data_type == "Char":
        it.set("DataType", "text")
        length = vm.length or 200
        it.set("Length", str(length))
    elif vm.sdtm_variable.endswith("SEQ"):
        it.set("DataType", "integer")
        it.set("Length", str(vm.length or 8))
    else:
        it.set("DataType", "float")
        it.set("Length", str(vm.length or 8))

    # Description
    desc = etree.SubElement(it, f"{{{ODM_NS}}}Description")
    tt = etree.SubElement(desc, f"{{{ODM_NS}}}TranslatedText")
    tt.set(f"{{{XML_NS}}}lang", "en")
    tt.text = vm.sdtm_label

    # Origin with Source attribute
    if vm.origin:
        origin_el = etree.SubElement(it, f"{{{DEFINE_NS}}}Origin")
        origin_el.set("Type", vm.origin.value)
        if vm.origin == VariableOrigin.CRF and vm.source_variable:
            origin_el.set("Source", f"CRF ({vm.source_variable})")
        elif vm.origin == VariableOrigin.DERIVED:
            origin_el.set("Source", "Derived")
        elif vm.origin == VariableOrigin.ASSIGNED:
            origin_el.set("Source", "Sponsor defined")

    # CodeListRef
    if vm.codelist_code:
        clr = etree.SubElement(it, f"{{{ODM_NS}}}CodeListRef")
        clr.set("CodeListOID", f"CL.{vm.codelist_code}")


# -- CodeList -----------------------------------------------------------------


def _add_codelists(
    mdv: etree._Element,
    specs: list[DomainMappingSpec],
    ct_ref: CTReference,
) -> None:
    """Add CodeList elements for all referenced codelists."""
    # Collect unique codelist codes across all specs
    used_codes: set[str] = set()
    for spec in specs:
        for vm in spec.variable_mappings:
            if vm.codelist_code:
                used_codes.add(vm.codelist_code)

    for code in sorted(used_codes):
        codelist = ct_ref.lookup_codelist(code)
        if codelist is None:
            # Unknown codelist -- create placeholder
            cl_el = etree.SubElement(mdv, f"{{{ODM_NS}}}CodeList")
            cl_el.set("OID", f"CL.{code}")
            cl_el.set("Name", code)
            cl_el.set("DataType", "text")
            continue

        cl_el = etree.SubElement(mdv, f"{{{ODM_NS}}}CodeList")
        cl_el.set("OID", f"CL.{code}")
        cl_el.set("Name", codelist.name)
        cl_el.set("DataType", "text")
        cl_el.set(f"{{{DEFINE_NS}}}Extensible", "Yes" if codelist.extensible else "No")

        for sv, term in sorted(codelist.terms.items()):
            cli = etree.SubElement(cl_el, f"{{{ODM_NS}}}CodeListItem")
            cli.set("CodedValue", sv)
            decode = etree.SubElement(cli, f"{{{ODM_NS}}}Decode")
            dt = etree.SubElement(decode, f"{{{ODM_NS}}}TranslatedText")
            dt.set(f"{{{XML_NS}}}lang", "en")
            dt.text = term.nci_preferred_term or sv

            # NCI C-code via Alias element (define.xml 2.0)
            if term.nci_code:
                alias = etree.SubElement(cli, f"{{{ODM_NS}}}Alias")
                alias.set("Context", "nci:ExtCodeID")
                alias.set("Name", term.nci_code)


# -- MethodDef ----------------------------------------------------------------


def _add_methods(mdv: etree._Element, specs: list[DomainMappingSpec]) -> None:
    """Add MethodDef elements for all derived variables."""
    for spec in specs:
        for vm in spec.variable_mappings:
            if not vm.computational_method:
                continue

            md = etree.SubElement(mdv, f"{{{ODM_NS}}}MethodDef")
            oid = f"MT.{spec.domain}.{vm.sdtm_variable}"
            md.set("OID", oid)
            md.set("Name", vm.sdtm_label[:40] if vm.sdtm_label else vm.sdtm_variable)
            md.set("Type", "Computation")

            desc = etree.SubElement(md, f"{{{ODM_NS}}}Description")
            tt = etree.SubElement(desc, f"{{{ODM_NS}}}TranslatedText")
            tt.set(f"{{{XML_NS}}}lang", "en")
            tt.text = vm.computational_method

            fe = etree.SubElement(md, f"{{{ODM_NS}}}FormalExpression")
            fe.set("Context", "Python")
            fe.text = vm.computational_method


# -- CommentDef ---------------------------------------------------------------


def _get_comment_text(spec: DomainMappingSpec, vm: VariableMapping) -> str | None:
    """Determine comment text for a variable, if any.

    Returns text for non-standard variables and SUPPQUAL candidates.
    """
    # Check if variable is a SUPPQUAL candidate
    if vm.sdtm_variable in spec.suppqual_candidates:
        source_info = f"Source: {vm.source_variable}. " if vm.source_variable else ""
        return f"Candidate for SUPPQUAL domain. {source_info}{vm.notes or ''}".strip()

    # Check if variable might be non-standard (origin == CRF and not well-known)
    # A simple heuristic: if the variable has notes mentioning non-standard
    if vm.notes and "non-standard" in vm.notes.lower():
        return f"Non-standard variable. {vm.notes or vm.sdtm_label}"

    return None


def _add_comments(mdv: etree._Element, specs: list[DomainMappingSpec]) -> None:
    """Add CommentDef elements for non-standard variables and SUPPQUAL candidates."""
    for spec in specs:
        for vm in spec.variable_mappings:
            comment_text = _get_comment_text(spec, vm)
            if not comment_text:
                continue

            cd = etree.SubElement(mdv, f"{{{ODM_NS}}}CommentDef")
            cd.set("OID", f"COM.{spec.domain}.{vm.sdtm_variable}")

            desc = etree.SubElement(cd, f"{{{ODM_NS}}}Description")
            tt = etree.SubElement(desc, f"{{{ODM_NS}}}TranslatedText")
            tt.set(f"{{{XML_NS}}}lang", "en")
            tt.text = comment_text


# -- ValueListDef -------------------------------------------------------------


def _get_vld_variables(
    specs: list[DomainMappingSpec],
) -> dict[str, set[str]]:
    """Pre-compute which variables have ValueListDefs, keyed by domain.

    Returns a dict of domain -> set of variable names with VLDs.
    Used by _add_item_group to add def:ValueListRef on ItemRef elements.
    """
    result: dict[str, set[str]] = {}
    for spec in specs:
        if spec.domain_class not in _FINDINGS_CLASSES:
            continue

        # Must have TESTCD and TRANSPOSE pattern
        has_testcd = any(vm.sdtm_variable.endswith("TESTCD") for vm in spec.variable_mappings)
        has_transpose = any(
            vm.mapping_pattern == MappingPattern.TRANSPOSE for vm in spec.variable_mappings
        )
        if not has_testcd or not has_transpose:
            continue

        # Find result variables
        vld_vars = {
            vm.sdtm_variable
            for vm in spec.variable_mappings
            if any(vm.sdtm_variable.endswith(s) for s in _RESULT_SUFFIXES)
        }
        if vld_vars:
            result[spec.domain] = vld_vars

    return result


def _add_value_lists(
    mdv: etree._Element,
    specs: list[DomainMappingSpec],
    generated_dfs: dict[str, pd.DataFrame] | None,
) -> None:
    """Add ValueListDef elements for Findings result variables.

    Per define.xml 2.0, ValueListDef is placed on each result variable
    (--ORRES, --STRESC, --STRESN), parameterized by --TESTCD values
    via WhereClauseDef. This replaces the pre-2.0 pattern of placing
    VLD on --TESTCD.
    """
    for spec in specs:
        if spec.domain_class not in _FINDINGS_CLASSES:
            continue

        # Find TESTCD variable for this domain
        testcd_var = next(
            (vm for vm in spec.variable_mappings if vm.sdtm_variable.endswith("TESTCD")),
            None,
        )
        if testcd_var is None:
            continue

        # Check for TRANSPOSE pattern
        has_transpose = any(
            vm.mapping_pattern == MappingPattern.TRANSPOSE for vm in spec.variable_mappings
        )
        if not has_transpose:
            continue

        # Identify result variables
        result_vars = [
            vm
            for vm in spec.variable_mappings
            if any(vm.sdtm_variable.endswith(s) for s in _RESULT_SUFFIXES)
        ]
        if not result_vars:
            continue

        # Get unique test codes from actual data if available
        test_codes: list[str] = []
        if generated_dfs and spec.domain in generated_dfs:
            df = generated_dfs[spec.domain]
            testcd_col = testcd_var.sdtm_variable
            if testcd_col in df.columns:
                test_codes = sorted(df[testcd_col].dropna().unique().tolist())

        if not test_codes:
            # No data available -- create placeholder VLDs for each result variable
            for result_vm in result_vars:
                vld = etree.SubElement(mdv, f"{{{DEFINE_NS}}}ValueListDef")
                vld.set("OID", f"VL.{spec.domain}.{result_vm.sdtm_variable}")
            continue

        # Create VLD for EACH result variable (not TESTCD)
        for result_vm in result_vars:
            vld = etree.SubElement(mdv, f"{{{DEFINE_NS}}}ValueListDef")
            vld.set("OID", f"VL.{spec.domain}.{result_vm.sdtm_variable}")

            for idx, tc in enumerate(test_codes, start=1):
                ir = etree.SubElement(vld, f"{{{ODM_NS}}}ItemRef")
                ir.set("ItemOID", f"IT.{spec.domain}.{result_vm.sdtm_variable}.{tc}")
                ir.set("OrderNumber", str(idx))
                ir.set("Mandatory", "No")

                wc_oid = f"WC.{spec.domain}.{result_vm.sdtm_variable}.{tc}"
                ir.set(f"{{{DEFINE_NS}}}WhereClauseOID", wc_oid)

        # WhereClauseDef elements -- one per (result_var, test_code) combination
        for result_vm in result_vars:
            for tc in test_codes:
                wc = etree.SubElement(mdv, f"{{{DEFINE_NS}}}WhereClauseDef")
                wc.set("OID", f"WC.{spec.domain}.{result_vm.sdtm_variable}.{tc}")

                rc = etree.SubElement(wc, f"{{{ODM_NS}}}RangeCheck")
                rc.set("Comparator", "EQ")
                rc.set("SoftHard", "Soft")
                # Always reference TESTCD ItemDef -- the condition variable
                rc.set(
                    f"{{{DEFINE_NS}}}ItemOID",
                    f"IT.{spec.domain}.{testcd_var.sdtm_variable}",
                )

                cv = etree.SubElement(rc, f"{{{ODM_NS}}}CheckValue")
                cv.text = tc

        # Create value-level ItemDefs for each (result_var, test_code)
        for result_vm in result_vars:
            for tc in test_codes:
                _add_item_def_for_value_level(mdv, spec.domain, result_vm, tc)


def _add_item_def_for_value_level(
    mdv: etree._Element,
    domain: str,
    result_vm: VariableMapping,
    testcd: str,
) -> None:
    """Create ItemDef for a value-level reference (test-code-specific result)."""
    it = etree.SubElement(mdv, f"{{{ODM_NS}}}ItemDef")
    it.set("OID", f"IT.{domain}.{result_vm.sdtm_variable}.{testcd}")
    it.set("Name", result_vm.sdtm_variable)
    it.set("SASFieldName", result_vm.sdtm_variable)

    # Data type from the result variable
    if result_vm.sdtm_data_type == "Char":
        it.set("DataType", "text")
        it.set("Length", str(result_vm.length or 200))
    else:
        it.set("DataType", "float")
        it.set("Length", str(result_vm.length or 8))

    desc = etree.SubElement(it, f"{{{ODM_NS}}}Description")
    tt = etree.SubElement(desc, f"{{{ODM_NS}}}TranslatedText")
    tt.set(f"{{{XML_NS}}}lang", "en")
    tt.text = f"{result_vm.sdtm_label} ({testcd})"


# -- Leaf elements ------------------------------------------------------------


def _add_leaf_elements(mdv: etree._Element, specs: list[DomainMappingSpec]) -> None:
    """Add def:leaf elements for each domain's XPT file location."""
    for spec in specs:
        leaf = etree.SubElement(mdv, f"{{{DEFINE_NS}}}leaf")
        leaf.set("ID", f"LF.{spec.domain}")
        leaf.set(f"{{{XLINK_NS}}}href", f"{spec.domain.lower()}.xpt")

        title = etree.SubElement(leaf, f"{{{DEFINE_NS}}}title")
        title.text = f"{spec.domain.lower()}.xpt"
