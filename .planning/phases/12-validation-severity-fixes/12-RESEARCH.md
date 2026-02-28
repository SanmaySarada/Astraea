# Phase 12: Validation and Severity Fixes - Research

**Researched:** 2026-02-28
**Domain:** SDTM Validation Rules Engine -- Adding missing rules and correcting severity levels
**Confidence:** HIGH

## Summary

Phase 12 addresses 8 specific audit findings (HIGH-06 through HIGH-09, HIGH-16, MED-01, MED-04, MED-05) from the Master Audit. The validation engine already exists with 45+ rules across 7 categories. This phase adds 3 new rules, corrects 2 severity levels, expands TS parameter coverage, extends TRC checks, and integrates TRCPreCheck into validate_all().

The existing codebase is well-structured with clear patterns. Every ValidationRule subclass follows the same evaluate() signature. Registration happens via `get_*_rules()` factory functions. TRCPreCheck is standalone (not a ValidationRule subclass) because it checks submission-level artifacts, not per-domain data. The planner can follow these established patterns exactly.

**Primary recommendation:** This is a straightforward phase -- all 8 items are well-scoped changes to existing code. No architectural decisions needed. Follow the existing patterns, write tests first, then implement.

## Standard Stack

No new libraries needed. This phase works entirely within the existing validation module.

### Core (already installed)
| Library | Purpose | Used For |
|---------|---------|----------|
| `pandas` | DataFrame operations | Rule evaluation on domain DataFrames |
| `pydantic` | Data models | RuleResult, ValidationRule base class |
| `loguru` | Logging | Debug output in rules |
| `pytest` | Testing | Unit tests for each rule/fix |

## Architecture Patterns

### Existing Validation Rule Pattern (follow exactly)
```
src/astraea/validation/
  rules/
    base.py            # RuleSeverity, RuleCategory, RuleResult, ValidationRule
    terminology.py     # ASTR-T001, ASTR-T002 + get_terminology_rules()
    presence.py        # ASTR-P001..P004 + get_presence_rules()
    consistency.py     # CrossDomainValidator (standalone) + get_consistency_rules() -> []
    limits.py          # ASTR-L001..L004 + get_limit_rules()
    format.py          # ASTR-F001..F003 + get_format_rules()
    fda_business.py    # FDAB057,055,039,009,030 + get_fda_business_rules()
    fda_trc.py         # TRCPreCheck (standalone) + get_fda_trc_rules() -> []
  engine.py            # ValidationEngine: register_defaults(), validate_domain(), validate_all()
```

### Pattern 1: Per-Domain ValidationRule Subclass
**What:** Each rule is a Pydantic BaseModel subclass with fixed `rule_id`, `description`, `category`, `severity` fields and an `evaluate()` method.
**When:** For rules that check a single domain's DataFrame (SEX codelist, --SEQ uniqueness, DM one-record-per-subject).
**Example:**
```python
class SomeRule(ValidationRule):
    rule_id: str = "RULE-ID"
    description: str = "Human description"
    category: RuleCategory = RuleCategory.SOME_CATEGORY
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(self, domain, df, spec, sdtm_ref, ct_ref) -> list[RuleResult]:
        if domain != "TARGET_DOMAIN":
            return []
        # ... check logic ...
        return results
```

### Pattern 2: Rule Registration
**What:** Each rule module exports a `get_*_rules()` function returning `list[ValidationRule]`.
**When:** Always. The engine calls these in `register_defaults()`.
**Example:**
```python
def get_fda_business_rules() -> list[ValidationRule]:
    return [FDAB057Rule(), FDAB055Rule(), ...]
```

### Pattern 3: TRCPreCheck (Standalone)
**What:** TRCPreCheck is NOT a ValidationRule subclass. It has its own `check_all()` method taking `(generated_domains, output_dir, study_id)`.
**When:** For submission-level checks that span all domains (not per-domain evaluation).
**Current integration:** `get_fda_trc_rules()` returns `[]`. TRCPreCheck must be called separately.

### Pattern 4: Test Pattern
**What:** Tests use mocked `CTReference`, `SDTMReference`, and `DomainMappingSpec` fixtures. Each rule class gets its own test class.
**Example in:** `tests/unit/validation/test_fda_rules.py`

