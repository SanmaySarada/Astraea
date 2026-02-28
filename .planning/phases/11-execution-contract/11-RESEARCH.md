# Phase 11: Execution Contract - Research

**Researched:** 2026-02-28
**Domain:** LLM-to-Executor derivation rule contract, column name resolution, bug fixes
**Confidence:** HIGH

## Summary

The core problem is a missing contract between the LLM mapping agent and the deterministic execution engine. The LLM generates derivation rules like `CONCAT(...)`, `RACE_FROM_CHECKBOXES(...)`, `ISO8601_PARTIAL_DATE(...)` in a free-form DSL, but the executor only recognizes a fixed set of registered transforms (`sas_date_to_iso`, `parse_string_date_to_iso`, etc.). The result: 10 of 18 DM columns are ALL NULL when executing the real mapping spec against real data.

This phase is entirely about code in the existing codebase -- no new libraries needed, no architectural changes. The work is: (1) define a formal derivation rule vocabulary, (2) implement handlers for each rule, (3) constrain the LLM prompt to only emit recognized rules, (4) build a column name resolution layer between eCRF names and actual SAS column names, and (5) fix three specific bugs (wildcard matching, date edge cases, auto-fix classification).

**Primary recommendation:** Define 8-10 derivation rule keywords that cover all DM mapping needs, implement them as dispatched handlers in `pattern_handlers.py`, and update `prompts.py` to enumerate the exact vocabulary the LLM must use.

## Standard Stack

No new libraries needed. This phase works entirely within the existing codebase.

### Core Files to Modify

| File | Purpose | Change Type |
|------|---------|-------------|
| `src/astraea/execution/pattern_handlers.py` | Derivation rule dispatch | Major: add rule handlers |
| `src/astraea/mapping/prompts.py` | LLM system prompt | Major: constrain derivation vocabulary |
| `src/astraea/execution/executor.py` | Dataset execution | Medium: column name resolution |
| `src/astraea/validation/report.py` | False positive matching | Minor: 1-line wildcard fix |
| `src/astraea/transforms/dates.py` | Date conversion | Minor: edge case fixes |
| `src/astraea/validation/autofix.py` | Auto-fix classification | Minor: fix USUBJID skip |

### Supporting Files

| File | Purpose | Change Type |
|------|---------|-------------|
| `src/astraea/mapping/transform_registry.py` | Transform registration | Add new rule names |
| `src/astraea/models/mapping.py` | StudyMetadata model | May need column alias map |
| `src/astraea/validation/known_false_positives.json` | Wildcard entries | No change (fix is in report.py) |

## Architecture Patterns

### Pattern 1: Formal Derivation Rule Vocabulary

**What:** A fixed set of derivation rule keywords that both the LLM and executor understand.

**Current state (broken):** The LLM invents arbitrary expressions:
```
CONCAT('PHA022121-C301', '-', irt.SSITENUM, '-', irt.SSUBJID)
MIN_DATE_PER_SUBJECT(ex.EXDAT_INT)
RACE_FROM_CHECKBOXES(dm.RACEAME, dm.RACEASI, ...)
ISO8601_PARTIAL_DATE(dm.BRTHYR_YYYY)
LAST_DISPOSITION_DATE_PER_SUBJECT(ds)
```

The executor checks `get_transform(rule)` which looks for exact matches in `AVAILABLE_TRANSFORMS` dict. None of the LLM's expressions match.

**Recommended vocabulary (derived from actual LLM output on DM domain):**

