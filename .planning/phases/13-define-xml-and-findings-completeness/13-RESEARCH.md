# Phase 13: Define.xml and Findings Completeness - Research

**Researched:** 2026-02-28
**Domain:** Define.xml 2.0 structural fixes + SDTM Findings domain derivations
**Confidence:** HIGH

## Summary

Phase 13 addresses two interrelated areas: (1) structural errors in define.xml generation that will cause P21 define.xml validation failures, and (2) missing Findings domain derivations (standardized results, normal range indicators, date imputation flags) that are Expected variables per SDTM-IG v3.4.

The define.xml issues are concentrated in `src/astraea/submission/define_xml.py` and involve correcting ValueListDef placement, adding NCI C-codes to CodeListItem elements, creating missing ItemDef elements for ValueListDef targets, and adding several missing attributes (KeySequence, def:Label, integer DataType for --SEQ, def:Origin Source, ODM Originator/AsOfDateTime).

The Findings completeness issues require new derivation logic in `src/astraea/execution/findings.py` and `src/astraea/execution/executor.py` for --STRESC/--STRESN/--STRESU standardized results, --NRIND normal range indicator, and --DTF/--TMF date imputation flags. The imputation flag utility already exists in `src/astraea/transforms/imputation.py` but is not wired into the executor.

**Primary recommendation:** Fix define.xml structural issues first (they are self-contained XML generation changes), then add Findings derivations (they require new DataFrame-level logic in the execution pipeline).

## Standard Stack

No new libraries needed. All changes use existing stack:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `lxml` | existing | XML generation for define.xml | Already in use; etree API for namespace-aware XML |
| `pandas` | >=2.2 | DataFrame operations for derivations | Already in use for all execution logic |
| `pydantic` | >=2.10 | Model updates (CodelistTerm NCI code field) | Already in use for all data models |

### No New Dependencies
All 11 audit findings can be addressed with existing libraries. No new packages required.

## Architecture Patterns

### Pattern 1: ValueListDef Correction (HIGH-11)

**Current (WRONG):** ValueListDef is placed on the --TESTCD variable with OID `VL.{domain}.{testcd_var}`.

**Correct:** ValueListDef must be placed on EACH result variable (--ORRES, --STRESC, --STRESN) parameterized by --TESTCD values via WhereClauseDef.

**What this means concretely:**

```python
# WRONG (current): One VLD on TESTCD
# VL.LB.LBTESTCD -> ItemRef for each test code

# CORRECT: Separate VLD for each result variable
# VL.LB.LBORRES  -> ItemRef for each test code (parameterized by LBTESTCD)
# VL.LB.LBSTRESC -> ItemRef for each test code (parameterized by LBTESTCD)
# VL.LB.LBSTRESN -> ItemRef for each test code (parameterized by LBTESTCD)
```

The `_add_value_lists()` function must be refactored to:
1. Identify result variables (those ending in ORRES, STRESC, STRESN) in Findings domains
2. Create a separate ValueListDef for EACH result variable
3. Each ValueListDef has ItemRef entries per unique test code
4. WhereClauseDef filters on the --TESTCD variable (not on the result variable)
5. The ItemDef.def:ValueListRef attribute on each result variable's ItemDef must point to the corresponding VLD

**Define.xml 2.0 rule:** "A value list now always describes the variable that references it." ValueListDef on --TESTCD was a define.xml v1.0 pattern that is explicitly not permitted in v2.0.

**Result variable identification heuristic:**
```python
_RESULT_SUFFIXES = ("ORRES", "STRESC", "STRESN")
result_vars = [vm for vm in spec.variable_mappings
               if any(vm.sdtm_variable.endswith(s) for s in _RESULT_SUFFIXES)]
```

### Pattern 2: NCI C-codes on CodeListItem (HIGH-12)

**Current:** CodeListItem has CodedValue and Decode/TranslatedText but no Alias element.

