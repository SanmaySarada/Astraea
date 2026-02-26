# Phase 2: Source Parsing and Domain Classification - Research

**Researched:** 2026-02-26
**Domain:** eCRF PDF extraction, LLM-based structured extraction, domain classification
**Confidence:** MEDIUM-HIGH

## Summary

Phase 2 introduces the first LLM calls into the Astraea pipeline. It has two major components: (1) extracting structured metadata from the 189-page eCRF PDF, and (2) classifying 36 raw SAS datasets to SDTM domains. Research focused on understanding the actual eCRF text format, the existing Phase 1 codebase that this phase builds on, PDF parsing library capabilities, and the Anthropic structured output API.

The eCRF text extraction (ECRF_text.txt) reveals a consistent but messy format: each form has a header block ("Form: Name"), followed by human-readable field descriptions, then a separate "Field Name / Data Type / SAS Label / Units / Values / Include / Field OID" table. The text extraction has significant garbling -- multi-line cell values are split across lines, page numbers interleave with data, and column boundaries are lost. This means naive text parsing will fail; the LLM must interpret the semi-structured text into structured form/field objects.

For domain classification, the 36 raw dataset filenames provide strong heuristic signals (ae.sas7bdat -> AE, lb_biochem.sas7bdat -> LB), but the system must not hardcode these. The classifier should use multiple signals: filename, variable names/labels from profiling, eCRF form associations, and SDTM-IG domain specs. Multiple lab files (lb_biochem, lb_hem, lb_urin, lb_coagulation, lb_urin_ole) must be detected as merging into a single LB domain.

**Primary recommendation:** Use pymupdf4llm for PDF-to-Markdown extraction with page_chunks=True, then use Claude with structured output (output_config with Pydantic) to interpret each form's content into structured ECRFForm/ECRFField models. For classification, use a two-stage approach: deterministic heuristic scoring first, then LLM for confirmation/correction with structured output.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pymupdf4llm` | >=0.3.4 | PDF to Markdown extraction | Fast (0.12s), designed for LLM consumption, table detection, GitHub-flavored Markdown output |
| `anthropic` | latest | Claude API for structured extraction and classification | Already in pyproject.toml; structured output with Pydantic is now GA |
| `pydantic` | >=2.10 | Output schema definitions for LLM calls | Already used throughout Phase 1; Claude SDK `.parse()` method accepts Pydantic models directly |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pdfplumber` | >=0.11 | Fallback table extraction | When pymupdf4llm fails to detect table structure on specific eCRF pages |
| `PyMuPDF` | >=1.25 | Underlying PDF engine (installed with pymupdf4llm) | Direct page access if needed for debugging |
| `tenacity` | >=9.0 | Retry logic for Claude API calls | Rate limiting, transient failures |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pymupdf4llm | Unstructured.io | Heavier, slower (1.29s vs 0.12s), designed for heterogeneous pipelines |
| pymupdf4llm | Claude Vision (PDF images) | More expensive per page, but handles complex layouts better; consider as fallback |
| Claude structured output | LangChain ChatAnthropic | Adds abstraction layer; for Phase 2 direct SDK is simpler; LangChain integration needed in Phase 3+ |

**Installation:**
```bash
pip install pymupdf4llm pdfplumber tenacity
```

Note: `anthropic` and `pydantic` are already in pyproject.toml dependencies.

## Architecture Patterns

### Recommended Project Structure (new files for Phase 2)
```
src/astraea/
  models/
    ecrf.py              # NEW: ECRFForm, ECRFField Pydantic models
    classification.py    # NEW: DomainClassification, DomainPlan models
  parsing/
    __init__.py          # NEW module
    pdf_extractor.py     # NEW: pymupdf4llm wrapper, page chunking
    ecrf_parser.py       # NEW: LLM-based structured extraction
    form_dataset_matcher.py  # NEW: eCRF form to raw dataset association
  classification/
    __init__.py          # NEW module
    heuristic.py         # NEW: deterministic scoring (filename, variables)
    classifier.py        # NEW: LLM-based domain classification
  llm/
    __init__.py          # NEW module
    client.py            # NEW: Anthropic client wrapper with structured output
  cli/
    app.py               # EXTEND: add parse-ecrf and classify commands
