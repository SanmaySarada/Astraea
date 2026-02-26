# Architecture Patterns

**Domain:** Agentic SDTM Mapping System (Clinical Data Standardization)
**Researched:** 2026-02-26

## Recommended Architecture

### High-Level: LangGraph StateGraph with Shared State

Use a **LangGraph StateGraph** as the orchestration backbone. Each specialized agent is a node in the graph. All nodes read from and write to a shared `TypedDict` state object. The orchestrator controls flow via conditional edges. Human review is implemented as LangGraph interrupts (built-in HITL support).

**Why LangGraph over alternatives:**
- **vs. AutoGen**: AutoGen is conversation-centric (agents chat with each other). SDTM mapping is a pipeline, not a conversation. LangGraph's graph-based flow maps naturally to sequential/branching pipelines with conditional routing.
- **vs. CrewAI**: CrewAI abstracts away control flow. SDTM mapping needs deterministic sequencing (you must parse before you classify, classify before you map). LangGraph gives explicit control.
- **vs. raw Claude API**: You lose persistence, checkpointing, HITL interrupts, and state management. You'd rebuild half of LangGraph yourself.
- **vs. DSPy**: DSPy is excellent for prompt optimization (and should be used for that purpose), but it is not an orchestration framework. Use DSPy modules inside LangGraph nodes.

**Confidence: HIGH** - LangGraph's StateGraph with shared state is the standard pattern for deterministic multi-step agent pipelines in 2025-2026. Well-documented, production-ready checkpointers exist (SQLite for dev, Postgres for prod).

```
                     +------------------+
                     |   CLI Entrypoint |
                     +--------+---------+
                              |
                     +--------v---------+
                     |   Orchestrator   |
                     |  (LangGraph      |
                     |   StateGraph)    |
                     +--------+---------+
                              |
          +-------------------+-------------------+
          |                   |                   |
+---------v------+  +---------v------+  +---------v------+
| 1. Parser      |  | 2. Domain      |  | 3. Mapper      |
|    Agent       |->|    Classifier  |->|    Agent       |
| (eCRF + SAS)   |  |    Agent       |  | (per domain)   |
+----------------+  +----------------+  +--------+-------+
                                                 |
                              +------------------+
                              |
                    +---------v------+
                    | 4. Derivation  |
                    |    Agent       |
                    +--------+-------+
                              |
                    +---------v------+
                    | 5. Validator   |
                    |  (Deterministic|
                    |   Rules)       |
                    +--------+-------+
                              |
                    +---------v------+
                    | 6. Human       |
                    |    Review Gate |
                    | (LangGraph     |
                    |  Interrupt)    |
                    +--------+-------+
                              |
                    +---------v------+
                    | 7. Dataset     |
                    |    Generator   |
                    | (pandas + xpt) |
                    +----------------+
```

---

## Component Boundaries

### Component 1: Parser Agent

**Responsibility:** Extract structured metadata from raw inputs (eCRF PDF + SAS files).

| Input | Output | LLM Required? |
|-------|--------|---------------|
| eCRF PDF/text | Structured form metadata (fields, types, labels, coded values, OIDs) per form | YES - LLM parses semi-structured PDF text into structured JSON |
| SAS .sas7bdat files | DataFrame profiles (variable names, types, labels, sample values, distributions) | NO - pyreadstat + pandas, deterministic |

**Boundary:** This agent does NOT classify or map. It only extracts and profiles. Its output is a standardized metadata schema that downstream agents consume.

**Key design decision:** eCRF parsing should happen once per study and be cached. The parsed eCRF metadata is a reusable artifact. SAS profiling also runs once and caches.

**Data structure produced:**
```python
@dataclass
class ECRFForm:
    form_name: str           # e.g., "Demographics"
    fields: list[ECRFField]  # structured field definitions

@dataclass
class ECRFField:
    field_name: str          # e.g., "BRTHDAT"
    data_type: str           # e.g., "$25", "1", "date"
    sas_label: str           # e.g., "Date of Birth"
    units: str | None
    coded_values: dict[str, str] | None  # code -> decode
    field_oid: str

@dataclass
class RawDatasetProfile:
    filename: str            # e.g., "ae.sas7bdat"
    variables: list[VariableProfile]
    row_count: int

@dataclass
class VariableProfile:
    name: str               # e.g., "AETERM"
    dtype: str              # numeric, character
    sas_label: str          # from SAS metadata
    n_unique: int
    n_missing: int
    sample_values: list[str]  # first 10 unique values
```

