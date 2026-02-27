# Phase 3: Core Mapping Engine (Demographics) - Research

**Researched:** 2026-02-27
**Domain:** LLM-driven SDTM variable mapping with structured output, proven on DM domain
**Confidence:** HIGH

## Summary

Phase 3 builds the core mapping engine -- the system's most valuable component. It takes a classified domain (from Phase 2), raw dataset profiles, eCRF metadata, SDTM-IG specs, and CT codelists, then uses Claude to propose variable-level mappings. The output is a structured mapping specification document (JSON + Excel) that serves as the reviewable artifact between LLM reasoning and deterministic execution.

The DM (Demographics) domain was chosen as the reference implementation because it exercises most mapping patterns (direct copy, rename, combine, derivation, lookup/recode, reformat) without requiring the hardest pattern (transpose). DM is also the anchor domain -- every other SDTM domain references DM's USUBJID, and several DM variables (RFSTDTC, RFENDTC, ARM) are derived from data in other source datasets (EX, IE, IRT).

**Primary recommendation:** Build a `MappingEngine` class that orchestrates: (1) gathering context for a domain, (2) calling Claude with structured output to propose mappings, (3) validating proposals against SDTM-IG and CT, (4) producing a `DomainMappingSpec` Pydantic model, and (5) serializing to Excel/JSON. The LLM proposes WHAT; deterministic code validates and will eventually execute HOW.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | installed | Claude API for mapping proposals | Already in stack, AstraeaLLMClient wraps it |
| `pydantic` | >=2.10 | Mapping spec data models, structured LLM output | Already in stack, forces schema compliance |
| `openpyxl` | 3.1.5 | Excel workbook output for mapping specs | Already installed, industry-standard Excel writer |
| `pandas` | >=2.2 | Data manipulation for context preparation | Already in stack |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `loguru` | installed | Trace mapping decisions and LLM calls | Every mapping call |
| `rich` | installed | CLI display of mapping results | `astraea map` command |

### No New Dependencies Required

Everything needed is already installed. The mapping engine is primarily new Pydantic models, a new module (`src/astraea/mapping/`), and LLM prompt engineering.

## Architecture Patterns

### Recommended Project Structure

```
src/astraea/
  mapping/
    __init__.py
    engine.py           # MappingEngine orchestrator
    context.py          # Builds LLM context for a domain
    spec_models.py      # Mapping spec Pydantic models (output schema)
    exporters.py        # Excel + JSON serialization
    confidence.py       # Confidence scoring logic
    transforms.py       # Executable transformation registry
```

### Pattern 1: Two-Phase Mapping (LLM Proposal + Deterministic Validation)

**What:** The LLM proposes mappings as structured JSON (via tool use). A deterministic validator then checks each proposal against SDTM-IG specs and CT codelists. Invalid proposals are flagged, not silently accepted.

**When to use:** Every mapping call.

**Why:** The LLM may propose a variable that does not exist in the SDTM-IG, assign the wrong codelist, or use an invalid CT term. Post-proposal validation catches these before they reach human review.

```python
# Flow:
# 1. Build context (profile + eCRF + SDTM spec + CT)
# 2. Call LLM -> get DomainMappingSpec (structured output)
# 3. Validate each VariableMapping against SDTM-IG
# 4. Validate CT terms against CTReference
# 5. Flag issues, adjust confidence
# 6. Return validated DomainMappingSpec
```

### Pattern 2: Context Assembly per Domain

**What:** For each domain, assemble a focused context package containing only the relevant information: the raw dataset profile (clinical columns only, no EDC), the matched eCRF form fields, the SDTM-IG domain spec, and the relevant CT codelists.

**When to use:** Before every LLM mapping call.

**Why:** Avoids context window overflow. DM needs ~5 CT codelists, not all 50+. The raw DM dataset has 32 clinical columns, not all 61.

```python
class MappingContext(BaseModel):
    """Everything the LLM needs to map one domain."""
    domain: str
    domain_spec: DomainSpec           # From SDTMReference
    source_profiles: list[DatasetProfile]  # Clinical vars only
    ecrf_forms: list[ECRFForm]        # Matched forms
    codelists: dict[str, Codelist]    # Only relevant CTs
    study_metadata: StudyMetadata     # STUDYID, etc.
    cross_domain_sources: dict[str, list[str]]  # e.g., {"RFSTDTC": ["ex.sas7bdat"]}
```

### Pattern 3: Mapping Pattern Classification

**What:** Each variable mapping is classified into one of 9 patterns. The LLM must specify the pattern and the engine validates it is handled correctly.

**Patterns for DM:**

