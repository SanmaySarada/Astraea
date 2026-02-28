# Phase 6: Findings Domains and Complex Transformations - Research

**Researched:** 2026-02-27
**Domain:** SDTM Findings-class domains (LB, VS, EG, PE), SUPPQUAL, TS, Trial Design (TA, TE, TV, TI, SV), RELREC
**Confidence:** HIGH

## Summary

Phase 6 is the technically hardest phase in the pipeline. It requires implementing the TRANSPOSE pattern handler -- the only major execution pattern not yet built -- plus multi-source lab merging, SUPPQUAL generation with referential integrity, the mandatory TS domain, and trial design domains. The raw Fakedata reveals two distinct data shapes for Findings domains:

1. **Already-vertical data** (lab_results.sas7bdat, ecg_results.sas7bdat): Pre-structured in SDTM-like tall format with TESTCD/TEST/ORRES/ORRESU columns. These need DIRECT/RENAME mappings, not transpose. lab_results has 1350 rows across Chemistry, Haematology, Coagulation, Urinalysis, Immunology, and Endocrinology. ecg_results has 896 rows with 21 distinct ECG test codes.

2. **EDC-format data** (lb_biochem, lb_coagulation, lb_hem, lb_urin, lb_urin_ole, llb, eg_pre, eg_post, eg3, pe): Raw CRF-style data where each row is a visit, and results are in a single "test performed" column per subcategory. These need normalization/column alignment and merging, but they are NOT in wide horizontal format either -- they record "was the test performed" (Y/N), collection date/time, and a result status column, but individual test results come from the central lab (lab_results.sas7bdat).

**Critical finding:** The actual Fakedata does NOT require a classical horizontal-to-vertical "unpivot" transpose. The lab sub-files (lb_biochem, lb_coagulation, lb_hem, lb_urin) are CRF collection metadata (date, time, performed Y/N, out-of-range clinically significant Y/N), while the actual lab results are already in the vertical lab_results.sas7bdat file from the central lab. The primary challenge is merging these data sources and normalizing column names, not pivoting wide data to tall. However, the TRANSPOSE handler must still be implemented for general-purpose use (other studies may have truly wide lab data).

**Primary recommendation:** Structure this phase around 6 sub-plans: (1) TRANSPOSE handler + Findings execution engine, (2) LB domain with multi-source merging, (3) EG domain with pre/post-dose handling, (4) PE domain + VS stub, (5) SUPPQUAL generator with referential integrity, (6) TS + Trial Design domains (TA, TE, TV, TI, SV).

## Standard Stack

No new libraries needed. Phase 6 uses the existing stack entirely.

### Core (Already Implemented)
| Component | Module | Purpose |
|-----------|--------|---------|
| DatasetExecutor | `execution/executor.py` | Spec + raw data -> SDTM DataFrame |
| Pattern Handlers | `execution/pattern_handlers.py` | 8 implemented + TRANSPOSE stub |
| Transform Registry | `mapping/transform_registry.py` | 15 registered transforms |
| MappingEngine | `mapping/engine.py` | LLM-based variable mapping proposals |
| SDTMReference | `reference/sdtm_ig.py` | Domain specs including LB, VS, EG, PE, SV, TS, TA, TE, TV, TI, SUPPQUAL |
| CTReference | `reference/controlled_terms.py` | Codelist lookup for CT values |
| XPT Writer | `io/xpt_writer.py` | DataFrame -> .xpt with validation |
| CrossDomainContext | `execution/executor.py` | RFSTDTC, SE, TV for --DY, EPOCH, VISIT |
| Preprocessing | `execution/preprocessing.py` | filter_rows, align_multi_source_columns |

### New Modules Needed
| Component | Location | Purpose |
|-----------|----------|---------|
| TransposeHandler | `execution/transpose.py` | Findings-specific wide-to-tall transformation logic |
| SUPPQUALGenerator | `execution/suppqual.py` | Deterministic SUPPQUAL generation from unmapped variables |
| TSGenerator | `execution/trial_summary.py` | TS domain population from study metadata |
| FindingsExecutor | `execution/findings.py` | Orchestrator for multi-source Findings domain execution |

### No New Dependencies
The entire Phase 6 stack is pandas operations on DataFrames. No new pip packages.

## Raw Data Profile (Actual Fakedata)

### Lab Data Sources