### Component 2: Domain Classifier Agent

**Responsibility:** Classify each raw SAS dataset to one or more SDTM domains.

| Input | Output | LLM Required? |
|-------|--------|---------------|
| RawDatasetProfile + ECRFForm associations | Domain classification (e.g., ae.sas7bdat -> AE, lb_biochem.sas7bdat -> LB) | YES - semantic matching |

**Boundary:** This agent classifies datasets, not variables. It determines "this raw file maps to SDTM domain X." Variable-level mapping is the Mapper Agent's job.

**Key complexity:** Some raw datasets map to multiple domains (e.g., dm.sas7bdat might contribute to DM + SUPPDM). Some domains require merging multiple raw datasets (e.g., all lb_* files -> LB domain). The classifier must output a many-to-many mapping.

**Data structure produced:**
```python
@dataclass
class DomainClassification:
    raw_dataset: str                    # e.g., "ae.sas7bdat"
    primary_domain: str                 # e.g., "AE"
    secondary_domains: list[str]        # e.g., ["SUPPAE"]
    confidence: float                   # 0.0 - 1.0
    rationale: str                      # LLM explanation

@dataclass
class DomainPlan:
    domain: str                         # e.g., "LB"
    source_datasets: list[str]          # e.g., ["lb_biochem", "lb_hem", ...]
    mapping_pattern: str                # "direct", "merge", "transpose"
    notes: str
```

### Component 3: Mapper Agent (per domain)

**Responsibility:** For each SDTM domain, propose variable-level mappings from raw source variables to SDTM target variables.

| Input | Output | LLM Required? |
|-------|--------|---------------|
| DomainPlan + RawDatasetProfile + ECRFForm + SDTM-IG domain spec + CT codelists | Variable mapping specification | YES - core LLM reasoning task |

**Boundary:** This is the highest-value LLM component. It proposes mappings but does NOT execute them. It produces a specification document, not transformed data.

**This agent must handle 5 mapping patterns:**
1. **Direct carry** - raw variable maps straight to SDTM (e.g., SUBJID -> USUBJID after prefixing)
2. **Rename** - same data, different variable name (e.g., SEX -> SEX, but with CT mapping)
3. **Transpose** - horizontal raw layout to vertical SDTM (e.g., wide lab results -> tall LB domain)
4. **Derivation** - calculated field (e.g., AGE from BRTHDAT and RFSTDTC)
5. **Merge** - combine multiple source datasets into one SDTM domain

**Data structure produced:**
```python
@dataclass
class VariableMapping:
    sdtm_variable: str          # target, e.g., "AEDECOD"
    sdtm_label: str             # e.g., "Dictionary-Derived Term"
    source_variable: str | None # raw source, e.g., "AETERM"
    source_dataset: str | None  # e.g., "ae.sas7bdat"
    mapping_type: str           # "direct", "rename", "transpose", "derive", "merge", "assign"
    mapping_logic: str          # human-readable description
    ct_codelist: str | None     # e.g., "C66729" (MedDRA)
    derivation_rule: str | None # for derived variables
    confidence: float
    notes: str

@dataclass
class DomainMappingSpec:
    domain: str
    domain_label: str
    key_variables: list[str]
    variable_mappings: list[VariableMapping]
    source_datasets: list[str]
    mapping_notes: str
```

### Component 4: Derivation Agent

**Responsibility:** Handle complex derivations that require programmatic logic -- date conversions, transposes, merges, calculated fields.

| Input | Output | LLM Required? |
|-------|--------|---------------|
| DomainMappingSpec (approved) + raw DataFrames | Derivation code/logic per variable | PARTIAL - LLM generates derivation logic, execution is deterministic |

**Boundary:** This agent takes approved mapping specs and produces executable transformation logic. It bridges the gap between "what to do" (mapping spec) and "how to do it" (pandas code/logic).

**Key derivations:**
- ISO 8601 date/time conversion (SAS dates -> ISO format)
- Horizontal-to-vertical transpose (wide lab data -> tall SDTM)
- USUBJID construction (STUDYID + SITEID + SUBJID)
- --DY calculation (study day from reference date)
- CT codelist application (raw values -> controlled terminology)

