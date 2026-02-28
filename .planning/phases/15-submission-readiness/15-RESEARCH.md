# Phase 15: Submission Readiness - Research

**Researched:** 2026-02-28
**Domain:** FDA submission artifact completeness, execution pipeline gaps, expanded validation
**Confidence:** HIGH (codebase inspection + FDA requirements research)

## Summary

Phase 15 addresses the remaining MED and LOW items from the FDA Compliance Audit that were not resolved in Phases 11-14. The focus areas are: (1) execution pipeline completion (SPLIT pattern, key-based merges, specimen/method/fasting), (2) DM mapping enforcement for ARM variables, (3) cSDRG content generation (Sections 2 and 6), (4) eCTD directory structure, (5) cSDRG non-standard variable justification, (6) pre-mapped SDTM data detection, (7) LC domain support, and (8) expanded FDA Business Rules.

All work is purely additive -- no architectural changes needed. The codebase has solid foundations (1567+ tests, 0 ruff/mypy errors). Each item is a well-scoped feature addition to existing modules.

**Primary recommendation:** Organize into 5-6 plans grouped by module proximity. Prioritize the execution pipeline items (SPLIT, merge, specimen handling) and cSDRG content first, as these have the highest submission impact. LC domain and expanded FDAB rules are the largest items and should each get their own plan.

## Standard Stack

No new libraries needed. All work uses existing stack:

### Core (already installed)
| Library | Purpose | Used For |
|---------|---------|----------|
| `pandas` | DataFrame operations | SPLIT pattern, LC domain generation, merge logic |
| `pydantic` | Data models | Any new models for LC, SPLIT config |
| `lxml` | XML generation | define.xml is already done |
| `jinja2` | Template rendering | cSDRG content (already using Jinja2) |
| `loguru` | Logging | All new code |
| `pytest` | Testing | All new tests |

### No New Dependencies
Every Phase 15 item can be implemented with existing libraries. No pip installs needed.

## Architecture Patterns

### Current Codebase Structure (relevant files)

```
src/astraea/
  execution/
    pattern_handlers.py    # SPLIT stub lives here (line 709)
    executor.py            # Multi-source merge logic
    findings.py            # Specimen/method/fasting goes here
    trial_summary.py       # Already has FDA_REQUIRED_PARAMS
  submission/
    csdrg.py               # cSDRG template (Jinja2)
    define_xml.py          # Already largely complete
  validation/
    rules/
      fda_business.py      # 6 rules implemented, need ~14 more
  profiling/
    profiler.py            # Pre-mapped data detection goes here
  mapping/
    engine.py              # DM ARM enforcement goes here
```

### Pattern 1: SPLIT Pattern Implementation
**What:** The SPLIT pattern extracts one source column into multiple SDTM target variables by parsing/splitting.
**When:** Rare -- typically for coded fields where "1=Yes,2=No" becomes separate binary flags, or where a single comment field splits into --TERM and --DECOD.
**Current state:** `handle_split()` in `pattern_handlers.py` is a stub returning `None` with a warning.
**Implementation approach:** Parse `mapping.derivation_rule` for a SPLIT directive that specifies: source column, delimiter or regex pattern, target position (1st, 2nd, etc). Use the existing derivation rule dispatch pattern (`_DERIVATION_DISPATCH` dict).

```python
# Example SPLIT derivation rules the LLM might generate:
# SPLIT(AETERM, ' - ', 0)  -> take first part
# SPLIT(COMMENT, regex, group_index) -> regex group extraction
# SUBSTRING(COMMENT, 0, 8) -> substring extraction
```

### Pattern 2: Key-Based Horizontal Merge
**What:** MED-12 says multi-source merge is concat-only. Need key-based horizontal joins (pandas merge on USUBJID/VISITNUM).
**Current state:** `merge_findings_sources()` in `findings.py` uses `pd.concat()` only.
**Implementation approach:** Add a `merge_mode` parameter to distinguish concat (vertical stack) from join (horizontal merge on keys). The executor already has `CrossDomainContext` for cross-domain data -- use a similar pattern.

