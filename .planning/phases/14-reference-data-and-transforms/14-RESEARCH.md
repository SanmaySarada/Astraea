# Phase 14: Reference Data and Transforms - Research

**Researched:** 2026-02-28
**Domain:** Bug fixes and gaps in reference data, validation rules, and transform utilities
**Confidence:** HIGH

## Summary

Phase 14 is a bug-fix and gap-filling phase targeting 14 specific requirements across three modules: reference data (`src/astraea/reference/`, `src/astraea/data/`), validation rules (`src/astraea/validation/rules/`), and transforms (`src/astraea/transforms/`). No new major features are needed -- every change is a targeted fix to an identified deficiency.

All issues have been confirmed by examining the actual source code. The fixes are straightforward -- most are data corrections in JSON, regex updates, or replacing `iterrows()` with pandas vectorized operations. The largest effort items are the C66738 codelist creation (requires populating ~30+ trial summary parameter codes) and the SEX/RACE/ETHNIC recoding wrappers.

**Primary recommendation:** Tackle these in dependency order -- reference data fixes first (they affect downstream validation), then transform fixes, then performance optimizations last.

## Standard Stack

No new libraries needed. All fixes use existing dependencies:

### Core (already installed)
| Library | Version | Purpose | Used For |
|---------|---------|---------|----------|
| `pandas` | >=2.2 | DataFrame operations | Vectorized replacements for `iterrows()` |
| `pydantic` | >=2.10 | Data models | No changes needed to models |
| `re` | stdlib | Regex | ISO 8601 pattern update |

### Supporting
No new dependencies required for any fix in this phase.

## Architecture Patterns

### No Structural Changes Needed

This phase modifies existing files in place. No new modules, no new classes, no architectural changes. The file-to-requirement mapping:

```
src/astraea/data/ct/codelists.json          # HIGH-14, MED-15, MED-16
src/astraea/data/sdtm_ig/domains.json       # HIGH-15
src/astraea/reference/controlled_terms.py   # MED-17
src/astraea/validation/rules/fda_business.py # MED-02 (FDAB009, FDAB030)
src/astraea/validation/rules/consistency.py  # MED-02 (ASTR-C005)
src/astraea/validation/rules/format.py       # MED-03
src/astraea/transforms/dates.py              # MED-03, MED-19, MED-20
src/astraea/transforms/char_length.py        # MED-22
src/astraea/transforms/epoch.py              # MED-02, MED-23
src/astraea/transforms/imputation.py         # MED-21
src/astraea/transforms/recoding.py           # MED-25
src/astraea/transforms/visit.py              # MED-02 (also uses iterrows)
```

### Pattern: Vectorized Pandas Over iterrows()

The `iterrows()` calls in FDAB009, FDAB030, ASTR-C005, and epoch.py should be replaced with `groupby()` + `nunique()` or `merge()` operations. The pattern:

**Before (iterrows):**
```python
mapping: dict[str, set[str]] = {}
for _, row in df.iterrows():
    key = row.get(key_col)
    val = row.get(val_col)
    if pd.notna(key) and pd.notna(val):
        mapping.setdefault(str(key), set()).add(str(val))
violations = {k: v for k, v in mapping.items() if len(v) > 1}
```

**After (vectorized):**
```python
valid = df[[key_col, val_col]].dropna()
grouped = valid.groupby(key_col)[val_col].nunique()
violation_keys = grouped[grouped > 1].index
# Get actual values for violation reporting:
violations = (
    valid[valid[key_col].isin(violation_keys)]
    .groupby(key_col)[val_col]
    .apply(lambda x: sorted(x.unique().tolist()))
    .to_dict()
)
```

### Pattern: Reverse Lookup with Collision Handling

The reverse lookup collision in `controlled_terms.py` (line 57-60) currently uses a flat dict where `last codelist wins`. The fix should use a `dict[str, list[str]]` or pick the correct codelist based on context:

**Current bug:** Both C66789 (Specimen Condition) and C78734 (Specimen Type) map `variable_mappings: ["LBSPEC"]`. The reverse lookup `_variable_to_codelist` stores only one. The last one loaded wins, silently dropping the other.

**Fix options:**
1. **Fix the data:** C66789 should map to `LBSPCND` (Specimen Condition), not `LBSPEC`. C78734 correctly maps to `LBSPEC` (Specimen Type). Fix the `variable_mappings` in codelists.json.
2. **Fix the code:** Change `_variable_to_codelist` to `dict[str, list[str]]` and return all matching codelists. The caller picks the right one.

**Recommendation:** Do BOTH. Fix the C66789 data (MED-15) AND make the reverse lookup robust against future collisions (MED-17). The code fix should log a warning when collisions are detected, and `get_codelist_for_variable()` should return a list or the first match with a logged warning.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 1:1 relationship checking (FDAB009) | iterrows loop | `df.groupby().nunique()` | O(n) vectorized vs O(n) iterrows with Python overhead |
| Unit consistency (FDAB030) | iterrows loop | `df.groupby().nunique()` | Same pattern |
| Study day sign check (ASTR-C005) | iterrows loop | `df.merge()` + vectorized comparison | Merge DM RFSTDTC into domain, compare vectorized |
| SE epoch matching | iterrows + dict lookup | `pd.merge_asof()` or interval-based merge | Built-in pandas range join |
| Date imputation | Custom logic | Existing `format_partial_iso8601` + new imputation helpers | Compose existing functions |

## Common Pitfalls

### Pitfall 1: C66738 Codelist Completeness
**What goes wrong:** Adding only a few TSPARMCD values to C66738 when the TS domain needs dozens of parameter codes (SSTDTC, SEND, PLESSION, TPHASE, ADDON, etc.). Incomplete codelist means TS validation will flag valid parameters as invalid.
**How to avoid:** Include at minimum these FDA-required TSPARMCD values: SSTDTC, SENDTC, PLESSION, TPHASE, ADDON, AGEMIN, AGEMAX, SEXPOP, STOTEFP, PCLAS, INDIC, TRT, TITLE, SPONSOR. The full CDISC C66738 codelist has 100+ terms. For v1, include the ~30 most common ones and mark the codelist as `"extensible": true`.
**Warning signs:** TS domain validation producing false positives for common parameters.

### Pitfall 2: ISO 8601 Timezone Regex Breaking Existing Matches
**What goes wrong:** Adding timezone offset support (`+HH:MM`/`-HH:MM`/`Z`) to the ISO 8601 regex pattern in `format.py` could break existing date validation if the regex change is not backward-compatible.
**How to avoid:** The timezone suffix is OPTIONAL and appended after the time component. The current regex `^\d{4}(-\d{2}(-\d{2}(T\d{2}(:\d{2}(:\d{2})?)?)?)?)?$` should be extended to: `^\d{4}(-\d{2}(-\d{2}(T\d{2}(:\d{2}(:\d{2})?)?(Z|[+-]\d{2}:\d{2})?)?)?)?$`. Timezone only applies when there is a time component (after T).
**Warning signs:** Previously passing dates now failing validation.

### Pitfall 3: Epoch Overlap Detection Must Not Break Valid SE Data
**What goes wrong:** SE elements can legitimately share a boundary date (SEENDTC of epoch A = SESTDTC of epoch B). Naive overlap detection flags these as overlaps.
**How to avoid:** Overlap means `start_A < end_B AND start_B < end_A` (strict less-than, not less-than-or-equal). Adjacent elements with shared boundary are NOT overlapping.
**Warning signs:** All subjects flagged as having overlapping epochs when they have properly sequenced elements.

### Pitfall 4: 200-byte Validation vs Optimization Confusion
**What goes wrong:** `char_length.py` currently only OPTIMIZES widths (finds minimum needed). MED-22 asks for 200-byte MAX VALIDATION. These are different concerns -- optimization sets width, validation rejects values exceeding 200 bytes.
**How to avoid:** Add a separate function (or extend `optimize_char_lengths`) that VALIDATES no value exceeds 200 bytes and returns violations. The optimization function should also cap at 200.
**Warning signs:** XPT files written with >200 byte character values that fail P21 validation.