**Design option:** This could be an LLM that generates Python/pandas code, or a rule-based engine with LLM fallback. Recommend **hybrid**: deterministic rules for known patterns (ISO dates, USUBJID, --DY), LLM-generated code for novel derivations.

### Component 5: Validator Agent

**Responsibility:** Run P21-style conformance checks on the proposed mapping spec and generated datasets.

| Input | Output | LLM Required? |
|-------|--------|---------------|
| DomainMappingSpec + generated DataFrames | Validation report (errors, warnings) | NO - deterministic rule engine |

**Boundary:** This is NOT an LLM agent. It is a deterministic rule engine. Validation rules are codified from SDTM-IG and P21 specifications. LLM judgment has no place in conformance checking.

**Validation categories:**
- Required variables present
- Variable types match SDTM-IG specification
- Controlled terminology values valid
- Date formats ISO 8601 compliant
- USUBJID format correct
- Domain-specific business rules (e.g., AESTDTC <= AEENDTC)
- Cross-domain consistency (e.g., all USUBJIDs in DM)

**Data structure produced:**
```python
@dataclass
class ValidationIssue:
    severity: str           # "ERROR", "WARNING", "NOTE"
    rule_id: str            # e.g., "SD0001"
    domain: str
    variable: str | None
    message: str
    affected_rows: int | None

@dataclass
class ValidationReport:
    domain: str
    issues: list[ValidationIssue]
    error_count: int
    warning_count: int
    pass_rate: float        # percentage of rules passed
```

### Component 6: Human Review Gate

**Responsibility:** Present mapping specifications to human reviewer, capture approvals and corrections.

| Input | Output | LLM Required? |
|-------|--------|---------------|
| DomainMappingSpec + ValidationReport | Approved/corrected mapping spec | NO - human interaction |

**Boundary:** This is the critical quality gate. The system pauses (LangGraph interrupt), presents the mapping spec in a readable format (CLI table/JSON), and waits for human action: approve, reject, or correct individual mappings.

**Implementation:** LangGraph's built-in interrupt mechanism. When the graph reaches the review node, it saves state via checkpoint and halts. The CLI resumes from the checkpoint when the human provides input.

**Key design principle:** The review interface must be domain-expert-friendly. Statistical programmers review mappings, not AI engineers. Output format should resemble traditional mapping specification documents they already use.

**Correction capture:**
```python
@dataclass
class HumanCorrection:
    domain: str
    sdtm_variable: str
    original_mapping: VariableMapping
    corrected_mapping: VariableMapping
    correction_type: str    # "source_change", "logic_change", "ct_change", "reject", "add"
    reason: str             # human explanation
    timestamp: str
    reviewer: str
```

### Component 7: Dataset Generator

**Responsibility:** Execute approved mapping specifications to produce final SDTM .xpt files.

| Input | Output | LLM Required? |
|-------|--------|---------------|
| Approved DomainMappingSpec + raw DataFrames | SDTM .xpt files | NO - deterministic pandas execution |

**Boundary:** This is pure data engineering. No LLM involved. Takes the approved mapping spec, applies transformations using pandas, and writes .xpt files using pyreadstat.

---

## Data Flow

### Stage-by-Stage Data Transformation

```
Stage 1: INPUT
  Raw SAS files (.sas7bdat) + eCRF PDF

Stage 2: PARSING (Parser Agent)
  -> list[ECRFForm] + list[RawDatasetProfile]
  Cached per study. Run once.

Stage 3: CLASSIFICATION (Domain Classifier Agent)
  -> list[DomainClassification] + list[DomainPlan]
  Maps raw datasets to SDTM domains.

Stage 4: MAPPING (Mapper Agent, per domain)
  -> list[DomainMappingSpec]
  Variable-level mapping proposals. Core LLM work.

Stage 5: VALIDATION (Validator)
  -> list[ValidationReport]
  Conformance check on proposed mappings.

Stage 6: HUMAN REVIEW (Review Gate)
  -> list[DomainMappingSpec] (approved/corrected)
  + list[HumanCorrection] (captured for learning)
  LangGraph interrupt. CLI pauses here.

Stage 7: DERIVATION EXECUTION (Derivation Agent)
  -> list[pd.DataFrame] (transformed SDTM data)
  Applies approved mapping logic.

Stage 8: FINAL VALIDATION (Validator, round 2)
  -> list[ValidationReport] on actual data
  Validates generated datasets, not just specs.

Stage 9: OUTPUT (Dataset Generator)
  -> .xpt files + define.xml metadata
```