| Rule Keyword | Signature | Purpose |
|-------------|-----------|---------|
| `CONCAT` | `CONCAT(val1, sep, val2, ...)` | String concatenation of columns/literals |
| `GENERATE_USUBJID` | `GENERATE_USUBJID` | STUDYID-SITEID-SUBJID (special case of CONCAT) |
| `ISO8601_DATE` | `ISO8601_DATE(source_col)` | Convert SAS numeric date to ISO 8601 |
| `ISO8601_DATETIME` | `ISO8601_DATETIME(source_col)` | Convert SAS numeric datetime to ISO 8601 |
| `ISO8601_PARTIAL_DATE` | `ISO8601_PARTIAL_DATE(year_col[, month_col[, day_col]])` | Build partial ISO 8601 from components |
| `PARSE_STRING_DATE` | `PARSE_STRING_DATE(source_col)` | Parse string date (DD Mon YYYY etc.) to ISO 8601 |
| `MIN_DATE_PER_SUBJECT` | `MIN_DATE_PER_SUBJECT(source_col)` | Earliest date per USUBJID (for RFSTDTC) |
| `MAX_DATE_PER_SUBJECT` | `MAX_DATE_PER_SUBJECT(source_col)` | Latest date per USUBJID (for RFENDTC) |
| `RACE_CHECKBOX` | `RACE_CHECKBOX(col1, col2, ...)` | Derive RACE from checkbox columns |
| `NUMERIC_TO_YN` | `NUMERIC_TO_YN(source_col)` | Convert 0/1 to Y/N |
| `LOOKUP_RECODE` | Already handled by pattern | Codelist-based recoding |
| `ASSIGN` | Already handled by pattern | Constant value assignment |

**Implementation approach:** Parse the rule keyword from `derivation_rule`, extract arguments, dispatch to the appropriate handler function. Use a simple parser -- the DSL is `KEYWORD(arg1, arg2, ...)`.

```python
# In pattern_handlers.py
import re

_RULE_PATTERN = re.compile(r'^(\w+)\((.*)\)$', re.DOTALL)

def parse_derivation_rule(rule: str) -> tuple[str, list[str]]:
    """Parse 'KEYWORD(arg1, arg2, ...)' into (keyword, [args])."""
    m = _RULE_PATTERN.match(rule.strip())
    if m:
        keyword = m.group(1).upper()
        args_str = m.group(2)
        # Split on commas, strip quotes and whitespace
        args = [a.strip().strip("'\"") for a in args_str.split(',') if a.strip()]
        return keyword, args
    # No parens -- bare keyword
    return rule.strip().upper(), []
```

**Confidence: HIGH** -- This is a straightforward dispatch pattern. The LLM output format is already semi-structured; we just need to parse and execute it.

### Pattern 2: Column Name Resolution Layer

**What:** A mapping between eCRF/IRT field names (which the LLM uses) and actual SAS column names.

**The problem in detail:** The LLM's mapping spec references:
- `SSUBJID` (eCRF/IRT name) -- actual SAS column is `Subject`
- `SSITENUM` (eCRF/IRT name) -- actual SAS column is `SiteNumber`
- `SCOUNTRY` (IRT name) -- does not exist in dm.sas7bdat at all
- `ICDAT_INT` (ie.sas7bdat column) -- correct name, but different dataset

The LLM is reading eCRF metadata which uses OID/IRT field names, not the actual SAS export column names. This is a fundamental disconnect.

**Actual SAS column names from dm.sas7bdat (clinical columns only):**
```
Subject          -> Subject name or identifier (maps to SUBJID)
SiteNumber       -> SiteNumber (maps to SITEID)
BRTHYR           -> [From IRT] Year of Birth
BRTHYR_YYYY      -> Year of Birth Year component
AGE              -> Age
SEX_STD          -> Sex Coded Value
ETHNIC_STD       -> Ethnicity Coded Value
RACEAME..RACEWHI -> Race checkbox columns (0/1 numeric)
```

**Recommended approach:** Build a column alias resolution step in the executor that runs BEFORE pattern handlers.

```python
# Column alias map for DM domain
# Built from: profiling metadata (SAS labels) + eCRF field mapping
COLUMN_ALIASES = {
    # eCRF/IRT name -> actual SAS column name
    "SSUBJID": "Subject",
    "SSITENUM": "SiteNumber",
    "BRTHYR_YYYY": "BRTHYR_YYYY",  # identity -- name matches
    "SEX_STD": "SEX_STD",          # identity
    "ETHNIC_STD": "ETHNIC_STD",    # identity
    # Cross-dataset references need dataset prefix resolution
}
```

**Two implementation options:**

1. **Pre-execution alias resolution (recommended):** Before executing any pattern handler, resolve all `source_variable` references in the mapping spec against actual DataFrame columns. If `source_variable="SSUBJID"` and the DataFrame has `Subject`, check the profiling metadata (SAS labels) for a match.