### Pitfall 5: Recoding Wrappers Must Handle Raw Data Variety
**What goes wrong:** SEX recoding assumes raw data uses standard values ("Male", "Female"). Real EDC data may use "M", "F", "1", "2", "male", "MALE", numeric codes, or language-specific values.
**How to avoid:** Each recoding wrapper should handle: uppercase, lowercase, mixed case, numeric codes (1/2 for SEX), common abbreviations, and return None for unrecognized values (not raise exceptions).
**Warning signs:** Recoding producing all-None columns because raw values do not match expected patterns.

## Code Examples

### FDAB009 Vectorized Replacement
```python
# Source: pandas groupby documentation
def check_one_to_one(df: pd.DataFrame, col_a: str, col_b: str) -> dict[str, list[str]]:
    """Find violations of 1:1 relationship between two columns."""
    valid = df[[col_a, col_b]].dropna().astype(str)
    if valid.empty:
        return {}
    counts = valid.groupby(col_a)[col_b].nunique()
    violation_keys = counts[counts > 1].index.tolist()
    if not violation_keys:
        return {}
    violations = (
        valid[valid[col_a].isin(violation_keys)]
        .groupby(col_a)[col_b]
        .apply(lambda x: sorted(x.unique().tolist()))
        .to_dict()
    )
    return violations
```

### FDAB030 Vectorized Replacement
```python
# Same pattern as FDAB009 but for TESTCD -> STRESU
valid = df[[testcd_col, stresu_col]].dropna().astype(str)
unit_counts = valid.groupby(testcd_col)[stresu_col].nunique()
violations = unit_counts[unit_counts > 1].index.tolist()
```

### ASTR-C005 Vectorized Replacement
```python
# Merge RFSTDTC from DM into domain, then vectorized comparison
dm_lookup = dm_df[["USUBJID", "RFSTDTC"]].dropna().copy()
dm_lookup["RFSTDTC"] = dm_lookup["RFSTDTC"].str[:10]

merged = df.merge(dm_lookup, on="USUBJID", how="left")
for dy_col in dy_cols:
    dtc_col = dy_col[:-2] + "DTC"
    if dtc_col not in df.columns:
        continue
    mask = merged[dy_col].notna() & merged[dtc_col].notna() & merged["RFSTDTC"].notna()
    subset = merged[mask].copy()
    subset["dtc_date"] = subset[dtc_col].astype(str).str[:10]
    subset["dy_num"] = pd.to_numeric(subset[dy_col], errors="coerce")
    inconsistent = (
        ((subset["dy_num"] > 0) & (subset["dtc_date"] < subset["RFSTDTC"])) |
        ((subset["dy_num"] < 0) & (subset["dtc_date"] > subset["RFSTDTC"]))
    )
    inconsistent_count = inconsistent.sum()
```

### Epoch Vectorized Replacement
```python
# Replace iterrows for SE pre-grouping with to_dict('records')
se_records = se_df.to_dict("records")
se_grouped: dict[str, list[dict]] = {}
for rec in se_records:
    subj = str(rec[usubjid_col])
    se_grouped.setdefault(subj, []).append({
        "sestdtc": str(rec["SESTDTC"]) if pd.notna(rec["SESTDTC"]) else "",
        "seendtc": str(rec.get("SEENDTC", "")) if pd.notna(rec.get("SEENDTC")) else "",
        "epoch": str(rec["EPOCH"]) if pd.notna(rec["EPOCH"]) else "",
    })
```