| Pattern | DM Example | Description |
|---------|-----------|-------------|
| assign | STUDYID, DOMAIN | Constant value assignment |
| direct | AGE -> AGE | Same name and content |
| rename | SEX_STD -> SEX | Different name, same content |
| reformat | BRTHYR_YYYY -> BRTHDTC | Year -> ISO 8601 partial date |
| combine | StudyEnvSiteNumber components -> USUBJID | Multiple sources -> one target |
| derivation | RFSTDTC from EX first dose date | Calculated from other data |
| lookup_recode | SEX "Female" -> "F", ETHNIC_STD -> ETHNIC | Map to CT submission values |
| transpose | N/A for DM | Not applicable to DM |
| attribute | All variables | Label, type, length per SDTM-IG |

### Pattern 4: Cross-Domain Source Resolution

**What:** Several DM variables (RFSTDTC, RFENDTC, RFXSTDTC, RFXENDTC, RFICDTC, ARM/ARMCD, COUNTRY) come from datasets OTHER than dm.sas7bdat. The mapping engine must identify and document these cross-domain dependencies.

**DM Cross-Domain Sources (from actual Fakedata):**

| DM Variable | Source Dataset | Source Variable | Derivation |
|-------------|---------------|-----------------|------------|
| RFSTDTC | ex.sas7bdat | EXDAT (first dose per subject) | Min EXDAT where EXYN="Yes" -> ISO 8601 |
| RFENDTC | ex.sas7bdat | EXDAT (last dose per subject) | Max EXDAT where EXYN="Yes" -> ISO 8601 |
| RFXSTDTC | ex.sas7bdat | EXDAT (first study treatment) | Same as RFSTDTC for this study |
| RFXENDTC | ex.sas7bdat | EXDAT (last study treatment) | Same as RFENDTC for this study |
| RFICDTC | ie.sas7bdat | ICDAT | Informed consent date -> ISO 8601 |
| RFPENDTC | ds.sas7bdat | Derived from disposition | End of participation date |
| COUNTRY | irt.sas7bdat | SCOUNTRY | "UNITED KINGDOM" -> "GBR", etc. |
| ARM/ARMCD | irt.sas7bdat | STRTG | Blinded in sample data |
| ACTARM/ACTARMCD | irt.sas7bdat | STRTG | Blinded in sample data |
| DTHDTC/DTHFL | ae.sas7bdat or ds.sas7bdat | Death-related fields | If subject died |

### Anti-Patterns to Avoid

- **Monolithic LLM call:** Do NOT send all 36 datasets + full IG in one prompt. Send only DM-relevant context.
- **LLM executing transformations:** The LLM proposes "RFSTDTC = min(EXDAT where EXYN=Yes)". It does NOT run pandas code. Execution is Phase 4+ concern.
- **Hardcoded mapping tables:** The engine should work for ANY study's DM, not just this one. The LLM reasons about the specific data; the engine validates against the standard.
- **Skipping CT validation:** Every proposed CT term MUST be validated against the bundled codelist before inclusion in the spec.

## Actual DM Raw Data Analysis

### dm.sas7bdat Structure (3 subjects, 61 columns)

**EDC System Columns (29 -- to be filtered out):**
projectid, project, studyid, environmentName, subjectId, StudySiteId, siteid, instanceId, InstanceName, InstanceRepeatNumber, folderid, Folder, FolderName, FolderSeq, TargetDays, DataPageId, DataPageName, PageRepeatNumber, RecordDate, RecordId, RecordPosition, MinCreated, MaxUpdated, SaveTS, StudyEnvSiteNumber, Subject, Site, SiteNumber, SiteGroup

**Clinical Data Columns (32):**