### Anti-Patterns to Avoid
- **Do NOT use LLM for any validation logic** -- all rules are deterministic
- **Do NOT change the ValidationRule.evaluate() signature** -- it is a fixed contract
- **Do NOT put TRCPreCheck into the per-domain rule registry** -- it has a different interface

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CT codelist lookup | Custom dict lookup | `ct_ref.lookup_codelist("C66731")` | Already returns Codelist model with `.terms` dict and `.extensible` flag |
| Domain spec lookup | Custom domain check | `sdtm_ref.get_domain_spec(domain)` | Already returns variable lists with core designations |

## Common Pitfalls

### Pitfall 1: C66731 SEX Is Non-Extensible
**What goes wrong:** Treating SEX validation like RACE (extensible). SEX codelist C66731 has exactly 4 valid terms: `M`, `F`, `U`, `UNDIFFERENTIATED`. Any other value is an ERROR, not a WARNING.
**How to avoid:** The new SEX rule must use `RuleSeverity.ERROR` and check against the C66731 codelist. The codelist IS present in bundled `codelists.json` with `extensible=False`.

### Pitfall 2: FDAB057 Severity Change May Break Existing Tests
**What goes wrong:** The test `test_invalid_ethnic_detected` in `test_fda_rules.py` line 139 asserts `results[0].severity == RuleSeverity.WARNING`. Changing FDAB057 to ERROR will break this test.
**How to avoid:** Update the test assertion simultaneously with the severity change.

### Pitfall 3: TRCPreCheck Integration Requires Different Call Signature
**What goes wrong:** Trying to register TRCPreCheck as a ValidationRule in the engine registry. TRCPreCheck.check_all() takes `(generated_domains, output_dir, study_id)` which is incompatible with the per-domain `evaluate()` signature.
**How to avoid:** Integration into `validate_all()` should call TRCPreCheck.check_all() alongside the existing cross-domain checks, not through the per-domain rule loop. The engine's `validate_all()` already has access to all domains dict.

### Pitfall 4: --SEQ Column Naming Is Domain-Prefixed
**What goes wrong:** Looking for a column literally named "SEQ". In SDTM, sequence variables are domain-prefixed: `AESEQ`, `LBSEQ`, `DMSEQ`, etc. The pattern is `{domain_prefix}SEQ`.
**How to avoid:** The SEQ uniqueness rule must dynamically construct the column name from the domain code (e.g., for "AE" look for "AESEQ", for "LB" look for "LBSEQ"). Use the 2-char prefix pattern already used in FDAB039Rule.

### Pitfall 5: validate_all() Needs output_dir and study_id for TRCPreCheck
**What goes wrong:** Current `validate_all()` signature is `validate_all(self, domains: dict[str, tuple[pd.DataFrame, DomainMappingSpec]])`. TRCPreCheck needs `output_dir` and `study_id` which are not currently passed.
**How to avoid:** Add optional `output_dir` and `study_id` parameters to `validate_all()`. When provided, run TRCPreCheck. When omitted, skip TRC (backward compatible).

## Code Examples

### New Rule: DM.SEX Codelist Validation (HIGH-07)
```python
class FDAB015Rule(ValidationRule):
    """FDAB015: DM.SEX values must conform to CT codelist C66731.

    SEX uses non-extensible codelist C66731 with exactly 4 valid values:
    M, F, U, UNDIFFERENTIATED. Invalid values cause FDA findings.
    """
    rule_id: str = "FDAB015"
    description: str = "DM.SEX values must conform to CT codelist C66731"
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(self, domain, df, spec, sdtm_ref, ct_ref) -> list[RuleResult]:
        if domain != "DM":
            return []
        if "SEX" not in df.columns:
            return [RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="SEX",
                message="DM domain is missing SEX variable",
                fix_suggestion="Add SEX variable to DM domain",
            )]
        # Check against C66731
        valid_terms: set[str] = set()
        codelist = ct_ref.lookup_codelist("C66731")
        if codelist:
            valid_terms = set(codelist.terms.keys())
        if valid_terms:
            sex_values = df["SEX"].dropna().unique()
            invalid = [str(v) for v in sex_values if str(v) not in valid_terms]
            if invalid:
                return [RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain,
                    variable="SEX",
                    message=f"Invalid SEX values: {invalid}. Valid: {sorted(valid_terms)}",
                    affected_count=sum(1 for v in df["SEX"].dropna() if str(v) not in valid_terms),
                    fix_suggestion="Map SEX values to C66731: M, F, U, UNDIFFERENTIATED",
                )]
        return []
```