### ISO 8601 Regex with Timezone Support
```python
# Updated pattern for format.py
_ISO_8601_PATTERN = re.compile(
    r"^\d{4}"                          # YYYY
    r"(-\d{2}"                         # -MM
    r"(-\d{2}"                         # -DD
    r"(T\d{2}"                         # THH
    r"(:\d{2}"                         # :MM
    r"(:\d{2})?"                       # :SS (optional)
    r")?"                              # end :MM group
    r"(Z|[+-]\d{2}:\d{2})?"           # timezone (optional, only with time)
    r")?"                              # end THH group
    r")?"                              # end -DD group
    r")?"                              # end -MM group
    r"$"
)
```

### ISO Datetime Passthrough in dates.py
```python
# New pattern for parse_string_date_to_iso to handle "YYYY-MM-DDTHH:MM:SS" input
_PATTERN_ISO_DATETIME = re.compile(
    r"^\s*(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?"
    r"(?:Z|[+-]\d{2}:\d{2})?\s*$"
)
# Place this check BEFORE the YYYY-MM-DD check in parse_string_date_to_iso
```

### HH:MM:SS Support in dates.py
```python
# Extend _PATTERN_DD_MON_YYYY_HHMM to support optional seconds
_PATTERN_DD_MON_YYYY_HHMMSS = re.compile(
    r"^\s*(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"\s+(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$",
    re.IGNORECASE,
)
```

### SEX Recoding Wrapper
```python
_SEX_MAP: dict[str, str] = {
    "male": "M", "m": "M", "1": "M",
    "female": "F", "f": "F", "2": "F",
    "unknown": "U", "u": "U",
    "undifferentiated": "UNDIFFERENTIATED",
}

def recode_sex(value: object) -> str | None:
    """Recode raw sex values to C66731 submission values (M/F/U/UNDIFFERENTIATED)."""
    if value is None or pd.isna(value):
        return None
    key = str(value).strip().lower()
    return _SEX_MAP.get(key)
```

### Epoch Overlap Detection
```python
def detect_epoch_overlaps(
    se_df: pd.DataFrame,
    usubjid_col: str = "USUBJID",
) -> list[dict]:
    """Detect overlapping SE elements per subject.

    Returns list of dicts with subject, epoch1, epoch2, overlap details.
    Adjacent elements (end == start) are NOT overlapping.
    """
    overlaps = []
    for subj, group in se_df.groupby(usubjid_col):
        elements = group.sort_values("SESTDTC").to_dict("records")
        for i in range(len(elements)):
            for j in range(i + 1, len(elements)):
                s_i = str(elements[i].get("SESTDTC", ""))[:10]
                e_i = str(elements[i].get("SEENDTC", ""))[:10]
                s_j = str(elements[j].get("SESTDTC", ""))[:10]
                if not s_i or not s_j:
                    continue
                # Open-ended: no end date means extends to infinity
                if e_i and s_j < e_i:  # strict less-than
                    overlaps.append({
                        "usubjid": str(subj),
                        "epoch_1": elements[i].get("EPOCH", ""),
                        "epoch_2": elements[j].get("EPOCH", ""),
                        "overlap_start": s_j,
                        "overlap_end": e_i,
                    })
    return overlaps
```

### 200-byte Max Validation
```python
def validate_char_max_length(
    df: pd.DataFrame,
    max_bytes: int = 200,
) -> dict[str, list[int]]:
    """Validate no character value exceeds max_bytes (XPT v5 limit).

    Returns dict mapping column name to list of row indices that exceed the limit.
    """
    violations: dict[str, list[int]] = {}
    string_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in string_cols:
        non_null = df[col].dropna()
        if len(non_null) == 0:
            continue
        byte_lens = non_null.astype(str).str.encode("ascii", errors="replace").str.len()
        over = byte_lens[byte_lens > max_bytes]
        if len(over) > 0:
            violations[col] = over.index.tolist()
    return violations
```

## Specific Requirement Details

### HIGH-14: C66738 (Trial Summary Parameter Code)

C66738 is the CDISC codelist for TSPARMCD values in the TS domain. The TS domain's TSPARMCD variable (line 2809-2814 in domains.json) references `"codelist_code": "C66738"` but this codelist does not exist in `codelists.json`.