```

### Pattern 1: Two-Phase eCRF Extraction (Deterministic + LLM)
**What:** First extract PDF to Markdown deterministically (pymupdf4llm), then use Claude to interpret the Markdown into structured Pydantic models.
**When to use:** Always for eCRF parsing.
**Why:** Separates the PDF-reading concern (deterministic, fast, cacheable) from the interpretation concern (LLM, slower, costs money). The Markdown intermediate representation can be inspected and debugged.

```python
# Step 1: PDF -> Markdown (deterministic, fast)
import pymupdf4llm

pages = pymupdf4llm.to_markdown(
    "ECRF.pdf",
    page_chunks=True,
    table_strategy="lines_strict",
)
# Returns list of dicts, each with 'metadata', 'text', 'tables' keys

# Step 2: Segment pages by form
# The eCRF has a header on every page: "Form: <name>"
# Group consecutive pages by form name

# Step 3: Markdown -> Structured data (LLM)
# Send each form's combined Markdown to Claude with structured output
```

### Pattern 2: Anthropic Structured Output with Pydantic
**What:** Use `client.messages.parse()` with Pydantic models to get guaranteed schema-compliant JSON from Claude.
**When to use:** Every LLM call in Phase 2 (eCRF parsing, classification).
**Why:** Eliminates JSON parsing errors, guarantees type safety, integrates directly with existing Pydantic model layer.

```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
from pydantic import BaseModel, Field
from anthropic import Anthropic

class ECRFField(BaseModel):
    field_number: int = Field(..., description="Field sequence number within the form")
    field_name: str = Field(..., description="SAS variable name (e.g., 'AETERM')")
    data_type: str = Field(..., description="Data type (e.g., '$25', '1', 'dd MMM yyyy')")
    sas_label: str = Field(..., description="SAS label describing the field")
    units: str | None = Field(None, description="Unit of measurement if applicable")
    coded_values: dict[str, str] | None = Field(None, description="Code-decode pairs (e.g., {'Y': 'Yes', 'N': 'No'})")
    field_oid: str | None = Field(None, description="Field OID from the eCRF")

class ECRFFormExtraction(BaseModel):
    form_name: str = Field(..., description="Form name exactly as it appears in the eCRF")
    fields: list[ECRFField] = Field(..., description="All fields defined in this form")

client = Anthropic()
response = client.messages.parse(
    model="claude-sonnet-4-20250514",  # Use Sonnet for high-volume extraction
    max_tokens=4096,
    temperature=0.2,  # Low for structured extraction
    messages=[
        {"role": "user", "content": f"Extract all fields from this eCRF form:\n\n{form_markdown}"}
    ],
    output_format=ECRFFormExtraction,
)
form = response.parsed_output  # Guaranteed ECRFFormExtraction instance
```

### Pattern 3: Multi-Signal Domain Classification
**What:** Combine deterministic heuristic scoring with LLM reasoning for robust classification.
**When to use:** Always for domain classification.
**Why:** Heuristics catch the obvious cases (ae.sas7bdat -> AE) cheaply. LLM handles ambiguous cases and provides reasoning. This prevents hallucination cascading -- the heuristic acts as a sanity check on LLM output.

```python
# Stage 1: Deterministic heuristic scoring (free, fast)
# - Filename pattern matching (ae -> AE, lb_* -> LB, dm -> DM)
# - Variable name overlap with SDTM-IG domain specs
# - SAS label keyword matching

# Stage 2: LLM classification (for confirmation + ambiguous cases)
# - Provides reasoning and confidence scores
# - Receives heuristic scores as additional context
# - Must agree with high-confidence heuristics or explain disagreement