### Shared State Schema (LangGraph TypedDict)

```python
from typing import TypedDict, Annotated
from operator import add

class AstraeaState(TypedDict):
    # Input paths
    raw_data_dir: str
    ecrf_path: str
    output_dir: str

    # Stage 2: Parsed metadata
    ecrf_forms: list[ECRFForm]
    dataset_profiles: list[RawDatasetProfile]

    # Stage 3: Classification
    domain_classifications: list[DomainClassification]
    domain_plans: list[DomainPlan]

    # Stage 4: Mapping specs (accumulated per domain)
    mapping_specs: Annotated[list[DomainMappingSpec], add]

    # Stage 5: Validation
    validation_reports: Annotated[list[ValidationReport], add]

    # Stage 6: Human review
    approved_specs: list[DomainMappingSpec]
    corrections: Annotated[list[HumanCorrection], add]

    # Stage 7-8: Generated data
    generated_datasets: dict[str, str]  # domain -> file path
    final_validation: list[ValidationReport]

    # Control flow
    current_domain_index: int
    domains_to_process: list[str]
    status: str  # "parsing", "classifying", "mapping", "reviewing", etc.
    errors: Annotated[list[str], add]
```

---

## Context Management Strategy

### The Problem

SDTM mapping requires feeding agents large reference materials:
- SDTM Implementation Guide (~300 pages)
- NCI Controlled Terminology (~50+ codelists, thousands of terms)
- eCRF metadata (189 pages for this study)
- Raw dataset profiles (36 datasets)

This exceeds any practical context window, especially when you need domain-specific subsets.

### Recommended Approach: Tool-Based Lookup (not RAG)

**Use structured tool calls, not vector-search RAG.** Here is why:

1. **SDTM-IG rules are structured, not unstructured.** Each domain has a specific variable list with defined types, labels, and rules. This is a lookup table, not free text. Store as JSON/YAML, expose as tool calls.

2. **CT codelists are key-value pairs.** Codelist C66729 maps specific terms. This is a dictionary lookup, not a semantic search problem.

3. **eCRF metadata is already parsed** (by the Parser Agent). It is structured data by the time the Mapper Agent sees it.

4. **RAG introduces unnecessary noise.** Vector similarity search on regulatory text can return wrong sections. A direct lookup ("give me the SDTM-IG spec for the AE domain") is 100% precise.

**Implementation:**

```python
# Tool: Get SDTM domain specification
def get_domain_spec(domain: str) -> dict:
    """Returns the SDTM-IG variable list for a given domain."""
    return sdtm_ig_data[domain]  # Pre-loaded JSON

# Tool: Lookup controlled terminology
def lookup_ct(codelist_id: str, term: str = None) -> dict:
    """Returns CT codelist or checks if a term is valid."""
    codelist = ct_data[codelist_id]
    if term:
        return {"valid": term in codelist["terms"], "codelist": codelist}
    return codelist

# Tool: Get eCRF form metadata
def get_ecrf_form(form_name: str) -> ECRFForm:
    """Returns parsed eCRF form metadata."""
    return ecrf_data[form_name]

# Tool: Get raw dataset profile
def get_dataset_profile(dataset_name: str) -> RawDatasetProfile:
    """Returns profiled metadata for a raw dataset."""
    return profiles[dataset_name]
```

**When to use RAG:** Only if you add support for free-text protocol documents (SAP, protocol synopsis) in future versions. For v1 with structured SDTM-IG + CT + eCRF, tool-based lookup is superior.

**Confidence: HIGH** - This aligns with the 2025 consensus that tool-based access outperforms RAG for structured/tabular reference data. RAG is for unstructured knowledge bases.

---

## Human-in-the-Loop Architecture

### Pattern: LangGraph Interrupt + CLI Resume

LangGraph has first-class support for human-in-the-loop via its interrupt mechanism:

