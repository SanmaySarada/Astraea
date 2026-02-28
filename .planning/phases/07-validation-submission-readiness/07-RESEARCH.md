# Phase 7: Validation and Submission Readiness - Research

**Researched:** 2026-02-27
**Domain:** SDTM conformance validation, define.xml generation, FDA submission compliance
**Confidence:** MEDIUM-HIGH

## Summary

This phase builds a comprehensive validation engine and submission artifact generator on top of the existing Astraea pipeline. The codebase already has significant validation foundations: CT codelist validation during mapping, required variable coverage checks, cross-domain USUBJID validation, XPT pre-write validation (name/label/ASCII/length), and date format handling. Phase 7 extends these into a formal rule engine with severity classification and adds define.xml generation, FDA TRC pre-checks, and a cSDRG template generator.

The recommended approach is a layered validation architecture: (1) a custom deterministic rule engine for SDTM-IG rules organized by validation type (terminology, presence, consistency, limit, format), (2) optional integration with the CDISC Rules Engine (CORE) for P21-equivalent external validation, and (3) define.xml generation using `lxml` with templates derived from the Define-XML 2.0 specification (not odmlib, which adds unnecessary complexity for our structured metadata).

**Primary recommendation:** Build a custom validation rule engine with Pydantic rule models, organize rules by VAL-01 through VAL-05 categories, generate define.xml directly from DomainMappingSpec metadata using lxml, and implement FDA TRC as a pre-flight checklist.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `lxml` | >=5.0 | define.xml generation | Industry standard for XML generation in Python. Supports namespaces, XPath, schema validation. Far more capable than stdlib ElementTree for namespace-heavy define.xml. Already widely used in pharma for define.xml generation. |
| `pydantic` | >=2.10 (existing) | Validation rule models, report models | Already in stack. Validation rules and reports are Pydantic models like everything else. |
| `pandas` | >=2.2 (existing) | Dataset-level validation checks | Already in stack. Validation operates on DataFrames. |
| `openpyxl` | >=3.1 (existing) | Validation report export to Excel | Already in stack. Used for mapping spec export. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `cdisc-rules-engine` | 0.15.0 | External P21-equivalent validation | Optional integration for "second opinion" validation against official CDISC rules. Requires downloading rules cache. |
| `jinja2` | >=3.1 | cSDRG template rendering | Generate cSDRG document from structured metadata. Markdown template with Jinja2 placeholders. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| lxml for define.xml | odmlib (swhume) | odmlib provides ODM object model but adds dependency for something we can build with lxml in ~500 lines. Our metadata is already in Pydantic models, so we just need XML serialization, not another object model layer. |
| lxml for define.xml | stdlib xml.etree.ElementTree | ElementTree has poor namespace support. define.xml requires multiple namespaces (def:, arm:, xlink:). lxml handles this cleanly. |
| Custom rule engine | cdisc-rules-engine only | CORE is excellent for external validation but its API is oriented toward CLI/batch processing, not tight integration with our pipeline. Custom rules give us predict-and-prevent (VAL-06) which CORE cannot do. |
| jinja2 for cSDRG | openpyxl/docx | cSDRG is fundamentally a narrative document. Markdown + Jinja2 is simpler than generating Word docs. User can convert to PDF/Word if needed. |

**Installation:**
```bash
pip install lxml jinja2
# Optional: pip install cdisc-rules-engine  (requires rules cache download)
```

## Architecture Patterns

### Recommended Project Structure
```
src/astraea/
  validation/               # NEW - Phase 7
    __init__.py
    engine.py               # ValidationEngine orchestrator
    rules/
      __init__.py
      base.py               # BaseRule, RuleResult, RuleSeverity models
      terminology.py         # VAL-01: CT validation rules
      presence.py            # VAL-02: Required variable/record rules
      consistency.py         # VAL-03: Cross-domain consistency rules
      limits.py              # VAL-04: Variable length limit rules
      format.py              # VAL-05: Date format, naming convention rules
      fda_business.py        # FDA Business Rules (FDAB*)
      fda_trc.py             # FDA Technical Rejection Criteria
    report.py               # ValidationReport model and generation
    predict.py              # VAL-06: Predict-and-prevent during mapping
  submission/               # NEW - Phase 7
    __init__.py
    define_xml.py           # define.xml 2.0 generator
    csdrg.py                # cSDRG template generator
    package.py              # Submission package assembly and size check
```