### New Rule: --SEQ Uniqueness (HIGH-08)
```python
class SeqUniquenessRule(ValidationRule):
    """--SEQ must be unique per USUBJID within a domain (P21 SD0007)."""
    rule_id: str = "ASTR-P005"
    description: str = "--SEQ must be unique per USUBJID within a domain"
    category: RuleCategory = RuleCategory.PRESENCE
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(self, domain, df, spec, sdtm_ref, ct_ref) -> list[RuleResult]:
        prefix = domain[:2]
        seq_col = f"{prefix}SEQ"
        if seq_col not in df.columns or "USUBJID" not in df.columns:
            return []
        # Group by USUBJID, check SEQ uniqueness
        grouped = df.groupby("USUBJID")[seq_col]
        dup_subjects = []
        for usubjid, seq_series in grouped:
            non_null = seq_series.dropna()
            if non_null.duplicated().any():
                dup_subjects.append(str(usubjid))
        if dup_subjects:
            return [RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable=seq_col,
                message=f"Duplicate {seq_col} values within USUBJID for {len(dup_subjects)} subject(s)",
                affected_count=len(dup_subjects),
                fix_suggestion=f"Ensure {seq_col} is unique per USUBJID",
                p21_equivalent="SD0007",
            )]
        return []
```

### New Rule: DM One-Record-Per-Subject (MED-05)
```python
class DMOneRecordPerSubjectRule(ValidationRule):
    """DM must have exactly one record per USUBJID."""
    rule_id: str = "ASTR-P006"
    description: str = "DM must have exactly one record per subject"
    category: RuleCategory = RuleCategory.PRESENCE
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(self, domain, df, spec, sdtm_ref, ct_ref) -> list[RuleResult]:
        if domain != "DM":
            return []
        if "USUBJID" not in df.columns:
            return []
        dup_mask = df["USUBJID"].duplicated(keep=False)
        if dup_mask.any():
            dup_count = df.loc[dup_mask, "USUBJID"].nunique()
            return [RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="USUBJID",
                message=f"DM has duplicate records for {dup_count} subject(s)",
                affected_count=int(dup_mask.sum()),
                fix_suggestion="Remove duplicate DM records -- DM must be one record per subject",
            )]
        return []
```

### Severity Fix: FDAB057 (HIGH-09)
```python
# In fda_business.py, line 36:
# CHANGE FROM:
severity: RuleSeverity = RuleSeverity.WARNING
# CHANGE TO:
severity: RuleSeverity = RuleSeverity.ERROR
```

### Severity Fix: ASTR-F002 ASCII (MED-01)
```python
# In format.py, line 104:
# CHANGE FROM:
severity: RuleSeverity = RuleSeverity.WARNING
# CHANGE TO:
severity: RuleSeverity = RuleSeverity.ERROR
```

### TRC Expansion: Check SDTMVER, STYPE, TITLE (HIGH-16)
```python
# In fda_trc.py, expand _check_ts_present() to check multiple mandatory params:
_TRC_REQUIRED_TS_PARAMS = {"SSTDTC", "SDTMVER", "STYPE", "TITLE"}

# For each param, if missing from TS TSPARMCD values, emit an ERROR result.
```

### FDA Required TS Expansion (HIGH-06)
The current `FDA_REQUIRED_PARAMS` in `trial_summary.py` has 7 entries:
```
SSTDTC, SPONSOR, INDIC, TRT, STYPE, SDTMVER, TPHASE
```

Per FDA guidance, expand to 26+ including:
```
TITLE, PLANSUB, RANDOM, SEXPOP, TBLIND, TCNTRL, OBJPRIM, REGID,
OUTMSPRI, FCNTRY, AGEMIN, AGEMAX, LENGTH, STOPRULE, ADAPT, ACTSUB,
NARMS, HLTSUBJI, SENDTC, ADDON, DCUTDTC, TTYPE, DCUTDESC
```

Note: This impacts both `trial_summary.py` (the frozenset and the builder) and `validate_ts_completeness()`. The TSConfig model may need new optional fields, or the additional params can be passed via `additional_params`.

### TRCPreCheck Integration into validate_all() (MED-04)
```python
# In engine.py, modify validate_all() signature:
def validate_all(
    self,
    domains: dict[str, tuple[pd.DataFrame, DomainMappingSpec]],
    *,
    output_dir: Path | None = None,
    study_id: str | None = None,
) -> list[RuleResult]:
    # ... existing per-domain + cross-domain logic ...

    # Add TRC checks when output_dir and study_id provided
    if output_dir is not None and study_id is not None:
        trc = TRCPreCheck()
        domain_dfs = {code: df for code, (df, _spec) in domains.items()}
        trc_results = trc.check_all(domain_dfs, output_dir, study_id)
        all_results.extend(trc_results)

    return all_results
```