### Pattern 3: Findings Domain Metadata Variables
**What:** --SPEC (specimen type), --METHOD (method), --FAST (fasting status) are Expected variables for LB domain per SDTM-IG v3.4.
**Current state:** Not implemented. No mentions in `findings.py`.
**Implementation approach:** Add derivation functions in `findings.py` that:
- Copy LBSPEC from source data if present (often in raw lab data)
- Copy LBMETHOD from source data if present
- Derive LBFAST from VISITNUM or time-based heuristics, or copy from source
- These are "pass-through if present" variables, not complex derivations

### Pattern 4: cSDRG Content Generation
**What:** Section 2 (Study Description) and Section 6 (Known Data Issues) are placeholders. Section 8 needs per-variable justification for non-standard variables.
**Current state:** `csdrg.py` uses Jinja2 template. Section 2 says "[Placeholder: Add study description...]". Section 6 says "[Placeholder: Document any known data quality issues...]".
**Implementation approach:**
- Section 2: Accept a `study_description` parameter (from TSConfig or separate input). Generate trial design summary from TS parameters (phase, blinding, control, objectives).
- Section 6: Auto-generate from validation report -- list unresolved findings with explanations. Auto-populate from `known_false_positives.json` entries.
- Non-standard variable justification: For each SUPPQUAL candidate, include source variable, reason for non-standard placement, and data origin.

### Pattern 5: eCTD Directory Structure
**What:** MED-25 requires enforcing `m5/datasets/tabulations/sdtm/` folder structure for output.
**Current state:** No directory structure enforcement exists.
**Implementation approach:** Add a `package_submission()` function in `submission/` that:
1. Takes output directory and generates proper eCTD structure
2. Copies/symlinks XPT files to correct locations
3. Places define.xml, acrf.pdf, csdrg.pdf in correct locations
4. Validates file naming (lowercase, no spaces, correct extensions)

### Pattern 6: Pre-Mapped SDTM Data Detection
**What:** `ecg_results.sas7bdat` and `lab_results.sas7bdat` already have SDTM variable names. Pipeline should detect and route differently.
**Current state:** `findings.py` normalizers handle these as special cases in comments but no formal detection.
**Implementation approach:** Add a `detect_sdtm_format()` function to profiler that checks if a dataset's columns match standard SDTM Findings variable patterns (--TESTCD, --TEST, --ORRES, --STRESC, --STRESN). Flag in profile. During classification, route pre-mapped data to a validate-only path.

### Pattern 7: LC Domain Generation
**What:** FDA requires dual lab domains: LB (SI units) + LC (conventional units) with 1:1 observation matching.
**Current state:** Not implemented at all.
**Implementation approach:**
- LC has identical structure to LB (same variables with LC prefix instead of LB)
- Generate LC by copying LB data and swapping unit columns:
  - LCORRES = conventional unit result
  - LCORRESU = conventional unit
  - LCSTRESC/LCSTRESN/LCSTRESU = standardized conventional values
- If source data only has one unit system, flag for unit conversion (conversion tables are out of scope for v1 but the structure must exist)
- LCSEQ must match LBSEQ for record pairing

### Pattern 8: FDA Business Rule Implementation
**What:** Expand from 6 to 20+ FDAB rules.
**Current state:** 6 rules: FDAB009, FDAB015, FDAB030, FDAB039, FDAB055, FDAB057.
**Implementation approach:** Follow existing pattern -- each rule is a `ValidationRule` subclass with `evaluate()` method, registered via `get_fda_business_rules()`. Priority rules to add:

| Rule ID | Description | Domain | Complexity |
|---------|------------|--------|------------|
| FDAB001 | AESER (Serious Event) must be Y or N | AE | Low |
| FDAB002 | AEREL (Causality) must use CT | AE | Low |
| FDAB003 | AEOUT (Outcome) must use CT | AE | Low |
| FDAB004 | AEACN (Action Taken) must use CT | AE | Low |
| FDAB005 | AE dates: AESTDTC <= AEENDTC | AE | Low |
| FDAB016 | DM.COUNTRY must use ISO 3166 | DM | Low |
| FDAB017 | CT compliance for all coded variables | All | Medium |
| FDAB020 | VISITNUM must be numeric | All | Low |
| FDAB021 | --DY must not include Day 0 | All | Low |
| FDAB022 | --DTC must be ISO 8601 | All | Low (already have format rule, promote) |
| FDAB025 | CMTRT must not be null | CM | Low |
| FDAB026 | EXTRT must not be null | EX | Low |
| FDAB035 | LBORRES/LBORRESU relationship | LB | Medium |
| FDAB036 | LBSTRESN/LBSTRESU relationship | LB | Medium |