2. **Prompt-side fix:** Inject actual SAS column names into the LLM prompt so it uses the right names from the start. This is more robust long-term but requires the profiling data to be available at prompt time (which it already is -- `source_profiles` are passed to `MappingContextBuilder`).

**Recommendation: Do BOTH.** Fix the prompt to include actual column names (reduces the problem), AND add a resolution layer as a safety net for cases where the LLM still gets names wrong.

**Confidence: HIGH** -- The problem is well-understood and the data needed for resolution (SAS column names + labels from profiling) already exists in the pipeline.

### Pattern 3: LLM Prompt Constraint

**What:** Update `MAPPING_SYSTEM_PROMPT` to enumerate the exact derivation rule vocabulary.

**Current prompt (line 60-62 in prompts.py):**
```
For derivation_rule, use a pseudo-code DSL describing the transformation
logic (e.g., ASSIGN("DM"), DIRECT(dm.AGE), CONCAT(STUDYID, "-", SITEID,
"-", SUBJID)).
```

This is too vague -- it gives examples but no constraints. The LLM invents new rule names freely.

**Recommended prompt section:**
```
## Derivation Rule Vocabulary

The derivation_rule field MUST use one of these recognized keywords.
The execution engine will reject any rule not in this list:

| Keyword | Usage | Example |
|---------|-------|---------|
| GENERATE_USUBJID | USUBJID construction | `GENERATE_USUBJID` |
| CONCAT | Concatenate values | `CONCAT(col1, '-', col2)` |
| ISO8601_DATE | SAS numeric date -> ISO | `ISO8601_DATE(AESTDAT_INT)` |
| ISO8601_DATETIME | SAS numeric datetime -> ISO | `ISO8601_DATETIME(EXDTTM_INT)` |
| ISO8601_PARTIAL_DATE | Year/month/day components -> ISO | `ISO8601_PARTIAL_DATE(BRTHYR_YYYY)` |
| PARSE_STRING_DATE | String date -> ISO | `PARSE_STRING_DATE(AESTDAT_RAW)` |
| MIN_DATE_PER_SUBJECT | Earliest date per subject | `MIN_DATE_PER_SUBJECT(EXDAT_INT)` |
| MAX_DATE_PER_SUBJECT | Latest date per subject | `MAX_DATE_PER_SUBJECT(EXDAT_INT)` |
| RACE_CHECKBOX | Derive RACE from checkbox cols | `RACE_CHECKBOX(RACEAME, RACEASI, ...)` |
| NUMERIC_TO_YN | 0/1 -> Y/N | `NUMERIC_TO_YN(AESLIFE)` |

Arguments MUST use actual SAS column names, NOT eCRF field names.
Use the column names shown in the Source Dataset Profile sections above.
```

**Confidence: HIGH** -- Prompt engineering to constrain output format is a well-established pattern.

### Anti-Patterns to Avoid

- **Do NOT make the DSL Turing-complete.** The derivation rule vocabulary should be a fixed set of keywords, not a programming language. Complex derivations that don't fit a keyword should be flagged for manual review, not expressed in ever-more-complex DSL.
- **Do NOT parse dataset prefixes from rule arguments.** The LLM writes `dm.BRTHYR_YYYY` but the executor works on a merged DataFrame. Strip dataset prefixes during resolution: `dm.BRTHYR_YYYY` -> `BRTHYR_YYYY`.
- **Do NOT silently fall through on unrecognized rules.** The current behavior (return NULL Series with a warning) is correct for safety, but the goal is to have ZERO unrecognized rules after this phase.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date parsing | Custom date parsers for each format | `parse_string_date_to_iso()` (already exists) | Already handles DD Mon YYYY, YYYY-MM-DD, partial dates -- just needs DDMonYYYY fix |
| USUBJID generation | Manual string concat | `generate_usubjid_column()` (already exists) | Already tested, handles edge cases, just needs to be dispatched from GENERATE_USUBJID rule |
| Regex-based DSL parser | Full parser/lexer | Simple regex `r'(\w+)\((.*)\)'` | The DSL is intentionally simple. A regex suffices. |
| Column name matching | Fuzzy string matching | Exact lookup with SAS label fallback | Fuzzy matching introduces non-determinism |