# Stage 3: Merge detection (deterministic)
# - Group datasets with same primary domain
# - Flag datasets sharing common prefixes (lb_biochem, lb_hem -> LB)
```

### Pattern 4: Cached Extraction Results
**What:** Cache all eCRF extraction and classification results to disk as JSON.
**When to use:** Always. These are expensive LLM calls that produce deterministic outputs for a given study.
**Why:** Re-running the pipeline should not re-parse the eCRF or re-classify domains unless the source files change.

### Anti-Patterns to Avoid
- **Sending all 189 pages to Claude at once:** Context window overflow. Process form by form.
- **Hardcoded form-to-dataset mapping rules:** Must work across studies (ECRF-04).
- **LLM-only classification without heuristic sanity check:** Hallucination cascading risk (PITFALLS.md C1).
- **Parsing the pre-extracted ECRF_text.txt instead of the PDF:** The text extraction already lost table structure. Re-extract from PDF with pymupdf4llm for better quality.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction | Custom PDF parser | pymupdf4llm `to_markdown()` | Handles encoding, layout, table detection automatically |
| JSON schema enforcement on LLM output | Manual JSON parsing + validation | `client.messages.parse()` with Pydantic | Constrained decoding guarantees schema compliance |
| Retry logic for API calls | Custom try/except loops | `tenacity` with exponential backoff | Handles rate limits, transient errors, configurable strategies |
| Form segmentation from PDF | Page-by-page regex | pymupdf4llm `page_chunks=True` + form header detection | Returns structured page metadata including page number |

**Key insight:** The Anthropic SDK's `.parse()` method with Pydantic models eliminates the entire class of "LLM returned invalid JSON" bugs. Use it for every LLM call.

## Common Pitfalls

### Pitfall 1: eCRF Text Garbling from PDF Extraction
**What goes wrong:** The eCRF text extraction loses table structure. Field names, data types, SAS labels, and coded values get split across lines and interleaved with page headers. The existing ECRF_text.txt shows this clearly -- "VSTEMP_U" and "NITS" on separate lines, coded values mixed with labels, page numbers ("57 of 188") in the middle of data.
**Why it happens:** PDF is a visual format. Text extraction follows reading order, not logical structure.
**How to avoid:**
1. Extract with pymupdf4llm (better table detection than raw text extraction)
2. Use the LLM to reconstruct structure from the garbled text
3. Validate extraction results: field count per form, all OIDs present, all field names are valid SAS names
**Warning signs:** Fewer fields extracted than expected, field names containing spaces, OIDs not matching field names.

### Pitfall 2: eCRF Forms Spanning Multiple Pages
**What goes wrong:** A single form (e.g., "Adverse Events") spans 12+ pages of the eCRF. If processing page-by-page, the form context is split and the LLM may produce duplicate or missing fields.
**Why it happens:** Large forms have many fields or many coded value options (see "Prior and Concomitant Medications" with 20+ frequency options).
**How to avoid:** Group all pages belonging to the same form before sending to the LLM. The eCRF has a consistent header: "Form: <name>" on every page. Concatenate all pages with the same form name.
**Warning signs:** Duplicate field names in extraction, fields missing from multi-page forms.

### Pitfall 3: Two Sections Per Form (Description + Field Table)
**What goes wrong:** Each eCRF form has TWO representations: (1) a human-readable description section with questions and response options, and (2) a structured field table with "Field Name / Data Type / SAS Label / Units / Values / Include / Field OID" headers. The LLM may confuse the two or extract from the wrong one.
**Why it happens:** The description section and field table are on different pages of the same form. Some forms repeat the description on multiple pages (e.g., "Vital Signs" has the description on pages 55-60 and the field table on pages 56-58).
**How to avoid:** In the prompt, explicitly instruct the LLM to extract from the FIELD TABLE section (identified by the header "Field Name Data Type SAS Label Units Values Include Field OID"), not the description section.
**Warning signs:** Extracted field names that look like question text, missing data types.

### Pitfall 4: Domain Classification Hallucination Cascade
**What goes wrong:** The LLM misclassifies a dataset (e.g., labels "haemh_screen.sas7bdat" as AE instead of MH). All downstream mapping is then wrong.
**Why it happens:** LLMs are confidently wrong. Dataset names like "haemh_screen" are ambiguous without context.
**How to avoid:**
1. Deterministic heuristic scoring BEFORE LLM classification
2. Cross-check: if heuristic says MH with high confidence but LLM says AE, flag for human review
3. Use SDTM-IG variable specs as matching signals (does this dataset have MH-specific variables like MHTERM?)
4. Provide eCRF form association as context to the classifier
**Warning signs:** Classification confidence < 0.7, heuristic and LLM disagreeing.

### Pitfall 5: Ambiguous Datasets That Don't Map to Standard Domains
**What goes wrong:** Some raw datasets don't map cleanly to any standard SDTM domain. In this study: `ctest.sas7bdat`, `ecoa.sas7bdat`, `epro.sas7bdat`, `irt.sas7bdat`, `irt_dummy.sas7bdat`, `lg.sas7bdat`, `llb.sas7bdat`, `ole.sas7bdat`, `pg.sas7bdat`. The classifier forces them into a domain when they should be flagged as "needs investigation."
**Why it happens:** Real clinical data has ancillary datasets (IRT = Interactive Response Technology, eCOA = electronic Clinical Outcome Assessment, ePRO = electronic Patient-Reported Outcome) that may map to custom domains or not map to SDTM at all.
**How to avoid:** The classifier must have an "UNCLASSIFIED" or "CUSTOM" option. Not every dataset maps to a standard SDTM domain. Provide a clear "I don't know" path.
**Warning signs:** Low confidence scores on datasets with non-standard names.

## Code Examples

### Example 1: PDF Extraction with pymupdf4llm
```python
# Source: pymupdf4llm documentation (https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html)
import pymupdf4llm
from pathlib import Path