### Anti-Patterns to Avoid
- **Do not generate LC from unit conversion algorithms.** If source data lacks dual units, create LC as a copy of LB with a flag indicating units were not converted. Unit conversion libraries are complex and error-prone -- out of scope.
- **Do not use LLM for SPLIT pattern.** SPLIT should be deterministic parsing based on the derivation rule.
- **Do not rewrite cSDRG generator.** Extend the existing Jinja2 template with new sections and parameters.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| eCTD folder assembly | Custom file copier | `shutil.copytree` + `pathlib` | Standard library handles this well |
| ISO 3166 country validation | Custom country list | Hardcoded set of ~250 codes | Small, stable dataset |
| SDTM variable pattern detection | Complex regex engine | Simple prefix + suffix checks | SDTM naming is highly regular |
| LC domain structure | New domain model | Copy LB DomainMappingSpec + relabel | LC is structurally identical to LB |

## Common Pitfalls

### Pitfall 1: LC Domain Record Count Mismatch
**What goes wrong:** LC and LB have different observation counts, failing FDA validation.
**Why it happens:** If filtering or deduplication is applied differently to the two domains.
**How to avoid:** Generate LC directly from LB data in a single pass. LCSEQ = LBSEQ.
**Warning signs:** Row count differs between LB and LC DataFrames.

### Pitfall 2: SPLIT Pattern Fragility
**What goes wrong:** SPLIT derivation rules from LLM are inconsistent in format.
**Why it happens:** The LLM invents arbitrary split expressions.
**How to avoid:** Support a small vocabulary of SPLIT operations: SUBSTRING, REGEX_GROUP, DELIMITER_PART. Log warnings for unrecognized patterns. Return source column unchanged on failure (not None).
**Warning signs:** handle_split returning None series.

### Pitfall 3: cSDRG Section 2 Empty Content
**What goes wrong:** Study description is blank because no input was provided.
**Why it happens:** The system has TS parameters but no free-text study description.
**How to avoid:** Auto-generate Section 2 from TS domain parameters (TITLE, TPHASE, TBLIND, INDIC, OBJPRIM, PLANSUB, NARMS). Fall back to a clear "[Study description not provided]" message rather than empty space.

### Pitfall 4: Expanded FDAB Rules with Wrong Severity
**What goes wrong:** New rules use WARNING when FDA considers them equal to ERROR.
**Why it happens:** FDA v1.6 removed severity levels but internal code still classifies.
**How to avoid:** Default all new FDAB rules to ERROR severity. The cSDRG must explain ALL findings regardless of severity, so ERROR is the safer default.

### Pitfall 5: Pre-Mapped Data Re-Mapping
**What goes wrong:** ecg_results and lab_results are already in SDTM format but the pipeline re-maps them, corrupting the data.
**Why it happens:** No detection mechanism for pre-mapped data.
**How to avoid:** Detection function checks for standard SDTM variable patterns (DOMAIN column present, --TESTCD/--TEST/--ORRES pattern). Detected datasets get routed to validate-only path.

## Code Examples

