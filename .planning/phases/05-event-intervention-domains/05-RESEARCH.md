# Phase 5: Event and Intervention Domains - Research

**Researched:** 2026-02-27
**Domain:** SDTM Events-class (AE, CE, MH, DS, DV) and Interventions-class (CM, EX) domains + IE (Findings but no-transpose)
**Confidence:** HIGH

## Summary

Phase 5 extends the proven DM mapping+execution pipeline to 8 additional SDTM domains. The existing MappingEngine, DatasetExecutor, pattern handlers, and transform infrastructure are fully ready -- no new patterns or handlers need to be invented. The core work is: (1) running the mapping engine on each domain with correct context, (2) handling domain-specific data quirks in the raw Fakedata, and (3) writing integration tests per domain.

All 8 domains use mapping patterns already implemented: ASSIGN, DIRECT, RENAME, REFORMAT, DERIVATION, LOOKUP_RECODE, and COMBINE. No TRANSPOSE is needed (that is Phase 6). All required CT codelists are already bundled (verified: 12 unique codelist codes across the 8 domains, all present in codelists.json).

**Primary recommendation:** Structure plans as 3 waves grouped by complexity, with AE (highest complexity, most variables, most codelists) as its own plan, then medium-complexity domains (CM, EX, DS), then simple domains (MH, IE, CE, DV). Each wave follows the same pattern: map domain -> review -> execute -> validate XPT output.

## Standard Stack

No new libraries needed. Phase 5 uses the existing stack entirely.

### Core (Already Implemented)
| Component | Module | Purpose |
|-----------|--------|---------|
| MappingEngine | `src/astraea/mapping/engine.py` | LLM-based variable mapping proposals |
| MappingContextBuilder | `src/astraea/mapping/context.py` | Assembles focused LLM context |
| DatasetExecutor | `src/astraea/execution/executor.py` | Spec + raw data -> SDTM DataFrame |
| Pattern Handlers | `src/astraea/execution/pattern_handlers.py` | ASSIGN, DIRECT, RENAME, REFORMAT, LOOKUP_RECODE, DERIVATION, COMBINE |
| Transform Registry | `src/astraea/mapping/transform_registry.py` | 15 registered transforms |
| XPT Writer | `src/astraea/io/xpt_writer.py` | DataFrame -> .xpt with validation |
| CrossDomainContext | `src/astraea/execution/executor.py` | RFSTDTC, SE, TV for --DY, EPOCH, VISIT |

### Supporting
| Component | Module | Purpose |
|-----------|--------|---------|
| SDTMReference | `src/astraea/reference/sdtm_ig.py` | Domain specs, variable specs, key variables |
| CTReference | `src/astraea/reference/controlled_terms.py` | Codelist lookup and validation |
| DomainReviewer | `src/astraea/review/reviewer.py` | Human review gate |
| SessionStore | `src/astraea/review/session.py` | Review session persistence |

### No Alternatives Needed
The entire Phase 5 stack is the existing codebase. No new dependencies.

## Raw Data Profile (Actual Fakedata)

### Domain-to-Source Mapping

| Domain | Source Files | Rows | Clinical Vars | Key Challenge |
|--------|-------------|------|---------------|---------------|
| **AE** | ae.sas7bdat | 14 | 110 | Most complex: MedDRA coded terms, 8 seriousness checkboxes (0/1->Y/N), severity, causality, action taken, outcome, multiple date fields |
| **CM** | cm.sas7bdat | 37 | 98 | WHODrug coded medications, dose parsing (text dose), partial dates (un UNK patterns), indication coded values |
| **EX** | ex.sas7bdat + ex_ole.sas7bdat | 12+2 | 31+24 | Two sources (main study + OLE), conditional records (EXYN=Y/N), date+time combination, capsule count as dose |
| **MH** | mh.sas7bdat + haemh.sas7bdat | 6+3 | 57+156 | Two sources (general MH + HAE-specific MH), MedDRA coded, many partial date variants |
| **DS** | ds.sas7bdat + ds2.sas7bdat | 5+5 | 30+63 | Two sources (EOT + EOS), disposition event coding, death-related variables in ds2 |
| **IE** | ie.sas7bdat | 3 | 41 | Findings-class but no transpose, inclusion/exclusion criteria, protocol version |
| **CE** | ce.sas7bdat | 16 | 59 | HAE attack events (study-specific), location checkboxes, severity, hospitalization |
| **DV** | dv.sas7bdat | 2 | 35 | Completely different EDC format (no standard column names), deviation metadata |