## Common Pitfalls

### Pitfall 1: Dataset Prefix Confusion in Derivation Rules
**What goes wrong:** LLM generates `CONCAT('PHA022121-C301', '-', irt.SSITENUM, '-', irt.SSUBJID)` where `irt.SSITENUM` means "column SSITENUM from the IRT dataset." But the executor has a merged DataFrame with no dataset prefixes on column names. Also, `SSITENUM` is not even the real column name.
**Why it happens:** The LLM sees eCRF metadata referencing IRT system names and uses them in derivation rules.
**How to avoid:** Strip `dataset.` prefixes during rule parsing, then run column name resolution on the remaining name. Example: `irt.SSITENUM` -> `SSITENUM` -> resolve to `SiteNumber`.
**Warning signs:** `KeyError: "SSITENUM not found in DataFrame columns"`

### Pitfall 2: Cross-Domain Derivation Rules Cannot Execute in Single-Domain Context
**What goes wrong:** `MIN_DATE_PER_SUBJECT(ex.EXDAT_INT)` requires data from `ex.sas7bdat`, but when executing the DM mapping, only `dm.sas7bdat` is loaded. The EX data is not available.
**Why it happens:** DM domain variables like RFSTDTC and RFENDTC are derived from EX (exposure) dates, which is a different dataset processed in a different domain.
**How to avoid:** Cross-domain rules (`MIN_DATE_PER_SUBJECT`, `MAX_DATE_PER_SUBJECT`, `LAST_DISPOSITION_DATE_PER_SUBJECT`) must either: (a) accept data from `CrossDomainContext`, or (b) be deferred to a post-execution enrichment step that runs after all domains are executed. Option (b) is more practical for v1.
**Warning signs:** Rules reference datasets not in `raw_dfs`.

### Pitfall 3: ISO 8601 Hour Without Minute
**What goes wrong:** `format_partial_iso8601(2023, 3, 15, 10, None, None)` currently returns `"2023-03-15T10"` which is INVALID per ISO 8601 and SDTM-IG v3.4 Section 4.1.4.1.
**Why it happens:** The function builds ISO 8601 by appending components, but does not enforce that time components are contiguous (hour requires minute to be present).
**How to avoid:** If `hour` is not None but `minute` is None, truncate before the time component entirely. Return `"2023-03-15"`.
**Warning signs:** P21 validation rule SD0070 failures.

### Pitfall 4: DDMonYYYY (No Spaces) Date Format
**What goes wrong:** SAS DATE9. format produces dates like `"30MAR2022"` (no spaces). The current `parse_string_date_to_iso()` only handles `"30 Mar 2022"` (with spaces). `"30MAR2022"` returns empty string.
**Why it happens:** The regex `_PATTERN_DD_MON_YYYY` requires whitespace between components.
**How to avoid:** Add a regex pattern for DDMonYYYY format: `r"^\s*(\d{1,2})(jan|feb|...|dec)(\d{4})\s*$"` (case-insensitive).

### Pitfall 5: Race Checkbox Logic
**What goes wrong:** DM race data is stored as separate checkbox columns (RACEAME=1, RACEASI=0, etc.). The SDTM RACE variable requires either a single race value or "MULTIPLE" if more than one checked. Column labels contain the race category name.
**Why it happens:** This is a common EDC pattern but requires understanding the checkbox-to-single-value transformation.
**How to avoid:** The `RACE_CHECKBOX` handler must: (1) identify which checkbox columns have value 1, (2) use column labels to determine race category names, (3) if exactly one checked, return that category name mapped through CT codelist C74457, (4) if multiple checked, return "MULTIPLE".

## Code Examples