**Correct structure per define.xml 2.0:**
```xml
<CodeListItem CodedValue="M">
  <Decode>
    <TranslatedText xml:lang="en">Male</TranslatedText>
  </Decode>
  <Alias Context="nci:ExtCodeID" Name="C20197"/>
</CodeListItem>
```

**Data gap:** The `CodelistTerm` model in `src/astraea/models/controlled_terms.py` does NOT have an `nci_code` field. The NCI C-code for each term (e.g., "C20197" for Male) is not stored in `codelists.json`.

**Required changes:**
1. Add `nci_code: str = Field(default="", ...)` to `CodelistTerm` model
2. Update `codelists.json` with NCI C-codes for each term (data enrichment task)
3. In `_add_codelists()`, emit `<Alias Context="nci:ExtCodeID" Name="{nci_code}"/>` on each CodeListItem

**Alternative (if data enrichment is deferred):** Emit Alias elements only when `nci_code` is populated. P21 will warn about missing codes but won't reject. This allows incremental rollout.

### Pattern 3: Missing ItemDef for ValueListDef ItemRef Targets (HIGH-13)

**Current:** ValueListDef contains ItemRef elements pointing to OIDs like `IT.LB.LBTESTCD.ALT` but no corresponding ItemDef with that OID is created.

**Fix:** For each ItemRef inside a ValueListDef, create a matching ItemDef:
```xml
<ItemDef OID="IT.LB.LBORRES.ALT" Name="LBORRES" SASFieldName="LBORRES"
         DataType="text" Length="200">
  <Description>
    <TranslatedText xml:lang="en">Result or Finding in Original Units</TranslatedText>
  </Description>
</ItemDef>
```

The OID pattern should be `IT.{domain}.{result_var}.{testcd}` (not `IT.{domain}.{testcd_var}.{testcd}` as currently generated). Each value-level ItemDef describes what the result variable looks like for that specific test code.

### Pattern 4: Findings Standardized Results Derivation (HIGH-04)

**Where to add:** After transpose produces --ORRES and --ORRESU, derive --STRESC, --STRESN, --STRESU.

**Derivation logic for LB domain:**
```python
def derive_standardized_results(df: pd.DataFrame, domain_prefix: str) -> pd.DataFrame:
    """Derive --STRESC, --STRESN, --STRESU from --ORRES, --ORRESU.

    For v1 (no unit conversion): copy ORRES -> STRESC,
    attempt numeric parse -> STRESN, copy ORRESU -> STRESU.
    """
    orres = f"{domain_prefix}ORRES"
    orresu = f"{domain_prefix}ORRESU"
    stresc = f"{domain_prefix}STRESC"
    stresn = f"{domain_prefix}STRESN"
    stresu = f"{domain_prefix}STRESU"

    # STRESC = character copy of ORRES
    df[stresc] = df[orres]

    # STRESN = numeric parse of ORRES (NaN for non-numeric)
    df[stresn] = pd.to_numeric(df[orres], errors="coerce")

    # STRESU = copy of ORRESU (no unit conversion in v1)
    if orresu in df.columns:
        df[stresu] = df[orresu]
    else:
        df[stresu] = None

    return df
```

**Important:** Full SI unit conversion (e.g., mg/dL -> mmol/L) is complex and study-specific. For v1, copy ORRESU to STRESU. Unit conversion can be a future enhancement. The key requirement is that --STRESC/--STRESN/--STRESU columns EXIST with reasonable values.

**Integration point:** This should be called in `FindingsExecutor.execute_lb()`, `execute_eg()`, and `execute_vs()` AFTER `self._executor.execute()` returns but BEFORE the DataFrame is finalized. The function should operate on the already-transposed/executed DataFrame.

### Pattern 5: NRIND Derivation (HIGH-05)