1. **Graph reaches review node** -> checkpoint saved automatically
2. **Interrupt raised** -> execution pauses, state persisted to SQLite
3. **CLI presents mapping spec** -> formatted table for human review
4. **Human provides input** -> approve all, reject domain, correct individual mappings
5. **Graph resumes from checkpoint** -> corrections merged into state
6. **Next node processes corrections** -> captures for learning loop

### Review Interface (CLI v1)

```
=== DOMAIN: AE (Adverse Events) ===
Source: ae.sas7bdat (1,247 rows, 23 variables)

Variable Mappings:
  #  SDTM Variable   Source        Type      Logic                    Conf
  1  STUDYID          --           assign    "PHA022121-C301"         1.00
  2  DOMAIN           --           assign    "AE"                     1.00
  3  USUBJID          SUBJID       derive    STUDYID || "-" || SUBJID 0.95
  4  AESEQ            --           derive    Sequence number          0.90
  5  AETERM           AETERM       direct    Direct carry             0.98
  6  AEDECOD          AETERM       derive    MedDRA preferred term    0.75  [!]
  7  AESTDTC          AESTDT       derive    ISO 8601 conversion      0.92
  ...

Validation: 2 warnings, 0 errors

Actions: [A]pprove all | [C]orrect #N | [R]eject domain | [S]kip to next
>
```

### Correction Granularity

Humans can correct at multiple levels:
- **Variable level:** "AEDECOD should come from AE_PTERM, not AETERM"
- **Logic level:** "The derivation for AESTDTC needs to handle partial dates"
- **Domain level:** "This dataset should map to SUPPAE, not AE"
- **Add missing:** "You missed AEACN (Action Taken)"

Each correction is captured with the original proposal and the correction, forming a training pair for the learning loop.

---

## Learning Loop Architecture

### Three-Tier Learning Strategy

**Tier 1: Example Database (Immediate, no training required)**

Store every approved mapping + correction as examples. Use them as few-shot demonstrations for future studies.

```python
@dataclass
class MappingExample:
    # Context
    study_id: str
    therapeutic_area: str
    source_variable_profile: VariableProfile
    ecrf_field: ECRFField | None

    # Mapping
    domain: str
    sdtm_variable: str
    mapping_type: str
    mapping_logic: str

    # Outcome
    was_corrected: bool
    original_proposal: VariableMapping | None  # if corrected
    final_mapping: VariableMapping
    human_reason: str | None  # if corrected
```

Storage: SQLite database. Query by domain + variable + therapeutic area to find relevant examples. Include as few-shot examples in Mapper Agent prompts.

**This is the highest-ROI learning mechanism.** Simple, requires no model training, immediately improves next-study performance.

**Tier 2: DSPy Prompt Optimization (Medium-term)**

Once you have 50+ approved mappings per domain, use DSPy's BootstrapFewShot optimizer to automatically select the best few-shot examples for each domain's mapping prompts.

```python
import dspy

class SDTMMapper(dspy.Module):
    def __init__(self):
        self.map_variable = dspy.ChainOfThought(
            "source_profile, ecrf_context, domain_spec, ct_codelists -> variable_mapping"
        )

    def forward(self, source_profile, ecrf_context, domain_spec, ct_codelists):
        return self.map_variable(
            source_profile=source_profile,
            ecrf_context=ecrf_context,
            domain_spec=domain_spec,
            ct_codelists=ct_codelists
        )

# Optimize with collected examples
optimizer = dspy.BootstrapFewShot(metric=mapping_accuracy_metric)
optimized_mapper = optimizer.compile(SDTMMapper(), trainset=approved_mappings)
```

**Why DSPy over fine-tuning:** Claude API does not support fine-tuning. DSPy optimizes prompts (few-shot selection + instruction optimization) against your collected examples. This is the practical "RL from corrections" for API-based LLMs.

**Confidence: HIGH** - DSPy is the established framework for prompt optimization from examples. BootstrapFewShot works with as few as 10 examples, MIPROv2 with 50+.

**Tier 3: Fine-Tuning (Long-term, optional)**

If you accumulate hundreds of mapping examples and want to use an open-source model (Llama, Mistral) alongside Claude, fine-tune on the correction dataset. This is a future consideration, not a v1 concern.

### Learning Database Schema