| Source File | Rows | Type | Key Columns | Role |
|-------------|------|------|-------------|------|
| lab_results.sas7bdat | 1350 | Pre-SDTM vertical | LBTESTCD, LBTEST, LBCAT, LBORRES, LBORRESU, LBORNRLO, LBORNRHI, LBSTRESC, LBSTRESN, LBSTRESU, LBSTNRLO, LBSTNRHI, LBNRIND, LBSPEC, LBMETHOD, LBBLFL, LBFAST, LBDTC, LBDY | **Primary lab results from central lab** -- already in SDTM-like tall format |
| lb_biochem.sas7bdat | 29 | EDC CRF | LBCPERF_BIOCHEM, LBCDAT_BIOCHEM, LBCTIM_BIOCHEM, LBOORCS_BIOCHEM, LBTEST_BIOCHEM | Collection metadata for biochemistry panel |
| lb_coagulation.sas7bdat | 25 | EDC CRF | LBGPERF_COAG, LBGDAT_COAG, LBGTIM_COAG, LBOORCS_COAG, LBTEST_COAG | Collection metadata for coagulation panel |
| lb_hem.sas7bdat | 24 | EDC CRF | LBHPERF, LBHDAT, LBHTIM, LBOORCS1, LBTEST1 | Collection metadata for haematology panel |
| lb_urin.sas7bdat | 15 | EDC CRF | LBUPERF_URIN, LBUDAT_URIN, LBUTIM_URIN, LBOORCS_URIN, LBTEST_URIN | Collection metadata for urinalysis |
| lb_urin_ole.sas7bdat | 8 | EDC CRF | LBUPERF1_URIN, LBUDAT1_URIN, LBUTIM1_URIN, LBOORCS1_URIN, LBTEST1_URIN | OLE extension urinalysis |
| llb.sas7bdat | 31 | EDC CRF (different) | LBNAM, LBCAT, LBTEST2, LBSPEC, LBORRES, LBORRESU, LBORNRLO, LBORNRHI, LBCLEV, LBFAST | **Local lab results** -- already vertical with actual result values |
| lab.sas7bdat | 0 | Central lab extract | 58 clinical cols | **Empty** -- schema-only, no data |

**Key insight:** The lab domain has TWO data sources with actual results:
1. `lab_results.sas7bdat` (1350 rows) -- central lab, already SDTM-structured with LBTESTCD/LBTEST/LBORRES/etc.
2. `llb.sas7bdat` (31 rows) -- local lab, has LBTEST2/LBORRES/LBORRESU but different column names and no SDTM test codes

The lb_biochem/lb_coagulation/lb_hem/lb_urin files are **CRF collection metadata only** (date performed, time, "out of range clinically significant" flag). They do NOT contain actual lab results. They may be useful for supplemental qualifiers (QORIG=CRF) or for enriching collection timestamps.

### ECG Data Sources

| Source File | Rows | Type | Key Columns | Role |
|-------------|------|------|-------------|------|
| ecg_results.sas7bdat | 896 | Pre-SDTM vertical | EGTESTCD, EGTEST, EGORRES, EGORRESU, EGSTRESC, EGSTRESN, EGSTRESU, EGDTC, EGTPT | **Primary ECG results** -- already SDTM-like tall format, 21 test codes |
| eg_pre.sas7bdat | 27 | EDC CRF | EGPERF3, EGDAT3, EGTIM3, EGDTM3, EGRS3, EGABS3, EGCS3, EG_TPT_PRE (="Pre-dose") | CRF pre-dose ECG records -- 3 triplicates per visit |
| eg_post.sas7bdat | 18 | EDC CRF | Same as eg_pre but EG_TPT_POST (="Post-dose") | CRF post-dose ECG records |
| eg3.sas7bdat | 27 | EDC CRF | Same structure but EG_TPT (="Not Applicable") | CRF non-timed ECG records |

**Key insight:** ecg_results.sas7bdat already has the computed ECG parameters (QTcF, QRS, PR, RR, HR, etc.) in SDTM format. The eg_pre/eg_post/eg3 files contain the raw CRF data with overall interpretation (Normal/Abnormal), clinical significance, and abnormality descriptions. The pre/post distinction is captured in EG_TPT_PRE/EG_TPT_POST columns (time point reference).

### PE Data Source

| Source File | Rows | Type | Key Columns | Role |
|-------------|------|------|-------------|------|
| pe.sas7bdat | 11 | EDC CRF | PEPERF, PEDAT, PEDAT_RAW | Very sparse -- only "PE performed" (Y) and date. No body system, no findings. |