### Pattern 1: Rule-Based Validation Engine

**What:** Each validation rule is a Pydantic model with `evaluate()` method returning structured results. Rules are registered in a rule registry by category and severity.

**When to use:** All validation (VAL-01 through VAL-05, FDA Business Rules, TRC).

**Example:**
```python
from enum import StrEnum
from pydantic import BaseModel, Field

class RuleSeverity(StrEnum):
    ERROR = "Error"      # Must fix before submission
    WARNING = "Warning"  # Should fix, explain in cSDRG if not
    NOTICE = "Notice"    # Informational, best practice

class RuleCategory(StrEnum):
    TERMINOLOGY = "Terminology"    # VAL-01
    PRESENCE = "Presence"          # VAL-02
    CONSISTENCY = "Consistency"    # VAL-03
    LIMIT = "Limit"               # VAL-04
    FORMAT = "Format"             # VAL-05
    FDA_BUSINESS = "FDA Business"
    FDA_TRC = "FDA TRC"

class RuleResult(BaseModel):
    rule_id: str                  # e.g., "ASTR-T001"
    rule_description: str
    category: RuleCategory
    severity: RuleSeverity
    domain: str | None = None
    variable: str | None = None
    message: str
    affected_count: int = 0
    fix_suggestion: str | None = None
    p21_equivalent: str | None = None  # e.g., "SD0002"

class ValidationRule(BaseModel):
    """Base class for all validation rules."""
    rule_id: str
    description: str
    category: RuleCategory
    severity: RuleSeverity

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        raise NotImplementedError
```

### Pattern 2: Define.xml Generation from Mapping Specs

**What:** Generate define.xml directly from the collection of DomainMappingSpec objects and their VariableMapping entries, which already contain all needed metadata (variable names, labels, types, origins, computational methods, codelist codes).

**When to use:** After all domains are validated and approved.

**Example:**
```python
from lxml import etree

DEFINE_NS = "http://www.cdisc.org/ns/def/v2.0"
ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
XLINK_NS = "http://www.w3.org/1999/xlink"

NSMAP = {
    None: ODM_NS,
    "def": DEFINE_NS,
    "xlink": XLINK_NS,
}

def generate_define_xml(
    specs: list[DomainMappingSpec],
    ct_ref: CTReference,
    study_id: str,
    output_path: Path,
) -> Path:
    """Generate define.xml 2.0 from mapping specifications."""
    root = etree.Element("ODM", nsmap=NSMAP)
    root.set("FileType", "Snapshot")
    root.set("FileOID", f"DEF.{study_id}")

    study = etree.SubElement(root, "Study")
    study.set("OID", f"STD.{study_id}")

    mdv = etree.SubElement(study, "MetaDataVersion")
    mdv.set("OID", "MDV.1")
    mdv.set("Name", f"{study_id} SDTM")

    # ItemGroupDef per domain
    for spec in specs:
        _add_item_group(mdv, spec)

    # ItemDef per variable (across all domains)
    for spec in specs:
        for mapping in spec.variable_mappings:
            _add_item_def(mdv, spec.domain, mapping)

    # CodeList definitions from CT reference
    _add_codelists(mdv, specs, ct_ref)

    # MethodDef for derived variables
    _add_methods(mdv, specs)

    tree = etree.ElementTree(root)
    tree.write(str(output_path), xml_declaration=True,
               encoding="UTF-8", pretty_print=True)
    return output_path
```

### Pattern 3: Predict-and-Prevent Validation (VAL-06)

**What:** Run lightweight validation rules DURING mapping, before dataset generation. Catches issues early so the mapping spec can be corrected before execution.

**When to use:** After LLM proposes mappings, before human review.

**Example:**
```python
def predict_and_prevent(
    proposal: DomainMappingProposal,
    domain_spec: DomainSpec,
    ct_ref: CTReference,
) -> list[RuleResult]:
    """Run predict-and-prevent rules on a mapping proposal.

    These are lightweight checks that can run on the spec alone
    (no generated data needed):
    - Required variables present
    - CT codelist codes valid
    - Variable names in SDTM-IG
    - No duplicate variable mappings
    - ASSIGN values match non-extensible codelists
    """
    results = []
    # ... check rules that operate on specs, not data
    return results
```