## Detailed Findings Per Requirement

### HIGH-06: FDA-mandatory TS Parameters (Currently 7, Need 26+)
**Current state:** `FDA_REQUIRED_PARAMS` in `trial_summary.py` has 7 params: SSTDTC, SPONSOR, INDIC, TRT, STYPE, SDTMVER, TPHASE.
**What must change:**
1. Expand `FDA_REQUIRED_PARAMS` frozenset to include all FDA-mandatory codes
2. The `build_ts_domain()` function currently hardcodes 8 "always-included" params (TITLE, SPONSOR, INDIC, TRT, PCLAS, STYPE, SDTMVER, TPHASE) and conditionally adds PLESSION, NARMS, ACESSION, ADDON
3. Many of the 26+ params require study-specific values that may not be available in TSConfig -- these should be added as optional fields on TSConfig or passed via `additional_params`
4. `validate_ts_completeness()` already checks against `FDA_REQUIRED_PARAMS` -- expanding the frozenset automatically expands validation
**Complexity:** MEDIUM -- need to decide which params become TSConfig fields vs additional_params

### HIGH-07: DM.SEX Codelist Validation
**Current state:** No rule checks DM.SEX against C66731.
**What must change:** Add new FDAB015Rule to fda_business.py, register in get_fda_business_rules().
**C66731 codelist:** EXISTS in bundled codelists.json, non-extensible, terms: M, F, U, UNDIFFERENTIATED.
**Complexity:** LOW -- follows exact same pattern as FDAB057/FDAB055.

### HIGH-08: --SEQ Uniqueness Check
**Current state:** No rule checks sequence number uniqueness.
**What must change:** Add SeqUniquenessRule to presence.py, register in get_presence_rules().
**Key detail:** SEQ column name is domain-prefixed (AESEQ, LBSEQ, etc.). Must check uniqueness per USUBJID, not globally.
**Complexity:** LOW -- straightforward groupby + duplicated check.

### HIGH-09: FDAB057 Severity WARNING -> ERROR
**Current state:** `fda_business.py` line 36: `severity: RuleSeverity = RuleSeverity.WARNING`
**What must change:** Change to `RuleSeverity.ERROR`. C66790 is non-extensible.
**Test impact:** `test_fda_rules.py` line 139 asserts `RuleSeverity.WARNING` -- must update.
**Complexity:** TRIVIAL -- one-line change + test update.

### HIGH-16: TRC Checks Beyond SSTDTC
**Current state:** `_check_ts_present()` in fda_trc.py only checks for SSTDTC.
**What must change:** Check for SDTMVER, STYPE, TITLE (at minimum). These are FDA Technical Rejection Criteria -- missing any causes immediate rejection.
**Complexity:** LOW -- extend existing _check_ts_present() with a list of required params.

### MED-01: ASTR-F002 Severity WARNING -> ERROR
**Current state:** `format.py` line 104: `severity: RuleSeverity = RuleSeverity.WARNING`
**What must change:** Change to `RuleSeverity.ERROR`. Non-ASCII in XPT causes data corruption.
**Test impact:** Check `test_limit_format_rules.py` for assertions on ASTR-F002 severity.
**Complexity:** TRIVIAL -- one-line change + test update.

### MED-04: TRCPreCheck into validate_all()
**Current state:** `validate_all()` runs per-domain rules + cross-domain checks but does NOT run TRCPreCheck. Callers must separately invoke TRCPreCheck.
**What must change:** Add optional `output_dir` and `study_id` params to `validate_all()`. When provided, run TRCPreCheck.check_all() and append results. Backward compatible when omitted.
**Complexity:** LOW -- add optional params, conditional call.

### MED-05: DM One-Record-Per-Subject
**Current state:** No rule enforces DM structure constraint.
**What must change:** Add DMOneRecordPerSubjectRule to presence.py, register in get_presence_rules().
**Complexity:** LOW -- simple duplicated() check on USUBJID in DM domain.

## Inventory of Current Rules (for reference)