**Key insight:** PE data is minimal. It records only that a PE was performed on a given date, with no individual body system findings or results. This maps to a very simple PE domain (or may need SUPPQUAL for the "performed" flag). PE is technically a Findings domain but does NOT require transpose -- there is no test-level data to transpose.

### VS (Vital Signs) Data

**No VS raw data file exists in Fakedata.** There is no vs.sas7bdat or vital_signs.sas7bdat. VS domain cannot be implemented for this study without additional data. The ctest.sas7bdat file contains C1-INH complement test data, not vital signs.

### Trial Design / Special Purpose Data Sources

**No dedicated raw files for SV, TA, TE, TV, TI, or TS exist in Fakedata.** These domains must be:
- **TS:** Populated from study protocol metadata (constants from the study design)
- **TA/TE/TV/TI:** Populated from study protocol (arm structure, elements, visits, I/E criteria)
- **SV:** Derived from visit-level data embedded in the EDC data (InstanceName/FolderName columns present in all raw files)

The ie.sas7bdat file exists and was already mapped in Phase 5. TI could potentially be derived from ie.sas7bdat.

## Architecture Patterns

### Pattern 1: The TRANSPOSE Handler Design

The TRANSPOSE pattern handler must be fundamentally different from all other handlers. Other handlers operate per-variable (one input mapping -> one output Series). TRANSPOSE operates per-domain: it restructures the entire DataFrame.

**Recommended approach: Two-stage TRANSPOSE**

```python
# Stage 1: TransposeSpec describes the reshape
@dataclass
class TransposeSpec:
    """Configuration for a wide-to-tall transformation."""
    id_vars: list[str]          # Columns to keep as-is (USUBJID, VISITNUM, date cols)
    value_vars: list[str]       # Columns to unpivot (the test result columns)
    testcd_mapping: dict[str, str]  # Column name -> TESTCD value
    test_mapping: dict[str, str]    # Column name -> TEST label
    unit_mapping: dict[str, str]    # Column name -> unit string
    result_var: str             # Target for ORRES (e.g., "LBORRES")
    testcd_var: str             # Target for TESTCD (e.g., "LBTESTCD")
    test_var: str               # Target for TEST (e.g., "LBTEST")
    unit_var: str               # Target for ORRESU (e.g., "LBORRESU")

# Stage 2: Execute transpose via pandas.melt()
def execute_transpose(df: pd.DataFrame, spec: TransposeSpec) -> pd.DataFrame:
    """Transform wide DataFrame to tall SDTM format using pandas.melt()."""
    melted = pd.melt(
        df,
        id_vars=spec.id_vars,
        value_vars=spec.value_vars,
        var_name='_source_col',
        value_name=spec.result_var,
    )
    # Map source column names to TESTCD/TEST/unit
    melted[spec.testcd_var] = melted['_source_col'].map(spec.testcd_mapping)
    melted[spec.test_var] = melted['_source_col'].map(spec.test_mapping)
    melted[spec.unit_var] = melted['_source_col'].map(spec.unit_mapping)
    melted = melted.drop(columns=['_source_col'])
    # Drop rows where result is null (test not performed)
    melted = melted.dropna(subset=[spec.result_var])
    return melted
```

**Why pandas.melt():** It is the standard pandas operation for wide-to-tall. It handles the core unpivot cleanly. The complexity is not in the melt itself but in knowing WHICH columns are test results vs. metadata -- that is the LLM's job (identifying value_vars and their TESTCD/TEST mappings).

**Integration with DatasetExecutor:** The TRANSPOSE pattern handler cannot follow the current per-variable pattern (returns pd.Series). It must return a full DataFrame. Options:
1. **Pre-processing step**: Run transpose BEFORE the normal per-variable handler loop. The transposed DataFrame becomes the input to the standard handlers.
2. **Special handler mode**: When a spec contains any TRANSPOSE mappings, the executor switches to a different execution path.

**Recommendation: Option 1 (pre-processing).** Add a `_pre_transpose()` step in DatasetExecutor.execute() that checks if the spec is Findings-class, and if so, runs the transpose first, then feeds the transposed DataFrame through the standard per-variable handlers.

### Pattern 2: Multi-Source Lab Merging

For this study, lab merging follows a specific pattern:

```
Primary source: lab_results.sas7bdat (1350 rows, SDTM-structured)
  + llb.sas7bdat (31 rows, local lab, different column names)
  = Merged LB domain

EDC CRF files (lb_biochem, lb_coagulation, lb_hem, lb_urin):
  -> Supplemental collection metadata (not actual results)
  -> Could enrich lab_results with collection time, CRF performed flag
  -> Or go to SUPPLB as supplemental qualifiers
```

**Merging strategy:**
1. Start with lab_results.sas7bdat as the base (already has SDTM variable names)
2. Normalize llb.sas7bdat column names (LBTEST2 -> LBTEST, etc.) and append
3. EDC CRF files: extract collection dates/times, merge by subject+visit to enrich LBDTC
4. Non-mappable EDC columns -> SUPPLB

### Pattern 3: ECG Pre/Post-Dose Handling

The ECG domain has a clear split:
- `ecg_results.sas7bdat`: Computed parameters with EGTPT already populated
- `eg_pre.sas7bdat` + `eg_post.sas7bdat` + `eg3.sas7bdat`: CRF records with overall interpretation

**Strategy:**
1. ecg_results.sas7bdat is the primary source (already SDTM-formatted)
2. eg_pre/eg_post/eg3 provide supplemental data:
   - EGTPT (time point: Pre-dose, Post-dose, Not Applicable)
   - EGRS3 (overall interpretation: Normal/Abnormal)
   - EGCS3 (clinical significance)
   - EGABS3 (abnormality description)
3. These supplemental fields go to SUPPEG (QNAM: EGCLSIG, EGABS, etc.)

### Pattern 4: SUPPQUAL Generation (Deterministic)

SUPPQUAL must be generated deterministically, never by the LLM. The generator takes:
- Parent domain DataFrame
- List of SUPPQUAL candidate variables (from DomainMappingSpec.suppqual_candidates)
- Parent domain SEQ variable for IDVARVAL

**SUPPQUAL structure:**
```
STUDYID  | RDOMAIN | USUBJID | IDVAR  | IDVARVAL | QNAM     | QLABEL              | QVAL        | QORIG
PHA...   | AE      | 001     | AESEQ  | 1        | AECLSIG  | Clinical Sig.       | Y           | CRF
PHA...   | LB      | 001     | LBSEQ  | 5        | LBTOX    | Toxicity Grade      | Grade 2     | CRF
```

**Rules:**
- RDOMAIN = parent domain code (2 chars)
- IDVAR = parent domain SEQ variable (e.g., "AESEQ", "LBSEQ")
- IDVARVAL = the actual SEQ value (as string)
- QNAM = max 8 chars, alphanumeric, must be unique within RDOMAIN
- QLABEL = max 40 chars
- QVAL = the actual value (always Char type in SUPPQUAL)
- QORIG = "CRF", "ASSIGNED", "DERIVED", "PROTOCOL"
- Referential integrity: every (RDOMAIN, USUBJID, IDVAR, IDVARVAL) must point to an existing parent record

**Generator algorithm:**
```python
def generate_suppqual(
    parent_df: pd.DataFrame,
    parent_domain: str,
    supp_variables: list[SuppVariable],  # QNAM, QLABEL, source_col, QORIG
    study_id: str,
) -> pd.DataFrame:
    records = []
    seq_var = f"{parent_domain}SEQ"
    for _, row in parent_df.iterrows():
        for sv in supp_variables:
            val = row.get(sv.source_col)
            if pd.notna(val) and str(val).strip():
                records.append({
                    "STUDYID": study_id,
                    "RDOMAIN": parent_domain,
                    "USUBJID": row["USUBJID"],
                    "IDVAR": seq_var,
                    "IDVARVAL": str(int(row[seq_var])),
                    "QNAM": sv.qnam,
                    "QLABEL": sv.qlabel,
                    "QVAL": str(val),
                    "QORIG": sv.qorig,
                    "QEVAL": sv.qeval or "",
                })
    return pd.DataFrame(records)
```

### Pattern 5: TS Domain Population

TS is a key-value domain. Each row is one parameter. Required parameters per FDA Business Rules:

| TSPARMCD | TSPARM | How to Populate | Source |
|----------|--------|-----------------|--------|
| SSTDTC | Study Start Date | Earliest RFSTDTC from DM | DM domain |
| SENDTC | Study End Date | Latest RFENDTC from DM | DM domain |
| SPONSOR | Clinical Study Sponsor | Study protocol | Config/constant |
| INDIC | Trial Disease/Condition Indication | "Hereditary Angioedema" | Config/constant |
| TRT | Investigational Therapy or Treatment | Study protocol | Config/constant |
| PCLAS | Pharmacological Class | Drug class | Config/constant |
| STYPE | Study Type | "INTERVENTIONAL" | Config/constant |
| SDTMVER | SDTM Version | "3.4" | Config/constant |
| TITLE | Study Title | Protocol title | Config/constant |
| NARMS | Planned Number of Arms | From protocol | Config/constant |
| ACESSION | Regulatory Agency Accession Number | IND/NDA number | Config/constant |
| PLESSION | Planned Enrollment | Target N | Config/constant |
| TPHASE | Trial Phase | "PHASE III TRIAL" | Config/constant |
| ADDON | Added on to Existing Treatments | "Y" or "N" | Config/constant |

**Implementation:** TS should be a simple DataFrame builder that takes a TSConfig Pydantic model with all required parameters and produces the TS DataFrame. Most values are sponsor-provided constants, not derived from raw data.

### Pattern 6: Trial Design Domains (TA, TE, TV, TI)

These domains describe the study DESIGN, not subject-level data:
- **TA (Trial Arms):** One row per planned element per arm. For this Phase III study: screening, treatment, follow-up elements in each arm.
- **TE (Trial Elements):** One row per planned element. Element code, description, start/end rules, duration.
- **TV (Trial Visits):** One row per planned visit per arm. Visit number, name, planned day.
- **TI (Trial Inclusion/Exclusion):** One row per I/E criterion. Already partially handled by IE domain in Phase 5.

**Source data:** These are protocol-level, not CRF-level. They must be populated from:
1. Study protocol document (manually extracted constants)
2. InstanceName/FolderName metadata in EDC files (for visit structure)
3. ie.sas7bdat for TI (already mapped as IE in Phase 5)

**Recommendation:** Provide a config-driven approach where the study team supplies a YAML/JSON with trial design parameters, and the system generates the domains deterministically. This is NOT an LLM task.

### Pattern 7: SV (Subject Visits) Domain

SV is derived from the visit-level metadata present in every raw EDC file:
- InstanceName (visit identifier)
- FolderName (visit folder)
- FolderSeq (visit sequence)

**Strategy:** Extract unique (USUBJID, InstanceName) pairs across all EDC files, map to VISITNUM/VISIT, and derive SVSTDTC (earliest date at that visit) and SVENDTC (latest date at that visit).

### Anti-Patterns to Avoid

- **Do NOT use the LLM to generate transpose logic or SUPPQUAL records.** These must be deterministic.
- **Do NOT try to merge lab CRF files with lab_results by unpivoting.** They contain different data (metadata vs. results).
- **Do NOT skip TS domain.** Missing TS triggers automatic FDA rejection.
- **Do NOT implement RELREC in Phase 6.** It adds complexity with minimal value for initial delivery. Defer to Phase 7 or later.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Wide-to-tall unpivot | Custom loop over columns | `pandas.melt()` | Handles all edge cases, fast, well-tested |
| SUPPQUAL record generation | LLM-proposed SUPPQUAL | Deterministic generator from parent domain + variable list | Referential integrity must be exact |
| TS parameter list | Custom hard-coded list | Config-driven YAML/JSON | Different studies have different required parameters |
| Normal range indicator | LLM comparison | Deterministic numeric comparison LBSTRESN vs LBSTNRLO/LBSTNRHI | Must be exact, not fuzzy |
| Visit name to VISITNUM mapping | LLM inference | Lookup table from FolderSeq/InstanceName | Must be consistent across all domains |

## Common Pitfalls

### Pitfall 1: Assuming Lab Sub-Files Contain Results
**What goes wrong:** Treating lb_biochem/lb_coagulation/lb_hem/lb_urin as containing actual lab results and trying to transpose them.
**Why it happens:** File names suggest they are lab result files. In reality, they are CRF collection metadata (was test performed, when, clinically significant OOR).
**How to avoid:** Use lab_results.sas7bdat as the primary source. Use EDC files only for supplemental metadata.
**Warning signs:** Very few rows (15-29) vs. expected lab result count (1350 in lab_results).