### Critical Data Patterns Observed

**Pattern 1: Checkbox-to-Y/N Conversion (AE seriousness)**
AE seriousness criteria (AESDTH, AESLIFE, AESHOSP, AESDISAB, AESCONG, AESMIE) are stored as numeric 0.0/1.0 in the raw data. SDTM requires "Y"/"N" strings (CT codelist C66742). This needs a REFORMAT or DERIVATION handler that converts 0->N, 1->Y.

```python
# Raw: AESDTH = 0.0 (float64)
# SDTM: AESDTH = "N" (C66742)
# Pattern: LOOKUP_RECODE with custom 0/1->Y/N mapping, or REFORMAT with a dedicated transform
```

**Pattern 2: _STD Columns as Pre-Coded Values**
Most categorical variables have companion `_STD` columns (e.g., AESER_STD, AEOUT_STD, CMDOSFRQ_STD) that already contain CT submission values. The LLM should map from _STD columns, not display columns.

```
AEOUT -> "Recovered/Resolved" (display)
AEOUT_STD -> "RECOVERED/RESOLVED" (CT submission value)
```

**Pattern 3: MedDRA Coded Terms**
AE and MH have extensive MedDRA coding (_PT, _PT_CODE, _SOC, _SOC_CODE, _HLGT, _HLT, _LLT). These map to AEDECOD (PT), AEBODSYS (SOC). Direct mapping from _PT column.

**Pattern 4: Multiple Source Datasets per Domain**
EX (ex + ex_ole), MH (mh + haemh), DS (ds + ds2) each merge 2 source files. The executor's `_merge_raw` method handles this via pd.concat. Source variable names may differ between files (e.g., ds has DSDECOD, ds2 has DSDECOD2).

**Pattern 5: Partial Dates**
CM has "un UNK 2004" format dates (year-only). MH has similar patterns. The existing `parse_string_date_to_iso` transform handles these.

**Pattern 6: DV Dataset Has Non-Standard Structure**
dv.sas7bdat uses completely different column naming (Deviation_Id, Category, Description, Date_Occurred, Subject_ID) -- not the typical EDC pattern. It does not have standard EDC columns (no SiteNumber, no Subject, etc.). USUBJID generation will need Subject_ID, and site info will need Site_Number.

## Architecture Patterns

### End-to-End Flow Per Domain

The proven DM pattern scales directly:

```
1. Profile raw data (already done by profiler)
2. Run MappingEngine.map_domain() -> DomainMappingSpec
3. Run DomainReviewer for human review -> approved spec
4. Build CrossDomainContext (RFSTDTC from DM, SE for EPOCH, TV for VISIT)
5. Run DatasetExecutor.execute() -> SDTM DataFrame
6. Run DatasetExecutor.execute_to_xpt() -> .xpt file
7. Validate output
```

### Multi-Source Domain Handling

For domains with multiple source files (EX, MH, DS):
```python
# MappingEngine receives all source profiles
engine.map_domain(
    domain="DS",
    source_profiles=[ds_profile, ds2_profile],
    ecrf_forms=[ds_form, ds2_form],
    study_metadata=study_meta,
)

# Executor receives all raw DataFrames
executor.execute(
    spec=ds_spec,
    raw_dfs={"ds": ds_df, "ds2": ds2_df},  # merged internally
    cross_domain=cross_domain_ctx,
)
```