### Anti-Patterns to Avoid

- **LLM-based validation:** Validators MUST be deterministic. Never use LLM to check conformance.
- **Monolithic validator:** Don't build one giant validate() function. Use rule objects that can be tested independently.
- **Validation only post-generation:** Must also validate during mapping (predict-and-prevent). The existing `mapping/validation.py` already does some of this.
- **Reimplementing all P21 rules from scratch:** Focus on the rules that matter for our output. Use CDISC Rules Engine for comprehensive external validation if needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| XML generation with namespaces | Custom string concatenation or ElementTree | `lxml` | define.xml requires complex namespace handling (def:, xlink:, arm:). lxml handles this correctly; string concat will produce invalid XML. |
| XML schema validation | Custom XML structure checker | `lxml.etree.XMLSchema` | define.xml has an official XSD schema. Validate against it, don't write manual checks. |
| P21-equivalent rule execution | 400+ custom rules | `cdisc-rules-engine` (optional) | If you need comprehensive P21 parity, use the official engine. Don't rewrite 400 rules. |
| cSDRG document formatting | Custom string formatting | `jinja2` templates | Template engine handles conditionals, loops, formatting. |
| ISO 8601 date validation regex | Custom regex | Existing `transforms/dates.py` | Already built and tested in the codebase. |

**Key insight:** The codebase already has ~60% of the validation logic scattered across mapping/validation.py, xpt_writer.py, transforms/ascii_validation.py, and transforms/char_length.py. Phase 7 consolidates and extends this into a formal rule engine, it does NOT start from zero.

## Common Pitfalls

### Pitfall 1: False Positive Storm Eroding Trust

**What goes wrong:** Validator reports hundreds of warnings per domain. Users ignore all of them, including real errors. Known P21 issue: v2405.2 generates false positives for LBSTRESC numeric values.
**Why it happens:** Overly aggressive rules, no severity tiering, no known-issue whitelist.
**How to avoid:** Three severity tiers (Error/Warning/Notice). Known false-positive whitelist maintained as JSON config. Only Errors block submission. Warnings require cSDRG explanation. Notices are informational only.
**Warning signs:** Users skipping validation output, more than 50 warnings per domain on clean data.

### Pitfall 2: define.xml / Dataset Mismatch

**What goes wrong:** define.xml lists variables not in the dataset, or dataset contains variables not in define.xml. FDA flags this in review.
**Why it happens:** define.xml generated from mapping specs but datasets generated separately. If execution drops a variable (e.g., all NaN), define.xml still lists it.
**How to avoid:** Generate define.xml AFTER dataset generation, from the actual DataFrames + mapping specs together. Cross-validate: every column in every XPT must appear in define.xml, and vice versa.
**Warning signs:** Column count mismatch between XPT and define.xml ItemGroupDef.

### Pitfall 3: CT Version / IG Version Misalignment

**What goes wrong:** Bundled CT version doesn't match declared SDTM-IG version. TS domain declares one version but validation uses another.
**Why it happens:** CT is updated quarterly. System may bundle newer CT than what the study declared.
**How to avoid:** Version manifest check at validation start. Read TS domain for declared versions (TSPARMCD=SDTMIGVER, TSPARMCD=CTVER), compare against bundled reference data versions. Fail fast on mismatch.
**Warning signs:** Inconsistent version numbers in TS vs reference data.

### Pitfall 4: Cross-Domain Consistency Gaps

**What goes wrong:** RFSTDTC in DM doesn't match earliest EXSTDTC. DSSTDTC for informed consent predates RFSTDTC. Study day calculations are inconsistent across domains.
**Why it happens:** Domains are mapped independently. Cross-domain consistency requires comparing generated datasets against each other.
**How to avoid:** Run cross-domain rules AFTER all domains are generated, not per-domain. Build a CrossDomainValidator that takes the full set of generated DataFrames.
**Warning signs:** --DY values that don't make sense (negative when they shouldn't be, inconsistent across domains for the same subject/date).

### Pitfall 5: define.xml Namespace Errors