```sql
-- Core mapping examples
CREATE TABLE mapping_examples (
    id INTEGER PRIMARY KEY,
    study_id TEXT,
    therapeutic_area TEXT,
    domain TEXT,
    sdtm_variable TEXT,
    source_variable TEXT,
    source_dataset TEXT,
    mapping_type TEXT,
    mapping_logic TEXT,
    was_corrected BOOLEAN,
    confidence REAL,
    created_at TIMESTAMP
);

-- Corrections (training signal)
CREATE TABLE corrections (
    id INTEGER PRIMARY KEY,
    example_id INTEGER REFERENCES mapping_examples(id),
    original_logic TEXT,
    corrected_logic TEXT,
    correction_type TEXT,
    human_reason TEXT,
    reviewer TEXT,
    created_at TIMESTAMP
);

-- Study metadata (for context matching)
CREATE TABLE studies (
    study_id TEXT PRIMARY KEY,
    therapeutic_area TEXT,
    phase TEXT,
    domains_mapped TEXT,  -- JSON list
    total_mappings INTEGER,
    correction_rate REAL,
    completed_at TIMESTAMP
);
```

---

## State Management and Session Persistence

### LangGraph Checkpointing

LangGraph's persistence layer handles session state automatically:

- **SQLite checkpointer** for local CLI usage (development and single-user)
- **Postgres checkpointer** for future multi-user/server deployment
- Each mapping session is a **thread** with a unique ID
- Every node transition creates a **checkpoint**
- Resume from any checkpoint (crash recovery, multi-session review)

### Session Lifecycle

```
1. User starts: `astraea map --data ./Fakedata --ecrf ./ECRF.pdf`
   -> Creates new thread, begins at Parser node

2. Parser completes, Classifier completes, Mapper runs per domain
   -> Checkpoint saved after each node

3. Graph reaches Human Review for domain AE
   -> Interrupt: session saved, CLI presents review interface

4. User reviews AE, approves with corrections
   -> Graph resumes, processes corrections, moves to next domain

5. User exits mid-session (Ctrl+C or closes terminal)
   -> State already checkpointed at last node transition

6. User resumes: `astraea resume --session <thread-id>`
   -> Loads checkpoint, continues from exact point of interruption

7. All domains reviewed and approved
   -> Dataset Generator runs, produces .xpt files
   -> Session marked complete
```

### Multi-Domain Processing Flow

The Mapper Agent runs per domain. With 36 raw datasets mapping to ~15 SDTM domains, the graph loops:

```python
# Simplified LangGraph flow
def should_continue_mapping(state: AstraeaState) -> str:
    if state["current_domain_index"] < len(state["domains_to_process"]):
        return "map_next_domain"
    return "proceed_to_review"

# Graph edges
graph.add_conditional_edges(
    "mapper",
    should_continue_mapping,
    {
        "map_next_domain": "mapper",      # loop back
        "proceed_to_review": "validator"   # exit loop
    }
)
```

**Design decision:** Map ALL domains first, then review ALL at once (batch review), or map-then-review per domain (incremental review)?

**Recommendation: Incremental review per domain.** Reasons:
- Human feedback on early domains (DM, AE) informs mapping of later domains
- Corrections to common patterns (date handling, USUBJID) propagate forward
- Keeps review sessions manageable (one domain at a time)
- Allows stopping and resuming between domains naturally

---

## Patterns to Follow

### Pattern 1: Separation of Proposal and Execution

**What:** LLM agents propose mappings (specifications). Deterministic code executes them.
**When:** Always. This is the core architectural principle.
**Why:** LLM output is non-deterministic. You want human review BEFORE irreversible data transformation. The mapping spec is the reviewable artifact.

### Pattern 2: Progressive Context Enrichment

**What:** Each stage enriches the shared state. Downstream agents see results of upstream agents.
**When:** Always. The Mapper Agent sees Parser output + Classifier output + reference data.
**Why:** Reduces LLM hallucination by grounding in concrete upstream results.

### Pattern 3: Confidence Scoring

**What:** Every LLM-produced mapping includes a confidence score.
**When:** Domain classification and variable mapping.
**Why:** Routes human attention. Low-confidence mappings get flagged in the review interface. High-confidence mappings can potentially be auto-approved (future).

### Pattern 4: Domain-Scoped Processing