### SPLIT Pattern Handler (new)
```python
def handle_split(df: pd.DataFrame, mapping: VariableMapping, **kwargs: object) -> pd.Series:
    """Extract a portion of a source column via SPLIT derivation rules."""
    rule = mapping.derivation_rule or ""
    if not rule:
        if mapping.source_variable and mapping.source_variable in df.columns:
            return df[mapping.source_variable].copy()
        return pd.Series(None, index=df.index, dtype="object")

    keyword, args = parse_derivation_rule(rule)

    if keyword == "SUBSTRING" and len(args) >= 3:
        col = _resolve_column(df, args[0], kwargs)
        if col and col in df.columns:
            start, end = int(args[1]), int(args[2])
            return df[col].astype(str).str[start:end]

    if keyword == "DELIMITER_PART" and len(args) >= 3:
        col = _resolve_column(df, args[0], kwargs)
        if col and col in df.columns:
            delimiter, part_idx = args[1], int(args[2])
            return df[col].astype(str).str.split(delimiter).str[part_idx]

    # Fallback: pass through source column
    if mapping.source_variable:
        col = _resolve_column(df, mapping.source_variable, kwargs)
        if col and col in df.columns:
            return df[col].copy()

    logger.warning("SPLIT: unrecognized rule '{}' for {}", rule, mapping.sdtm_variable)
    return pd.Series(None, index=df.index, dtype="object")
```

### Pre-Mapped SDTM Detection
```python
_FINDINGS_INDICATORS = {"TESTCD", "TEST", "ORRES", "STRESC", "STRESN"}

def detect_sdtm_format(profile: DatasetProfile) -> bool:
    """Detect if a profiled dataset is already in SDTM Findings format."""
    col_names = {v.name.upper() for v in profile.variables if not v.is_edc_column}
    # Check for standard Findings suffixes with a domain prefix
    for prefix in ("LB", "EG", "VS", "PE", "QS"):
        matches = sum(1 for ind in _FINDINGS_INDICATORS if f"{prefix}{ind}" in col_names)
        if matches >= 3:
            return True
    # Check for DOMAIN column with standard domain code
    if "DOMAIN" in col_names:
        return True
    return False
```

### LC Domain Generation
```python
def generate_lc_from_lb(lb_df: pd.DataFrame, study_id: str) -> pd.DataFrame:
    """Generate LC domain by mirroring LB data with LC prefix.

    For v1, no unit conversion -- LC is a structural copy of LB
    with LC variable names. Unit conversion deferred to future version.
    """
    lc_df = lb_df.copy()

    # Rename LB-prefixed columns to LC
    rename_map = {}
    for col in lc_df.columns:
        if col.startswith("LB") and col != "LBBLFL":
            rename_map[col] = "LC" + col[2:]

    lc_df = lc_df.rename(columns=rename_map)
    lc_df["DOMAIN"] = "LC"

    # LCSEQ mirrors LBSEQ for 1:1 pairing
    if "LCSEQ" in lc_df.columns:
        pass  # Already renamed from LBSEQ
    return lc_df
```

### cSDRG Section 2 Auto-Generation
```python
def _generate_study_description(ts_params: dict[str, str]) -> str:
    """Generate Section 2 text from TS domain parameters."""
    title = ts_params.get("TITLE", "[Title not available]")
    phase = ts_params.get("TPHASE", "[Phase not specified]")
    indication = ts_params.get("INDIC", "[Indication not specified]")
    blinding = ts_params.get("TBLIND", "[Blinding not specified]")
    control = ts_params.get("TCNTRL", "[Control not specified]")
    narms = ts_params.get("NARMS", "[Not specified]")
    plansub = ts_params.get("PLANSUB", "[Not specified]")

    return (
        f"**{title}**\n\n"
        f"This is a {phase}, {blinding.lower()}, {control.lower()} study "
        f"investigating {indication.lower()}. "
        f"The study was designed with {narms} treatment arm(s) "
        f"and a planned enrollment of {plansub} subjects."
    )
```

### FDAB Rule Template (AE domain example)
```python
class FDAB001Rule(ValidationRule):
    """FDAB001: AE.AESER must be Y or N."""
    rule_id: str = "FDAB001"
    description: str = "AE.AESER (Serious Event) must be Y or N"
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(self, domain, df, spec, sdtm_ref, ct_ref) -> list[RuleResult]:
        if domain != "AE" or "AESER" not in df.columns:
            return []
        valid = {"Y", "N"}
        vals = df["AESER"].dropna().unique()
        invalid = [str(v) for v in vals if str(v) not in valid]
        if not invalid:
            return []
        return [RuleResult(
            rule_id=self.rule_id,
            rule_description=self.description,
            category=self.category,
            severity=self.severity,
            domain=domain,
            variable="AESER",
            message=f"Invalid AESER values: {invalid}. Must be Y or N.",
            affected_count=sum(1 for v in df["AESER"].dropna() if str(v) not in valid),
            fix_suggestion="Map AESER to Y/N controlled terminology",
        )]
```