**What goes wrong:** define.xml uses wrong namespace prefixes, missing namespace declarations, or incorrect element nesting. XML is technically valid but define.xml schema validation fails.
**Why it happens:** define.xml 2.0 uses multiple XML namespaces (ODM, def:, xlink:). Hand-building XML without proper namespace management produces subtle errors.
**How to avoid:** Use lxml with explicit NSMAP. Validate generated define.xml against the official CDISC define.xml 2.0 XSD schema before including in submission package.

## Code Examples

### Validation Rule Implementation (Terminology - VAL-01)

```python
# Source: Custom implementation following SDTM-IG v3.4 + CT validation pattern
class TerminologyRule(ValidationRule):
    """Check that variable values match CDISC Controlled Terminology."""

    rule_id: str = "ASTR-T001"
    description: str = "Variable value must be in the assigned CT codelist"
    category: RuleCategory = RuleCategory.TERMINOLOGY
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        results = []
        for mapping in spec.variable_mappings:
            if not mapping.codelist_code:
                continue
            if mapping.sdtm_variable not in df.columns:
                continue

            cl = ct_ref.lookup_codelist(mapping.codelist_code)
            if cl is None:
                continue

            values = df[mapping.sdtm_variable].dropna().unique()
            valid_terms = set(cl.terms.keys())

            for val in values:
                if str(val) not in valid_terms:
                    severity = (
                        RuleSeverity.ERROR if not cl.extensible
                        else RuleSeverity.WARNING
                    )
                    results.append(RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=severity,
                        domain=domain,
                        variable=mapping.sdtm_variable,
                        message=(
                            f"Value '{val}' not in "
                            f"{'non-extensible' if not cl.extensible else 'extensible'} "
                            f"codelist {cl.name} ({mapping.codelist_code})"
                        ),
                        affected_count=int((df[mapping.sdtm_variable] == val).sum()),
                        fix_suggestion=(
                            f"Use one of: {', '.join(sorted(list(valid_terms)[:5]))}..."
                            if not cl.extensible else None
                        ),
                    ))
        return results
```

### FDA TRC Pre-Check

```python
# Source: FDA Technical Rejection Criteria (incorporated into Study Data TCG)
class TRCPreCheck:
    """FDA Technical Rejection Criteria pre-flight checklist."""

    def check_all(
        self,
        generated_domains: dict[str, pd.DataFrame],
        output_dir: Path,
        study_id: str,
    ) -> list[RuleResult]:
        results = []

        # TRC 1736: DM dataset must be present
        if "DM" not in generated_domains:
            results.append(RuleResult(
                rule_id="FDA-TRC-1736",
                rule_description="DM dataset must be present",
                category=RuleCategory.FDA_TRC,
                severity=RuleSeverity.ERROR,
                message="DM domain not found in generated datasets. "
                        "FDA will reject submission without dm.xpt.",
                fix_suggestion="Ensure DM domain is mapped and generated.",
            ))

        # TRC 1734: TS dataset with SSTDTC must be present
        if "TS" not in generated_domains:
            results.append(RuleResult(
                rule_id="FDA-TRC-1734",
                rule_description="TS dataset with study start date must be present",
                category=RuleCategory.FDA_TRC,
                severity=RuleSeverity.ERROR,
                message="TS domain not found. FDA requires ts.xpt with SSTDTC.",
            ))
        else:
            ts_df = generated_domains["TS"]
            if "TSPARMCD" in ts_df.columns:
                sstdtc = ts_df[ts_df["TSPARMCD"] == "SSTDTC"]
                if sstdtc.empty:
                    results.append(RuleResult(
                        rule_id="FDA-TRC-1734",
                        rule_description="TS must contain SSTDTC",
                        category=RuleCategory.FDA_TRC,
                        severity=RuleSeverity.ERROR,
                        message="TS domain missing SSTDTC (Study Start Date) parameter.",
                    ))

        # TRC 1735: define.xml must be present
        define_path = output_dir / "define.xml"
        if not define_path.exists():
            results.append(RuleResult(
                rule_id="FDA-TRC-1735",
                rule_description="define.xml must be present",
                category=RuleCategory.FDA_TRC,
                severity=RuleSeverity.ERROR,
                message="define.xml not found in output directory.",
                fix_suggestion="Generate define.xml before submission.",
            ))

        # TRC: STUDYID consistency across all domains
        studyid_values = set()
        for domain_name, df in generated_domains.items():
            if "STUDYID" in df.columns:
                studyid_values.update(df["STUDYID"].dropna().unique())
        if len(studyid_values) > 1:
            results.append(RuleResult(
                rule_id="FDA-TRC-STUDYID",
                rule_description="STUDYID must be consistent across all domains",
                category=RuleCategory.FDA_TRC,
                severity=RuleSeverity.ERROR,
                message=f"Multiple STUDYID values found: {studyid_values}",
            ))

        # TRC: File naming conventions (lowercase domain.xpt)
        for domain_name in generated_domains:
            expected_filename = f"{domain_name.lower()}.xpt"
            actual_path = output_dir / expected_filename
            if not actual_path.exists():
                results.append(RuleResult(
                    rule_id="FDA-TRC-FILENAME",
                    rule_description="XPT filenames must be lowercase domain codes",
                    category=RuleCategory.FDA_TRC,
                    severity=RuleSeverity.ERROR,
                    domain=domain_name,
                    message=f"Expected file {expected_filename} not found.",
                ))

        return results
```