def extract_ecrf_pages(pdf_path: str | Path) -> list[dict]:
    """Extract eCRF PDF to page-level Markdown chunks.

    Returns list of dicts with keys: 'metadata', 'text', 'tables'.
    """
    pages = pymupdf4llm.to_markdown(
        str(pdf_path),
        page_chunks=True,
        table_strategy="lines_strict",
        show_progress=True,
    )
    return pages


def group_pages_by_form(pages: list[dict]) -> dict[str, str]:
    """Group extracted pages by eCRF form name.

    Returns dict of form_name -> concatenated Markdown text.
    """
    import re

    forms: dict[str, list[str]] = {}
    current_form = "UNKNOWN"

    for page in pages:
        text = page.get("text", "")
        # Look for form header pattern
        match = re.search(r"Form:\s*(.+?)(?:\n|$)", text)
        if match:
            current_form = match.group(1).strip()

        if current_form not in forms:
            forms[current_form] = []
        forms[current_form].append(text)

    return {name: "\n\n".join(chunks) for name, chunks in forms.items()}
```

### Example 2: Anthropic Structured Output for eCRF Field Extraction
```python
from pydantic import BaseModel, Field
from anthropic import Anthropic

class ECRFFieldExtracted(BaseModel):
    """A single field extracted from an eCRF form's field table."""
    field_number: int
    field_name: str = Field(..., description="SAS variable name, uppercase, no spaces")
    data_type: str = Field(..., description="e.g., '$25', '1', 'dd MMM yyyy', 'HH:nn', '5.2'")
    sas_label: str
    units: str | None = None
    coded_values: dict[str, str] | None = Field(
        None, description="Map of code -> decode, e.g., {'Y': 'Yes', 'N': 'No'}"
    )
    field_oid: str | None = Field(None, description="Usually same as field_name")

class ECRFFormExtracted(BaseModel):
    """Structured extraction of one eCRF form."""
    form_name: str
    fields: list[ECRFFieldExtracted]

ECRF_EXTRACTION_PROMPT = """You are extracting structured metadata from a clinical trial eCRF (electronic Case Report Form).

The text below contains pages from a single eCRF form. Each form has:
1. A human-readable description section (questions, response options)
2. A FIELD TABLE section with headers: "Field Name  Data Type  SAS Label  Units  Values  Include  Field OID"

Extract ONLY from the FIELD TABLE section. For each field row, extract:
- field_number: The sequence number (leftmost column)
- field_name: The SAS variable name (e.g., AETERM, VSDAT)
- data_type: The data type/format (e.g., $25, 1, dd MMM yyyy)
- sas_label: The human-readable label
- units: Measurement units if specified
- coded_values: Code-to-decode mappings (e.g., Y=Yes, N=No) if present
- field_oid: The Field OID (rightmost column, often same as field_name)

IMPORTANT: Field names are SAS variable names -- uppercase, no spaces, max 8 chars.
If a field name appears to be split across lines, join the parts.

Here is the form text:

{form_text}
"""

def extract_form_fields(
    client: Anthropic,
    form_name: str,
    form_text: str,
) -> ECRFFormExtracted:
    """Extract structured fields from a single eCRF form using Claude."""
    response = client.messages.parse(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        temperature=0.2,
        messages=[{
            "role": "user",
            "content": ECRF_EXTRACTION_PROMPT.format(form_text=form_text),
        }],
        output_format=ECRFFormExtracted,
    )
    return response.parsed_output