| Raw Column | Label | Sample Values | Maps To |
|-----------|-------|---------------|---------|
| Subject | Subject identifier | "01", "02", "05" | SUBJID (via combine -> USUBJID) |
| SiteNumber | Site number | "440", "010", "480" | SITEID |
| StudyEnvSiteNumber | Study-site number | "301-04401" | STUDYID extraction (prefix "301") |
| BRTHYR_RAW | Year of Birth (char) | "1960", "1975", "1983" | BRTHDTC (partial: year only) |
| BRTHYR_YYYY | Year of Birth (numeric) | 1960.0, 1975.0, 1983.0 | BRTHDTC (alternate source) |
| BRTHYR_MM | Birth month | all NaN | BRTHDTC (month component -- missing) |
| BRTHYR_DD | Birth day | all NaN | BRTHDTC (day component -- missing) |
| AGE | Age | 61.0, 46.0, 40.0 | AGE (direct, or derive from BRTHDTC + RFSTDTC) |
| SEX | Sex (display) | "Female", "Male" | Reference only |
| SEX_STD | Sex (coded) | "F", "M" | SEX (already CT submission values!) |
| ETHNIC | Ethnicity (display) | "Not Hispanic or Latino" | Reference only |
| ETHNIC_STD | Ethnicity (coded) | "NOT HISPANIC OR LATINO" | ETHNIC |
| RACEAME..RACENTRE | Race checkboxes | 0.0 or 1.0 each | RACE (combine: find which = 1) |
| DMCBP/DMCBP_STD | Childbearing status | "Post-menopausal" | SUPPDM (not a standard DM var) |
| HEIGHT/HEIGHT_RAW | Height | 155.0, 161.4, 183.0 | Not DM -- goes to VS domain |
| HEIGHT_UNITS | Height units | "cm" | Not DM -- goes to VS domain |
| AGE_CALCULATED | Calculated age | all NaN | Redundant with AGE |
| RecordDate | Visit date | datetime | DMDTC (date of collection) |

### Key DM Mapping Challenges in This Data

1. **RACE from checkboxes:** Race is stored as 6 binary columns (RACEAME, RACEASI, RACEBLA, RACENAT, RACEWHI, RACENTRE). Must be combined: find which column(s) = 1, map column label to CT submission value. If multiple = 1, use "MULTIPLE". All subjects here are WHITE only.

2. **BRTHDTC partial date:** Only birth YEAR is available (BRTHYR_YYYY). Month and day are NaN. Must produce partial ISO 8601: "1960" (year only).

3. **COUNTRY from IRT:** Country comes from irt.sas7bdat (SCOUNTRY), not dm.sas7bdat. Values are full names ("UNITED KINGDOM") that must map to ISO 3166-1 alpha-3 ("GBR").

4. **Reference dates from EX/IE/DS:** RFSTDTC, RFENDTC, RFICDTC, etc. all come from other datasets. The mapping spec must document these cross-domain derivations even though execution happens later.

5. **ARM is blinded:** IRT shows STRTG="Blinded" for all subjects. The mapping must handle this gracefully (ARM/ARMCD may be populated from unblinded data or left with ARMNRS="NOT ASSIGNED" if not yet unblinded).

6. **StudyEnvSiteNumber parsing:** Format "301-04401" contains STUDYID prefix "301" and a site-specific suffix. Need to parse for STUDYID and SITEID derivation.

## SDTM DM Domain Specification (27 variables)

### Required Variables (must be present)

| Variable | Label | Type | CT Codelist |
|----------|-------|------|-------------|
| STUDYID | Study Identifier | Char | - |
| DOMAIN | Domain Abbreviation | Char | C66734 |
| USUBJID | Unique Subject Identifier | Char | - |
| SUBJID | Subject Identifier for the Study | Char | - |
| SITEID | Study Site Identifier | Char | - |
| SEX | Sex | Char | C66731 (non-extensible) |
| COUNTRY | Country | Char | ISO3166 |

### Expected Variables (should be present if data collected)

| Variable | Label | Type | CT Codelist | Source in Fakedata |
|----------|-------|------|-------------|-------------------|
| RFSTDTC | Subject Reference Start Date/Time | Char | - | ex.sas7bdat min(EXDAT) |
| RFENDTC | Subject Reference End Date/Time | Char | - | ex.sas7bdat max(EXDAT) |
| RFXSTDTC | Date/Time of First Study Treatment | Char | - | ex.sas7bdat |
| RFXENDTC | Date/Time of Last Study Treatment | Char | - | ex.sas7bdat |
| RFICDTC | Date/Time of Informed Consent | Char | - | ie.sas7bdat ICDAT |
| RFPENDTC | Date/Time of End of Participation | Char | - | ds.sas7bdat |
| DTHDTC | Date/Time of Death | Char | - | ae/ds if applicable |
| DTHFL | Subject Death Flag | Char | C66742 (non-ext) | Y/null |
| AGE | Age | Num | - | dm.sas7bdat AGE |
| AGEU | Age Units | Char | C66781 (non-ext) | Assign "YEARS" |
| RACE | Race | Char | C74457 (extensible) | dm.sas7bdat RACE* checkboxes |
| ARMCD | Planned Arm Code | Char | - | irt.sas7bdat |
| ARM | Description of Planned Arm | Char | - | irt.sas7bdat |
| ACTARMCD | Actual Arm Code | Char | - | irt.sas7bdat |
| ACTARM | Description of Actual Arm | Char | - | irt.sas7bdat |
| ARMNRS | Reason Arm is Null | Char | - | If blinded |