### define.xml ItemGroupDef Generation

```python
# Source: Define-XML 2.0 Specification (CDISC)
def _add_item_group(mdv: etree._Element, spec: DomainMappingSpec) -> None:
    """Add an ItemGroupDef element for one domain."""
    ig = etree.SubElement(mdv, "ItemGroupDef")
    ig.set("OID", f"IG.{spec.domain}")
    ig.set("Name", spec.domain)
    ig.set("Repeating", "Yes" if spec.domain != "DM" else "No")
    ig.set("IsReferenceData", "Yes" if spec.domain_class == "Trial Design" else "No")
    ig.set("SASDatasetName", spec.domain)
    ig.set("Purpose", "Tabulation")
    ig.set(f"{{{DEFINE_NS}}}Structure", spec.structure)
    ig.set(f"{{{DEFINE_NS}}}Class", spec.domain_class)
    ig.set(f"{{{DEFINE_NS}}}ArchiveLocationID", f"LF.{spec.domain}")

    # Description
    desc = etree.SubElement(ig, "Description")
    tt = etree.SubElement(desc, "TranslatedText")
    tt.set(f"{{{XML_NS}}}lang", "en")
    tt.text = spec.domain_label

    # ItemRef for each variable
    for mapping in spec.variable_mappings:
        iref = etree.SubElement(ig, "ItemRef")
        iref.set("ItemOID", f"IT.{spec.domain}.{mapping.sdtm_variable}")
        iref.set("OrderNumber", str(mapping.order))
        iref.set("Mandatory", "Yes" if mapping.core == CoreDesignation.REQ else "No")
        if mapping.computational_method:
            iref.set("MethodOID", f"MT.{spec.domain}.{mapping.sdtm_variable}")
```

## FDA Technical Rejection Criteria (TRC)

Based on FDA documentation (incorporated into Study Data Technical Conformance Guide):

| Error ID | Check | Severity | Notes |
|----------|-------|----------|-------|
| 1734 | ts.xpt must exist with SSTDTC (study start date) as valid ISO 8601 | REJECT | TS dataset is mandatory regardless of data standard |
| 1735 | define.xml must exist with exact filename "define.xml" | REJECT | No filename variations allowed |
| 1736 | For SDTM: dm.xpt and define.xml must be in Module 5 | REJECT | DM is mandatory for SDTM submissions |
| 1738 | STUDYID must match across all datasets and STF file | REJECT | New rule added ~2025 |
| -- | Correct STF file-tags for standardized datasets | REJECT | File tagging in eCTD |
| -- | Dataset file naming: lowercase domain code + .xpt | REJECT | e.g., "ts_xpt.xpt" is NOT valid |

**Confidence: MEDIUM** - TRC checks are well-documented by FDA but specific error IDs were gathered from multiple sources; some may have been updated.

## FDA Business Rules

Based on FDA Business Rules v1.5/v1.6 documentation:

| Rule ID | What It Checks | Severity | Implementation |
|---------|---------------|----------|----------------|
| FDAB009 | Paired variables must have 1:1 relationship (e.g., --TESTCD and --TEST, variable name and label) | Error | Check all Findings --TESTCD/--TEST pairs for 1:1 mapping |
| FDAB030 | Standard units should be used for numeric results | Warning | Check --STRESU values against expected unit codelists |
| FDAB039 | Normal range boundaries should be numeric when result is numeric (LBORNRLO, LBORNRHI) | Warning | Check that --ORNRLO/--ORNRHI are numeric when --STRESN is populated |
| FDAB055 | Race should be self-reported by trial participants, not assigned | Warning | Check that RACE values in DM use proper CT (C74457) and note in cSDRG that data is self-reported |
| FDAB057 | Ethnicity must offer minimum two choices: HISPANIC OR LATINO, NOT HISPANIC OR LATINO | Warning | Check ETHNIC values in DM against CT codelist C66790 |

**Confidence: MEDIUM** - Rule IDs confirmed from multiple sources. Specific check logic inferred from descriptions; exact implementation details should be validated against the official FDA Business Rules Excel file.

## define.xml 2.0 Structure

The define.xml 2.0 file follows the CDISC ODM 1.3.2 schema with define.xml extensions:

```
ODM (root)
  Study
    GlobalVariables (StudyName, StudyDescription, ProtocolName)
    MetaDataVersion
      ItemGroupDef (per domain)       -- dataset-level metadata
        Description
        ItemRef (per variable)        -- references ItemDef
      ItemDef (per variable)          -- variable-level metadata
        Description
        def:Origin                    -- CRF, Derived, Assigned, etc.
        CodeListRef                   -- links to CodeList
        def:ValueListRef              -- links to ValueListDef for Findings
      CodeList                        -- CT codelist definitions
        CodeListItem (per term)
      MethodDef                       -- computational methods for derived vars
        Description
        FormalExpression
      def:ValueListDef               -- value-level metadata (Findings domains)
        ItemRef + def:WhereClauseDef
      def:WhereClauseDef             -- conditions for value-level metadata
        RangeCheck
      def:leaf (per dataset file)    -- file locations
```

Key elements mapped from our data model:

| define.xml Element | Source in Astraea | Notes |
|-------------------|-------------------|-------|
| ItemGroupDef | DomainMappingSpec | One per domain |
| ItemDef | VariableMapping | One per variable |
| def:Origin | VariableMapping.origin | Already tracked as VariableOrigin enum |
| MethodDef | VariableMapping.computational_method | Already tracked on derivation mappings |
| CodeListRef | VariableMapping.codelist_code | Already tracked |
| CodeList | CTReference codelists | Bundled CT data |
| ValueListDef | Findings domain --TESTCD values | Needed for LB, VS, EG, PE |
| WhereClauseDef | Findings domain test-specific metadata | Links to ValueListDef |

**Confidence: HIGH** - define.xml 2.0 spec is stable and well-documented. Our VariableMapping model already captures origin, computational_method, and codelist_code, which are the three hardest metadata elements.

## cSDRG (Clinical Study Data Reviewer's Guide)

The cSDRG is a narrative document following the PHUSE template. Key sections:

| Section | Content | Source in Astraea |
|---------|---------|-------------------|
| 1. Introduction | Study overview, purpose of guide | StudyMetadata |
| 2. Study Description | Trial design, objectives, endpoints | Manual / TS domain |
| 3. Data Standards and Dictionary Inventory | SDTM-IG version, CT version, MedDRA version, dictionaries used | Reference data version files |
| 4. Dataset Overview | List of all domains with record counts, purpose | DomainMappingSpec collection |
| 5. Domain-Specific Information | Per-domain details: source data, mapping approach, non-standard variables, deviations from IG | DomainMappingSpec + validation results |
| 6. Data Issues and Handling | Known data issues, imputation rules, partial dates, missing data conventions | Validation report + mapping notes |
| 7. Validation Results Summary | P21 validation summary, known false positives, explanation of warnings | Validation report |
| 8. Non-Standard Variables | Justification for SUPPQUAL variables and any custom domains | SUPPQUAL candidates from specs |

**Confidence: MEDIUM** - cSDRG structure based on PHUSE template guidance. Specific section numbers may vary between the standard cSDRG and the newer icSDRG format.