### Example 1: Derivation Rule Parser and Dispatcher
```python
# Source: pattern_handlers.py (new code)
import re

_RULE_RE = re.compile(r'^(\w+)\s*\((.*)\)$', re.DOTALL)

def parse_derivation_rule(rule: str) -> tuple[str, list[str]]:
    """Parse KEYWORD(arg1, arg2) -> (KEYWORD, [arg1, arg2])."""
    rule = rule.strip()
    m = _RULE_RE.match(rule)
    if m:
        keyword = m.group(1).upper()
        raw_args = m.group(2)
        args = []
        for arg in raw_args.split(','):
            arg = arg.strip().strip("'\"")
            # Strip dataset prefix: dm.BRTHYR_YYYY -> BRTHYR_YYYY
            if '.' in arg and not arg.replace('.', '').replace('-', '').isdigit():
                arg = arg.split('.')[-1]
            args.append(arg)
        return keyword, args
    return rule.upper(), []


# Dispatch table for derivation rules
_DERIVATION_DISPATCH: dict[str, Callable] = {
    "GENERATE_USUBJID": _handle_generate_usubjid,
    "CONCAT": _handle_concat,
    "ISO8601_DATE": _handle_iso8601_date,
    "ISO8601_DATETIME": _handle_iso8601_datetime,
    "ISO8601_PARTIAL_DATE": _handle_iso8601_partial_date,
    "PARSE_STRING_DATE": _handle_parse_string_date,
    "MIN_DATE_PER_SUBJECT": _handle_min_date_per_subject,
    "MAX_DATE_PER_SUBJECT": _handle_max_date_per_subject,
    "RACE_CHECKBOX": _handle_race_checkbox,
    "RACE_FROM_CHECKBOXES": _handle_race_checkbox,  # alias
    "NUMERIC_TO_YN": _handle_numeric_to_yn,
}
```

### Example 2: CONCAT Handler
```python
def _handle_concat(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series:
    """Concatenate columns and literal values.

    Args are either column names (resolved from df) or literal strings.
    Literal strings are those that don't match any column name.
    """
    parts: list[pd.Series] = []
    for arg in args:
        resolved = _resolve_column(df, arg, kwargs)
        if resolved is not None:
            parts.append(df[resolved].astype(str))
        else:
            # Treat as literal
            parts.append(pd.Series(arg, index=df.index, dtype="object"))

    if not parts:
        return pd.Series(None, index=df.index, dtype="object")

    result = parts[0]
    for part in parts[1:]:
        result = result + part
    return result
```

### Example 3: Column Name Resolution
```python
def _resolve_column(
    df: pd.DataFrame,
    name: str,
    kwargs: dict,
) -> str | None:
    """Resolve a column name, trying exact match then alias lookup.

    Returns the actual column name in df, or None if not found.
    """
    # Strip dataset prefix
    if '.' in name:
        name = name.split('.')[-1]

    # Exact match
    if name in df.columns:
        return name

    # Check column aliases from kwargs
    aliases: dict[str, str] = kwargs.get("column_aliases", {})
    if name in aliases and aliases[name] in df.columns:
        return aliases[name]

    # Known standard aliases (hardcoded for common EDC patterns)
    STANDARD_ALIASES = {
        "SSUBJID": "Subject",
        "SSITENUM": "SiteNumber",
        "SCOUNTRY": None,  # Not available in this dataset
    }
    if name in STANDARD_ALIASES:
        resolved = STANDARD_ALIASES[name]
        if resolved and resolved in df.columns:
            return resolved

    return None
```

### Example 4: Wildcard Fix (1-line change)
```python
# In report.py, flag_known_false_positives(), lines 110-115
# BEFORE (broken):
if entry_domain is not None and result.domain != entry_domain:
    continue
if entry_variable is not None and result.variable != entry_variable:
    continue

# AFTER (fixed):
if entry_domain is not None and entry_domain != "*" and result.domain != entry_domain:
    continue
if entry_variable is not None and entry_variable != "*" and result.variable != entry_variable:
    continue
```

### Example 5: ISO 8601 Partial Date Fix (hour without minute)
```python
# In dates.py, format_partial_iso8601()
# BEFORE (broken):
if hour is None:
    return result
result += f"T{hour:02d}"

if minute is None:
    return result  # Returns "2023-03-15T10" -- INVALID

# AFTER (fixed):
if hour is None or minute is None:
    return result  # Truncate entire time component if incomplete
result += f"T{hour:02d}:{minute:02d}"
```

