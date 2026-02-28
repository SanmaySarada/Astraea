---
phase: 07-validation-submission-readiness
plan: 05
subsystem: submission
tags: [define-xml, xml, cdisc, fda, submission, lxml]
depends_on:
  requires: ["07-02", "07-03"]
  provides: ["define.xml 2.0 generator from DomainMappingSpec"]
  affects: ["07-06", "07-07"]
tech_stack:
  added: ["lxml>=5.0"]
  patterns: ["XML namespace handling with lxml etree", "define.xml 2.0 ODM structure"]
key_files:
  created:
    - src/astraea/submission/define_xml.py
    - src/astraea/submission/__init__.py
    - tests/unit/submission/__init__.py
    - tests/unit/submission/test_define_xml.py
  modified:
    - pyproject.toml
decisions:
  - id: "D-07-05-01"
    description: "lxml used for XML generation with proper namespace handling (not xml.etree.ElementTree)"
  - id: "D-07-05-02"
    description: "CommentDef generated for SUPPQUAL candidates and variables with 'non-standard' in notes field"
  - id: "D-07-05-03"
    description: "ValueListDef only generated for Findings domains with TRANSPOSE pattern and actual data available"
metrics:
  duration: "~3 min"
  completed: "2026-02-28"
---

# Phase 7 Plan 5: Define.xml 2.0 Generator Summary

**One-liner:** Complete define.xml 2.0 generator using lxml with ItemGroupDef, ItemDef, CodeList, MethodDef, CommentDef, and ValueListDef elements from DomainMappingSpec objects.

## What Was Done

### Task 1: define.xml 2.0 generator
- Created `src/astraea/submission/define_xml.py` with `generate_define_xml()` function
- ODM root with FileType="Snapshot", ODMVersion="1.3.2", define.xml 2.0 namespaces
- Study/GlobalVariables with StudyName, StudyDescription, ProtocolName
- MetaDataVersion with DefineVersion="2.0.0", StandardName="CDISC SDTM"
- ItemGroupDef per domain with Repeating, IsReferenceData, Structure, Class, ArchiveLocationID
- ItemDef per variable with DataType, Length, Origin, CodeListRef
- CodeList elements from CTReference with extensibility flag and CodeListItems
- MethodDef for derived variables with Description and FormalExpression (Context="Python")
- CommentDef for non-standard variables and SUPPQUAL candidates
- ValueListDef for Findings domains with WhereClauseDef per test code
- def:leaf elements for dataset file locations
- Added lxml>=5.0 to pyproject.toml dependencies

### Task 2: define.xml unit tests
- 11 tests covering all define.xml structural elements
- test_basic_structure: ODM root, Study, MetaDataVersion, ItemGroupDef count, ItemDef count
- test_item_group_attributes: OID, Name, Repeating, SASDatasetName, Structure, Class
- test_item_def_attributes: OID, Name, DataType, Description, Origin
- test_codelist_generation: CodeList with CodeListItems, CodeListRef from ItemDef
- test_method_def: MethodDef with Description, FormalExpression, MethodOID reference from ItemRef
- test_comment_def_nonstandard: CommentDef for non-standard variables with CommentOID reference
- test_comment_def_suppqual: CommentDef for SUPPQUAL candidates with source variable info
- test_multiple_domains: 2 ItemGroupDefs, correct ItemDef count, no duplicate OIDs
- test_findings_value_list: ValueListDef with ItemRef and WhereClauseDef for test codes
- test_leaf_elements: def:leaf with xlink:href for each domain
- test_output_file_written: file exists, XML declaration, valid XML

## Deviations from Plan

None -- plan executed exactly as written.

## Verification Results

- `pytest tests/unit/submission/test_define_xml.py -x -q` -- 11 tests pass
- `ruff check src/astraea/submission/define_xml.py` -- all checks pass
- Generated define.xml is valid XML with ODM root and correct namespaces
- define.xml contains ItemGroupDef, ItemDef, CodeList, MethodDef, CommentDef, ValueListDef elements

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | d0c79ce | feat(07-05): add define.xml 2.0 generator |
| 2 | ef17193 | test(07-05): add define.xml 2.0 generator unit tests |