**Derivation logic:**
```python
def derive_nrind(df: pd.DataFrame, domain_prefix: str) -> pd.DataFrame:
    """Derive --NRIND from --STRESN vs --STNRLO/--STNRHI."""
    stresn = f"{domain_prefix}STRESN"
    stnrlo = f"{domain_prefix}STNRLO"
    stnrhi = f"{domain_prefix}STNRHI"
    nrind = f"{domain_prefix}NRIND"

    # Only derive where STRESN and at least one range bound exist
    has_result = df[stresn].notna() if stresn in df.columns else pd.Series(False, index=df.index)
    has_lo = df[stnrlo].notna() if stnrlo in df.columns else pd.Series(False, index=df.index)
    has_hi = df[stnrhi].notna() if stnrhi in df.columns else pd.Series(False, index=df.index)

    # Convert to numeric for comparison
    result_num = pd.to_numeric(df.get(stresn), errors="coerce")
    lo_num = pd.to_numeric(df.get(stnrlo), errors="coerce")
    hi_num = pd.to_numeric(df.get(stnrhi), errors="coerce")

    conditions = [
        has_result & has_lo & (result_num < lo_num),
        has_result & has_hi & (result_num > hi_num),
        has_result & has_lo & has_hi & (result_num >= lo_num) & (result_num <= hi_num),
    ]
    choices = ["LOW", "HIGH", "NORMAL"]

    df[nrind] = np.select(conditions, choices, default=None)
    # Convert numpy None to pandas NA for proper handling
    df[nrind] = df[nrind].where(df[nrind] != "0", other=None)

    return df
```

**Valid NRIND values per CT codelist C78736:** NORMAL, HIGH, LOW, ABNORMAL, HIGH HIGH, LOW LOW. For basic derivation, use NORMAL/HIGH/LOW. ABNORMAL can be used as a catch-all when only one bound is available and the result is outside it.

**Where to add:** In FindingsExecutor after standardized results derivation (NRIND depends on STRESN).

### Pattern 6: Date Imputation Flags (HIGH-03)

**Current state:** The imputation utility exists in `src/astraea/transforms/imputation.py` with `get_date_imputation_flag()` and `get_time_imputation_flag()`. These are fully implemented but NOT wired into the executor.

**Integration approach:** The executor needs to track the original (partial) DTC value before REFORMAT converts it to full ISO 8601. Then generate --DTF/--TMF by comparing original vs imputed.

**Key challenge:** The current REFORMAT handler for dates (`handle_reformat` -> `parse_string_date_to_iso`) does NOT impute missing date components -- it truncates. "Mar 2022" becomes "2022-03", not "2022-03-01". This means --DTF is only needed when actual imputation occurs (filling in missing day/month).