```

### Example 3: Heuristic Domain Scorer
```python
from astraea.models.profiling import DatasetProfile
from astraea.reference.sdtm_ig import SDTMReference

# Filename-to-domain heuristic patterns
FILENAME_PATTERNS: dict[str, list[str]] = {
    "AE": ["ae"],
    "CM": ["cm", "conmed"],
    "DM": ["dm", "demo"],
    "DS": ["ds", "disp"],
    "DV": ["dv", "deviat"],
    "EG": ["eg", "ecg"],
    "EX": ["ex", "expos", "dose"],
    "IE": ["ie", "incl", "excl"],
    "LB": ["lb", "lab", "biochem", "hem", "coag", "urin", "chem"],
    "MH": ["mh", "medhist", "haemh"],
    "PE": ["pe", "physex"],
    "VS": ["vs", "vital"],
    "CE": ["ce"],
}

def score_by_filename(dataset_name: str) -> dict[str, float]:
    """Score domain likelihood by filename pattern matching."""
    scores: dict[str, float] = {}
    name_lower = dataset_name.lower().replace(".sas7bdat", "")

    for domain, patterns in FILENAME_PATTERNS.items():
        for pattern in patterns:
            if name_lower == pattern:
                scores[domain] = 1.0  # exact match
                break
            elif name_lower.startswith(pattern + "_") or pattern in name_lower:
                scores[domain] = max(scores.get(domain, 0), 0.7)

    return scores


def score_by_variable_overlap(
    profile: DatasetProfile,
    ref: SDTMReference,
) -> dict[str, float]:
    """Score domain likelihood by variable name overlap with SDTM-IG specs."""
    # Get non-EDC clinical variable names from the profile
    clinical_vars = {
        v.name.upper()
        for v in profile.variables
        if not v.is_edc_column
    }

    scores: dict[str, float] = {}
    for domain_code in ref.list_domains():
        spec = ref.get_domain_spec(domain_code)
        if spec is None:
            continue

        # Domain-specific variables (exclude common identifiers like STUDYID, USUBJID)
        common_vars = {"STUDYID", "DOMAIN", "USUBJID"}
        domain_vars = {
            v.name for v in spec.variables
            if v.name not in common_vars
        }

        overlap = clinical_vars & domain_vars
        if domain_vars:
            scores[domain_code] = len(overlap) / len(domain_vars)

    return scores
```

### Example 4: LLM Domain Classification with Structured Output
```python
from pydantic import BaseModel, Field

class DomainClassificationResult(BaseModel):
    """LLM classification of a raw dataset to an SDTM domain."""
    primary_domain: str = Field(
        ..., description="SDTM domain code (e.g., 'AE', 'LB') or 'UNCLASSIFIED'"
    )
    secondary_domains: list[str] = Field(
        default_factory=list,
        description="Additional domains this dataset contributes to (e.g., SUPPAE)",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., description="Why this classification was chosen")
    merge_candidates: list[str] = Field(
        default_factory=list,
        description="Other dataset names that should merge with this one into the same domain",
    )

CLASSIFICATION_PROMPT = """You are classifying a raw clinical trial dataset to an SDTM domain.

Available SDTM domains: {available_domains}

Dataset: {dataset_name}
Row count: {row_count}
Clinical variables (excluding EDC system columns):
{variable_summary}

eCRF form association (if known): {ecrf_form}

Heuristic scores (automated, for reference):
{heuristic_scores}

Classify this dataset to the most appropriate SDTM domain.
If the dataset does not map to any standard domain, use "UNCLASSIFIED".
If this dataset should merge with other datasets into one domain, list the merge candidates.
"""
```

### Example 5: Form-to-Dataset Association
```python
def match_form_to_datasets(
    form: ECRFFormExtracted,
    profiles: list[DatasetProfile],
) -> list[tuple[str, float]]:
    """Match an eCRF form to raw datasets by variable name overlap.

    Returns list of (dataset_name, overlap_score) sorted by score descending.
    """
    form_field_names = {f.field_name.upper() for f in form.fields}

    matches = []
    for profile in profiles:
        clinical_vars = {
            v.name.upper()
            for v in profile.variables
            if not v.is_edc_column
        }

        overlap = form_field_names & clinical_vars
        if overlap:
            # Score: what fraction of form fields appear in this dataset
            score = len(overlap) / len(form_field_names) if form_field_names else 0
            matches.append((profile.filename, score))

    return sorted(matches, key=lambda x: x[1], reverse=True)