**Challenge:** When source files have different column names (DSDECOD vs DSDECOD2), the merge produces a wide DataFrame with both columns. The LLM must map from the correct source column for each record type. For DS, this likely means separate mapping passes or the LLM understanding both column sets.

### Recommended Plan Structure

**Wave 1: AE Domain (Solo -- Most Complex)**
- AE has the most variables (29), most codelists (5), checkbox pattern, MedDRA coding, and is the highest-regulatory-importance domain after DM
- Validate the full E2E pipeline with the most complex case first

**Wave 2: Medium Complexity (CM, EX, DS)**
- CM: Drug coding, dose parsing, partial dates
- EX: Two sources, conditional dosing, date/time combination
- DS: Two sources (EOT/EOS), disposition coding, death variables

**Wave 3: Simple Domains (MH, IE, CE, DV)**
- MH: MedDRA coded, two sources but straightforward
- IE: Findings-class but simple (no transpose), just criteria recording
- CE: HAE-specific clinical events, straightforward event recording
- DV: Non-standard source format but small (2 rows), simple mapping

### Cross-Domain Data Dependencies

All domains except DM need:
1. **RFSTDTC lookup** (from DM) -- for --DY calculation
2. **SE data** (if available) -- for EPOCH assignment
3. **TV data** (if available) -- for VISITNUM assignment

This means DM must be executed first, and its RFSTDTC values extracted into CrossDomainContext. This is already supported by the executor.