### Example 6: DDMonYYYY Date Pattern
```python
# In dates.py, add new regex pattern:
_PATTERN_DDMONYYYY = re.compile(
    r"^\s*(\d{1,2})(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{4})\s*$",
    re.IGNORECASE,
)

# In parse_string_date_to_iso(), add before YYYY-MM-DD check:
m = _PATTERN_DDMONYYYY.match(s)
if m:
    day = int(m.group(1))
    month = _MONTH_ABBREV[m.group(2).lower()]
    year = int(m.group(3))
    if not _validate_date_components(year=year, month=month, day=day):
        logger.warning("Invalid date: '{}'", s)
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"
```

### Example 7: RACE_CHECKBOX Handler
```python
def _handle_race_checkbox(
    df: pd.DataFrame,
    args: list[str],
    mapping: VariableMapping,
    **kwargs: object,
) -> pd.Series:
    """Derive RACE from checkbox columns.

    Each arg is a checkbox column name (value 0/1 or NaN).
    Column labels contain the race category name.
    Race categories are mapped to CT C74457 submission values.
    If multiple checked, return "MULTIPLE".
    """
    CT_RACE_MAP = {
        "American Indian or Alaska Native": "AMERICAN INDIAN OR ALASKA NATIVE",
        "Asian": "ASIAN",
        "Black or African American": "BLACK OR AFRICAN AMERICAN",
        "Native Hawaiian or Other Pacific Islander": "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
        "White": "WHITE",
        "Not Reported": "NOT REPORTED",
        "Other": "OTHER",
    }

    # Resolve column names and get their labels
    resolved_cols = []
    for arg in args:
        col = _resolve_column(df, arg, kwargs)
        if col is not None:
            resolved_cols.append(col)

    if not resolved_cols:
        return pd.Series(None, index=df.index, dtype="object")

    def derive_race(row):
        checked = []
        for col in resolved_cols:
            val = row.get(col)
            if pd.notna(val) and str(val).strip() in ("1", "1.0", "True"):
                # Extract race name from column label or column name
                race_name = _extract_race_from_col(col)
                if race_name:
                    checked.append(CT_RACE_MAP.get(race_name, race_name.upper()))
        if len(checked) == 0:
            return None
        if len(checked) == 1:
            return checked[0]
        return "MULTIPLE"

    return df.apply(derive_race, axis=1)
```

## Specific Bug Analysis

### Bug 1: CRIT-01 - Wildcard Matching in known_false_positives
**File:** `src/astraea/validation/report.py` lines 110-115
**Root cause:** `entry_domain="*"` compared with `result.domain="DM"` -- `"DM" != "*"` is True, so the entry never matches.
**Fix:** Add `and entry_domain != "*"` check (and same for entry_variable). Two lines changed.
**Impact:** 8 of 11 whitelist entries use `"*"` and are currently dead entries.
**Confidence: HIGH** -- The fix is trivially correct.

### Bug 2: CRIT-02 - USUBJID All-NULL
**File:** `src/astraea/execution/pattern_handlers.py` handle_derivation()
**Root cause:** `handle_derivation()` checks `if "USUBJID" in rule.upper()` on line 166, which would match `CONCAT('PHA022121-C301', '-', irt.SSITENUM, '-', irt.SSUBJID)` since "SSUBJID" contains "SUBJID" not "USUBJID". Wait -- "CONCAT(...SSUBJID)" does NOT contain "USUBJID". So the USUBJID special case is not triggered.
**Actual fix:** The `GENERATE_USUBJID` rule must be recognized. Also, even if it were triggered, the source column names (SSUBJID, SSITENUM) don't exist in the DataFrame.
**Confidence: HIGH** -- Two-part fix: (1) parse derivation rule to dispatch GENERATE_USUBJID/CONCAT, (2) resolve column names.

### Bug 3: HIGH-02 - BRTHDTC Raw Numeric
**File:** `src/astraea/execution/pattern_handlers.py` handle_reformat()
**Root cause:** `handle_reformat()` calls `get_transform(mapping.derivation_rule)` with `derivation_rule="ISO8601_PARTIAL_DATE(dm.BRTHYR_YYYY)"`. There is no transform registered with that exact name. The function falls through to passthrough.
**Fix:** `handle_reformat()` should also use the derivation rule parser to extract the keyword and dispatch.
**Confidence: HIGH**