```

## eCRF Structure Analysis

**Based on actual examination of ECRF_text.txt (11,069 lines, 188 pages):**

### Identified Forms (39 unique forms)
The eCRF contains 39 distinct forms. Key forms and their likely SDTM domain mappings:

| eCRF Form | Likely Domain | Raw Dataset(s) |
|-----------|---------------|-----------------|
| Subject Enrollment | DM | dm.sas7bdat |
| Demographics | DM | dm.sas7bdat |
| Adverse Events | AE | ae.sas7bdat |
| Prior and Concomitant Medications | CM | cm.sas7bdat |
| Medical History | MH | mh.sas7bdat |
| Medical History - HAE Characteristics | MH | haemh.sas7bdat, haemh_screen.sas7bdat |
| Vital Signs | VS | (likely within ctest or dedicated) |
| 12-Lead ECG | EG | ecg_results.sas7bdat |
| 12-Lead ECG - Pre-Dose | EG | eg_pre.sas7bdat |
| 12-Lead ECG - Post-Dose | EG | eg_post.sas7bdat |
| Hematology | LB | lb_hem.sas7bdat |
| Chemistry | LB | lb_biochem.sas7bdat |
| Coagulation | LB | lb_coagulation.sas7bdat |
| Urinalysis | LB | lb_urin.sas7bdat |
| Urinalysis Open Label | LB | lb_urin_ole.sas7bdat |
| Inclusion/Exclusion Criteria | IE | ie.sas7bdat |
| Study Drug Administration | EX | ex.sas7bdat |
| End of Study | DS | ds.sas7bdat |
| End of Treatment | DS | ds2.sas7bdat |
| HAE Attack | CE | ce.sas7bdat |
| Pharmacokinetics | PC (custom) | (likely ctest or dedicated) |
| Pregnancy Test | LB | pg.sas7bdat |
| Complete Physical Examination | PE | pe.sas7bdat |
| Drug Accountability | DA | da_disp.sas7bdat |
| Randomization | DM (SUPPDM) | (within dm or irt) |

### eCRF Page Structure Pattern
Every page follows this pattern:
```
QC GS 20230804 CCB015: All Forms- Unique
Project Name: PHA022121-C301
Form: <Form Name>
Generated On: 04 Aug 2023 15:56:39

[Content: either description section OR field table section]

QC GS 20230804 CCB015 (81)