### Pitfall 2: SUPPQUAL Referential Integrity Breakage
**What goes wrong:** SUPPQUAL records reference SEQ values that do not exist in the parent domain after filtering or row removal.
**Why it happens:** Parent domain is filtered (e.g., removing "not performed" rows) after SUPPQUAL is generated.
**How to avoid:** Always generate SUPPQUAL AFTER the parent domain is finalized. Validate referential integrity as a post-step.
**Warning signs:** P21 validation errors about orphaned SUPPQUAL records.

### Pitfall 3: LBNRIND Derivation Errors
**What goes wrong:** Normal range indicator (NORMAL/LOW/HIGH/ABNORMAL) does not match the actual numeric comparison of LBSTRESN vs. reference ranges.
**Why it happens:** lab_results.sas7bdat already has LBNRIND populated. If it is overwritten with a re-derived value, discrepancies can occur. Also, non-numeric results (e.g., "Not detect") cannot be compared to ranges.
**How to avoid:** Use the source LBNRIND when available. Only derive when missing. Handle non-numeric results explicitly.
**Warning signs:** LBNRIND = "LOW" but LBSTRESN is within LBSTNRLO-LBSTNRHI range.

### Pitfall 4: Missing TS Parameters Causing FDA Rejection
**What goes wrong:** TS domain is generated but missing mandatory parameters. FDA validates TS completeness as part of technical conformance checks. Missing parameters = automatic technical rejection.
**Why it happens:** Not all required parameters are obvious. The FDA Business Rules document lists conditional parameters that depend on study type.
**How to avoid:** Use the full FDA Business Rules parameter list as a checklist. Validate TS completeness before output.
**Warning signs:** TS domain has fewer than 15 rows (typical minimum for a Phase III study).

### Pitfall 5: ECG Triplicate Record Handling
**What goes wrong:** ECG data from eg_pre/eg_post/eg3 has 3 replicate measurements per visit (EGNUM3 = 1, 2, 3). Failing to handle triplicates leads to incorrect EGSEQ, missing EGGRPID, or lost data.
**Why it happens:** Each ECG visit has 3 individual tracings. The EGGRPID should group them, and EGSEQ should sequence them within a subject.
**How to avoid:** Use EGNUM3 to assign EGGRPID (group triplicates) and include it in EGSEQ generation sort keys.

### Pitfall 6: QNAM Length Violations
**What goes wrong:** SUPPQUAL QNAM values exceed 8 characters, causing XPT write failure.
**Why it happens:** Source variable names are often long (e.g., "LBOORCS_BIOCHEM"). Using them directly as QNAM violates the 8-char limit.
**How to avoid:** Always truncate/remap QNAM to max 8 chars. Build a QNAM mapping table upfront.

## Code Examples

### TRANSPOSE via pandas.melt()
```python
# Source: pandas official documentation
# For truly wide lab data (not this study's data, but the general pattern):
import pandas as pd

# Wide format: one column per test
wide_df = pd.DataFrame({
    "USUBJID": ["001", "001", "002"],
    "VISITNUM": [1, 2, 1],
    "WBC": [5.2, 5.5, 6.1],
    "RBC": [4.5, 4.3, 4.8],
    "HGB": [14.0, 13.5, 15.2],
})

# Transpose to tall SDTM LB format
tall_df = pd.melt(
    wide_df,
    id_vars=["USUBJID", "VISITNUM"],
    value_vars=["WBC", "RBC", "HGB"],
    var_name="LBTESTCD",
    value_name="LBORRES",
)

# Map test codes to full names and units
test_info = {
    "WBC": ("White Blood Cell Count", "10^9/L"),
    "RBC": ("Red Blood Cell Count", "10^12/L"),
    "HGB": ("Hemoglobin", "g/dL"),
}
tall_df["LBTEST"] = tall_df["LBTESTCD"].map(lambda x: test_info[x][0])
tall_df["LBORRESU"] = tall_df["LBTESTCD"].map(lambda x: test_info[x][1])
```