```python
# After DM execution:
dm_df = executor.execute(dm_spec, ...)
rfstdtc_lookup = dict(zip(dm_df["USUBJID"], dm_df["RFSTDTC"]))
cross_domain = CrossDomainContext(rfstdtc_lookup=rfstdtc_lookup)
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CT codelist lookup | Custom mapping dicts | CTReference.lookup_codelist() + LOOKUP_RECODE handler | Already handles extensible/non-extensible, synonyms, submission values |
| Date conversion | Per-domain date parsing | parse_string_date_to_iso / sas_date_to_iso via REFORMAT handler | Already handles "DD Mon YYYY", SAS numeric, partial dates |
| --DY calculation | Per-domain study day logic | DatasetExecutor._derive_dy() + calculate_study_day_column | Already handles matching --DTC to --DY via column suffix |
| --SEQ generation | Custom sequence numbering | DatasetExecutor._generate_seq() + generate_seq | Already handles USUBJID-scoped monotonic sequences |
| EPOCH assignment | Manual epoch logic | DatasetExecutor._assign_epoch() + assign_epoch | Already handles SE-based epoch determination |
| USUBJID generation | String concatenation | handle_derivation with generate_usubjid | Already handles study+site+subject joining |
| Column ordering | Manual reordering | DatasetExecutor._enforce_column_order() | Already reads order from VariableMapping.order |

**Key insight:** The entire execution infrastructure from Phase 4.1 was built to be domain-agnostic. Phase 5 should produce mapping specs and let the existing pipeline do all the work.

## Common Pitfalls

### Pitfall 1: Checkbox 0/1 to Y/N Conversion
**What goes wrong:** AE seriousness checkboxes are float64 (0.0/1.0) in raw data. If mapped via DIRECT, the SDTM output contains 0.0/1.0 instead of "Y"/"N". This fails P21 validation for CT codelist C66742.
**How to avoid:** Use LOOKUP_RECODE with a custom recode (1.0->"Y", 0.0->"N") or use DERIVATION with a transform. The LOOKUP_RECODE handler may need enhancement to handle numeric source values being matched as strings against codelist terms. Alternative: add a `numeric_to_yn` transform to the transform registry.
**Warning signs:** P21 validation error "value not found in codelist C66742"

### Pitfall 2: Multi-Source Datasets with Different Column Names
**What goes wrong:** DS comes from ds.sas7bdat (DSDECOD, DSTERM) and ds2.sas7bdat (DSDECOD2, DSENDAT2). After pd.concat merge, both DSDECOD and DSDECOD2 exist as separate columns with NaN where the other file's rows are. The LLM may propose mapping from DSDECOD, missing the ds2 rows entirely.
**How to avoid:** Either (a) pre-process multi-source datasets to align column names before feeding to the mapper, or (b) use COMBINE/DERIVATION patterns with a coalesce-style rule: "DSDECOD from ds.DSDECOD, fallback to ds2.DSDECOD2". Option (a) is simpler and more reliable.
**Warning signs:** Missing disposition records, NaN in Required variables

### Pitfall 3: DV Dataset Non-Standard Column Names
**What goes wrong:** dv.sas7bdat has completely different column naming (Subject_ID not Subject, Site_Number not SiteNumber, Date_Occurred not a standard date column). The standard USUBJID generation expects SiteNumber and Subject columns. The profiler may classify these columns incorrectly.
**How to avoid:** When executing DV, pass custom site_col="Site_Number" and subject_col="Subject_ID" to executor.execute(). The executor already supports these parameters.
**Warning signs:** USUBJID generation failure, ExecutionError on USUBJID

### Pitfall 4: Partial Date Handling for CM Start Dates
**What goes wrong:** CM start dates include "un UNK 2004" (year-only), "un UNK 2000" patterns. These must produce "2004" (ISO 8601 partial year) in CMSTDTC, not be imputed to full dates. If the LLM maps from CMSTDAT (SAS datetime) instead of CMSTDAT_RAW (character), the partial dates lose their incompleteness.
**How to avoid:** For --DTC variables, the LLM should prefer _RAW string columns and use parse_string_date_to_iso transform, which preserves partial date components. The SAS datetime columns (CMSTDAT) have been interpolated by the EDC system and may not represent the actual precision of the original data.
**Warning signs:** All dates appearing as full YYYY-MM-DD when some should be partial

### Pitfall 5: AETERM vs AEDECOD Distinction
**What goes wrong:** AETERM is the verbatim reported term, AEDECOD is the MedDRA Preferred Term (dictionary-derived). The raw data has AETERM (verbatim) and AETERM_PT (MedDRA PT). Confusing these means AEDECOD contains verbatim text instead of coded terms.
**How to avoid:** Map AETERM <- raw AETERM (direct), AEDECOD <- raw AETERM_PT (rename). Same pattern for AEBODSYS <- AETERM_SOC.
**Warning signs:** AEDECOD values not matching MedDRA dictionary

### Pitfall 6: EX Records Where Drug Was Not Administered
**What goes wrong:** EX raw data has EXYN = "Yes"/"No". Records where EXYN = "No" should NOT appear in the SDTM EX domain (EX records represent actual exposures). Including them inflates the exposure dataset with non-events.
**How to avoid:** Filter EX source data to EXYN_STD = "Y" before mapping. This is a pre-processing step, not a mapping pattern. The LLM should be instructed about this in the context, or a DERIVATION rule should include the filter condition.
**Warning signs:** EX records with no dose date, no dose amount

### Pitfall 7: AESEV Missing from Raw Data
**What goes wrong:** The AE domain spec has AESEV (Severity/Intensity, C66769: MILD/MODERATE/SEVERE). The raw data does not have a direct AESEV column -- it has AEGRSER/AEGRSER_STD which is "CTCAE Grade" (Grade 1-3). These are related but not identical: severity (MILD/MODERATE/SEVERE) vs CTCAE toxicity grade (1/2/3). AETOXGR (Standard Toxicity Grade) is the correct target for CTCAE grade, while AESEV needs derivation from AEGRSER.
**How to avoid:** Map AETOXGR <- AEGRSER_STD (CTCAE grade number). Derive AESEV by mapping Grade 1->MILD, Grade 2->MODERATE, Grade 3->SEVERE. The LLM must understand this distinction.
**Warning signs:** AESEV containing numeric grades instead of text severity

## SDTM Domain Specifications (from domains.json)

### AE: Adverse Events (Events Class)
- **Structure:** One record per adverse event per subject
- **Key Variables:** STUDYID, USUBJID, AETERM, AESTDTC
- **Required (5):** STUDYID, DOMAIN, USUBJID, AESEQ, AETERM, AEDECOD
- **Expected (5):** AEBODSYS, AESER, AEACN, AEREL, AESTDTC, AEENDTC
- **Codelists:** C66769 (Severity), C66742 (Y/N for seriousness), C66767 (Action Taken), C66768 (Outcome)
- **Special:** 7 seriousness criterion flags (AESDTH, AESLIFE, AESHOSP, AESDISAB, AESCONG, AESCAN, AESMIE) all use C66742

### CM: Concomitant Medications (Interventions Class)
- **Structure:** One record per medication occurrence or constant-dosing interval per subject
- **Key Variables:** STUDYID, USUBJID, CMTRT, CMSTDTC
- **Required (4):** STUDYID, DOMAIN, USUBJID, CMSEQ, CMTRT
- **Expected (2):** CMSTDTC, CMENDTC
- **Codelists:** C71620 (Unit), C71113 (Frequency), C66729 (Route)
- **Special:** CMDOSE is Permissible, CMINDC (Indication) is Permissible, CMCLAS/CMCLASCD from ATC coding

### EX: Exposure (Interventions Class)
- **Structure:** One record per constant-dosing interval per subject
- **Key Variables:** STUDYID, USUBJID, EXTRT, EXSTDTC
- **Required (4):** STUDYID, DOMAIN, USUBJID, EXSEQ, EXTRT
- **Expected (4):** EXDOSE, EXDOSU, EXDOSFRM, EXSTDTC, EXENDTC
- **Codelists:** C71620 (Unit), C66726 (Dose Form), C71113 (Frequency), C66729 (Route)
- **Special:** Filter to EXYN=Y records only; merge ex.sas7bdat + ex_ole.sas7bdat

### MH: Medical History (Events Class)
- **Structure:** One record per medical history event per subject
- **Key Variables:** STUDYID, USUBJID, MHTERM
- **Required (4):** STUDYID, DOMAIN, USUBJID, MHSEQ, MHTERM
- **Expected (3):** MHDECOD, MHBODSYS, MHSTDTC, MHENDTC
- **Codelists:** C66742 (Y/N for prespecified/occur), C66728 (Relation to Reference Period)
- **Special:** Merge mh + haemh (HAE-specific medical history)

### DS: Disposition (Events Class)
- **Structure:** One record per disposition status or protocol milestone per subject
- **Key Variables:** STUDYID, USUBJID, DSDECOD, DSSTDTC
- **Required (5):** STUDYID, DOMAIN, USUBJID, DSSEQ, DSTERM, DSDECOD
- **Expected (2):** DSCAT, DSSTDTC
- **Codelists:** C66727 (Disposition Event: COMPLETED, ADVERSE EVENT, DEATH, etc.)
- **Special:** ds = treatment disposition (EOT), ds2 = study disposition (EOS). May produce 2 DS records per subject (one treatment, one study). DSCAT differentiates.

### IE: Inclusion/Exclusion Criteria Not Met (Findings Class -- no transpose)
- **Structure:** One record per inclusion/exclusion criterion not met per subject
- **Key Variables:** STUDYID, USUBJID, IETESTCD
- **Required (6):** STUDYID, DOMAIN, USUBJID, IESEQ, IETESTCD, IETEST, IECAT
- **Expected (3):** IEORRES, IESTRESC, IEDTC
- **No domain-specific codelists** (just C66734 for DOMAIN)
- **Special:** Only records where criteria were NOT met. If all subjects met all criteria, IE may be empty.

### CE: Clinical Events (Events Class)
- **Structure:** One record per event per subject
- **Key Variables:** STUDYID, USUBJID, CETERM, CESTDTC
- **Required (4):** STUDYID, DOMAIN, USUBJID, CESEQ, CETERM
- **Expected (3):** CEDECOD, CECAT, CESTDTC, CEENDTC
- **Codelists:** C66742 (Y/N for prespecified/occur)
- **Special:** In this study, CE represents HAE attacks (hereditary angioedema episodes) with location, severity, and timing data

### DV: Protocol Deviations (Events Class)
- **Structure:** One record per deviation per subject
- **Key Variables:** STUDYID, USUBJID, DVTERM, DVSTDTC
- **Required (4):** STUDYID, DOMAIN, USUBJID, DVSEQ, DVTERM
- **Expected (3):** DVDECOD, DVCAT, DVSTDTC
- **Codelists:** C99079 (Epoch)
- **Special:** Non-standard source format (different column naming convention)

## CT Codelists Status

All 12 unique codelist codes referenced by Phase 5 domains are bundled and verified:

| Code | Name | Terms | Ext | Used By |
|------|------|-------|-----|---------|
| C66727 | Disposition Event | 10 | Yes | DS.DSDECOD |
| C66728 | Relation to Reference Period | 5 | No | MH.MHENRF |
| C66729 | Route of Administration | 11 | Yes | CM.CMROUTE, EX.EXROUTE |
| C66726 | Pharmaceutical Dosage Form | 14 | Yes | EX.EXDOSFRM |
| C66734 | Domain Abbreviation | 25 | No | All domains (DOMAIN) |
| C66742 | No Yes Response | 2 | No | AE (8 vars), MH (2), CE (2) |
| C66767 | Action Taken with Study Treatment | 7 | No | AE.AEACN |
| C66768 | Outcome of Event | 6 | No | AE.AEOUT |
| C66769 | Severity/Intensity Scale | 3 | No | AE.AESEV |
| C71113 | Frequency | 9 | Yes | CM.CMDOSFRQ, EX.EXDOSFRQ |
| C71620 | Unit | 22 | Yes | CM.CMDOSU, EX.EXDOSU |
| C99079 | Epoch | 5 | Yes | DV.EPOCH |

**No missing codelists.** Phase 5 can proceed without CT additions.

## Execution Pipeline Gaps

### Gap 1: Numeric 0/1 to Y/N Transform (MUST ADD)
The AE seriousness checkboxes (AESDTH, AESLIFE, AESHOSP, etc.) are stored as float64 0.0/1.0. The LOOKUP_RECODE handler maps string values through codelist terms, but C66742 has terms {"N", "Y"} -- it does not handle numeric 0/1 input. Need either:
- **Option A (recommended):** Add a `numeric_to_yn` transform function to the registry that converts 0->"N", 1->"Y", NaN->None. Use via REFORMAT pattern.
- **Option B:** Enhance LOOKUP_RECODE to handle numeric source values by converting to string first.

### Gap 2: SPLIT Pattern Handler (STUB)
The SPLIT handler is currently a stub returning None. Phase 5 may need it for AE where combined date+time fields need splitting, but in practice the raw data has separate date (AESTDAT) and time (AESTTIM) columns, so COMBINE or separate REFORMAT may suffice. If SPLIT is not needed for Phase 5 data, defer to Phase 6.

### Gap 3: Multi-Source Column Alignment
When two source files have different column names (DSDECOD vs DSDECOD2), pd.concat produces a wide DataFrame. The LLM needs to handle this, but the mapping spec can only reference one source_variable per mapping. Solutions:
- **Option A (recommended):** Pre-process to align column names before mapping (rename DSDECOD2->DSDECOD, DSENDAT2->DSENDAT in ds2 before merge)
- **Option B:** Use DERIVATION with coalesce logic
- **Option C:** Map each source file to a separate spec, execute separately, then concat results

### Gap 4: EX Record Filtering (Drug Not Administered)
The executor does not currently filter source rows. EX needs rows where EXYN_STD="N" excluded. Solutions:
- **Option A (recommended):** Add a pre-filter step in the executor or as a pre-processing utility
- **Option B:** Let the LLM handle it in mapping logic (fragile, hard to verify)

### Gap 5: DV Custom Column Names
The DV source uses Subject_ID/Site_Number instead of Subject/SiteNumber. The executor.execute() already supports site_col and subject_col parameters. Just need to pass the correct values.

## Code Examples

### Domain Mapping Call (Proven on DM)
```python
from astraea.mapping.engine import MappingEngine
from astraea.mapping.context import MappingContextBuilder