**What:** Process one SDTM domain at a time, not the entire study at once.
**When:** Mapping and review stages.
**Why:** Keeps context focused, makes review manageable, enables incremental progress.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Monolithic LLM Call

**What:** Sending all 36 datasets + full SDTM-IG + all codelists in one prompt.
**Why bad:** Exceeds context limits, causes "lost in the middle" attention degradation, impossible to debug.
**Instead:** Domain-scoped calls with tool-based reference lookup.

### Anti-Pattern 2: LLM-Based Validation

**What:** Using the LLM to check SDTM conformance.
**Why bad:** SDTM validation rules are deterministic and well-specified. LLM adds non-determinism and cost to something that should be exact. False negatives are dangerous in regulatory submission.
**Instead:** Deterministic rule engine. Every P21 rule is codifiable.

### Anti-Pattern 3: Unstructured Mapping Output

**What:** LLM returns free-text description of mappings.
**Why bad:** Downstream processing requires parsing free text, which is error-prone. Human review needs structured comparison.
**Instead:** Force structured output (JSON/Pydantic) from LLM calls. LangGraph supports structured output via output parsers.

### Anti-Pattern 4: Skipping Human Review for "High Confidence" Mappings

**What:** Auto-approving mappings above a confidence threshold in v1.
**Why bad:** Trust must be earned. In regulatory context, every mapping needs human accountability. Confidence calibration requires many studies to validate.
**Instead:** Show confidence to guide attention, but require explicit approval for all mappings in v1. Auto-approval can be a v2 feature after confidence calibration.

### Anti-Pattern 5: Storing Raw LLM Responses as the Knowledge Base

**What:** Saving conversation logs as learning data.
**Why bad:** Noisy, unstructured, not queryable. Future prompt optimization needs clean input-output pairs.
**Instead:** Store structured MappingExample + HumanCorrection records in SQLite.

---

## Technology Choices for Architecture Components

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Orchestration | LangGraph StateGraph | Graph-based flow, built-in HITL, checkpointing |
| LLM | Claude API (Anthropic) | Strong reasoning, structured output, tool use |
| Prompt optimization | DSPy | Automated few-shot selection from correction data |
| SAS I/O | pyreadstat | Reads .sas7bdat, writes .xpt, fast, maintained by Roche |
| Data manipulation | pandas | Industry standard for tabular data in Python |
| State persistence | SQLite (dev) / Postgres (prod) | LangGraph checkpointer backends |
| Knowledge base | SQLite | Mapping examples, corrections, study metadata |
| Reference data | JSON/YAML files | SDTM-IG specs, CT codelists (bundled, not fetched) |
| CLI | Click or Typer | Python CLI frameworks |
| Validation engine | Custom Python | Deterministic P21-style rules |

---

## Scalability Considerations

| Concern | Single Study (v1) | Multi-Study (v2) | Enterprise (v3) |
|---------|-------------------|-------------------|-----------------|
| State storage | SQLite file | SQLite per study | PostgreSQL |
| LLM calls | Sequential per domain | Parallel domains | Batch + parallel |
| Knowledge base | Local SQLite | Shared SQLite | PostgreSQL + search |
| Review interface | CLI | CLI + file export | Web UI |
| Concurrent users | 1 | 1 | Multiple |
| Session management | File-based threads | File-based threads | Server-based threads |

---

## Suggested Build Order (Critical Dependencies)

### Phase 1: Foundation (must build first)

1. **SAS I/O layer** - Read .sas7bdat, write .xpt. No LLM needed. Pure pyreadstat + pandas.
2. **Reference data loader** - Load SDTM-IG specs + CT codelists from bundled JSON/YAML.
3. **Data models** - Define all dataclasses (ECRFForm, RawDatasetProfile, DomainMappingSpec, etc.)
4. **eCRF parser** - LLM-based extraction of structured metadata from eCRF text.

**Rationale:** Everything downstream depends on being able to read data and access reference standards. The data models are the contract between all components.

### Phase 2: Core Pipeline (build in order)

5. **Dataset profiler** - Deterministic profiling of raw SAS datasets.
6. **Domain classifier** - First LLM agent. Simpler than mapping (classification vs generation).
7. **Mapper agent (single domain)** - Core LLM task. Start with DM (Demographics) -- simplest domain.
8. **Validator (basic)** - Required variables present, types correct, CT values valid.