### Bug 4: HIGH-10 - USUBJID Auto-Fix Skip
**File:** `src/astraea/validation/autofix.py` lines 318-320
**Root cause:** `_AUTO_FIXABLE_MISSING_VARS` includes "USUBJID" (line 67), so `classify_issue()` returns AUTO_FIXABLE. But `apply_fixes()` at line 319 does `continue` (skips). The classification says "fixable" but the implementation says "skip."
**Fix:** Either (a) remove USUBJID from `_AUTO_FIXABLE_MISSING_VARS` and classify as NEEDS_HUMAN, or (b) implement the actual fix (requires source data access). Recommendation: Option (a) for now -- classify USUBJID as NEEDS_HUMAN with reason "USUBJID requires source data and study_id for derivation."
**Confidence: HIGH**

### Bug 5: HIGH-17 - ISO 8601 Hour Without Minute
**File:** `src/astraea/transforms/dates.py` format_partial_iso8601() line 380-381
**Root cause:** The function appends `T{hour:02d}` and then checks if minute is None. Should not emit time component at all if minute is missing.
**Fix:** Change `if hour is None:` to `if hour is None or minute is None:` and return result (truncating time entirely). Then minute/second handling follows naturally.
**Confidence: HIGH**

### Bug 6: MED-18 - DDMonYYYY Format
**File:** `src/astraea/transforms/dates.py`
**Root cause:** No regex pattern for SAS DATE9. format (e.g., "30MAR2022", no spaces).
**Fix:** Add `_PATTERN_DDMONYYYY` regex and handler in `parse_string_date_to_iso()`.
**Confidence: HIGH**

## Cross-Domain Derivation Strategy

Several DM variables require data from other datasets:
- `RFSTDTC` = earliest EX dose date per subject (from `ex.sas7bdat`)
- `RFENDTC` = latest EX dose date per subject (from `ex.sas7bdat`)
- `RFICDTC` = informed consent date (from `ie.sas7bdat`)
- `RFPENDTC` = last disposition date (from `ds.sas7bdat`)

**Options:**

1. **Expand `raw_dfs` to include cross-domain data** -- Load EX, IE, DS data when executing DM mapping. Pro: everything runs in one pass. Con: breaks the "one domain at a time" execution model.

2. **Two-pass execution for DM** -- First pass: map everything available from dm.sas7bdat. Second pass: enrich with cross-domain data. Pro: clean separation. Con: more complex orchestration.

3. **Defer cross-domain derivations to a post-processing step** -- Execute all domains independently, then run a "DM enrichment" step that fills RFSTDTC/RFENDTC from completed EX domain data. Pro: simplest to implement. Con: requires all domains to be executed before DM is complete.

**Recommendation: Option 1 for Phase 11.** The executor already accepts `raw_dfs: dict[str, pd.DataFrame]` -- just pass additional DataFrames. For `MIN_DATE_PER_SUBJECT(ex.EXDAT_INT)`, load ex.sas7bdat as an additional raw_df. The derivation handler extracts the relevant column, groups by subject, and computes the min date.

This is pragmatic for v1. The executor already handles merged DataFrames. Adding cross-domain data as additional entries in `raw_dfs` avoids new architecture.

**Confidence: MEDIUM** -- The approach works but cross-domain column name conflicts may arise. Need to namespace columns if datasets have overlapping names.

## Column Name Resolution: Full Analysis

**The mismatch problem, precisely documented:**

| LLM Uses (eCRF Name) | Actual SAS Column | Dataset | Notes |
|---|---|---|---|
| `SSUBJID` | `Subject` | dm, ae, ex, ie, ds | EDC system column; always present |
| `SSITENUM` | `SiteNumber` | dm, ae, ex, ie, ds | EDC system column; always present |
| `SCOUNTRY` | (not present) | dm | LLM hallucinated; no country column in dm.sas7bdat |
| `ICDAT_INT` | `ICDAT_INT` | ie | Correct name; different dataset |
| `EXDAT_INT` | `EXDAT_INT` | ex | Correct name; different dataset |
| `BRTHYR_YYYY` | `BRTHYR_YYYY` | dm | Correct name |
| `SEX_STD` | `SEX_STD` | dm | Correct name |
| `ETHNIC_STD` | `ETHNIC_STD` | dm | Correct name |