**What to add:** A new entry in `codelists.json` under key `"C66738"` with:
- `name`: "Trial Summary Parameter Code"
- `extensible`: true (sponsors can add custom parameters)
- `variable_mappings`: ["TSPARMCD"]
- `terms`: At minimum these FDA-required/common parameters:

| TSPARMCD | Full Name |
|----------|-----------|
| SSTDTC | Study Start Date |
| SENDTC | Study End Date |
| SPONSOR | Sponsor Name |
| TITLE | Study Title |
| INDIC | Trial Indication |
| TRT | Investigational Therapy or Treatment |
| PCLAS | Pharmacological Class |
| PLESSION | Planned Number of Subjects |
| SEXPOP | Sex of Participants |
| AGEMIN | Planned Minimum Age |
| AGEMAX | Planned Maximum Age |
| STOTEFP | Reason for Study Stopping |
| ADDON | Added on to Existing Treatment |
| TPHASE | Trial Phase Classification |
| SDTMVER | SDTM Version |
| TTYPE | Trial Type |
| ACESSION | Accession Number |
| COMPTRT | Comparator Treatment |
| REGID | Registry Identifier |
| HLTSUBJI | Healthy Subject Indicator |
| RANDOM | Trial Is Randomized |
| STYPE | Study Type |
| ADAPT | Adaptive Design |
| INTMODEL | Intervention Model |
| CURTRT | Control Type |
| DOSFRQ | Planned Dose Frequency |
| ROUTE | Planned Route of Administration |
| OBJPRIM | Trial Primary Objective |

**Confidence: HIGH** -- TSPARMCD values are well-documented in SDTM-IG v3.4 Appendix C1.

### HIGH-15: PE and QS key_variables VISITNUM Issue

**Problem:** PE and QS domains have `VISITNUM` in their `key_variables` arrays but do NOT have `VISITNUM` defined in their `variables` arrays. LB and VS have it in both.

**Fix:** Add VISITNUM as a variable entry to both PE and QS domain variable lists, matching the pattern used in LB/VS:
```json
{
    "name": "VISITNUM",
    "label": "Visit Number",
    "data_type": "Num",
    "core": "Exp",
    "cdisc_notes": "Clinical encounter number.",
    "codelist_code": null,
    "order": <appropriate order>
}
```

Also add VISIT (the character companion) if missing, matching LB/VS pattern.

**Confidence: HIGH** -- confirmed by code inspection, fix pattern clear from LB/VS.

### MED-15: C66789 Variable Mapping Correction

**Problem:** C66789 (Specimen Condition) has `"variable_mappings": ["LBSPEC"]` but should be `["LBSPCND"]`. LBSPEC is the variable for Specimen Type (C78734). Specimen Condition maps to LBSPCND.

**Fix:** Change line 293 in codelists.json from `"LBSPEC"` to `"LBSPCND"`.

**Confidence: HIGH** -- SDTM-IG v3.4 clearly distinguishes LBSPEC (Specimen Type) from LBSPCND (Specimen Condition).

### MED-16: C66742 Missing Variable Mappings

**Problem:** C66742 (No Yes Response) currently maps to: DTHFL, AESER, AESCAN, AESCONG, AESDISAB, AESDTH, AESHOSP, AESLIFE, AESMIE, AECONTRT, MHPRESP, MHOCCUR.

**Missing:** CEOCCUR, CEPRESP, LBBLFL, VSBLFL (and likely others like EGBLFL, DVBLFL, PEBLFL).

**Fix:** Expand the `variable_mappings` array to include all --OCCUR, --PRESP, and --BLFL variables that use the Y/N codelist.

**Confidence: HIGH** -- these are standard SDTM variables that use C66742.

### MED-17: Reverse Lookup Collision Bug

**Problem:** In `controlled_terms.py` lines 57-60, the reverse lookup dict `_variable_to_codelist` maps each variable name to exactly ONE codelist code. When multiple codelists share a variable (LBSPEC maps to both C66789 and C78734), the last one loaded wins silently.

