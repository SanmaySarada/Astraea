# Domain Pitfalls

**Domain:** Agentic AI for SDTM mapping (clinical data standardization)
**Researched:** 2026-02-26
**Confidence:** HIGH for SDTM/clinical pitfalls; MEDIUM for multi-agent/RL pitfalls

---

## Critical Pitfalls

Mistakes that cause rewrites, regulatory rejection, or fundamental architecture failure.

---

### C1: Hallucination Cascading Across the Agent Pipeline

**What goes wrong:** A single agent (e.g., the Domain Classifier) hallucates a classification -- say, labeling a concomitant medications dataset as Adverse Events. Every downstream agent (Mapper, Derivation, Validator) builds on this wrong foundation. The Mapping Agent confidently maps CM variables to AE SDTM variables. The Derivation Agent generates AE-specific derived fields. By the time the Validator catches it (if it even does), the entire pipeline output is garbage.

**Why it happens:** LLMs are confidently wrong. Downstream agents have no independent way to verify upstream claims -- they trust the input context. Research from UC Berkeley (2025) found that "a minor hallucination from a Research Agent becomes fact for the Execution Agent, causing small errors to snowball into complete system failure." In SDTM mapping specifically, domain classification errors are catastrophic because every variable mapping depends on the target domain.

**Warning signs:**
- Validator catching domain-level errors (wrong required variables, wrong identifier variables)
- SDTM variable names appearing that don't belong to the classified domain
- Mapping spec reviews showing obviously wrong domain assignments
- High rate of P21 validation errors of the "variable not expected in domain" type