**Key insight:** The LLM gets most names right for clinical data columns. The mismatches are concentrated in EDC system columns (`Subject`, `SiteNumber`) which have generic names that differ from the eCRF field names. These are the same across ALL datasets.

**Recommended alias map (global, not per-domain):**
```python
EDC_COLUMN_ALIASES = {
    "SSUBJID": "Subject",
    "SSITENUM": "SiteNumber",
    "SSITE": "Site",
    "SSITEGROUP": "SiteGroup",
}
```

This small, static map covers the known mismatches. It should be applied as part of column resolution before any pattern handler executes.

## State of the Art

| Old Approach | Current Approach | Impact |
|-------------|-----------------|--------|
| Free-form derivation_rule text | Formal keyword vocabulary | LLM output becomes executable |
| No column name resolution | Alias-based resolution | eCRF names map to SAS columns |
| Wildcard `"*"` as literal | Wildcard `"*"` matches all | False positive suppression works |

## Open Questions

1. **How should cross-domain data be namespaced?** When loading `ex.sas7bdat` as additional data for DM execution, both datasets have `Subject` and `SiteNumber` columns. The merge step (`pd.concat`) would duplicate these. Solution: either use a dict-based lookup (don't merge, access separately) or prefix columns.

2. **Should the derivation vocabulary be validated at spec-creation time?** After the LLM generates a spec, the enrichment step could check that every `derivation_rule` uses a recognized keyword and reject/warn on unrecognized ones. This gives earlier feedback than waiting for execution.

3. **How to handle SCOUNTRY (hallucinated column)?** The LLM mapped COUNTRY from `irt.SCOUNTRY` but this column doesn't exist. Options: (a) drop the mapping, (b) derive from site metadata, (c) add to StudyMetadata as a constant. Recommend (a) for now -- let the executor log a warning and produce NULL for COUNTRY.

4. **How far to extend the vocabulary beyond DM?** The initial vocabulary covers DM needs. AE, EX, and other domains will generate rules like `MEDDRA_LOOKUP`, `CONCAT_DATE_TIME`, etc. Should Phase 11 define ALL possible rules across all domains, or just the ones needed for DM to work?

   **Recommendation:** Define the full vocabulary for all domains in the prompt (so the LLM knows what's available), but only implement handlers needed for DM execution in Phase 11. Mark unimplemented rules with a TODO handler that returns NULL with a clear warning.

## Sources

### Primary (HIGH confidence)
- `output/DM_mapping.json` -- Actual LLM-generated mapping spec for DM domain (real output)
- `src/astraea/execution/pattern_handlers.py` -- Current executor dispatch logic
- `src/astraea/mapping/prompts.py` -- Current LLM prompt
- `src/astraea/mapping/transform_registry.py` -- Registered transform functions
- `src/astraea/transforms/dates.py` -- Current date conversion code
- `src/astraea/validation/report.py` -- False positive matching code
- `Fakedata/dm.sas7bdat` -- Actual SAS column names (read via pyreadstat)
- `.planning/MASTER_AUDIT.md` -- All audit findings with evidence

### Secondary (MEDIUM confidence)
- `Fakedata/ae.sas7bdat`, `ex.sas7bdat`, `ie.sas7bdat`, `ds.sas7bdat` -- Cross-domain column names

## Metadata

**Confidence breakdown:**
- Derivation vocabulary design: HIGH -- based on actual LLM output analysis
- Column name resolution: HIGH -- based on actual SAS column inspection
- Bug fixes (wildcard, dates, autofix): HIGH -- root causes identified with exact line numbers
- Cross-domain strategy: MEDIUM -- approach is sound but untested
- Full-domain vocabulary scope: MEDIUM -- only DM analyzed in depth

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (stable -- internal codebase, no external dependencies)