<page_number> of 188
```

### Field Table Structure
The field table sections have this header:
```
Field Name Data Type SAS Label    Units    Values    Include    Field OID
```

Each row contains:
- Sequence number (1, 2, 3...)
- Field name (SAS variable name, e.g., AETERM)
- Data type ($25, 1, dd MMM yyyy, HH:nn, 5.2, etc.)
- SAS label (human-readable description)
- Units (if applicable)
- Coded values (e.g., "Y = Yes, N = No")
- Field OID (usually matches field name)

**Data types observed:**
- `$N` = character of width N (e.g., $25, $1, $200)
- `N` or `N.N` = numeric (e.g., 1, 3, 5.2)
- `dd MMM yyyy` = date format
- `HH:nn` = time format
- `dd MMM yyyy HH:nn` = datetime format (derived fields)

## Dataset-to-Domain Mapping Analysis

### Clear Mappings (high heuristic confidence)
| Dataset | Domain | Signal |
|---------|--------|--------|
| ae.sas7bdat | AE | Exact name match |
| cm.sas7bdat | CM | Exact name match |
| dm.sas7bdat | DM | Exact name match |
| ds.sas7bdat | DS | Exact name match |
| dv.sas7bdat | DV | Exact name match |
| ex.sas7bdat | EX | Exact name match |
| ie.sas7bdat | IE | Exact name match |
| mh.sas7bdat | MH | Exact name match |
| pe.sas7bdat | PE | Exact name match |

### Multi-File Domain Merges
| Datasets | Domain | Merge Rationale |
|----------|--------|-----------------|
| lb_biochem, lb_hem, lb_urin, lb_coagulation, lb_urin_ole | LB | All lab subtype prefixes |
| eg_pre, eg_post, eg3, ecg_results | EG | All ECG variants |
| ds, ds2 | DS | Both disposition datasets |
| haemh, haemh_screen | MH (or CE) | Both HAE medical history |
| ex, ex_ole | EX | Both exposure variants |

### Ambiguous Datasets (need LLM + eCRF context)
| Dataset | Possible Domains | Challenge |
|---------|-----------------|-----------|
| c1_inh.sas7bdat | LB (Central Lab) | C1 INH functional assay = lab test |
| ctest.sas7bdat | Unknown | Need to inspect variables |
| da_disp.sas7bdat | DA (Drug Accountability) | DA not in bundled SDTM-IG domains |
| ecoa.sas7bdat | QS (Questionnaires) | eCOA = electronic Clinical Outcome Assessment |
| epro.sas7bdat | QS | ePRO = electronic Patient-Reported Outcome |
| irt.sas7bdat | DM/SUPPDM | IRT = randomization/drug assignment |
| irt_dummy.sas7bdat | DM/SUPPDM | IRT dummy data |
| lab.sas7bdat | LB | Likely local lab results |
| lab_results.sas7bdat | LB | Another lab results file |
| lg.sas7bdat | Unknown | Need to inspect |
| llb.sas7bdat | LB | Likely local lab |
| ole.sas7bdat | Custom | Open-Label Extension metadata |
| pg.sas7bdat | LB or custom | Pregnancy test |

## LLM Integration Patterns

### Anthropic SDK Structured Output (GA, not beta)
**Confidence: HIGH** -- Structured output is now generally available for Claude Opus 4.6, Sonnet 4.6, Sonnet 4.5, Opus 4.5, and Haiku 4.5. No beta headers required.

Key API pattern:
```python
from anthropic import Anthropic
from pydantic import BaseModel

client = Anthropic()  # Uses ANTHROPIC_API_KEY env var

# Option 1: Pydantic model with .parse()
response = client.messages.parse(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[...],
    output_format=MyPydanticModel,
)
result = response.parsed_output  # MyPydanticModel instance

# Option 2: Raw JSON schema with output_config
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[...],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": MyPydanticModel.model_json_schema(),
        }
    },
)
import json
result = json.loads(response.content[0].text)
```

### Model Selection for Phase 2 Tasks
Per CLAUDE.md rules on model selection:

| Task | Model | Temperature | Rationale |
|------|-------|-------------|-----------|
| eCRF field extraction | claude-sonnet-4-20250514 | 0.2 | High-volume (39 forms), structured extraction |
| Domain classification | claude-sonnet-4-20250514 | 0.1 | Classification is analytical, needs consistency |
| Ambiguous dataset analysis | claude-sonnet-4-20250514 | 0.2 | Some reasoning flexibility needed |

### Shared LLM Client Wrapper
Build a thin wrapper around the Anthropic client that:
1. Handles API key loading from environment
2. Applies retry logic via tenacity
3. Logs every call (model, temperature, token count, latency) per CLAUDE.md rules
4. Enforces explicit max_tokens per CLAUDE.md rules

```python
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
from pydantic import BaseModel
from typing import TypeVar
import time

T = TypeVar("T", bound=BaseModel)

class AstraeaLLMClient:
    """Thin wrapper around Anthropic SDK with logging and retry."""

    def __init__(self) -> None:
        self._client = Anthropic()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=30))
    def parse(
        self,
        model: str,
        messages: list[dict],
        output_format: type[T],
        max_tokens: int = 4096,
        temperature: float = 0.1,
        system: str | None = None,
    ) -> T:
        """Call Claude with structured output, returning a Pydantic model instance."""
        start = time.monotonic()

        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
            "output_format": output_format,
        }
        if system:
            kwargs["system"] = system

        response = self._client.messages.parse(**kwargs)

        elapsed = time.monotonic() - start
        logger.info(
            "LLM call: model={}, temp={}, tokens_in={}, tokens_out={}, latency={:.2f}s",
            model,
            temperature,
            response.usage.input_tokens,
            response.usage.output_tokens,
            elapsed,
        )

        return response.parsed_output
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Beta header for structured output | GA with `output_config.format` | Late 2025 | No beta headers needed; `.parse()` method with Pydantic |
| Manual JSON parsing of LLM output | Constrained decoding via schema | 2025 | Eliminates JSON parsing errors entirely |
| pymupdf4llm basic text | pymupdf4llm with page_chunks + table_strategy | 2025 | Structured page-level output with table detection |