engine = MappingEngine(llm_client, sdtm_ref, ct_ref)
ae_spec = engine.map_domain(
    domain="AE",
    source_profiles=[ae_profile],
    ecrf_forms=[ae_form],
    study_metadata=study_meta,
    cross_domain_profiles={"dm": dm_profile},  # for USUBJID context
)
```

### Domain Execution Call (Proven on DM)
```python
from astraea.execution.executor import DatasetExecutor, CrossDomainContext

# Build cross-domain context from DM
cross_domain = CrossDomainContext(
    rfstdtc_lookup=dict(zip(dm_result["USUBJID"], dm_result["RFSTDTC"])),
)

executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
ae_df = executor.execute(
    ae_spec,
    raw_dfs={"ae": ae_raw_df},
    cross_domain=cross_domain,
    study_id="PHA022121-C301",
)
```

### Numeric-to-YN Transform (TO ADD)
```python
def numeric_to_yn(value) -> str | None:
    """Convert numeric 0/1 or checkbox values to Y/N for C66742."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        if value == 1 or value == 1.0:
            return "Y"
        if value == 0 or value == 0.0:
            return "N"
    # Handle string "1"/"0" as well
    s = str(value).strip()
    if s in ("1", "1.0"):
        return "Y"
    if s in ("0", "0.0"):
        return "N"
    return None
```

### Multi-Source Pre-Processing (TO ADD for DS)
```python
def align_ds_sources(ds_df: pd.DataFrame, ds2_df: pd.DataFrame) -> pd.DataFrame:
    """Align column names between ds and ds2 before merge."""
    # ds2 uses suffixed names (DSDECOD2, DSENDAT2, etc.)
    rename_map = {
        "DSDECOD2": "DSDECOD",
        "DSDECOD2_STD": "DSDECOD_STD",
        "DSENDAT2": "DSENDAT",
        "DSENDAT2_RAW": "DSENDAT_RAW",
        # ... etc
    }
    ds2_aligned = ds2_df.rename(columns=rename_map)
    # Add DSCAT to differentiate
    ds_df = ds_df.copy()
    ds_df["DSCAT"] = "DISPOSITION EVENT"  # or "TREATMENT"
    ds2_aligned["DSCAT"] = "PROTOCOL MILESTONE"  # or "STUDY"
    return pd.concat([ds_df, ds2_aligned], ignore_index=True)
```

## Complexity Assessment Per Domain

| Domain | Complexity | Variables | Codelists | Multi-Source | Special Handling |
|--------|-----------|-----------|-----------|-------------|-----------------|
| AE | HIGH | 29 | 5 | No | Checkbox 0/1->Y/N, MedDRA, severity vs grade, multiple action fields |
| CM | MEDIUM | 19 | 3 | No | Partial dates, dose text parsing, WHODrug coding |
| EX | MEDIUM | 15 | 4 | Yes (2 files) | Filter EXYN=N, date+time, capsule dose, OLE merge |
| DS | MEDIUM | 10 | 1 | Yes (2 files) | EOT/EOS merge, column alignment, DSCAT differentiation |
| MH | LOW-MED | 14 | 2 | Yes (2 files) | HAE-specific MH merge, MedDRA, partial dates |
| IE | LOW | 12 | 0 | No | Findings-class but no transpose, criteria format |
| CE | LOW-MED | 14 | 1 | No | HAE attacks, location data, study-specific terms |
| DV | LOW | 11 | 1 | No | Non-standard column names, small dataset |

## Recommended Wave Structure

**Wave 1 (Plan 05-01): AE Domain End-to-End**
- Add numeric_to_yn transform to registry
- Map AE domain via MappingEngine
- Execute AE spec via DatasetExecutor
- Validate: all 29 variables, 5 codelists, seriousness flags, MedDRA terms
- Integration test with real ae.sas7bdat

**Wave 2 (Plan 05-02): CM + EX Domains**
- Add source row filtering utility (for EX EXYN=N exclusion)
- Map CM domain (dose, route, frequency, indication)
- Map EX domain (merge ex + ex_ole, filter to administered only)
- Execute both, validate XPT output
- Integration tests

**Wave 3 (Plan 05-03): DS + MH Domains**
- Add multi-source column alignment utility (for DS ds+ds2)
- Map DS domain (EOT + EOS merge, disposition coding, DSCAT)
- Map MH domain (mh + haemh merge, MedDRA)
- Execute both, validate XPT output
- Integration tests

**Wave 4 (Plan 05-04): IE + CE + DV Domains**
- Map IE domain (criteria not met)
- Map CE domain (HAE attacks)
- Map DV domain (non-standard format, custom column names)
- Execute all three, validate XPT output
- Integration tests

**Wave 5 (Plan 05-05): Cross-Domain Validation + Full Suite**
- Cross-domain USUBJID validation (all 8 domains vs DM)
- End-to-end CLI flow test (map -> review -> execute for all domains)
- Summary validation report across all domains
- Documentation of domain-specific mapping decisions

## Open Questions

1. **MedDRA coded terms in AEDECOD/MHDECOD:** Should these be direct-mapped from the _PT (Preferred Term) column, or should there be MedDRA codelist validation? MedDRA is not bundled (it is a licensed dictionary). For v1, recommend direct mapping from _PT column without MedDRA validation. MedDRA validation is a Phase 7 concern.

2. **EX dose derivation:** The raw EX data has EXCAP (capsules taken) and EXDTTM (datetime). SDTM EX expects EXDOSE (numeric dose) and EXDOSU (unit). If the study drug is a capsule with a fixed dose per capsule, EXDOSE = EXCAP * dose_per_capsule. The dose_per_capsule is protocol-specific. Recommend: map EXCAP directly to a SUPPEX qualifier if dose cannot be derived, or let the LLM propose a derivation based on protocol context.

3. **DS domain structure:** Should the EOT (end of treatment) and EOS (end of study) disposition records be separate rows in one DS domain or separate datasets? SDTM standard says one DS domain with DSCAT to differentiate. Recommend: merge with DSCAT = "DISPOSITION EVENT" for treatment and "PROTOCOL MILESTONE" for study.

4. **haemh_screen.sas7bdat:** This file has 0 rows. Include in MH source list but expect it to contribute nothing. Should not cause errors.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `src/astraea/mapping/engine.py`, `src/astraea/execution/executor.py`, `src/astraea/execution/pattern_handlers.py`
- Bundled reference data: `src/astraea/data/sdtm_ig/domains.json` (all 8 domain specs verified)
- Bundled CT data: `src/astraea/data/ct/codelists.json` (all 12 referenced codelists verified present)
- Raw data profiling: All 12 Fakedata SAS files profiled with pyreadstat

### Secondary (MEDIUM confidence)
- SDTM-IG v3.4 specification for domain structures and variable definitions
- DM integration test pattern from `tests/integration/execution/test_dm_execution.py`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new components needed, all proven on DM
- Architecture: HIGH -- exact same pattern as DM, just more domains
- Domain specs: HIGH -- verified against bundled domains.json
- CT codelists: HIGH -- all 12 codes verified present
- Raw data mapping: MEDIUM -- profiled but LLM quality depends on context assembly
- Pitfalls: HIGH -- identified from actual data inspection

**Research date:** 2026-02-27
**Valid until:** Indefinite (codebase-specific, not dependent on external libraries)