### Permissible Variables

| Variable | Label | Type | CT Codelist |
|----------|-------|------|-------------|
| BRTHDTC | Date/Time of Birth | Char | - |
| ETHNIC | Ethnicity | Char | C66790 (non-ext) |
| DMDTC | Date/Time of Collection | Char | - |
| DMDY | Study Day of Collection | Num | - |

## Mapping Spec Data Models (Pydantic)

### Core Output Models

```python
from enum import Enum
from pydantic import BaseModel, Field

class MappingPattern(str, Enum):
    """The 9 mapping patterns from requirements."""
    ASSIGN = "assign"           # Constant value
    DIRECT = "direct"           # Same name, same content
    RENAME = "rename"           # Different name, same content
    REFORMAT = "reformat"       # Same value, different representation
    SPLIT = "split"             # One source -> multiple targets
    COMBINE = "combine"         # Multiple sources -> one target
    DERIVATION = "derivation"   # Calculated field
    LOOKUP_RECODE = "lookup_recode"  # Map to CT terms
    TRANSPOSE = "transpose"     # Wide -> tall (Findings)

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"       # >0.85 - Direct match or well-established pattern
    MEDIUM = "MEDIUM"   # 0.6-0.85 - Reasonable inference, some ambiguity
    LOW = "LOW"         # <0.6 - Uncertain, needs human review

class VariableMapping(BaseModel):
    """Mapping specification for a single SDTM variable."""
    sdtm_variable: str = Field(..., description="Target SDTM variable name")
    sdtm_label: str = Field(..., description="SDTM variable label")
    sdtm_data_type: str = Field(..., description="'Char' or 'Num'")
    core: str = Field(..., description="Req/Exp/Perm")

    # Source
    source_dataset: str | None = Field(None, description="Source SAS file")
    source_variable: str | None = Field(None, description="Source column name")
    source_label: str | None = Field(None, description="Source column label")

    # Mapping logic
    mapping_pattern: MappingPattern
    mapping_logic: str = Field(..., description="Human-readable description of the mapping")
    derivation_rule: str | None = Field(
        None, description="Executable derivation pseudo-code for derived variables"
    )
    assigned_value: str | None = Field(
        None, description="For ASSIGN pattern: the constant value"
    )

    # CT
    codelist_code: str | None = Field(None, description="CT codelist code if applicable")
    codelist_name: str | None = Field(None, description="CT codelist name")

    # Confidence
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    confidence_rationale: str = Field(
        ..., description="Why this confidence level was assigned"
    )

    # Notes
    notes: str = Field(default="", description="Additional mapping notes")


class DomainMappingSpec(BaseModel):
    """Complete mapping specification for one SDTM domain."""
    domain: str
    domain_label: str
    domain_class: str
    structure: str

    study_id: str
    source_datasets: list[str]
    cross_domain_sources: list[str] = Field(
        default_factory=list,
        description="Datasets from other domains contributing variables"
    )

    variable_mappings: list[VariableMapping]

    # Summary
    total_variables: int
    required_mapped: int
    expected_mapped: int
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int

    # Metadata
    mapping_timestamp: str
    model_used: str
    unmapped_source_variables: list[str] = Field(
        default_factory=list,
        description="Source variables not mapped to any SDTM target"
    )
    suppqual_candidates: list[str] = Field(
        default_factory=list,
        description="Source variables that may belong in SUPPDM"
    )
```

### LLM Output Schema (What Claude Returns)

The LLM should NOT return the full `DomainMappingSpec`. It should return a simpler proposal that the engine enriches:

```python
class VariableMappingProposal(BaseModel):
    """What the LLM proposes for one variable."""
    sdtm_variable: str
    source_dataset: str | None
    source_variable: str | None
    mapping_pattern: MappingPattern
    mapping_logic: str
    derivation_rule: str | None = None
    assigned_value: str | None = None
    codelist_code: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str

class DomainMappingProposal(BaseModel):
    """Complete LLM proposal for a domain (tool-use output schema)."""
    domain: str
    variable_proposals: list[VariableMappingProposal]
    unmapped_source_variables: list[str]
    suppqual_candidates: list[str]
    mapping_notes: str
```

The engine then:
1. Validates each proposal against SDTM-IG (variable exists, correct type)
2. Validates CT terms against CTReference
3. Enriches with SDTM-IG labels, core designations, codelist names
4. Computes confidence levels from numeric scores
5. Produces the full `DomainMappingSpec`

## LLM Agent Structure

### System Prompt Design