## State of the Art

| Area | Current State | Target State | Impact |
|------|--------------|-------------|--------|
| SPLIT pattern | Stub returning None | Functional SUBSTRING/DELIMITER/REGEX | Handles split-type mappings |
| Multi-source merge | Concat only | Concat + key-based horizontal join | Enables DM+treatment arm joins |
| Specimen/Method/Fasting | Not implemented | Pass-through from source data | Expected variables populated |
| DM ARM variables | Not enforced in prompts | Post-mapping validation check | Catches missing ARM/ARMCD |
| cSDRG Sections 2,6 | Placeholders | Auto-generated from TS + validation | Submission-quality document |
| eCTD structure | Not enforced | Assembly function creates m5/ tree | Correct folder layout |
| Non-standard justification | Generic notes | Per-variable justification text | P21 compliance |
| Pre-mapped detection | Not implemented | Profile-level flag | Routes to validate-only path |
| LC domain | Not implemented | Mirrors LB with LC prefix | FDA SDTCG v5.7 compliance |
| FDAB rules | 6 implemented | 20+ implemented | Better validation coverage |

## Open Questions

1. **LC domain unit conversion:** The FDA mandates SI units in LB and conventional in LC. If source data only has one unit system, should Astraea attempt conversion or just flag it? **Recommendation:** For v1, create LC as a structural copy and add a validation warning saying "Unit conversion not performed -- manual review required." Unit conversion tables are complex (different per analyte) and error-prone.

2. **SPLIT pattern vocabulary:** What SPLIT operations should the LLM be allowed to propose? **Recommendation:** Support SUBSTRING, DELIMITER_PART, and REGEX_GROUP. Anything else falls back to pass-through with warning.

3. **DM ARM enforcement:** Should this be a mapping prompt constraint or a post-execution validation check? **Recommendation:** Both. Add ARM/ARMCD/ACTARM/ACTARMCD to the DM domain spec's required variables check in the presence rules. This catches the gap regardless of LLM output quality.

4. **cSDRG output format:** Currently Markdown. FDA expects PDF. **Recommendation:** Keep Markdown generation, note that PDF conversion (via pandoc or similar) is a LOW item. The content is what matters for v1.

## Sources

### Primary (HIGH confidence)
- **Codebase inspection** -- direct reading of all relevant source files
- `.planning/FDA_COMPLIANCE_AUDIT.md` -- complete inventory of MED/LOW items
- `.planning/PIPELINE_HANDS_ON_AUDIT.md` -- execution pipeline gaps
- `.planning/research/FDA_SUBMISSION_REQUIREMENTS.md` -- exhaustive FDA requirements

### Secondary (HIGH confidence)
- SDTM-IG v3.4 domain specifications (bundled in `src/astraea/data/sdtm_ig/domains.json`)
- FDA Study Data Technical Conformance Guide (SDTCG v5.7/v6.0) -- LC domain requirement
- FDA Business Rules v1.5 Excel spreadsheet -- FDAB rule definitions

## Metadata

**Confidence breakdown:**
- SPLIT pattern: HIGH -- codebase has clear stub, implementation path is straightforward
- LC domain: MEDIUM -- structural copy is simple but unit conversion scope unclear
- cSDRG content: HIGH -- existing Jinja2 template just needs more parameters
- eCTD structure: HIGH -- well-documented folder layout, simple file operations
- FDA Business Rules: HIGH -- existing pattern is clear, just need more rule classes
- Pre-mapped detection: MEDIUM -- heuristic approach, may need tuning
- Specimen/Method/Fasting: HIGH -- pass-through from source data, simple implementation

**Research date:** 2026-02-28
**Valid until:** Indefinite (codebase-specific research, not library-dependent)