**Prevention:**
- Independent verification at each pipeline stage -- the Mapping Agent should re-verify domain classification, not blindly trust it
- Deterministic sanity checks between agents: after Domain Classifier, run a rule-based check (does this dataset have AETERM? Then it's probably AE, regardless of what the LLM said)
- Confidence scores on every agent output; route low-confidence results to human review
- Circuit breakers: if Validator finds >N errors, halt and re-run from the failing stage

**Detection:** Build domain-classification ground truth from the eCRF form names. If the eCRF says "Adverse Events" and the classifier says "CM", that's a hard fail.

**Phase:** Must be addressed in Phase 1 (core pipeline). This is not a nice-to-have -- it's table stakes for a multi-agent system.

---

### C2: SDTM Controlled Terminology Misapplication

**What goes wrong:** The LLM maps free-text values to the wrong CT codelist terms, uses terms from the wrong codelist version, or applies extensible codelist rules to non-extensible codelists. Example: mapping "Headache" to the wrong AETERM codelist, or worse, using a CT version that doesn't match the declared SDTM-IG version.

**Why it happens:** CDISC publishes CT updates quarterly (most recent: 2025-09-26). There is a strict one-to-one relationship between SDTM-IG versions and supported CT versions. LLMs have no inherent awareness of version constraints. Additionally, non-extensible codelists (like SEX) require exact matches -- "Male" is valid, "male" is not, "M" is not. Extensible codelists allow additions but the LLM may not understand which codelists are which.

**Warning signs:**
- P21 validation errors: "value not found in codelist"
- Thousands of false positives in validation (known P21 issue with LBSTRESC in version 2405.2)
- Inconsistent CT versions across domains in the same study
- Free-text values leaking through where coded values are required

**Prevention:**
- Bundle CT codelists as structured lookup tables (JSON/CSV), not as LLM prompt context
- CT lookup must be deterministic: exact match against the bundled codelist, not LLM "best guess"
- Validate CT version alignment at system initialization: SDTM-IG version X requires CT version Y, enforce this
- For non-extensible codelists, use strict dictionary lookup with zero tolerance for fuzzy matching
- For extensible codelists, allow LLM to propose new terms but flag them for human review

**Detection:** Run CT validation as a post-mapping step before generating datasets. Any unmapped or mismatched term should halt that variable's processing.

**Phase:** Phase 1 (core mapping). CT application is not something to "add later" -- incorrect CT means FDA technical rejection.

---

### C3: Version Mismatch Between SDTM-IG and Controlled Terminology

**What goes wrong:** The system generates datasets claiming compliance with SDTM-IG v3.4 but uses CT terms from a v3.3-era codelist, or vice versa. FDA requires specific version alignment (as of March 15, 2025: SDTMv2.0 + SDTMIG v3.4). Technical rejection criteria include 3 out of 4 checks related to the TS (Trial Summary) domain, which declares the standards version.

**Why it happens:** CT is updated quarterly. SDTM-IG versions change less frequently but have strict version coupling. A system bundling "the latest CT" without tracking which IG version it pairs with will produce datasets that look correct locally but fail FDA validation.

**Warning signs:**
- TS domain TSVAL entries for "SDTM-IG version" not matching the CT version used
- P21 validation warnings about version mismatches
- define.xml declaring one version while datasets use another

**Prevention:**
- Create a version manifest: a single config file that locks SDTM-IG version + CT version + P21 rules version together
- Validate the manifest at system startup
- Make version selection explicit (user chooses or system detects from study metadata)
- Ship multiple CT versions and select based on study requirements

**Detection:** Automated check: parse TS domain for declared versions, compare against bundled CT version, fail fast on mismatch.

**Phase:** Phase 1 (infrastructure). This is a configuration concern but has regulatory consequences.

---

### C4: SUPPQUAL Referential Integrity Failures

**What goes wrong:** SUPPQUAL (Supplemental Qualifier) records are generated without valid parent records in the parent domain, or parent records are generated without their required SUPPQUAL records. Example: SUPPAE contains a record referencing AESEQ=5, but AE only has records up to AESEQ=4. Or: the raw data contains non-standard variables that should go to SUPPQUAL but the system drops them silently.

**Why it happens:** SUPPQUAL is conceptually tricky -- it's a separate dataset that supplements its parent domain with a vertical key-value structure (QNAM, QLABEL, QVAL, QORIG). The LLM must decide which raw variables go to the main domain vs. SUPPQUAL, maintain referential integrity via RDOMAIN/USUBJID/IDVAR/IDVARVAL, and get the QNAM naming conventions right. This is a multi-step reasoning task that LLMs frequently get wrong.

**Warning signs:**
- P21 errors: "SUPPQUAL record has no matching parent record"
- Raw variables disappearing from output (not in domain, not in SUPPQUAL)
- QNAM values that don't follow naming conventions (max 8 chars, alphanumeric)
- Duplicate QNAM values within the same parent domain

**Prevention:**
- SUPPQUAL generation must be a deterministic post-processing step, not LLM-generated
- After mapping agent proposes variable assignments, a rule-based engine should: (a) identify unmapped raw variables, (b) determine if they belong in SUPPQUAL, (c) generate SUPPQUAL records with verified referential integrity
- Validate parent-child linkage programmatically before output
- Build a "coverage report" showing every raw variable and its destination (domain variable, SUPPQUAL, or explicitly excluded)

**Detection:** Coverage audit: for every raw variable in every raw dataset, the system must account for where it went. Unaccounted variables are a red flag.

**Phase:** Phase 2 (advanced mapping). SUPPQUAL is not needed for MVP but is required for submission-quality output.

---

### C5: Non-Deterministic LLM Output for the Same Input

**What goes wrong:** Running the same raw dataset through the pipeline twice produces different SDTM mappings. Variable X maps to VSORRES in run 1 and VSSTRESN in run 2. This is unacceptable in a regulated environment where reproducibility is required.

**Why it happens:** LLMs are inherently stochastic. Even with temperature=0, there is no guarantee of identical outputs (implementation-level sampling can vary). For clinical data submissions, this means the system could produce different datasets from the same input, which is a regulatory compliance disaster.

**Warning signs:**
- QC runs producing different results from production runs
- Human reviewers seeing different mapping proposals on re-runs
- Validation results changing between runs without data changes

**Prevention:**
- Set temperature=0 for all mapping-critical LLM calls
- Cache LLM outputs: once a mapping is approved, store it deterministically and reuse it
- Use structured output (JSON mode / tool calling) to constrain LLM responses to valid SDTM structures
- Implement a "mapping specification" layer: the LLM proposes, the spec is saved, and dataset generation is purely deterministic from the spec
- Add a reproducibility test to CI: run the same input twice, diff the outputs

**Detection:** Automated regression test: run pipeline on reference dataset, compare output hash to known-good baseline.

**Phase:** Phase 1 (core architecture). The mapping-spec-then-generate pattern must be baked in from day one.

---

### C6: Context Window Overflow with Large Datasets

**What goes wrong:** A raw SAS dataset with 200 variables and 50,000 rows cannot fit into an LLM context window. Even metadata-only approaches (variable names, labels, sample values) can overflow when combined with SDTM-IG reference text, CT codelists, and eCRF context. Research shows Claude's effective context degrades at 60-120K tokens, with "context rot" causing the model to miss information buried in the middle of long prompts.

**Why it happens:** The Astraea pipeline needs to provide the LLM with: (a) raw dataset metadata, (b) relevant eCRF form metadata, (c) SDTM-IG domain specification, (d) relevant CT codelists, (e) prior mapping examples/corrections. For a complex domain like LB (Lab) with dozens of tests and codelists, this easily exceeds context limits.

**Warning signs:**
- Mapping quality degrading for larger/more complex domains
- LLM "forgetting" instructions from system prompt as context fills up
- Inconsistent handling of variables at the end of long variable lists
- Token costs spiking for certain domains

**Prevention:**
- Process one domain at a time, not the entire study at once
- Within a domain, chunk variables into groups (e.g., 10-20 variables per LLM call)
- Use a retrieval strategy: only include relevant CT codelists, not all codelists
- Separate the LLM call into focused sub-tasks: (1) classify variable type, (2) propose target variable, (3) define transformation -- not all at once
- Pre-filter eCRF context to only the relevant form for the current domain
- Monitor token usage per call and alert when approaching limits

**Detection:** Track tokens-per-call metrics. If any call exceeds 80% of context window, flag for chunking review.

**Phase:** Phase 1 (core architecture). The chunking/retrieval strategy is an architectural decision that's expensive to retrofit.

---

## Moderate Pitfalls

Mistakes that cause delays, rework, or technical debt.

---

### M1: Agent Coordination Loops and Step Repetition

**What goes wrong:** Agents get stuck in loops -- the Mapping Agent proposes a mapping, the Validator rejects it, the Mapping Agent proposes the same mapping again, infinitely. Or the orchestrator repeatedly invokes the same agent without progressing. The MAST taxonomy (2025) identifies "Step Repetition" as one of the 14 core failure modes in multi-agent systems.

**Why it happens:** The agent lacks memory of what it already tried, or the rejection feedback is too vague for the agent to course-correct. In SDTM mapping, this manifests as: Validator says "AESER value invalid," Mapper re-proposes the same value because it doesn't know what valid values are.

**Warning signs:**
- Same LLM call appearing multiple times in logs
- Pipeline runtime growing without proportional progress
- Token costs spiking for a single dataset
- Agents producing identical outputs on retry

**Prevention:**
- Implement a retry budget: max N retries per variable/domain, then escalate to human review
- Pass structured error context on retry: not just "invalid" but "AESER must be Y or N per CT codelist C66742"
- Maintain agent memory across retries: "You already tried X, that failed because Y"
- Add circuit breakers: if pipeline has been running >T minutes for a single domain, halt and report

**Detection:** Log every agent invocation with input hash. If the same hash appears more than twice, trigger alert.

**Phase:** Phase 1 (pipeline orchestration). Loop prevention must be in the orchestrator from the start.

---

### M2: ISO 8601 Date/Time Conversion Edge Cases

**What goes wrong:** Dates in raw clinical data are messy: partial dates ("2023-UN-UN"), dates in local formats ("15/03/2023"), timezone-unaware timestamps, dates stored as SAS numeric values (days since 1960-01-01), and dates with only year and month. The SDTM standard requires ISO 8601 format (YYYY-MM-DDTHH:MM:SS) but also has specific rules for partial dates: missing components are omitted (not imputed), represented with truncation from the right.

**Why it happens:** Raw data comes from EDC systems with varying date formats. SAS stores dates as numeric values internally. Partial dates are common in clinical data (patient reports "sometime in March 2023"). The rules for representing partial dates in ISO 8601 for SDTM are specific: "2023-03" is valid (year-month), "2023---15" is NOT valid. Each missing component up to the last non-missing component is a hyphen.

**Warning signs:**
- P21 errors about invalid date formats
- Dates showing as "." (missing) when they should be partial
- SAS numeric dates not converting correctly (off by one day due to timezone)
- Inconsistent date formats within the same domain

**Prevention:**
- Build date conversion as a deterministic utility, NOT an LLM task
- Create a date parser that handles: SAS numeric dates, partial dates, multiple input formats (DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD)
- Implement SDTM-specific partial date formatting rules
- Unit test extensively: test every edge case (leap years, partial dates, timezone boundaries, Unix epoch vs SAS epoch)
- Detect ambiguous dates (is 03/04/2023 March 4 or April 3?) and flag for human review

**Detection:** Validate all --DTC variables against ISO 8601 regex pattern after conversion. Any non-matching value is a hard error.

**Phase:** Phase 1 (core utilities). Date conversion is needed for every domain and must be rock-solid.

---

### M3: eCRF PDF Parsing Failures for Table Structures

**What goes wrong:** The eCRF PDF contains structured tables with field names, data types, SAS labels, coded values, and OIDs. PDF parsing tools fail to extract these tables correctly -- merged cells get misaligned, multi-line cell content gets split into separate rows, headers get separated from data, and page breaks within tables cause row loss. Looking at the actual eCRF text extraction for this project, the text is already semi-garbled: field values are separated from their labels, page numbers are interleaved with data, and table structure is lost.

**Why it happens:** PDFs are a visual format, not a data format. Table detection relies on heuristics (line detection for camelot, character clustering for pdfplumber). Clinical eCRFs have inconsistent formatting: some pages have clean tables, others have free-text annotations mixed with structured data. Research comparing 12 PDF table extraction tools found "appalling" results across the board.

**Warning signs:**
- Extracted field counts not matching expected counts per form
- SAS labels appearing as separate rows instead of cell values
- Field OIDs misaligned with field names
- Missing forms (pages that failed extraction silently)

**Prevention:**
- Use pdfplumber (best for layout-sensitive extraction) as primary, with pymupdf as fallback
- Build form-level validation: for each eCRF form, verify that extracted fields match expected structure (field name + data type + SAS label + OID)
- Support a "pre-parsed eCRF" mode: allow users to provide a structured JSON/CSV of eCRF metadata, bypassing PDF parsing entirely
- Build a manual correction workflow: when parsing fails, present extracted text and let the user fix it
- Consider using Claude's vision capability to process eCRF pages as images for complex layouts

**Detection:** After extraction, compute a "parsing confidence score": % of forms where field count matches header count, % of fields with valid OIDs, % of forms with at least one field.

**Phase:** Phase 1 (parser agent). This is the first step in the pipeline. If parsing fails, everything downstream is wrong.

---

### M4: Horizontal-to-Vertical Transpose Errors (Labs, Vital Signs)

**What goes wrong:** Raw lab data often comes in wide format (one column per test: WBC, RBC, HGB, etc.). SDTM requires vertical format (one row per test, with LBTESTCD, LBORRES, LBORRESU columns). The transpose logic is complex: each column becomes multiple rows, units must be carried from headers, reference ranges must be mapped, and the relationship between LBORRES (character result) and LBSTRESN (numeric standardized result) must be maintained.

**Why it happens:** This is a structural transformation, not just a renaming. The LLM needs to understand that column "WBC" with value "5.2" and unit "10^3/uL" becomes a row with LBTESTCD="WBC", LBORRES="5.2", LBORRESU="10^3/uL", and then also needs to standardize: LBSTRESC="5.2", LBSTRESN=5.2, LBSTRESU="10^9/L" (SI units). Getting any part of this chain wrong produces invalid lab data.

**Warning signs:**
- Row counts in output not matching expected (input_columns x input_rows)
- Missing units in LBORRESU or LBSTRESU
- LBSTRESN values that don't match LBSTRESC (string/numeric mismatch)
- Duplicate LBSEQ values within the same subject/visit

**Prevention:**
- Transpose logic must be deterministic Python code (pandas melt/pivot), NOT LLM-generated
- The LLM's role: identify which raw columns are test results, what the test codes are, what the units are. The actual transpose: pure code
- Build a transpose template per domain type (LB, VS, EG) with validation
- Unit conversion tables should be deterministic lookups, not LLM reasoning

**Detection:** Post-transpose validation: verify row counts, check for NULL units, validate LBORRES/LBSTRESN consistency.

**Phase:** Phase 2 (advanced transformations). Simple direct-map and rename domains should work in Phase 1.

---

### M5: Reward Hacking in the RL Feedback Loop

**What goes wrong:** The RL system learns to game the reward signal rather than genuinely improve mapping accuracy. Example: if the reward is "fewer human corrections," the system learns to produce vague/safe mappings that humans don't bother correcting (rather than precise mappings). Or it learns to map everything to the most common target variable because that's "usually right" and reduces correction rate.

**Why it happens:** The reward model is a proxy for actual mapping quality. Any gap between the proxy and the true objective gets exploited. Research from 2025 shows this is the single most common failure mode in RLHF systems, with the policy "exploiting inaccuracies of the reward function rather than learning the intended behavior."

**Warning signs:**
- Mapping accuracy plateauing while human corrections decrease (system learned to be safe, not correct)
- Distribution of target variables becoming less diverse (system defaulting to common mappings)
- Complex mappings (transposes, derivations) being avoided in favor of simple direct maps
- System producing fewer SUPPQUAL records over time (avoidance behavior)

**Prevention:**
- Use multi-dimensional reward: not just "accepted/rejected" but separate scores for domain classification accuracy, variable mapping accuracy, CT compliance, and transformation correctness
- Include deterministic validation as part of the reward (P21 pass/fail is objective, not gameable)
- Monitor mapping diversity metrics: if the system starts avoiding complex mappings, the reward is misspecified
- Use rule-based verification as the primary reward signal, human feedback as secondary (aligns with 2025 research on combining binary verifiers with RL)
- Implement reward shaping: gradient regularization to keep policy in regions where reward is well-calibrated

**Detection:** Track mapping type distribution over time. Alert if direct-map proportion increases while transpose/derivation proportion decreases.

**Phase:** Phase 3 (RL pipeline). This is a Phase 3 concern but the reward model design should be planned in Phase 2.

---

### M6: Cold Start Problem for the RL Pipeline

**What goes wrong:** The RL system needs human corrections to improve, but early versions are so inaccurate that humans spend more time correcting than doing the mapping manually. Users lose trust and stop using the system, starving the RL pipeline of training data. The system never reaches the accuracy threshold where it becomes useful.

**Why it happens:** Classic chicken-and-egg: the system needs corrections to get better, but it needs to be somewhat good to generate useful corrections. For SDTM mapping specifically, statistical programmers are expensive ($150-300/hr) and won't tolerate a tool that creates more work than it saves.

**Warning signs:**
- User adoption dropping after initial trial
- Correction rate >60% in early usage (users correcting more than they accept)
- Users bypassing the system and doing manual mapping
- Feedback data volume stagnating

**Prevention:**
- Pre-seed with supervised fine-tuning: before any user sees the tool, train on a corpus of known-good SDTM mappings (the fake data in this project is a starting point)
- Curate high-quality prompt examples (few-shot learning) that cover the common mapping patterns
- Start with easy domains (DM, AE, DS -- relatively standard structure) where accuracy will be highest, building user trust before tackling hard domains (LB, EG)
- Set user expectations: "this is an assistant, not an autopilot" -- present mappings as suggestions, not decisions
- Track and report accuracy improvements to users: "your corrections improved accuracy by X%"

**Detection:** Track correction rate per domain per week. If it's not trending down, the RL pipeline has a problem.

**Phase:** Phase 2 (human review) and Phase 3 (RL). The pre-seeding and few-shot strategy must be designed in Phase 1.

---

### M7: P21 Validation Rule Version Drift

**What goes wrong:** The built-in validator uses P21 rules that don't match what the FDA actually runs. The system passes internal validation but fails FDA validation. Or the system flags thousands of false positives (known issue: P21 v2405.2 generates false positives for LBSTRESC numeric values), causing users to ignore all warnings.

**Why it happens:** P21 updates its validation rules independently of SDTM-IG releases. The FDA publishes its own validation rules (latest: v1.6) that may differ from P21 community rules. False positives erode trust in the validator, leading to "alert fatigue" where real issues get ignored.

**Warning signs:**
- Internal validation passing but external P21 finding errors
- Thousands of validation messages per dataset (likely false positive storm)
- Users ignoring validation output because "it always has errors"
- Rule counts not matching between internal validator and P21

**Prevention:**
- Do NOT reimplement P21 from scratch -- use P21 Community Edition or map to its published rule set
- Version-lock validation rules to match the FDA's published validation rules (currently v1.6)
- Categorize validation findings: CRITICAL (will cause rejection), WARNING (should be explained in Reviewer's Guide), INFO (cosmetic)
- Build a known-false-positive whitelist based on published P21 known issues
- Test against real P21 output: generate datasets, run through actual P21, compare results

**Detection:** Periodically run generated datasets through the real P21 tool and compare results with internal validation. Divergence is a bug.

**Phase:** Phase 2 (validation). Internal validation in Phase 1 can be simple; P21-aligned validation is a Phase 2 concern.

---

## Minor Pitfalls

Mistakes that cause annoyance, minor rework, or degraded UX.

---

### m1: Token Cost Explosion for Iterative Refinement

**What goes wrong:** Each mapping iteration sends the full context (raw metadata + SDTM-IG + CT + eCRF + prior attempts) to the LLM. For a study with 36 datasets, even metadata-only calls add up. If the system retries failed mappings, costs multiply. A single study mapping could cost $50-200 in API calls.

**Prevention:**
- Cache successful mappings aggressively -- never re-map an approved variable
- Use smaller/cheaper models for classification tasks (domain classification doesn't need the full Claude model)
- Implement token budgets per study with alerts
- Profile token usage per agent and optimize the most expensive calls first

**Phase:** Phase 1 (architecture). Token-aware design should be built in, not bolted on.

---

### m2: RELREC Relationship Mapping Errors

**What goes wrong:** The RELREC (Related Records) domain captures relationships between records across domains -- e.g., linking an AE record to the CM record for the concomitant medication used to treat it. Getting RELREC wrong means losing critical data relationships.

**Prevention:**
- Defer RELREC to Phase 2 or later -- it's not required for basic SDTM compliance
- When implemented, use deterministic relationship detection based on explicit keys (USUBJID + dates), not LLM inference
- Validate all RELREC references: every RDOMAIN/USUBJID/IDVAR/IDVARVAL must point to an existing record

**Phase:** Phase 3 (advanced features). RELREC is rarely needed for initial submissions and is hard to get right.

---

### m3: SAS Transport File (.xpt) Format Edge Cases

**What goes wrong:** Generated .xpt files fail to load in SAS or P21 due to: variable name length >8 characters, variable label length >40 characters, character variable length >200 characters, or invalid dataset names. The XPT format (SAS Transport v5) has strict constraints that pandas' xport libraries may not enforce.

**Prevention:**
- Validate all variable names (<=8 chars, alphanumeric), labels (<=40 chars), and dataset names (<=8 chars) BEFORE writing XPT
- Use the `xport` Python library with explicit format validation
- Test generated XPT files by reading them back and comparing to source
- Build a pre-write validation check that catches truncation issues

**Phase:** Phase 2 (dataset generation). Phase 1 can output CSV for validation; XPT is a Phase 2 concern.

---

### m4: Define.xml Generation Errors

**What goes wrong:** The define.xml (dataset metadata document) must exactly match the generated datasets: every variable, every codelist, every value-level metadata entry. Mismatches between define.xml and actual datasets are a common FDA finding.

**Prevention:**
- Generate define.xml AFTER datasets are final, directly from the dataset metadata -- never manually
- Validate define.xml against datasets: every variable in define.xml must exist in the dataset, and vice versa
- Use existing define.xml generation libraries rather than building from scratch

**Phase:** Phase 3 (submission readiness). Define.xml is not needed for core mapping validation.

---

### m5: Inconsistent Agent Outputs Due to Prompt Drift

**What goes wrong:** As prompts are refined during development, different agents end up with subtly incompatible assumptions. The Domain Classifier uses SDTM-IG v3.4 terminology but the Mapping Agent's prompt was written against v3.3. Or the Derivation Agent expects dates in one format but the Mapping Agent outputs another.

**Prevention:**
- Centralize all SDTM reference material in a single source of truth (a reference module) that all agent prompts draw from
- Version-control all prompts alongside code
- Include prompt integration tests: run the full pipeline and verify agents produce compatible outputs
- Use typed interfaces between agents (Pydantic models) so format mismatches are caught at the boundary

**Phase:** Phase 1 (architecture). Agent interface contracts should be defined before agents are built.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1: eCRF Parsing | PDF table extraction fails on this specific eCRF | Build fallback: allow manual JSON input of eCRF metadata |
| Phase 1: Domain Classification | Hallucination cascading to downstream agents | Independent verification + deterministic sanity checks |
| Phase 1: Core Mapping | Non-deterministic outputs between runs | Mapping spec layer: LLM proposes, spec is saved, generation is deterministic |
| Phase 1: Date Conversion | ISO 8601 partial date edge cases | Deterministic utility with exhaustive unit tests |
| Phase 1: Architecture | Context window overflow for complex domains | Chunking strategy designed upfront, not retrofitted |
| Phase 2: CT Application | Version mismatch between IG and CT | Version manifest locking all standard versions together |
| Phase 2: SUPPQUAL | Referential integrity failures | Deterministic SUPPQUAL generation, not LLM-generated |
| Phase 2: Validation | P21 false positive storm eroding user trust | Known-issue whitelist + severity categorization |
| Phase 2: Transpose Logic | Lab/VS data structural transformation errors | Deterministic pandas code for transpose, LLM only for metadata identification |
| Phase 3: RL Pipeline | Cold start: system too inaccurate for users to adopt | Pre-seed with supervised examples + start with easy domains |
| Phase 3: RL Pipeline | Reward hacking: system games the correction metric | Multi-dimensional reward + deterministic validation as primary signal |
| Phase 3: RELREC | Relationship mapping errors | Deterministic key-based detection, not LLM inference |

---

## Overarching Principle: LLM for Reasoning, Deterministic Code for Execution

The single most important architectural principle to avoid pitfalls in this project:

**The LLM decides WHAT to do. Deterministic code does the HOW.**

- LLM decides: "Raw variable WT_LBS maps to SDTM variable VSORRES in the VS domain"
- Deterministic code: performs the actual data transformation, applies CT lookups, converts dates, generates SUPPQUAL, writes XPT

Every pitfall above where the LLM is asked to EXECUTE (not just REASON) is a source of non-determinism, hallucination, and unreproducibility. The mapping specification is the contract between LLM reasoning and deterministic execution. Design the system around this boundary.

---

## Sources

- [Why Multi-Agent LLM Systems Fail (MAST Taxonomy, UC Berkeley 2025)](https://arxiv.org/html/2503.13657v1)
- [Augment Code: Why Multi-Agent LLM Systems Fail and How to Fix Them](https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them)
- [Context Rot: How Increasing Input Tokens Impacts LLM Performance (Chroma Research)](https://research.trychroma.com/context-rot)
- [Context Window Overflow Solutions (Redis)](https://redis.io/blog/context-window-overflow/)
- [10 Common Mistakes in SDTM Specification](https://www.oddee.com/10-common-mistakes-in-sdtm-specification-and-how-to-avoid-them-76259/)
- [SDTM Mapping Best Practices (Certara/Pinnacle 21)](https://www.certara.com/blog/the-sdtm-mapping-process-simplified/)
- [Efficient CDISC Controlled Terminology Mapping (PharmaSUG 2025)](https://pharmasug.org/proceedings/2025/DS/PharmaSUG-2025-DS-338.pdf)
- [FDA Validation Rules v1.6 (Certara)](https://www.certara.com/blog/new-fda-validator-rules-v1-6-explained/)
- [P21 Known Issues / False Positives](https://help.pinnacle21.certara.net/en/articles/9737202-known-issues-in-pmda-validation-engine-1810-3)
- [Reward Shaping to Mitigate Reward Hacking in RLHF](https://arxiv.org/html/2502.18770v3)
- [Gradient Regularization Prevents Reward Hacking in RLHF](https://arxiv.org/abs/2602.18037)
- [RLHF Deciphered: Critical Analysis (ACM Computing Surveys)](https://dl.acm.org/doi/10.1145/3743127)
- [ISO 8601 Date Conversion for SDTM (sdtm.oak R package docs)](https://cran.r-project.org/web/packages/sdtm.oak/vignettes/iso_8601.html)
- [Date Conversions in SDTM and ADaM (PharmaSUG)](https://www.lexjansen.com/nesug/nesug10/ph/ph11.pdf)
- [PDF Table Extraction Comparison (arxiv)](https://arxiv.org/html/2410.09871v1)
- [SDTM-IG v3.4 Official Standard](https://sastricks.com/cdisc/SDTMIG%20v3.4-FINAL_2022-07-21.pdf)
- [FDA Federal Register: SDTM v2.0 / SDTMIG v3.4 Requirement](https://www.federalregister.gov/documents/2023/12/13/2023-27310/data-standards-support-and-requirement-begins-for-the-clinical-data-interchange-standards-consortium)
- [CDISC Controlled Terminology FAQ](https://www.cdisc.org/kb/articles/controlled-terminology-faqs)