The system prompt should:
1. Define the role (SDTM mapping specialist)
2. Explain the 9 mapping patterns with examples
3. Set expectations for structured output
4. Emphasize: propose WHAT, not execute HOW

### Tool Definitions for the Mapper Agent

Rather than stuffing everything into the prompt, provide reference data as tool calls the LLM can invoke:

```python
tools = [
    # Primary output tool (forced via tool_choice)
    {
        "name": "propose_domain_mapping",
        "description": "Propose variable-level mappings for an SDTM domain",
        "input_schema": DomainMappingProposal.model_json_schema()
    },
]
```

However, since `AstraeaLLMClient.parse()` already forces a single tool output, the approach should be:
1. Put ALL context (domain spec, profiles, eCRF, CT summaries) into the user message
2. Use `parse()` with `DomainMappingProposal` as `output_format`
3. The context is structured enough that it fits in one call for DM

### Prompt Template (DM-specific context)

```
You are an SDTM mapping specialist. Given raw clinical data metadata, eCRF form
definitions, and the SDTM-IG domain specification, propose a complete variable-level
mapping specification for the {domain} domain.

## SDTM Domain: {domain} ({domain_label})
Structure: {structure}
Class: {domain_class}

### Required Variables:
{for each Req variable: name, label, type, codelist}

### Expected Variables:
{for each Exp variable: name, label, type, codelist}

### Permissible Variables:
{for each Perm variable: name, label, type, codelist}

## Source Data: {dataset_filename}
{row_count} subjects, {clinical_var_count} clinical variables

### Clinical Variables:
{for each non-EDC variable: name, label, dtype, n_unique, n_missing, sample_values}

## eCRF Form: {form_name}
{for each field: field_name, data_type, sas_label, coded_values}

## Cross-Domain Sources Available:
- ex.sas7bdat: First/last dose dates (for RFSTDTC, RFENDTC, RFXSTDTC, RFXENDTC)
- ie.sas7bdat: Informed consent date (for RFICDTC)
- irt.sas7bdat: Country, treatment arm (for COUNTRY, ARM, ARMCD)
- ds.sas7bdat: Disposition (for RFPENDTC)

## Controlled Terminology:
{for each relevant codelist: code, name, extensible, all submission values}

## Study Metadata:
Study ID: PHA022121-C301
Site numbering: StudyEnvSiteNumber format "301-SSSNN" (e.g., "301-04401")

## Instructions:
1. Map every Required and Expected SDTM variable
2. Map Permissible variables if source data supports them
3. For each mapping, specify the pattern, source, logic, and confidence
4. Identify source variables that don't map to any standard DM variable (suppqual_candidates)
5. For cross-domain derivations, describe the logic but note the source dataset
6. Confidence: 0.9+ for direct/obvious mappings, 0.7-0.9 for reasonable inference, <0.7 for uncertain
```

### Temperature and Model

Per project rules:
- **Model:** `claude-sonnet-4-20250514` for initial implementation (faster iteration), upgrade to opus for production quality
- **Temperature:** 0.1 for direct/rename mappings, 0.2 for derivations (use 0.1 as default since AstraeaLLMClient already defaults to this)
- **Max tokens:** 4096 should be sufficient for DM (27 variables)

## Executable Transformation Generation

### What This Means

For each mapping pattern, the `derivation_rule` field should contain a standardized pseudo-code that can be interpreted by a deterministic execution engine (built in Phase 4+).

### Transformation Registry Pattern

```python
# Each mapping pattern has a registered handler
TRANSFORM_REGISTRY = {
    MappingPattern.ASSIGN: AssignTransform,
    MappingPattern.DIRECT: DirectCopyTransform,
    MappingPattern.RENAME: RenameTransform,
    MappingPattern.REFORMAT: ReformatTransform,
    MappingPattern.COMBINE: CombineTransform,
    MappingPattern.DERIVATION: DerivationTransform,
    MappingPattern.LOOKUP_RECODE: LookupRecodeTransform,
}
```

### Derivation Rule Pseudo-Code Format

For MAP-12 (natural language to executable), the mapping spec should include standardized derivation rules:

```
# ASSIGN
STUDYID: ASSIGN("PHA022121-C301")
DOMAIN: ASSIGN("DM")

# DIRECT
AGE: DIRECT(dm.AGE)

# RENAME
SEX: RENAME(dm.SEX_STD)

# REFORMAT
BRTHDTC: PARTIAL_ISO8601(year=dm.BRTHYR_YYYY, month=dm.BRTHYR_MM, day=dm.BRTHYR_DD)

# COMBINE
USUBJID: CONCAT(STUDYID, "-", dm.StudyEnvSiteNumber[-5:], "-", dm.Subject)

# DERIVATION (cross-domain)
RFSTDTC: ISO8601(MIN(ex.EXDAT WHERE ex.EXYN == "Yes" AND ex.subject == dm.Subject))
RFICDTC: ISO8601(ie.ICDAT WHERE ie.Subject == dm.Subject) [join on Subject]

# LOOKUP_RECODE
ETHNIC: CODELIST_LOOKUP(dm.ETHNIC_STD, C66790)
RACE: RACE_CHECKBOX(dm.RACEAME=>"AMERICAN INDIAN OR ALASKA NATIVE", dm.RACEWHI=>"WHITE", ..., multi=>"MULTIPLE")
COUNTRY: COUNTRY_MAP(irt.SCOUNTRY, {"UNITED KINGDOM":"GBR","CANADA":"CAN","POLAND":"POL"})

# ATTRIBUTE
All: SET_LABEL(variable, sdtm_label), SET_TYPE(variable, sdtm_type)
```

This pseudo-code is NOT Python -- it is a DSL that the future execution engine interprets. For Phase 3, we just need to produce it consistently. Execution is Phase 4+.

## Excel/JSON Output Format

### Excel Workbook Structure

Use openpyxl to create a mapping specification workbook with standard industry layout:

**Sheet 1: "Mapping Spec"**

| Column | Content |
|--------|---------|
| A | Row # |
| B | SDTM Variable |
| C | SDTM Label |
| D | SDTM Type |
| E | Core (Req/Exp/Perm) |
| F | Source Dataset |
| G | Source Variable |
| H | Source Label |
| I | Mapping Pattern |
| J | Mapping Logic |
| K | Derivation Rule |
| L | CT Codelist |
| M | Confidence |
| N | Confidence Level |
| O | Notes |

**Sheet 2: "Unmapped Variables"**

| Column | Content |
|--------|---------|
| A | Source Dataset |
| B | Source Variable |
| C | Source Label |
| D | Disposition (SUPPDM candidate / Not applicable / Excluded) |

**Sheet 3: "Summary"**

- Domain, study, date
- Total variables mapped
- Confidence distribution
- Cross-domain dependencies
- Validation issues

### JSON Output

The `DomainMappingSpec` Pydantic model serializes directly to JSON via `model_dump_json(indent=2)`. Store alongside Excel at a configured output path.

## Confidence Scoring

### Scoring Rules

| Scenario | Score Range | Level |
|----------|-----------|-------|
| Direct match: same variable name, same content | 0.95-1.0 | HIGH |
| Rename with _STD suffix matching CT exactly | 0.90-0.95 | HIGH |
| Well-known derivation (USUBJID, AGE) | 0.85-0.95 | HIGH |
| Cross-domain derivation with clear source | 0.70-0.85 | MEDIUM |
| CT recode with clear mapping | 0.80-0.90 | HIGH |
| Race checkbox combination | 0.75-0.85 | MEDIUM |
| Partial date from incomplete components | 0.70-0.80 | MEDIUM |
| Country name to ISO 3166 mapping | 0.75-0.85 | MEDIUM |
| Blinded ARM data | 0.60-0.70 | MEDIUM |
| No clear source identified | 0.30-0.50 | LOW |
| LLM proposed but CT validation failed | 0.20-0.40 | LOW |

### Post-LLM Confidence Adjustments

The engine should adjust LLM-provided confidence:
- **Upgrade:** If CT validation passes on a lookup_recode, add +0.05
- **Downgrade:** If proposed CT term not in codelist, reduce to max 0.4
- **Downgrade:** If proposed source variable not found in profile, reduce to 0.3
- **Flag:** If Req variable has confidence < 0.7, flag for mandatory human review

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Excel output | Custom XML/CSV writer | openpyxl (already installed) | Handles formatting, multiple sheets, styles |
| CT validation | String matching in LLM | CTReference.validate_term() | Deterministic, exact match, already built |
| Date formatting | LLM-generated date strings | transforms/dates.py functions | Already tested with 80 tests, handles all edge cases |
| USUBJID generation | LLM string concatenation | transforms/usubjid.py | NaN-safe, validated, 258 lines of tested code |
| SDTM variable lookup | LLM memory of SDTM-IG | SDTMReference.get_domain_spec() | Authoritative, bundled JSON, already tested |
| ISO country codes | LLM guessing | Deterministic lookup table | 249 countries, exact mapping needed |

## Common Pitfalls

### Pitfall 1: Race Checkbox Combination Logic