**Rationale:** Domain classification is a simpler LLM task than variable mapping -- good for proving the agent pattern works. DM domain is the simplest to map (mostly direct carries). Basic validation gives immediate quality feedback.

### Phase 3: Human Loop (build after core works)

9. **LangGraph orchestrator** - Wire components into StateGraph with shared state.
10. **Human review gate** - LangGraph interrupt + CLI review interface.
11. **Correction capture** - Store human corrections in SQLite.

**Rationale:** You need working components before you can orchestrate them. The review gate is the quality control -- must work before expanding to more domains.

### Phase 4: Expand and Harden

12. **Mapper agent (all domains)** - Extend to AE, LB, VS, CM, EX, etc.
13. **Derivation agent** - Handle transposes, date conversions, complex derivations.
14. **Full validator** - Complete P21-style rule set.
15. **Dataset generator** - Produce final .xpt files from approved specs.

### Phase 5: Learning Loop

16. **Example database** - Query past mappings for few-shot examples.
17. **DSPy integration** - Optimize prompts from collected examples.
18. **Cross-study generalization** - Test on second study to validate learning.

**Rationale:** Learning requires data. You need to complete at least one full study mapping before the learning loop has training signal. Do not invest in learning infrastructure before the core pipeline works end-to-end.

---

## Open Architecture Questions

1. **Parallel domain mapping:** Should domains be mapped in parallel (faster) or sequential (allows corrections to propagate)? Recommend starting sequential, add parallel later.

2. **eCRF-to-dataset association:** How does the system know which eCRF forms correspond to which raw datasets? The Parser Agent needs a heuristic (form name matching) or LLM-based association.

3. **SUPPQUAL handling:** Supplemental qualifiers are a common source of complexity. They require knowing which variables do NOT fit in the parent domain. The Mapper Agent needs explicit SUPPQUAL logic.

4. **Define.xml generation:** Regulatory submissions require define.xml alongside .xpt files. This is a structured metadata file describing all datasets and variables. Should be deterministic generation from approved mapping specs.

5. **Multi-study knowledge base queries:** When the system has mapped 5+ studies, how to efficiently retrieve relevant examples? Simple SQL queries by domain + variable name may suffice initially; vector search only needed if scaling to hundreds of studies.

---

## Sources

- [LangGraph Official Documentation](https://docs.langchain.com/oss/python/langgraph/graph-api) - StateGraph API, persistence, HITL
- [LangGraph Multi-Agent Orchestration Guide](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-multi-agent-orchestration-complete-framework-guide-architecture-analysis-2025)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) - Checkpointing, threads, resume
- [LangChain HITL Documentation](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [DSPy Optimizers](https://dspy.ai/learn/optimization/optimizers/) - BootstrapFewShot, MIPROv2
- [pyreadstat (Roche)](https://github.com/Roche/pyreadstat) - SAS/XPT I/O for Python
- [RAG vs Tool Use for LLMs (2025)](https://medium.com/@sumeet.pardeshi.online/rag-vs-tool-use-for-llms-the-ultimate-guide-to-choosing-the-right-approach-in-2025-c5c06b0922f6)
- [RAG vs Long Context Models](https://www.elastic.co/search-labs/blog/rag-vs-long-context-model-llm)
- [SDTM Specification Automation Using ML (PHUSE 2025)](https://www.lexjansen.com/phuse-us/2025/ml/PAP_ML20.pdf)
- [Efficient CDISC CT Mapping (PharmaSUG 2025)](https://pharmasug.org/proceedings/2025/DS/PharmaSUG-2025-DS-338.pdf)
- [Automating SDTM Programming with GenAI (PharmaSUG China 2025)](https://www.lexjansen.com/pharmasug-cn/2025/AI/Pharmasug-China-2025-AI144.pdf)
- [Google ADK Multi-Agent Patterns](https://google.github.io/adk-docs/agents/multi-agents/)
- [AgentScope Multi-Agent Framework](https://www.analyticsvidhya.com/blog/2026/01/agentscope-ai/)
- [Multi-Agent LLMs Coordination](https://www.deepchecks.com/how-multi-agent-llms-differ-from-traditional-llms/)