**Current collision found:** `LBSPEC -> ['C66789', 'C78734']`

**After MED-15 fix:** This specific collision goes away (C66789 will map to LBSPCND instead). But the code should still be hardened for future safety.

**Fix approach:**
1. Change `_variable_to_codelist` to `dict[str, list[str]]`
2. `get_codelist_for_variable()` returns the first match (most common case) but logs a warning if multiple exist
3. Add a new method `get_codelists_for_variable()` returning all matches

**Confidence: HIGH** -- bug confirmed by code inspection and test script.

### MED-02: iterrows() Performance

**Files with iterrows():**
1. `fda_business.py:268` -- FDAB009 (TESTCD/TEST 1:1 check)
2. `fda_business.py:299` -- FDAB009 (reverse TEST/TESTCD check)
3. `fda_business.py:363` -- FDAB030 (STRESU consistency)
4. `consistency.py:274` -- ASTR-C005 (RFSTDTC lookup build)
5. `consistency.py:298` -- ASTR-C005 (study day sign check)
6. `epoch.py:56` -- SE data pre-grouping
7. `visit.py:51` -- visit mapping (also iterrows, not in requirements but should fix)

**Fix:** Replace with pandas vectorized operations (groupby, merge, to_dict). See Code Examples section above.

**Confidence: HIGH** -- standard pandas optimization patterns.

### MED-03: ISO 8601 Timezone Offset

**Current regex:** `^\d{4}(-\d{2}(-\d{2}(T\d{2}(:\d{2}(:\d{2})?)?)?)?)?$`
**Missing:** `Z`, `+HH:MM`, `-HH:MM` timezone suffixes.

**Fix locations:**
1. `validation/rules/format.py` line 27 -- the validation regex
2. `transforms/dates.py` -- `parse_string_date_to_iso()` should pass through timezone-aware ISO strings

**ISO 8601 timezone formats:**
- `Z` (UTC)
- `+HH:MM` (positive offset, e.g., `+05:30`)
- `-HH:MM` (negative offset, e.g., `-04:00`)
- These appear ONLY after a time component

**Confidence: HIGH** -- ISO 8601 timezone format is well-defined.

### MED-19: HH:MM:SS Seconds Support

**Problem:** `_PATTERN_DD_MON_YYYY_HHMM` only captures HH:MM, not HH:MM:SS.

**Fix:** Make the seconds group optional in the regex: `(\d{1,2}):(\d{2})(?::(\d{2}))?`

**Confidence: HIGH** -- simple regex extension.

### MED-20: ISO Datetime Passthrough

**Problem:** `parse_string_date_to_iso("2022-03-30T14:30:00")` returns `""` because no pattern matches ISO datetime strings with the T separator.

**Fix:** Add a `_PATTERN_ISO_DATETIME` regex before the `_PATTERN_YYYY_MM_DD` check. It should match `YYYY-MM-DDTHH:MM(:SS)?` and return the string as-is (passthrough).

**Confidence: HIGH** -- straightforward pattern addition.

### MED-21: Date Imputation Functions

**Problem:** `imputation.py` only has flag detection functions (`get_date_imputation_flag`, `get_time_imputation_flag`). No actual imputation functions exist.

**Needed functions:**
- `impute_partial_date(partial_dtc: str, method: str = "first") -> str` -- impute missing components. Methods: "first" (Jan 1 / 00:00:00), "last" (Dec 31 / 23:59:59), "mid" (Jun 15 / 12:00:00).
- Imputation must compose with existing `get_date_imputation_flag()` to set the flag.

**Confidence: HIGH** -- standard SDTM imputation rules.

### MED-22: 200-byte Max Validation

**Problem:** `char_length.py` `optimize_char_lengths()` computes optimal width but does not validate that no value exceeds the XPT v5 maximum of 200 bytes.

**Fix:** Add `validate_char_max_length()` function and optionally cap the optimization at 200.

**Confidence: HIGH** -- XPT v5 200-byte limit is well-documented.