**What goes wrong:** The LLM proposes mapping RACEWHI directly to RACE. But RACE in SDTM is a single text value ("WHITE"), not a number (1.0). And if multiple race checkboxes are checked, the value should be "MULTIPLE". If none are checked, it could be "UNKNOWN" or "NOT REPORTED".

**Why it happens:** The raw data stores race as 6 binary columns, which is unusual. The LLM may not handle the multi-select logic correctly.

**How to avoid:** The derivation rule must explicitly define the combination logic: iterate all RACE* columns, collect labels where value=1, if count=0 use "NOT REPORTED", if count=1 use the race value, if count>1 use "MULTIPLE".

### Pitfall 2: SEX Codelist Mismatch

**What goes wrong:** The raw data has SEX_STD values "F" and "M" which ARE valid CT submission values. But the raw SEX column has "Female" and "Male" which are NOT submission values. The LLM might map the wrong column.

**How to avoid:** Always map from the _STD (coded) column when available. The engine should prefer _STD columns for any variable with a codelist.

### Pitfall 3: BRTHDTC with Missing Components

**What goes wrong:** Only BRTHYR_YYYY is populated (1960, 1975, 1983). BRTHYR_MM and BRTHYR_DD are all NaN. The LLM might generate "1960-01-01" (imputing missing components) instead of the correct partial date "1960".

**How to avoid:** Use the existing `format_partial_iso8601(year=1960, month=None, day=None)` which correctly produces "1960". The derivation rule must explicitly use partial date logic.

### Pitfall 4: StudyEnvSiteNumber Parsing for STUDYID

**What goes wrong:** StudyEnvSiteNumber is "301-04401". STUDYID should be "PHA022121-C301" (the protocol number), NOT "301" (the study number prefix). SITEID should be derived from SiteNumber ("440") not from parsing StudyEnvSiteNumber.

**How to avoid:** STUDYID is typically a constant for the entire study, assigned from study metadata. The mapping should use ASSIGN with the protocol study ID, not parse it from data. SITEID comes from SiteNumber column.

### Pitfall 5: Cross-Domain Join Keys

**What goes wrong:** DM has Subject="01", EX has subject="02", IE has no Subject column but matches by subjectId (EDC internal ID). Joining across datasets on the wrong key produces incorrect reference dates.

**How to avoid:** The mapping spec should document the join key for each cross-domain source. In this data, Subject is the common key across dm, ex, ie, irt, ds datasets. The execution engine (Phase 4) handles the actual join.

### Pitfall 6: Blinded ARM Data

**What goes wrong:** IRT shows STRTG="Blinded" for all subjects. The LLM might try to guess the arm or leave ARM/ARMCD blank. SDTM requires either populated ARM values or ARMNRS explaining why they are null.

**How to avoid:** If arm data is blinded, set ARMNRS to a coded reason (e.g., "UNBLINDED DATA NOT YET AVAILABLE") and leave ARM/ARMCD/ACTARM/ACTARMCD as null. Document this in mapping notes.

## Code Examples

### MappingEngine Core Flow

```python
class MappingEngine:
    """Orchestrates LLM-based SDTM domain mapping."""

    def __init__(
        self,
        llm_client: AstraeaLLMClient,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ):
        self._llm = llm_client
        self._sdtm = sdtm_ref
        self._ct = ct_ref

    def map_domain(
        self,
        domain: str,
        source_profiles: list[DatasetProfile],
        ecrf_forms: list[ECRFForm],
        study_metadata: StudyMetadata,
        cross_domain_profiles: dict[str, DatasetProfile] | None = None,
    ) -> DomainMappingSpec:
        # 1. Get SDTM domain spec
        domain_spec = self._sdtm.get_domain_spec(domain)

        # 2. Build context
        context = self._build_context(
            domain_spec, source_profiles, ecrf_forms,
            study_metadata, cross_domain_profiles
        )

        # 3. Call LLM
        proposal = self._llm.parse(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": context}],
            system=MAPPING_SYSTEM_PROMPT,
            output_format=DomainMappingProposal,
            temperature=0.1,
            max_tokens=4096,
        )

        # 4. Validate and enrich
        spec = self._validate_and_enrich(proposal, domain_spec)

        return spec
```

### Race Checkbox Combination

```python
def derive_race_from_checkboxes(
    row: pd.Series,
    race_columns: dict[str, str],  # col_name -> CT submission value
) -> str:
    """Combine race checkbox columns into SDTM RACE value.

    race_columns example:
        {"RACEAME": "AMERICAN INDIAN OR ALASKA NATIVE",
         "RACEASI": "ASIAN", "RACEBLA": "BLACK OR AFRICAN AMERICAN",
         "RACENAT": "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
         "RACEWHI": "WHITE", "RACENTRE": "NOT REPORTED"}
    """
    selected = []
    for col, ct_value in race_columns.items():
        val = row.get(col)
        if val is not None and float(val) == 1.0:
            selected.append(ct_value)

    if len(selected) == 0:
        return "NOT REPORTED"
    elif len(selected) == 1:
        return selected[0]
    else:
        return "MULTIPLE"
```