### SUPPQUAL Generation
```python
# Deterministic SUPPQUAL generator
def generate_suppqual(
    parent_df: pd.DataFrame,
    domain: str,
    study_id: str,
    supp_vars: list[dict],  # [{"qnam": "AECLSIG", "qlabel": "Clin Sig", "source": "EGCS3_STD", "qorig": "CRF"}]
) -> pd.DataFrame:
    seq_var = f"{domain}SEQ"
    records = []
    for _, row in parent_df.iterrows():
        for sv in supp_vars:
            val = row.get(sv["source"], "")
            if pd.notna(val) and str(val).strip():
                records.append({
                    "STUDYID": study_id,
                    "RDOMAIN": domain,
                    "USUBJID": row["USUBJID"],
                    "IDVAR": seq_var,
                    "IDVARVAL": str(int(row[seq_var])),
                    "QNAM": sv["qnam"][:8],  # Enforce max 8 chars
                    "QLABEL": sv["qlabel"][:40],  # Enforce max 40 chars
                    "QVAL": str(val),
                    "QORIG": sv["qorig"],
                    "QEVAL": sv.get("qeval", ""),
                })
    return pd.DataFrame(records)
```

### LBNRIND Derivation
```python
def derive_nrind(row: pd.Series) -> str:
    """Derive normal range indicator from numeric result and ranges."""
    stresn = row.get("LBSTRESN")
    nrlo = row.get("LBSTNRLO")
    nrhi = row.get("LBSTNRHI")

    if pd.isna(stresn):
        return ""
    try:
        val = float(stresn)
    except (ValueError, TypeError):
        return ""

    if pd.notna(nrlo) and pd.notna(nrhi):
        lo, hi = float(nrlo), float(nrhi)
        if val < lo:
            return "LOW"
        elif val > hi:
            return "HIGH"
        else:
            return "NORMAL"
    elif pd.notna(nrlo):
        return "LOW" if val < float(nrlo) else "NORMAL"
    elif pd.notna(nrhi):
        return "HIGH" if val > float(nrhi) else "NORMAL"
    return ""
```

### TS Domain Builder
```python
from pydantic import BaseModel

class TSConfig(BaseModel):
    study_id: str
    study_title: str
    sponsor: str
    indication: str
    treatment: str
    pharmacological_class: str
    study_type: str = "INTERVENTIONAL"
    sdtm_version: str = "3.4"
    trial_phase: str = "PHASE III TRIAL"
    planned_enrollment: int | None = None
    number_of_arms: int | None = None
    # ... additional parameters

def build_ts_domain(config: TSConfig, dm_df: pd.DataFrame | None = None) -> pd.DataFrame:
    params = [
        ("TITLE", "Trial Title", config.study_title),
        ("SPONSOR", "Clinical Study Sponsor", config.sponsor),
        ("INDIC", "Trial Disease/Condition Indication", config.indication),
        ("TRT", "Investigational Therapy or Treatment", config.treatment),
        ("PCLAS", "Pharmacological Class of Inv. Therapy", config.pharmacological_class),
        ("STYPE", "Study Type", config.study_type),
        ("SDTMVER", "SDTM Version", config.sdtm_version),
        ("TPHASE", "Trial Phase Classification", config.trial_phase),
    ]
    if dm_df is not None and "RFSTDTC" in dm_df.columns:
        sstdtc = dm_df["RFSTDTC"].dropna().min()
        sendtc = dm_df["RFENDTC"].dropna().max() if "RFENDTC" in dm_df.columns else ""
        params.append(("SSTDTC", "Study Start Date", str(sstdtc)))
        params.append(("SENDTC", "Study End Date", str(sendtc)))

    rows = []
    for i, (parmcd, parm, val) in enumerate(params, 1):
        rows.append({
            "STUDYID": config.study_id,
            "DOMAIN": "TS",
            "TSSEQ": i,
            "TSPARMCD": parmcd,
            "TSPARM": parm,
            "TSVAL": val,
        })
    return pd.DataFrame(rows)
```

## Data Flow for Phase 6

### LB Domain Flow
```
lab_results.sas7bdat (1350 rows, primary)
  -> Normalize column names (most already SDTM)
  -> DIRECT/RENAME mappings for LBTESTCD, LBTEST, LBORRES, etc.

llb.sas7bdat (31 rows, local lab)
  -> Normalize: LBTEST2 -> LBTEST, etc.
  -> Merge with lab_results via pd.concat

lb_biochem/lb_coag/lb_hem/lb_urin (CRF metadata)
  -> Extract collection date/time enrichment
  -> Non-standard variables -> SUPPLB

Combined -> Standard executor pipeline -> LB.xpt + SUPPLB.xpt
```