## Existing Validation in the Codebase

The codebase already implements significant validation that Phase 7 consolidates:

| Existing Component | Location | What It Validates | Phase 7 Action |
|-------------------|----------|-------------------|----------------|
| CT codelist validation | `mapping/validation.py` | Codelist existence, non-extensible term matching | Wrap as TerminologyRule, extend to runtime data values |
| Required variable coverage | `mapping/validation.py:check_required_coverage()` | Required SDTM-IG variables have mappings | Wrap as PresenceRule |
| Cross-domain USUBJID | `execution/executor.py:validate_cross_domain_usubjid()` | All USUBJIDs exist in DM | Wrap as ConsistencyRule |
| XPT pre-write validation | `io/xpt_writer.py:validate_for_xpt_v5()` | Name length, label length, char length, ASCII | Wrap as LimitRule + FormatRule |
| ASCII validation | `transforms/ascii_validation.py` | Non-ASCII characters in string columns | Already handles fix + detect |
| Character length optimization | `transforms/char_length.py` | Optimizes char widths for XPT | Used for LimitRule |
| Date format handling | `transforms/dates.py` | ISO 8601 conversion, partial dates | Used for FormatRule |

**Key insight:** Phase 7 does NOT start from zero. It creates a unified validation framework that wraps existing checks and adds new ones.

## CDISC Rules Engine (CORE) Integration

The `cdisc-rules-engine` package (v0.15.0, Feb 2026) provides P21-equivalent validation:

**Integration approach:**
```python
from cdisc_rules_engine.models.dataset.pandas_dataset import PandasDataset

# Wrap our DataFrames as PandasDataset objects
dataset = PandasDataset(dataframe=df)

# Execute rules from cache
results = engine.validate(dataset, rules=rules_cache)
```

**Requirements:**
- Python 3.12 or 3.13 (we use 3.12 -- compatible)
- Rules cache must be downloaded from GitHub repo (resources/cache/)
- Supports XPT and DataFrame input
- MIT licensed

**Recommendation:** Use as optional external validation, not primary. Our custom rule engine handles predict-and-prevent (VAL-06) and tight pipeline integration. CORE provides "second opinion" comprehensive validation.

**Confidence: MEDIUM** - CORE's Python API is not well-documented. The PandasDataset integration path exists but examples are sparse. May require reading source code to integrate fully.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| define.xml 2.0 | define.xml 2.1 (optional) | 2024 | v2.1 adds Analysis Results Metadata; v2.0 still accepted by FDA |
| P21 Community Edition only | CDISC CORE (open source) | 2023-2025 | CORE is the official CDISC validation engine, replacing need for P21 license |
| cSDRG standalone | icSDRG (integrated) | 2025 | PHUSE developing integrated guide combining cSDRG + iADRG; standard cSDRG still accepted |
| Manual TRC checks | Automated TRC in validation tools | 2021+ | FDA enforcing TRC since Sept 2021; can be automated |
| FDA Business Rules v1.5 | FDA Business Rules now in CDISC CORE format | 2024 | CDISC and FDA collaborating on machine-executable rules |

**Deprecated/outdated:**
- define.xml v1.0: Do not use. v2.0 minimum for FDA submissions.
- Manual validation only: FDA expects systematic validation evidence.

## Open Questions

1. **CDISC Rules Engine cache size and download mechanism**
   - What we know: Cache must be downloaded from GitHub repo. Contains rule definitions in JSON/YAML.
   - What's unclear: Size of cache, whether it can be bundled with the package, update frequency.
   - Recommendation: Make CORE integration optional. Ship with our custom rules. User can opt-in to CORE validation with a CLI flag.

2. **define.xml 2.0 vs 2.1**
   - What we know: FDA accepts both. v2.1 adds Analysis Results Metadata (ARM).
   - What's unclear: Whether any FDA centers prefer v2.1 for SDTM.
   - Recommendation: Implement v2.0 (simpler, sufficient for SDTM tabulation data). Add v2.1 support later if needed.