### Post-Proposal CT Validation

```python
def validate_ct_terms(
    proposal: DomainMappingProposal,
    ct_ref: CTReference,
) -> list[str]:
    """Validate all proposed CT terms against reference data."""
    issues = []
    for vm in proposal.variable_proposals:
        if vm.codelist_code:
            codelist = ct_ref.lookup_codelist(vm.codelist_code)
            if codelist is None:
                issues.append(
                    f"{vm.sdtm_variable}: codelist {vm.codelist_code} not found"
                )
            elif vm.assigned_value and not codelist.extensible:
                if vm.assigned_value not in codelist.terms:
                    issues.append(
                        f"{vm.sdtm_variable}: value '{vm.assigned_value}' "
                        f"not in non-extensible codelist {vm.codelist_code}"
                    )
    return issues
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual mapping specs in Excel | LLM-proposed with human review | 2024-2025 | 80% reduction in initial mapping time |
| Keyword matching for variable mapping | Semantic understanding via LLM | 2024 | Handles non-obvious mappings |
| One mapping call per variable | Batch proposal per domain | Standard | Fewer API calls, coherent cross-variable logic |
| Free-text LLM output | Structured output via tool use | 2024 | Guaranteed schema compliance |

## Open Questions

1. **STUDYID source:** The raw data does not have an explicit STUDYID column with the protocol number "PHA022121-C301". It only has StudyEnvSiteNumber prefix "301". Should STUDYID be a configuration parameter passed to the mapping engine, or should the LLM infer it from the data?
   - **Recommendation:** STUDYID should be part of `StudyMetadata` configuration, not LLM-inferred. It is a study-level constant.

2. **Cross-domain execution scope:** Phase 3 produces the mapping SPECIFICATION. Should it also produce a "data requirements" manifest listing exactly which columns from which datasets are needed for execution?
   - **Recommendation:** Yes. The spec should include a `data_requirements` section listing required joins. This makes Phase 4 execution straightforward.

3. **SUPPDM candidates:** DMCBP (Childbearing Status) is not a standard DM variable. Should the mapping engine automatically route non-standard variables to SUPPDM, or flag them for human decision?
   - **Recommendation:** Flag as suppqual_candidates. Do not auto-create SUPPDM in Phase 3. SUPPQUAL generation is a Phase 5+ concern (per PITFALLS.md C4).

4. **Excel formatting:** Should the Excel spec use conditional formatting (red for LOW confidence, green for HIGH)?
   - **Recommendation:** Yes, minimal formatting. Color-code confidence levels. This makes human review faster.

## Sources

### Primary (HIGH confidence)
- Actual dm.sas7bdat data profiling (3 subjects, 61 columns) -- direct analysis
- Actual ex.sas7bdat, ie.sas7bdat, irt.sas7bdat, ds.sas7bdat data -- direct analysis
- SDTMReference.get_domain_spec('DM') -- bundled SDTM-IG v3.4 JSON (27 variables)
- CTReference codelists: C66731 (Sex), C74457 (Race), C66790 (Ethnicity), C66781 (Age Unit), C66742 (No/Yes)
- Existing codebase: AstraeaLLMClient, transforms/dates.py, transforms/usubjid.py, models/*

### Secondary (MEDIUM confidence)
- ARCHITECTURE.md component boundaries and data flow patterns
- PITFALLS.md C1 (hallucination cascading), C2 (CT misapplication), C5 (non-determinism)
- STACK.md technology choices (all already installed)

### Tertiary (LOW confidence)
- Excel formatting best practices (general industry knowledge)
- Derivation pseudo-code DSL design (no established standard; custom design)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and tested
- Architecture: HIGH - follows established patterns from ARCHITECTURE.md, proven by Phase 2 LLM client
- DM data analysis: HIGH - directly profiled actual Fakedata
- Mapping spec models: HIGH - based on SDTM-IG v3.4 spec + actual data analysis
- LLM prompt design: MEDIUM - follows AstraeaLLMClient pattern, but prompt tuning will need iteration
- Confidence scoring: MEDIUM - thresholds are initial estimates, will calibrate during testing
- Excel format: MEDIUM - standard industry layout, openpyxl already available

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable -- SDTM-IG v3.4 does not change)