**Decision needed by planner:** If the current pipeline does NOT impute dates (it truncates per SDTM rules), then --DTF/--TMF flags would only be needed for cases where imputation IS performed (which currently doesn't happen). The planner should decide:
- Option A: Wire in DTF/TMF for future imputation support (infrastructure)
- Option B: Add actual date imputation logic + DTF/TMF generation together
- Option C: Skip DTF/TMF for v1 since no imputation occurs (truncation is correct SDTM behavior)

**If imputation IS added:** Store original DTC in a temporary column, impute to full date, then compare to generate flags.

```python
# In executor, after REFORMAT produces --DTC columns:
for dtc_col in [c for c in result_df.columns if c.endswith("DTC")]:
    dtf_col = dtc_col.replace("DTC", "DTF")
    if dtf_col in mapped_vars:  # Only if DTF is in the spec
        result_df[dtf_col] = result_df.apply(
            lambda row: get_date_imputation_flag(
                row.get(f"_orig_{dtc_col}", ""), row[dtc_col]
            ), axis=1
        )
```

### Pattern 7: Define.xml Attribute Completeness (MED-06 through MED-10)

**MED-06: KeySequence on ItemRef**
Add `KeySequence` attribute to ItemRef elements for key variables. Key variables are defined in the domain spec (SDTM-IG). The value is a positive integer indicating sort priority.

```python
# In _add_item_group():
key_vars = spec.key_variables  # Need this on DomainMappingSpec or from sdtm_ref
for idx, vm in enumerate(spec.variable_mappings, start=1):
    ir = etree.SubElement(ig, f"{{{ODM_NS}}}ItemRef")
    # ... existing attributes ...
    if vm.sdtm_variable in key_vars:
        ir.set("KeySequence", str(key_vars.index(vm.sdtm_variable) + 1))
```

**Data requirement:** `DomainMappingSpec` or the SDTMReference must provide key variables per domain. Check if `sdtm_ig/domains.json` has this data.

**MED-07: def:Label on ItemGroupDef**
Simple addition -- set `def:Label` to the dataset label (same as Description TranslatedText):
```python
ig.set(f"{{{DEFINE_NS}}}Label", spec.domain_label)
```

**MED-08: Integer DataType for --SEQ**
Currently `_add_item_def()` sets DataType="float" for all Num variables. --SEQ variables should use DataType="integer":
```python
if vm.sdtm_data_type == "Num":
    if vm.sdtm_variable.endswith("SEQ"):
        it.set("DataType", "integer")
    else:
        it.set("DataType", "float")
```

**MED-09: def:Origin Source attribute**
The `<def:Origin>` element can have a `Source` attribute indicating where the data came from. For CRF origin, Source="CRF page reference"; for Derived, Source might be a computation reference.

```python
if vm.origin:
    origin_el = etree.SubElement(it, f"{{{DEFINE_NS}}}Origin")
    origin_el.set("Type", vm.origin.value)
    # Add Source attribute based on origin type
    if vm.origin == VariableOrigin.CRF and vm.source_variable:
        origin_el.set("Source", f"CRF ({vm.source_variable})")
    elif vm.origin == VariableOrigin.DERIVED and vm.computational_method:
        origin_el.set("Source", "Derived")
```

**MED-10: Originator and AsOfDateTime on ODM root**
Add these attributes to `_create_odm_root()`:
```python
root.set("Originator", "Astraea-SDTM")
root.set("AsOfDateTime", datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S"))
```
Note: `AsOfDateTime` represents when the data/metadata was valid, while `CreationDateTime` is when the file was generated. They can be the same for initial generation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date imputation flags | Custom comparison logic | `astraea.transforms.imputation.get_date_imputation_flag()` | Already implemented and tested |
| Numeric parsing for STRESN | Custom float parsing | `pd.to_numeric(series, errors="coerce")` | Handles all edge cases (whitespace, empty strings, non-numeric text) |
| NRIND conditional logic | Nested if/else chains | `numpy.select(conditions, choices)` | Vectorized, handles NaN correctly, much faster than row-wise apply |
| XML namespace handling | String concatenation | lxml etree with NSMAP | Already in use; handles namespace prefixes correctly |
| Unit conversion tables | Custom lookup dicts | Defer to future phase | Full SI conversion is study-specific and complex; copy ORRESU for v1 |

## Common Pitfalls

### Pitfall 1: ValueListDef/ItemDef OID Collisions
**What goes wrong:** When creating ItemDef entries for value-level metadata, OIDs like `IT.LB.LBORRES.ALT` could collide with the domain-level `IT.LB.LBORRES` if not carefully namespaced.
**How to avoid:** Use a clear OID convention: `IT.{domain}.{variable}` for domain-level, `IT.{domain}.{variable}.{testcd}` for value-level. Ensure `_add_item_def()` does not create duplicates by collecting all needed ItemDefs first, then emitting them.
**Warning signs:** lxml won't catch duplicate OIDs -- only P21 validation will. Add a unit test that checks for OID uniqueness.

### Pitfall 2: STRESN Derivation for Non-Numeric Results
**What goes wrong:** Lab tests like "Urine Color" have text results ("YELLOW", "CLEAR"). `pd.to_numeric("YELLOW", errors="coerce")` correctly returns NaN, but STRESC should still contain the value. Make sure the derivation handles mixed numeric/text results in the same domain.
**How to avoid:** Always set STRESC = ORRES (character copy). Only set STRESN for rows where the value is actually numeric. Never set STRESN to 0 for non-numeric results.

### Pitfall 3: NRIND Without Reference Ranges
**What goes wrong:** Not all tests have reference ranges (qualitative tests, subjective assessments). Attempting NRIND derivation without STNRLO/STNRHI produces all-null results or errors.
**How to avoid:** Only derive NRIND for rows where at least one of STNRLO/STNRHI is populated AND STRESN is numeric. Leave NRIND as null for qualitative tests.

### Pitfall 4: Modifying DataFrame After Column Order Enforcement
**What goes wrong:** The executor's `_enforce_column_order()` drops unmapped columns. If standardized result derivation happens AFTER execution, the new columns (STRESC, STRESN, STRESU, NRIND) will be dropped because they weren't in the original spec's variable_mappings.
**How to avoid:** Either (a) add STRESC/STRESN/STRESU/NRIND to the variable_mappings in the spec before execution, or (b) perform derivation BEFORE column order enforcement, or (c) add derived columns after execution and manually enforce order.

### Pitfall 5: WhereClauseDef Referencing Wrong OID Pattern
**What goes wrong:** Current code uses `f"IT.{spec.domain}.{testcd_var.sdtm_variable}"` as the ItemOID in RangeCheck. When switching VLD to result variables, the filter still needs to reference the TESTCD ItemDef (the condition variable), not the result variable.
**How to avoid:** The RangeCheck `def:ItemOID` in WhereClauseDef should always point to the TESTCD variable's ItemDef OID, regardless of which result variable the VLD is attached to.

### Pitfall 6: KeySequence Numbering
**What goes wrong:** KeySequence must start at 1 and be contiguous for the key variables of a domain. Using the overall variable order (1, 2, 3 for STUDYID, DOMAIN, USUBJID when they happen to also be keys) is correct, but if a key variable is not in position 1-N of the overall order, the KeySequence values will be wrong.
**How to avoid:** Number KeySequence independently: iterate only over key variables in their key order, not their overall variable order.

## Code Examples

### ValueListDef on Result Variables (corrected)
```python
# Source: define.xml 2.0 spec + PHUSE completion guidelines
def _add_value_lists(mdv, specs, generated_dfs):
    """Add ValueListDef elements for Findings result variables."""
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

        # Get unique test codes from actual data
        test_codes = []
        if generated_dfs and spec.domain in generated_dfs:
            df = generated_dfs[spec.domain]
            if testcd_var.sdtm_variable in df.columns:
                test_codes = sorted(df[testcd_var.sdtm_variable].dropna().unique().tolist())

        if not test_codes:
            continue

        # Create VLD for EACH result variable (not TESTCD)
        result_suffixes = ("ORRES", "STRESC", "STRESN")
        result_vars = [
            vm for vm in spec.variable_mappings
            if any(vm.sdtm_variable.endswith(s) for s in result_suffixes)
        ]

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

        # WhereClauseDef elements (shared across result vars but unique OIDs)
        for result_vm in result_vars:
            for tc in test_codes:
                wc = etree.SubElement(mdv, f"{{{DEFINE_NS}}}WhereClauseDef")
                wc.set("OID", f"WC.{spec.domain}.{result_vm.sdtm_variable}.{tc}")

                rc = etree.SubElement(wc, f"{{{ODM_NS}}}RangeCheck")
                rc.set("Comparator", "EQ")
                rc.set("SoftHard", "Soft")
                # Always reference TESTCD ItemDef -- the condition variable
                rc.set(f"{{{DEFINE_NS}}}ItemOID",
                       f"IT.{spec.domain}.{testcd_var.sdtm_variable}")

                cv = etree.SubElement(rc, f"{{{ODM_NS}}}CheckValue")
                cv.text = tc

        # Create ItemDefs for value-level references
        for result_vm in result_vars:
            for tc in test_codes:
                _add_item_def_for_value_level(
                    mdv, spec.domain, result_vm, tc
                )
```

### NCI C-code Alias on CodeListItem
```python
# Source: define.xml 2.0 spec, Alias element with nci:ExtCodeID context
def _add_codelist_item(cl_el, coded_value, term):
    """Add CodeListItem with Decode and optional Alias for NCI code."""
    cli = etree.SubElement(cl_el, f"{{{ODM_NS}}}CodeListItem")
    cli.set("CodedValue", coded_value)

    decode = etree.SubElement(cli, f"{{{ODM_NS}}}Decode")
    dt = etree.SubElement(decode, f"{{{ODM_NS}}}TranslatedText")
    dt.set(f"{{{XML_NS}}}lang", "en")
    dt.text = term.nci_preferred_term or coded_value

    # NCI C-code via Alias element
    if hasattr(term, 'nci_code') and term.nci_code:
        alias = etree.SubElement(cli, f"{{{ODM_NS}}}Alias")
        alias.set("Context", "nci:ExtCodeID")
        alias.set("Name", term.nci_code)
```

### Standardized Results + NRIND Derivation
```python
# Integration in FindingsExecutor
def _derive_findings_variables(self, df, domain_prefix):
    """Derive STRESC, STRESN, STRESU, NRIND for a Findings domain."""
    orres = f"{domain_prefix}ORRES"
    orresu = f"{domain_prefix}ORRESU"

    if orres not in df.columns:
        return df

    # STRESC = character copy of ORRES
    df[f"{domain_prefix}STRESC"] = df[orres]

    # STRESN = numeric parse (NaN for non-numeric)
    df[f"{domain_prefix}STRESN"] = pd.to_numeric(df[orres], errors="coerce")

    # STRESU = copy of ORRESU (no unit conversion in v1)
    if orresu in df.columns:
        df[f"{domain_prefix}STRESU"] = df[orresu]

    # NRIND from STRESN vs reference ranges
    stnrlo = f"{domain_prefix}STNRLO"
    stnrhi = f"{domain_prefix}STNRHI"
    stresn = f"{domain_prefix}STRESN"

    if stresn in df.columns:
        result_num = df[stresn]
        lo_num = pd.to_numeric(df.get(stnrlo), errors="coerce") if stnrlo in df.columns else None
        hi_num = pd.to_numeric(df.get(stnrhi), errors="coerce") if stnrhi in df.columns else None

        nrind = pd.Series(pd.NA, index=df.index, dtype="object")
        if lo_num is not None:
            nrind = nrind.where(~(result_num < lo_num) | result_num.isna(), "LOW")
        if hi_num is not None:
            nrind = nrind.where(~(result_num > hi_num) | result_num.isna(), "HIGH")
        if lo_num is not None and hi_num is not None:
            normal_mask = (result_num >= lo_num) & (result_num <= hi_num)
            nrind = nrind.where(~normal_mask, "NORMAL")

        df[f"{domain_prefix}NRIND"] = nrind

    return df
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ValueListDef on --TESTCD | ValueListDef on result vars (--ORRES, --STRESC, --STRESN) | define.xml 2.0 (2013) | Structural change; current code uses pre-2.0 pattern |
| No NCI codes on CodeListItem | Alias element with nci:ExtCodeID context | define.xml 2.0 | P21 checks for these; missing = validation warning |
| Generic float DataType | Integer for --SEQ, float for other Num | ODM 1.3.2 / define.xml 2.0 | Minor but P21 flags incorrect DataType |

## Open Questions

1. **NCI C-codes data enrichment scope**
   - What we know: CodelistTerm model lacks `nci_code` field; `codelists.json` has no NCI C-codes per term
   - What's unclear: How many of the ~20 codelists need C-codes? Is this a manual data entry task or can it be scripted from NCI EVS?
   - Recommendation: Add the field to the model, populate for the most critical codelists (Sex, Race, Yes/No) first, defer comprehensive coverage

2. **Date imputation: truncation vs actual imputation**
   - What we know: Current date transforms truncate (no imputation). DTF/TMF flags document imputation, not truncation.
   - What's unclear: Does the study data actually need date imputation? Are there partial dates that need to become full dates?
   - Recommendation: Add infrastructure for DTF/TMF generation, implement with conservative logic (only flag when actual imputation occurs)

3. **Unit conversion for STRESU**
   - What we know: Full SI unit conversion is study-specific and complex (mg/dL -> mmol/L requires molecular weight)
   - What's unclear: Does the FDA expect standardized units in v1 or is copying ORRESU acceptable?
   - Recommendation: Copy ORRESU -> STRESU for v1. Document in define.xml MethodDef. Add unit conversion in a future phase.

4. **Key variables data source**
   - What we know: KeySequence requires knowing which variables are key variables for each domain
   - What's unclear: Is this data already in `domains.json`? If not, where to source it?
   - Recommendation: Check `domains.json` for key_variables field; if absent, derive from SDTM-IG spec (STUDYID, USUBJID, --SEQ are always keys for repeating domains)

## Sources

### Primary (HIGH confidence)
- Existing codebase: `src/astraea/submission/define_xml.py` (current implementation analyzed line-by-line)
- Existing codebase: `src/astraea/execution/findings.py` (FindingsExecutor, normalize functions)
- Existing codebase: `src/astraea/execution/executor.py` (DatasetExecutor execution pipeline)
- Existing codebase: `src/astraea/transforms/imputation.py` (DTF/TMF utility -- exists, not wired in)
- Existing codebase: `src/astraea/models/controlled_terms.py` (CodelistTerm model -- no nci_code field)
- Existing codebase: `src/astraea/data/ct/codelists.json` (C78736 Reference Range Indicator codelist)
- Existing codebase: `src/astraea/data/sdtm_ig/domains.json` (LBSTRESC, LBSTRESN, etc. definitions)

### Secondary (MEDIUM confidence)
- [CDISC Define-XML v2.0 Specification](https://cdn2.hubspot.net/hubfs/236249/Website%20Section%20Images/Website%20downloads/Define-XML-2-0-Specification.pdf) - ValueListDef placement rules
- [CDISC Define-XML v2.0 Wiki - Value-level Metadata: Vital Signs](https://wiki.cdisc.org/display/DEFXML2DOT1/Value-Level%20Metadata:%20Vital%20Signs%20Domain) - VLD on result variables pattern
- [PHUSE Define-XML 2.0 Completion Guidelines](https://phuse.s3.eu-central-1.amazonaws.com/Deliverables/Optimizing+the+Use+of+Data+Standards/Define-XML+Version+2.0+Completion+Guidelines.pdf) - KeySequence, Originator, Alias, Origin Source
- [Pinnacle 21 DD0063: Missing Alias](https://www.pinnacle21.com/forum/dd0063-missing-alias) - P21 check for NCI codes on CodeListItem
- [PharmaSUG 2018 DS-13: Global Checklist to QC SDTM Lab Data](https://www.lexjansen.com/pharmasug/2018/DS/PharmaSUG-2018-DS13.pdf) - NRIND derivation patterns
- [PhUSE 2023 SI09: Standardizing SDTM Laboratory Programming](https://www.lexjansen.com/phuse-us/2023/si/PAP_SI09.pdf) - STRESC/STRESN derivation

### Tertiary (LOW confidence)
- Web search results for NRIND derivation logic -- confirmed against CT codelist C78736 in bundled data

## Metadata

**Confidence breakdown:**
- Define.xml structural fixes (HIGH-11, 12, 13): HIGH - clear spec violations with well-documented corrections
- MED attribute fixes (MED-06 through MED-10): HIGH - straightforward attribute additions
- Findings derivations (HIGH-04, HIGH-05): HIGH - standard SDTM patterns, well-understood
- Date imputation flags (HIGH-03): MEDIUM - depends on whether actual imputation occurs in pipeline

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (stable domain; define.xml 2.0 spec is mature)