### EG Domain Flow
```
ecg_results.sas7bdat (896 rows, primary)
  -> DIRECT/RENAME mappings (already SDTM-like)
  -> Has EGTPT, EGGRPID, etc.

eg_pre/eg_post/eg3 (CRF data, 72 rows total)
  -> Extract: interpretation, clinical significance, abnormality descriptions
  -> Merge timepoint info into ecg_results or -> SUPPEG

Combined -> Standard executor pipeline -> EG.xpt + SUPPEG.xpt
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Hand-code SUPPQUAL per domain | Deterministic generator driven by variable list | Referential integrity guaranteed |
| TS populated manually | Config-driven TS builder | Completeness validation automated |
| Wide-to-tall custom code per domain | Generic transpose handler + pandas.melt | Reusable across studies |

## Open Questions

1. **llb.sas7bdat LBTESTCD mapping:** The local lab file has LBTEST2 (test name) but no LBTESTCD (test code). How to assign standard LBTESTCD codes? Options: (a) LLM-based matching to CDISC Lab Test Code CT, (b) manual mapping table, (c) leave as study-specific codes.
   - Recommendation: Use LLM to propose LBTESTCD mappings during the mapping phase, validate against CT.

2. **VS domain absence:** No vital signs data exists in Fakedata. Should we create a VS stub/placeholder, or skip VS entirely?
   - Recommendation: Skip VS for this study. Implement the VS mapping pattern in the generic transpose handler but do not generate VS.xpt.

3. **Trial Design data source:** TA, TE, TV require protocol-level design data not present in raw EDC files. How to source this?
   - Recommendation: Create a study_design.yaml config file with arm/element/visit definitions. Generate TA/TE/TV deterministically from config.

4. **RELREC complexity:** DOM-15 requires RELREC. How complex is this for the current data?
   - What we know: RELREC links records across domains (e.g., AE to CM). It requires identifying relationships by key (USUBJID + dates or coded references).
   - Recommendation: Implement a minimal RELREC with only obvious relationships (AE-CM by subject+date overlap). Mark as optional/deferred if too complex.

5. **lab.sas7bdat purpose:** The file exists but has 0 rows. Is it a central lab schema that was never populated?
   - Recommendation: Ignore it. The 58-column schema suggests it is a central lab extract format that was superseded by lab_results.sas7bdat.

## Recommended Plan Structure

Based on the data analysis, the phase should be split into 6 sub-plans:

| Sub-plan | Focus | Complexity | Dependencies |
|----------|-------|-----------|--------------|
| 06-01 | TRANSPOSE handler + Findings execution engine | HIGH | None (foundational) |
| 06-02 | LB domain (multi-source merge, primary Findings domain) | HIGH | 06-01 |
| 06-03 | EG domain (pre/post-dose, ecg_results + CRF merge) | MEDIUM | 06-01 |
| 06-04 | PE domain + VS stub | LOW | 06-01 |
| 06-05 | SUPPQUAL generator + SUPPLB + SUPPEG | HIGH | 06-02, 06-03 |
| 06-06 | TS + Trial Design (TA, TE, TV, TI, SV) + RELREC | MEDIUM | Phase 5 DM/SE data |

## Sources

### Primary (HIGH confidence)
- Actual Fakedata file analysis (pyreadstat profiling of all relevant .sas7bdat files)
- domains.json SDTM-IG reference specs for LB, VS, EG, PE, SV, TS, TA, TE, TV, TI, SUPPQUAL
- Existing codebase: execution/executor.py, execution/pattern_handlers.py, models/mapping.py, transforms/

### Secondary (MEDIUM confidence)
- PITFALLS.md C4 (SUPPQUAL referential integrity), M4 (transpose errors)
- ARCHITECTURE.md component boundaries and data flow patterns
- pandas.melt() official documentation for transpose operations

### Tertiary (LOW confidence)
- FDA Business Rules for TS mandatory parameters (should be verified against current FDA guidance document)
- RELREC implementation complexity (limited codebase examples)

## Metadata

**Confidence breakdown:**
- Raw data analysis: HIGH - directly profiled all relevant files
- TRANSPOSE handler design: HIGH - pandas.melt() is well-understood; data analysis shows most data is already vertical
- SUPPQUAL generation: HIGH - SUPPQUAL spec is well-defined, algorithm is straightforward
- TS parameters: MEDIUM - FDA Business Rules list needs verification against current guidance
- Trial Design domains: MEDIUM - no raw data source; requires config-driven approach
- RELREC: LOW - complex cross-domain linking, should be kept minimal

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable -- no fast-moving dependencies)
