# Astraea-SDTM

An agentic AI system that maps raw clinical trial data to CDISC SDTM format. Point it at a folder of raw SAS datasets and an annotated eCRF PDF, and it produces submission-ready SDTM `.xpt` files, `define.xml`, and a reviewer's guide.

The system uses specialized LLM agents to propose variable-level mappings, then deterministic code executes them. A human reviews and corrects every mapping before datasets are generated. Corrections feed back into a learning system that improves accuracy over time.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Pipeline Walkthrough](#pipeline-walkthrough)
  - [Step 1: Profile Raw Data](#step-1-profile-raw-data)
  - [Step 2: Parse eCRF PDF](#step-2-parse-ecrf-pdf)
  - [Step 3: Classify Datasets](#step-3-classify-datasets-to-sdtm-domains)
  - [Step 4: Map Variables](#step-4-map-variables-per-domain)
  - [Step 5: Human Review](#step-5-review-mappings-human-in-the-loop)
  - [Step 6: Execute Mappings](#step-6-execute-mappings--produce-xpt-files)
  - [Step 7: Trial Design Domains](#step-7-generate-trial-design-domains)
  - [Step 8: Validate](#step-8-validate--auto-fix)
  - [Step 9: Submission Artifacts](#step-9-generate-submission-artifacts)
- [Output Files](#output-files)
- [Project Structure](#project-structure)
- [CLI Reference](#cli-reference)
- [Architecture](#architecture)
- [Development](#development)
- [Requirements](#requirements)
- [License](#license)

---

## How It Works

```
Raw SAS files (.sas7bdat)  ──┐
                             ├──▶  Profile  ──▶  Classify  ──▶  Map (LLM)
Annotated eCRF (PDF)  ───────┘                                    │
                                                                  ▼
                                                        Human Review Gate
                                                          (approve/correct)
                                                                  │
                                                                  ▼
                                                    Execute  ──▶  Validate
                                                                  │
                                                                  ▼
                                                      .xpt + define.xml + cSDRG
                                                      (submission-ready output)
```

**Key principle:** The LLM decides *what* to map. Deterministic code does *how*. The LLM proposes a mapping specification (e.g., "raw variable `AETERM` maps to SDTM variable `AETERM` via direct copy"). A human approves it. Then pandas executes the transformation and pyreadstat writes the `.xpt` file. No LLM is involved in the actual data transformation.

---

## Quick Start

### Prerequisites

- **Python 3.12** (required exactly -- `cdisc-rules-engine` needs it)
- **Anthropic API key** (for LLM steps -- profiling and review don't need it)

### Install

```bash
git clone <repo-url>
cd Astraea-SDTM

python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Configure

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Run the Full Pipeline

```bash
./run.sh
```

This walks you through all 9 steps interactively. At each step you can continue, skip, or quit. It detects existing output from previous runs so you never redo work accidentally.

---

## Pipeline Walkthrough

### Step 1: Profile Raw Data

```bash
astraea profile Fakedata/ -o output/profiles.json
```

Reads all `.sas7bdat` files and computes per-variable statistics: name, label, data type, missing %, unique values, value distributions. Flags EDC system columns (projectid, instanceId, etc.) separately from clinical data. No API key needed.

**Output:** `output/profiles.json`

```json
{
  "filename": "ae.sas7bdat",
  "row_count": 14,
  "col_count": 135,
  "variables": [
    {
      "name": "AETERM",
      "label": "Reported Term for the Adverse Event",
      "dtype": "character",
      "n_unique": 12,
      "missing_pct": 0.0,
      "sample_values": ["Headache", "Nausea", "Fatigue"],
      "is_edc_column": false,
      "is_date": false
    }
  ]
}
```

Add `-d` for variable-level detail in the terminal.

---

### Step 2: Parse eCRF PDF

```bash
astraea parse-ecrf ECRF.pdf -o output/ecrf_extraction.json
```

Uses Claude to read the annotated eCRF PDF and extract structured form/field metadata: field names, data types, SAS labels, coded values (dropdowns), and field OIDs. Runs once per study and caches the result.

**Output:** `output/ecrf_extraction.json`

```json
{
  "forms": [
    {
      "form_name": "Demographics",
      "fields": [
        {
          "field_name": "SEX",
          "data_type": "1",
          "sas_label": "Sex",
          "coded_values": {"M": "Male", "F": "Female"},
          "field_oid": "SEX"
        }
      ],
      "page_numbers": [21, 22]
    }
  ]
}
```

---

### Step 3: Classify Datasets to SDTM Domains

```bash
astraea classify Fakedata/ --ecrf ECRF.pdf -o output/classification.json
```

For each raw SAS file, determines which SDTM domain it belongs to (DM, AE, LB, etc.). Uses a combination of heuristic filename/variable matching and LLM semantic analysis. Handles cases where one file maps to multiple domains or multiple files merge into one domain.

**Output:** `output/classification.json`

```json
{
  "raw_dataset": "ae.sas7bdat",
  "primary_domain": "AE",
  "confidence": 1.0,
  "reasoning": "Filename matches, variables follow AE naming convention...",
  "heuristic_scores": [{"domain": "AE", "score": 1.0}]
}
```

---

### Step 4: Map Variables (per domain)

```bash
astraea map-domain Fakedata/ ECRF.pdf DM --output-dir output/
```

For each SDTM domain, the LLM proposes how every target variable should be created from the raw source data. Each mapping includes the source variable, mapping pattern, derivation logic, controlled terminology codelist, confidence score, and rationale.

**Mapping patterns:**
| Pattern | Description | Example |
|---------|-------------|---------|
| `assign` | Set a constant value | STUDYID = "PHA022121-C301" |
| `direct` | Copy from source as-is | SUBJID = SSUBJID |
| `rename` | Copy with name change | AETERM = AE_TERM_RAW |
| `reformat` | Copy with format change | AESTDTC = ISO8601(AESTDT) |
| `derivation` | Compute from multiple sources | USUBJID = STUDYID + SITEID + SUBJID |
| `lookup_recode` | Map through a codelist | SEX: "M" -> "M", "F" -> "F" |
| `transpose` | Pivot wide to tall (Findings) | Lab columns -> LBTESTCD rows |

**Output:** `output/DM_mapping.json` + `output/DM_mapping.xlsx`

```json
{
  "domain": "DM",
  "domain_label": "Demographics",
  "variable_mappings": [
    {
      "sdtm_variable": "USUBJID",
      "mapping_pattern": "derivation",
      "derivation_rule": "GENERATE_USUBJID",
      "source_dataset": "irt",
      "confidence": 0.9,
      "confidence_level": "high",
      "confidence_rationale": "Standard USUBJID construction..."
    }
  ]
}
```

The `.xlsx` file is the same data in a human-readable spreadsheet.

---

### Step 5: Review Mappings (Human in the Loop)

```bash
astraea review-domain output/DM_mapping.json --output-dir output/
```

This is the interactive quality gate. For each domain, the system shows a Rich table of every proposed mapping and you decide what to do.

**Main actions:**
| Action | Description |
|--------|-------------|
| `approve-all` | Accept all mappings as-is |
| `review` | Review individually (two-tier: HIGH confidence auto-approved, MEDIUM/LOW reviewed one by one) |
| `skip` | Skip this domain |
| `quit` | Save progress and exit |

**Per-variable actions (during individual review):**
| Action | Description |
|--------|-------------|
| `a` | Approve this mapping |
| `c` | Correct this mapping |
| `s` | Skip this variable |
| `q` | Quit (progress saved) |

**Correction types (when correcting):**
| Type | Description |
|------|-------------|
| `s` | Source change -- wrong source column |
| `r` | Reject -- remove this variable |
| `o` | Other/logic change -- note what needs fixing |

If you quit mid-review, your progress is saved to SQLite. Resume anytime:

```bash
astraea resume              # resume most recent session
astraea sessions            # list all sessions
```

**Output:** `output/DM_mapping_reviewed.json` (approved spec with corrections applied)

---

### Step 6: Execute Mappings -> Produce .xpt Files

```bash
# DM first (other domains reference it)
astraea execute-domain output/DM_mapping_reviewed.json Fakedata/ --output-dir output/xpt/

# Other domains (pass --dm-path for study day calculation)
astraea execute-domain output/AE_mapping_reviewed.json Fakedata/ --output-dir output/xpt/ \
    --dm-path output/xpt/dm.xpt
```

Takes the approved mapping spec and raw data, applies all transformations (direct copy, derivations, date conversions, codelist lookups, transposes), and writes SDTM-compliant `.xpt` files.

**Output:** `output/xpt/dm.xpt`, `output/xpt/ae.xpt`, etc.

---

### Step 7: Generate Trial Design Domains

```bash
astraea generate-trial-design output/trial_design_config.json \
    --output-dir output/xpt/ \
    --data-dir Fakedata/ \
    --dm-path output/xpt/dm.xpt
```

Generates the trial design domains from a JSON configuration file:

| Domain | Description | FDA Status |
|--------|-------------|------------|
| TS | Trial Summary | **Mandatory** -- missing TS = automatic rejection |
| TA | Trial Arms | Required |
| TE | Trial Elements | Required |
| TV | Trial Visits | Required |
| TI | Trial Inclusion/Exclusion | Required |
| SV | Subject Visits | Required |

**Output:** `output/xpt/ts.xpt`, `ta.xpt`, `te.xpt`, `tv.xpt`

---

### Step 8: Validate & Auto-Fix

```bash
astraea validate output/xpt/ --study-id PHA022121-C301 --auto-fix
```

Runs P21-style conformance checks on all generated datasets:
- **Terminology rules** -- controlled terminology values match NCI codelists
- **Presence rules** -- required variables exist, no unexpected nulls
- **Consistency rules** -- cross-domain USUBJID consistency, date logic
- **Format rules** -- ISO 8601 dates, variable name/label lengths
- **FDA Business Rules** -- FDAB057 (ethnicity), FDAB055 (race), etc.
- **FDA TRC pre-checks** -- Technical Rejection Criteria compliance

The `--auto-fix` flag automatically fixes deterministic issues (wrong CT case, missing DOMAIN column, name/label truncation, non-ASCII characters) and re-validates.

**Output:** Terminal report with errors/warnings/notices + `output/xpt/validation_report.md`

---

### Step 9: Generate Submission Artifacts

```bash
# define.xml (FDA-required metadata)
astraea generate-define output/xpt/ --study-id PHA022121-C301

# Reviewer's guide
astraea generate-csdrg output/xpt/ --study-id PHA022121-C301

# eCTD package
astraea package-submission \
    --source-dir output/xpt/ \
    --output-dir output/submission/ \
    --study-id PHA022121-C301
```

| Artifact | Description |
|----------|-------------|
| `define.xml` | Machine-readable metadata describing every dataset and variable. Includes ItemGroupDef, ItemDef, CodeList, MethodDef, ValueListDef. Required by FDA. |
| `csdrg.md` | Clinical Study Data Reviewer's Guide. Explains mapping rationale, non-standard variables, data handling decisions. PHUSE-structured. |
| `submission/` | eCTD directory structure (`m5/datasets/tabulations/sdtm/`) with all files in FDA-expected locations. |

---

## Output Files

After a full pipeline run, the `output/` directory contains:

```
output/
  profiles.json                    # Step 1: Raw data profiling results
  ecrf_extraction.json             # Step 2: Parsed eCRF form/field metadata
  classification.json              # Step 3: Dataset-to-domain classifications
  DM_mapping.json / .xlsx          # Step 4: Mapping specs (one per domain)
  AE_mapping.json / .xlsx
  CM_mapping.json / .xlsx
  ... (13 domains total)
  DM_mapping_reviewed.json         # Step 5: Reviewed/approved specs
  trial_design_config.json         # Step 7: Trial design configuration
  xpt/
    dm.xpt                         # Step 6: SDTM datasets (SAS Transport)
    ae.xpt
    cm.xpt
    ts.xpt                         # Step 7: Trial design datasets
    ta.xpt, te.xpt, tv.xpt
    define.xml                     # Step 9: FDA metadata
    csdrg.md                       # Step 9: Reviewer's guide
    validation_report.md           # Step 8: Validation results
  submission/
    m5/datasets/tabulations/sdtm/  # Step 9: eCTD package
```

---

## Project Structure

```
src/astraea/
  cli/            # Typer CLI commands and Rich display formatting
  models/         # Pydantic data models (shared contract between all components)
  io/             # SAS reader (pyreadstat), XPT writer
  profiling/      # Dataset profiler (variable stats, EDC detection, date detection)
  parsing/        # eCRF PDF parser (pymupdf4llm + Claude structured extraction)
  classification/ # Domain classifier (heuristic scorer + LLM semantic matching)
  reference/      # SDTM-IG specs + NCI CT codelists (bundled JSON, not API calls)
  mapping/        # LLM mapping engine (context builder, prompt templates, post-validation)
  review/         # Human review gate (interactive CLI, session persistence, correction capture)
  execution/      # Dataset executor (pattern handlers, Findings executor, SUPPQUAL generator)
  transforms/     # Date conversion, USUBJID, --DY, --SEQ, EPOCH, codelist recoding
  validation/     # P21-style rule engine (terminology, presence, consistency, FDA rules)
  submission/     # define.xml generator, cSDRG template, eCTD packager
  learning/       # Correction store (SQLite + ChromaDB), retriever, DSPy optimizer
  llm/            # Anthropic API client wrapper with retry logic
  data/           # Bundled reference data (SDTM-IG domains.json, CT codelists.json)

tests/
  unit/           # Fast tests, no I/O, no LLM calls (~2100 tests)
  integration/    # Tests using real files from Fakedata/
  fixtures/       # Shared test data and conftest.py
```

**100 source files, ~23,500 lines of code, 2,182 tests.**

---

## CLI Reference

| Command | Description | API Key? |
|---------|-------------|----------|
| `astraea profile <dir>` | Profile raw SAS datasets | No |
| `astraea parse-ecrf <pdf>` | Parse eCRF PDF to structured metadata | Yes |
| `astraea classify <dir>` | Classify datasets to SDTM domains | Yes |
| `astraea map-domain <dir> <pdf> <domain>` | Generate mapping spec for a domain | Yes |
| `astraea review-domain <spec>` | Interactively review a mapping spec | No |
| `astraea resume [session-id]` | Resume interrupted review session | No |
| `astraea sessions` | List all review sessions | No |
| `astraea execute-domain <spec> <dir>` | Execute mapping spec -> .xpt file | No |
| `astraea generate-trial-design <config>` | Generate TS, TA, TE, TV, TI, SV | No |
| `astraea validate <dir>` | Run P21-style conformance validation | No |
| `astraea auto-fix <dir>` | Auto-fix deterministic validation issues | No |
| `astraea generate-define <dir>` | Generate define.xml 2.0 | No |
| `astraea generate-csdrg <dir>` | Generate reviewer's guide | No |
| `astraea package-submission` | Assemble eCTD submission package | No |
| `astraea reference <domain>` | Query SDTM-IG domain specs | No |
| `astraea codelist <id>` | Query controlled terminology codelists | No |
| `astraea learn-ingest` | Ingest review corrections into learning DB | No |
| `astraea learn-stats` | Show learning system accuracy trends | No |
| `astraea learn-optimize` | Run DSPy prompt optimization | No |

---

## Architecture

### Core Design Principle

> The LLM decides WHAT to map. Deterministic code does HOW.

The mapping specification is the contract between LLM reasoning and deterministic execution. The LLM never touches the actual data. It proposes a spec, a human approves it, and then pandas + pyreadstat execute it.

### Agent Pipeline

```
1. Parser Agent      ── reads eCRF PDF + SAS files, extracts metadata
2. Domain Classifier ── classifies raw datasets to SDTM domains
3. Mapper Agent      ── proposes variable-level mappings (per domain)
4. Validator         ── deterministic P21-style conformance checks
5. Human Review Gate ── interactive approval/correction (CLI)
6. Dataset Generator ── executes approved specs, writes .xpt files
```

### Technology Stack

| Component | Technology |
|-----------|-----------|
| LLM | Claude (Anthropic SDK) |
| Data manipulation | pandas + numpy |
| SAS I/O | pyreadstat (read .sas7bdat, write .xpt) |
| PDF parsing | pymupdf4llm + pdfplumber |
| Data models | Pydantic v2 |
| CLI | Typer + Rich |
| Validation | Custom P21-style rule engine |
| Learning | SQLite + ChromaDB + DSPy |
| Logging | loguru |
| Testing | pytest + pytest-asyncio |
| Linting | ruff |

### Reference Data

SDTM-IG domain specifications and NCI Controlled Terminology codelists are bundled as JSON files (not fetched at runtime). Tool-based lookup, not RAG -- structured data is looked up directly, not searched via vector similarity.

### Learning System

Human corrections are stored in SQLite and ChromaDB. When mapping future studies, the system retrieves similar past corrections as few-shot examples in the LLM prompt. DSPy optimizes prompt selection from accumulated examples.

```
Human corrects mapping  ──▶  Stored in learning DB
                                    │
Future mapping call  ──▶  Retrieve similar corrections  ──▶  Few-shot examples in prompt
```

---

## Development

### Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Tests

```bash
pytest                          # full suite (2,182 tests)
pytest tests/unit/              # unit only (fast, no I/O)
pytest tests/integration/       # integration only (reads Fakedata/)
pytest -x -q tests/unit/test_specific.py  # single file, stop on first failure
```

### Lint & Type Check

```bash
ruff check src/ tests/
ruff format src/ tests/
mypy src/
```

### Code Conventions

- Pydantic models for all data structures passed between components
- Type hints on all function signatures
- Validators are always deterministic rule engines, never LLM-based
- `loguru` for logging, never `print()` for debug output
- Raise specific exceptions over returning None/empty

---

## Requirements

- **Python 3.12** (exactly -- `cdisc-rules-engine` requires it)
- **Anthropic API key** (for eCRF parsing, classification, and mapping steps)
- Sample data: `.sas7bdat` files + annotated eCRF PDF

### SDTM Standards Supported

- SDTM Implementation Guide v3.4
- NCI Controlled Terminology (bundled, version-locked)
- FDA Technical Rejection Criteria v1.6
- define.xml v2.0

### Domains Supported

| Class | Domains |
|-------|---------|
| Special Purpose | DM, SV, SUPPQUAL |
| Events | AE, CE, DS, DV, MH |
| Interventions | CM, EX |
| Findings | LB, VS, EG, PE |
| Trial Design | TS, TA, TE, TV, TI |