3. **ValueListDef complexity for Findings domains**
   - What we know: LB, VS, EG, PE require value-level metadata (per-test metadata for each --TESTCD value). This is the most complex part of define.xml.
   - What's unclear: How to efficiently generate WhereClauseDef for every unique test code.
   - Recommendation: Build ValueListDef generation for Findings domains, sourcing test-specific metadata from the transpose configuration. May need to parse generated DataFrames to discover unique --TESTCD values.

4. **FDA Business Rules completeness**
   - What we know: Rules FDAB009, FDAB030, FDAB039, FDAB055, FDAB057 identified.
   - What's unclear: The complete list of FDA business rules (v1.5 has ~60 rules). The Excel file is not easily machine-parseable.
   - Recommendation: Implement the 5 identified rules first. Add more as needed based on validation results.

5. **Submission package size (5GB limit)**
   - What we know: FDA has a 5GB limit per submission package.
   - What's unclear: Whether our study data is anywhere near this limit.
   - Recommendation: Add a simple size check. With 36 raw datasets this is unlikely to be an issue, but the check is trivial to implement.

## Sources

### Primary (HIGH confidence)
- CDISC Define-XML 2.0 Specification: [Define-XML v2.0 | CDISC](https://www.cdisc.org/standards/data-exchange/define-xml/define-xml-v2-0)
- FDA Technical Rejection Criteria: [FDA TRC Presentation](https://www.fda.gov/media/160970/download), [FDA TRC Document](https://www.fda.gov/media/100743/download)
- CDISC Rules Engine GitHub: [cdisc-org/cdisc-rules-engine](https://github.com/cdisc-org/cdisc-rules-engine)
- CDISC Rules Engine PyPI: [cdisc-rules-engine 0.15.0](https://pypi.org/project/cdisc-rules-engine/)
- odmlib Python package: [swhume/odmlib](https://github.com/swhume/odmlib)
- odmlib examples: [swhume/odmlib_examples](https://github.com/swhume/odmlib_examples)

### Secondary (MEDIUM confidence)
- FDA Business Rules v1.5: [FDA Business Rules Excel](https://www.fda.gov/media/116935/download)
- Pinnacle 21 FDA Business Rules explanation (redirected to Certara): [Certara Blog](https://www.certara.com/blog/new-fda-validator-rules-v1-6-explained/)
- PHUSE cSDRG Package: [PHUSE Advance Hub](https://advance.phuse.global/display/WEL/Clinical+Study+Data+Reviewer's+Guide+(cSDRG)+Package)
- PharmaSUG 2025 icSDRG paper: [PharmaSUG-2025-SS-269](https://pharmasug.org/proceedings/2025/SS/PharmaSUG-2025-SS-269.pdf)
- PharmaSUG 2025 CORE paper: [PharmaSUG-2025-SD-044](https://pharmasug.org/proceedings/2025/SD/PharmaSUG-2025-SD-044.pdf)
- FDA Study Data Technical Conformance Guide v4.4: [FDA TCG](https://www.fda.gov/media/133219/download)
- Quanticate TRC analysis: [Why submissions fail TRC](https://www.quanticate.com/blog/why-do-a-3rd-of-submissions-fail-the-technical-rejection-criteria)

### Tertiary (LOW confidence)
- PHUSE 2024 FDA business rules + CDISC Open Rules paper: [PHUSE DS05](https://www.lexjansen.com/phuse/2024/ds/PAP_DS05.pdf) (could not fetch content)
- PharmaSUG 2025 define.xml automation: [PharmaSUG-2025-MM-277](https://pharmasug.org/proceedings/2025/MM/PharmaSUG-2025-MM-277.pdf) (not fetched)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - lxml and custom rule engine are well-established patterns
- Architecture: HIGH - Rule-based validation is the standard approach for SDTM; define.xml structure is stable
- FDA TRC: MEDIUM - TRC checks identified from multiple FDA sources but error IDs may have been updated
- FDA Business Rules: MEDIUM - Key rules identified but complete list not machine-readable
- CDISC Rules Engine integration: MEDIUM - Package exists and supports Python 3.12, but API documentation is sparse
- define.xml generation: HIGH - Structure well-documented, our models already capture required metadata
- cSDRG: MEDIUM - Template structure known from PHUSE, but exact section requirements may vary

**Research date:** 2026-02-27
**Valid until:** 2026-04-27 (60 days - validation standards change slowly)