**Deprecated/outdated:**
- `output_format` parameter (old beta) still works but `output_config.format` is the GA API
- `client.beta.messages.parse()` (beta path) replaced by `client.messages.parse()` (GA)

## Open Questions

1. **pymupdf4llm table quality on THIS specific eCRF**
   - What we know: pymupdf4llm handles tables with clear borders well
   - What's unclear: The eCRF may have borderless tables that confuse detection
   - Recommendation: Prototype early. Extract pages 1-20, compare pymupdf4llm output to ECRF_text.txt. If tables are garbled, try pdfplumber or Claude Vision as fallback.

2. **eCRF forms with duplicate/variant layouts**
   - What we know: "Vital Signs" appears with slightly different field tables across visits (VSDAT vs VSDAT1, VSTIM vs VSTIM1)
   - What's unclear: Should these be treated as one form or separate forms?
   - Recommendation: Merge pages with same "Form:" header, let LLM handle variant field names.

3. **Datasets with no eCRF form match**
   - What we know: Some datasets (irt, irt_dummy, ecoa, epro) may not have corresponding eCRF forms
   - What's unclear: How many datasets will remain unmatched
   - Recommendation: Build the matcher to report unmatched datasets explicitly. These become "UNCLASSIFIED" and require manual review.

4. **Datasets outside bundled SDTM-IG domains**
   - What we know: Bundled domains are AE, CM, DM, DS, EG, EX, IE, LB, MH, VS (10 domains)
   - What's unclear: Several datasets may map to domains not yet in the bundled data (DA, QS, PC, SV, CE)
   - Recommendation: The classifier should still classify to the correct domain code even if the domain spec is not bundled. Phase 2 should expand the bundled SDTM-IG data to include CE, DA, PC, QS, SV, and trial design domains.

5. **Cost estimation for LLM calls**
   - What we know: ~39 forms to extract, ~36 datasets to classify
   - What's unclear: Exact token counts per form (depends on form size)
   - Recommendation: Budget approximately 39 extraction calls (Sonnet, ~2K-4K tokens each) + 36 classification calls (Sonnet, ~1K-2K tokens each). Estimated cost: $2-5 per study for Phase 2.

## Sources

### Primary (HIGH confidence)
- Actual ECRF_text.txt analysis (11,069 lines, 188 pages, 39 unique forms)
- Phase 1 codebase examination: models/, profiling/, reference/, io/, cli/
- Fakedata/ directory listing (36 SAS files)
- Bundled SDTM-IG domains.json (10 domains: AE, CM, DM, DS, EG, EX, IE, LB, MH, VS)
- [Anthropic Structured Output docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) -- GA, output_config.format, .parse() with Pydantic
- [pymupdf4llm API docs](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html) -- to_markdown(), page_chunks, table_strategy

### Secondary (MEDIUM confidence)
- [pymupdf4llm PyPI](https://pypi.org/project/pymupdf4llm/) -- v0.3.4, Feb 2026
- [pymupdf4llm GitHub](https://github.com/pymupdf/pymupdf4llm) -- table handling capabilities
- [Anthropic structured outputs announcement](https://techbytes.app/posts/claude-structured-outputs-json-schema-api/) -- GA status confirmed

### Tertiary (LOW confidence)
- Table extraction quality on this specific eCRF -- needs prototype validation
- Cost estimates -- based on rough token count calculations, not actual measurement

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pymupdf4llm well-documented, Anthropic structured output is GA
- Architecture: HIGH -- patterns derive directly from Phase 1 codebase analysis and ARCHITECTURE.md
- eCRF structure: HIGH -- based on direct examination of actual ECRF_text.txt
- Domain classification: MEDIUM-HIGH -- heuristic patterns are clear, LLM integration pattern is standard, but ambiguous datasets need prototype testing
- Pitfalls: HIGH -- directly informed by PITFALLS.md and actual eCRF examination

**Research date:** 2026-02-26
**Valid until:** 2026-03-26 (30 days -- stable libraries, no fast-moving components)