| Module | Rule ID | Description | Severity |
|--------|---------|-------------|----------|
| terminology.py | ASTR-T001 | CT values must match codelist | ERROR (non-ext) / WARNING (ext) |
| terminology.py | ASTR-T002 | DOMAIN column must match domain code | ERROR |
| presence.py | ASTR-P001 | Required variables must be present | ERROR |
| presence.py | ASTR-P002 | Expected variables should be present | WARNING |
| presence.py | ASTR-P003 | Dataset should have >= 1 record | WARNING |
| presence.py | ASTR-P004 | USUBJID must be present and complete | ERROR |
| consistency.py | ASTR-C001 | USUBJID consistency with DM | ERROR |
| consistency.py | ASTR-C002 | STUDYID consistency across domains | ERROR |
| consistency.py | ASTR-C003 | RFSTDTC vs EXSTDTC consistency | WARNING |
| consistency.py | ASTR-C004 | DOMAIN column value consistency | ERROR |
| consistency.py | ASTR-C005 | Study day sign consistency | WARNING |
| limits.py | ASTR-L001 | Variable name <= 8 chars | ERROR |
| limits.py | ASTR-L002 | Variable label <= 40 chars | ERROR |
| limits.py | ASTR-L003 | Character values <= 200 bytes | ERROR |
| limits.py | ASTR-L004 | Dataset size reasonableness | NOTICE/WARNING |
| format.py | ASTR-F001 | ISO 8601 date format | ERROR |
| format.py | ASTR-F002 | ASCII-only character data | **WARNING (to change)** |
| format.py | ASTR-F003 | Domain code valid for XPT naming | ERROR |
| fda_business.py | FDAB057 | DM.ETHNIC CT C66790 | **WARNING (to change)** |
| fda_business.py | FDAB055 | DM.RACE CT C74457 | WARNING |
| fda_business.py | FDAB039 | Normal range numeric check | WARNING |
| fda_business.py | FDAB009 | TESTCD/TEST 1:1 relationship | ERROR |
| fda_business.py | FDAB030 | STRESU consistency per TESTCD | WARNING |
| fda_trc.py | FDA-TRC-1736 | DM domain must be present | ERROR |
| fda_trc.py | FDA-TRC-1734 | TS + SSTDTC must be present | ERROR |
| fda_trc.py | FDA-TRC-1735 | define.xml must be present | ERROR |
| fda_trc.py | FDA-TRC-STUDYID | STUDYID consistent | ERROR |
| fda_trc.py | FDA-TRC-FILENAME | Lowercase .xpt filenames | ERROR |

## Open Questions

1. **FDA Required TS Params -- exact list?** The audit says "26+" but doesn't provide a definitive list. The SDTM-IG v3.4 and FDA guidance documents define the list, but it varies by submission type (NDA vs BLA vs IND). Recommendation: use a commonly-accepted list of ~26 params from FDA CDER guidance and document the source.

2. **TSConfig model expansion scope?** Adding 19+ optional fields to TSConfig is a significant model change. Alternative: keep TSConfig lean and document that callers should pass study-specific params via `additional_params`. Recommendation: add the most common params (PLANSUB, RANDOM, TBLIND, FCNTRY, AGEMIN, AGEMAX, OBJPRIM, REGID) as optional fields; leave exotic ones for additional_params.

3. **Should TRC check ALL 26+ TS params or just the critical 4?** The TRC checks in fda_trc.py are meant for "will cause immediate rejection" criteria. Not all 26 TS params cause rejection. Recommendation: TRC checks the top ~4-6 rejection-causing params (SSTDTC, SDTMVER, STYPE, TITLE); the full 26+ check stays in validate_ts_completeness() as WARNINGs.

## Sources

### Primary (HIGH confidence)
- Direct code inspection of all files in `src/astraea/validation/` -- current rule structure, severities, patterns
- Direct code inspection of `src/astraea/execution/trial_summary.py` -- FDA_REQUIRED_PARAMS, TSConfig
- Direct inspection of `src/astraea/data/ct/codelists.json` -- C66731 confirmed present, non-extensible, 4 terms
- Master Audit at `.planning/MASTER_AUDIT.md` -- definitive list of findings to address

### Secondary (MEDIUM confidence)
- FDA CDER guidance on required TS parameters -- referenced in audit but not independently verified
- P21 rule SD0007 (--SEQ uniqueness) -- standard P21 rule, well-known

## Metadata

**Confidence breakdown:**
- Rule patterns: HIGH -- directly read and analyzed existing code
- C66731 codelist: HIGH -- confirmed in bundled data
- Severity corrections: HIGH -- directly verified current values in source
- TS parameter expansion list: MEDIUM -- referenced from audit, not independently verified against FDA source
- TRC integration approach: HIGH -- analyzed validate_all() signature and TRCPreCheck interface

**Research date:** 2026-02-28
**Valid until:** Indefinite (internal codebase research, not version-dependent)