### MED-23: EPOCH Overlap Detection

**Problem:** `epoch.py` assigns epochs but does not detect overlapping SE elements. If two elements have overlapping date ranges for the same subject, the epoch assignment is ambiguous.

**Fix:** Add `detect_epoch_overlaps()` function that checks for overlapping SESTDTC/SEENDTC ranges per USUBJID. Adjacent elements (end == start) are NOT overlaps.

**Confidence: HIGH** -- straightforward date range overlap detection.

### MED-24: TV Domain Integration in visit.py

**Problem:** `visit.py` `assign_visit()` requires an externally-provided `visit_mapping` dict. There is no integration with the TV (Trial Visits) domain to auto-generate this mapping.

**Fix:** Add a function `build_visit_mapping_from_tv(tv_df: pd.DataFrame) -> dict[str, tuple[float, str]]` that reads the TV domain and produces the mapping dict.

**Confidence: MEDIUM** -- TV domain structure varies; need to check what columns are available.

### MED-25: SEX, RACE, ETHNIC Recoding Wrappers

**Problem:** `recoding.py` only has `numeric_to_yn()` for C66742. Missing convenience wrappers for:
- SEX (C66731): raw values -> M/F/U/UNDIFFERENTIATED
- RACE (C74457): raw values -> CDISC race terms
- ETHNIC (C66790): raw values -> HISPANIC OR LATINO / NOT HISPANIC OR LATINO / etc.

**Fix:** Add `recode_sex()`, `recode_race()`, `recode_ethnic()` functions with comprehensive input handling (case-insensitive, numeric codes, common abbreviations).

**Confidence: HIGH** -- codelist values are defined in codelists.json.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `iterrows()` for row-by-row processing | `groupby()` + vectorized ops | pandas best practice | 10-100x faster for large datasets |
| Flat reverse lookup dict | Multi-value dict with collision detection | This phase | Prevents silent data loss |
| ISO 8601 without timezone | ISO 8601 with optional timezone offset | This phase | Supports real-world clinical data |

## Open Questions

1. **C66738 term completeness:** The full C66738 codelist from NCI has 100+ terms. How many should be included? Recommendation: include the ~30 most common FDA-required terms and mark as extensible.

2. **TV domain column names:** MED-24 requires knowing the exact TV domain column structure. Need to check if our domains.json TV spec has the right columns (VISITNUM, VISIT, ARMCD, etc.) for building the mapping.

3. **Imputation method selection:** MED-21 imputation functions need a configurable method (first/last/mid of month, first/last of year). Who decides the method -- the mapping spec or a global config? Recommendation: parameter on the function, default to "first" (most conservative).

## Sources

### Primary (HIGH confidence)
- Source code inspection of all files listed in Architecture Patterns section
- `src/astraea/data/ct/codelists.json` -- current codelist definitions
- `src/astraea/data/sdtm_ig/domains.json` -- current domain specifications
- `.planning/MASTER_AUDIT.md` -- requirement definitions and confirmation status

### Secondary (MEDIUM confidence)
- SDTM-IG v3.4 Appendix C1 for TSPARMCD values (from training data, should be verified against bundled reference)
- pandas documentation for groupby/merge vectorization patterns

### Tertiary (LOW confidence)
- None -- all findings confirmed by direct code inspection

## Metadata

**Confidence breakdown:**
- Reference data fixes (HIGH-14, HIGH-15, MED-15, MED-16, MED-17): HIGH -- confirmed bugs with clear fixes
- Performance fixes (MED-02): HIGH -- standard pandas patterns
- Date/time fixes (MED-03, MED-19, MED-20, MED-21): HIGH -- well-defined formats
- Validation additions (MED-22, MED-23): HIGH -- straightforward logic
- Recoding wrappers (MED-25): HIGH -- codelist values known
- TV integration (MED-24): MEDIUM -- TV domain structure needs verification

**Research date:** 2026-02-28
**Valid until:** indefinite (bug fixes, not library-dependent)
