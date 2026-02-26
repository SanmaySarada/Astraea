# Project Research Summary

**Project:** Astraea-SDTM
**Domain:** Agentic AI system for clinical trial data mapping (raw data to CDISC SDTM)
**Researched:** 2026-02-26
**Confidence:** MEDIUM-HIGH

## Executive Summary

Astraea-SDTM is an agentic AI pipeline that automates SDTM (Study Data Tabulation Model) mapping -- the process of transforming raw clinical trial data into FDA-mandated standardized datasets. Expert practitioners build this as a multi-stage pipeline: parse source data and eCRF documents, classify datasets to SDTM domains, propose variable-level mappings, validate against CDISC conformance rules, submit to human review, and generate XPT files for regulatory submission. The recommended approach uses LangGraph as the orchestration backbone with Claude as the reasoning engine, enforcing a strict architectural boundary: the LLM decides WHAT to map, deterministic Python code executes HOW.

The stack is well-defined and high-confidence: LangGraph for multi-agent orchestration, Claude via Anthropic SDK for reasoning, pyreadstat for SAS/XPT I/O, pymupdf4llm for eCRF PDF parsing, and the CDISC Rules Engine for validation. Python 3.12 is a hard constraint driven by the CDISC validation engine. The learning system uses a pragmatic three-tier approach: few-shot RAG from stored corrections (Phase 1), DSPy prompt optimization (Phase 2), with fine-tuning deferred indefinitely. ChromaDB is replaced by SQLite for structured mapping examples, with ChromaDB reserved for eCRF chunk retrieval only.

The top risks are hallucination cascading across the agent pipeline (a wrong domain classification poisons all downstream mapping), controlled terminology misapplication (wrong CT version or non-extensible codelist violations cause FDA rejection), and non-deterministic LLM output (unacceptable in a regulated environment). All three are mitigated by the core architectural principle: LLM proposes a mapping specification, human reviews it, and deterministic code executes it. The cold-start problem for the learning loop is real -- start with easy domains (DM, AE) where accuracy will be highest to build user trust before tackling hard domains (LB, VS transposes).

## Key Findings

### Recommended Stack

The stack converges on a Python 3.12 environment with well-established libraries. Every major choice has a clear rationale and HIGH confidence. See `.planning/research/STACK.md` for full decision log.

**Core technologies:**
- **LangGraph** (>=1.0.7): Multi-agent orchestration -- graph-based pipeline with built-in state management, checkpointing, and human-in-the-loop interrupts. Chosen over CrewAI (role-based, not pipeline-oriented), AutoGen (conversation-oriented, wrong paradigm), and custom orchestration (reimplements solved problems).
- **Claude API** (anthropic SDK): LLM reasoning for classification, mapping proposals, eCRF interpretation. Used via langchain-anthropic within LangGraph nodes.
- **pyreadstat** (>=1.3.3): Read .sas7bdat, write .xpt. Maintained by Roche (pharma company). Handles SAS metadata (labels, formats) which is critical for mapping. One library for both read and write.
- **pymupdf4llm** (>=0.3.4): PDF-to-Markdown extraction for the 189-page eCRF. 10x faster than Unstructured.io, produces LLM-ready Markdown with table detection.
- **cdisc-rules-engine**: Official CDISC open-source validator (CORE). The only viable option for automated validation -- Pinnacle 21 has no Python API.
- **Pydantic** (>=2.10): Data models for all agent interfaces, SDTM domain specs, mapping specifications. Enforces typed contracts between pipeline stages.
- **Typer + Rich**: CLI framework with formatted terminal output for mapping review interface.

**Critical version constraint:** Python 3.12 exactly, driven by cdisc-rules-engine requirements. This is non-negotiable.

### Expected Features

The feature landscape is well-mapped with clear dependency chains. See `.planning/research/FEATURES.md` for the full 12 table-stakes and 10 differentiator breakdown.

**Must have (table stakes):**
- All 9 mapping transformation types (direct copy, rename, reformat, split, combine, derivation, lookup/recode, transpose, variable attribute mapping)
- Core SDTM domain coverage (DM, AE, CM, EX, LB, VS, MH, DS at minimum)
- CDISC Controlled Terminology application with version pinning
- Mapping specification output (Excel workbook, industry-standard format)
- XPT file output, USUBJID generation, ISO 8601 date handling
- Traceability (source-to-target lineage for every variable)

**Should have (differentiators -- these are the reason to build Astraea):**
- Automated eCRF PDF parsing (eliminates 2-4 weeks of manual annotation)
- Learning from human corrections (no competitor does this)
- Confidence scoring per mapping (guides reviewer attention)
- Intelligent domain assignment via LLM
- Multi-source merge intelligence (e.g., 5 lab datasets into single LB domain)
- Explain-the-mapping natural language descriptions

**Defer (v2+):**
- ADaM dataset generation (different product entirely)
- MedDRA/WHODrug coding (accept pre-coded data)
- SaaS platform / web UI (prove engine as CLI first)
- Visual drag-and-drop mapping UI (anti-feature)
- Protocol PDF parsing (too variable, start with eCRF only)

### Architecture Approach

The architecture follows a LangGraph StateGraph with 7 components connected by a shared typed state object. The core principle is separation of proposal and execution: LLM agents produce mapping specifications (reviewable artifacts), deterministic code executes transformations. Context management uses tool-based structured lookups (not vector RAG) for SDTM-IG specs and CT codelists, since these are structured reference data, not unstructured knowledge. Human review uses LangGraph's native interrupt mechanism with CLI resume from checkpoints. See `.planning/research/ARCHITECTURE.md` for full component specs and data models.

**Major components:**
1. **Parser Agent** -- extracts structured metadata from eCRF PDF (LLM) and SAS files (deterministic). Run once per study, cached.
2. **Domain Classifier Agent** -- classifies raw datasets to SDTM domains. Many-to-many mapping (multiple sources can merge into one domain).
3. **Mapper Agent** -- proposes variable-level mappings per domain. Core LLM reasoning task. Outputs structured DomainMappingSpec.
4. **Derivation Agent** -- handles complex transformations (transposes, date conversions, calculated fields). Hybrid: deterministic rules for known patterns, LLM for novel derivations.
5. **Validator** -- deterministic P21-style conformance rules. NOT an LLM agent. Runs twice: once on specs, once on generated data.
6. **Human Review Gate** -- LangGraph interrupt. CLI presents mapping spec table, captures approvals/corrections. Corrections stored for learning.
7. **Dataset Generator** -- executes approved specs via pandas, writes .xpt files via pyreadstat. Pure data engineering, no LLM.

### Critical Pitfalls

The top 5 pitfalls that must inform architecture and phase planning. See `.planning/research/PITFALLS.md` for full analysis with detection strategies.

1. **Hallucination cascading across agents** -- A wrong domain classification from the classifier poisons every downstream agent. Mitigate with independent verification at each stage, deterministic sanity checks (e.g., does dataset have AETERM? Then it maps to AE), and confidence-gated human review.
2. **Controlled terminology misapplication** -- Wrong CT version or fuzzy-matching non-extensible codelists causes FDA technical rejection. Mitigate by making CT lookup deterministic (exact match against bundled codelist JSON, never LLM "best guess"), and locking SDTM-IG + CT versions together in a manifest.
3. **Non-deterministic LLM output** -- Same input producing different mappings across runs is a regulatory compliance disaster. Mitigate with the mapping-spec-then-generate architecture: LLM proposes once, spec is saved deterministically, all downstream processing is reproducible.
4. **Context window overflow** -- Complex domains (LB with dozens of tests and codelists) overflow context and cause "lost in the middle" degradation. Mitigate by processing one domain at a time, chunking variables into groups of 10-20 per LLM call, and using tool-based reference lookup instead of stuffing everything in context.
5. **ISO 8601 date conversion edge cases** -- Partial dates, SAS numeric dates, ambiguous formats (DD/MM vs MM/DD) are pervasive in clinical data. Mitigate by building date conversion as a deterministic utility with exhaustive unit tests, never as an LLM task.

## Implications for Roadmap

Based on combined research findings, the project naturally decomposes into 5 phases with clear dependency ordering.

### Phase 1: Foundation and Data Infrastructure
**Rationale:** Everything depends on being able to read data, access SDTM reference standards, and define the typed contracts between components. The data models ARE the architecture -- they must be right before any agent is built.
**Delivers:** SAS I/O layer, SDTM-IG + CT reference data loader (bundled JSON), version manifest, all Pydantic data models (ECRFForm, RawDatasetProfile, DomainMappingSpec, VariableMapping, ValidationIssue, HumanCorrection), deterministic date conversion utility, deterministic CT lookup module, project scaffolding (Typer CLI skeleton, logging, config).
**Addresses:** T9 (data ingestion), T7 (CDISC metadata), T12 (ISO 8601 dates), T3 (controlled terminology infrastructure)
**Avoids:** C3 (version mismatch -- manifest enforced from day one), M2 (date edge cases -- deterministic utility built first), m5 (prompt drift -- typed interfaces defined before agents exist)

### Phase 2: Core Agent Pipeline (Single Domain)
**Rationale:** Prove the multi-agent pattern works end-to-end on the simplest domain (DM -- Demographics) before scaling. DM is mostly direct carries and renames, minimal derivations. This phase validates the LangGraph orchestration, the LLM-proposes/code-executes boundary, and the human review interface.
**Delivers:** Parser Agent (eCRF + SAS profiling), Domain Classifier Agent, Mapper Agent (DM domain only), basic Validator (required variables, types, CT values), LangGraph StateGraph wiring, Human Review Gate (CLI interface with Rich tables), correction capture to SQLite.
**Addresses:** T1 (mapping types -- direct, rename, reformat, combine for USUBJID), T11 (USUBJID generation), D1 (eCRF parsing), D3 (domain assignment), D8 (confidence scoring)
**Avoids:** C1 (hallucination cascading -- independent verification built in), C5 (non-determinism -- mapping spec layer from day one), C6 (context overflow -- domain-scoped processing), M1 (coordination loops -- retry budgets and circuit breakers), M3 (eCRF parsing failures -- fallback to manual JSON input)

### Phase 3: Multi-Domain Expansion and Validation
**Rationale:** Extend the proven pipeline to all core SDTM domains, including the hard ones (Findings class domains requiring transpose). This is the largest phase and the one that delivers the core product value. P21-aligned validation becomes critical here.
**Delivers:** Mapper Agent extended to AE, CM, EX, LB, VS, MH, DS, EG, PE, IE, CE, DV domains. Derivation Agent for transposes (LB, VS, EG), date derivations, study day calculations. Full deterministic validator aligned with P21 rules. SUPPQUAL generation engine. XPT file output. Mapping specification Excel export.
**Addresses:** T2 (domain coverage), T1 (all 9 transformation types including transpose), T4 (mapping spec output), T6 (P21 validation), T8 (XPT output), T10 (traceability), D9 (multi-source merge for lab data), D6 (SUPPQUAL decision-making), D10 (explain-the-mapping)
**Avoids:** C2 (CT misapplication -- deterministic lookup enforced), C4 (SUPPQUAL integrity -- deterministic generation), M4 (transpose errors -- deterministic pandas code, LLM only identifies metadata), M7 (P21 version drift -- version-locked rules)

### Phase 4: Validation, Compliance, and Submission Readiness
**Rationale:** After core mapping works, add the regulatory submission artifacts. define.xml and full traceability documentation are required for FDA submission but do not affect the mapping engine itself.
**Delivers:** define.xml generation (v2.0+), full traceability documentation, pre-submission validation report (D7), CDISC Rules Engine integration for independent validation, Reviewer's Guide template generation.
**Addresses:** T5 (define.xml), D7 (pre-submission validation report)
**Avoids:** m4 (define.xml errors -- generate from final dataset metadata, never manually)

### Phase 5: Learning System and Cross-Study Intelligence
**Rationale:** Learning requires data. You need at least one complete study mapping before the learning loop has training signal. By this phase, the SQLite correction database from Phase 2-3 has real data to work with.
**Delivers:** Few-shot RAG from correction database (query similar past mappings as prompt examples), DSPy prompt optimization (when 50+ corrections accumulated), cross-study template library, accuracy tracking dashboard.
**Addresses:** D2 (learning from corrections), D5 (cross-study learning), D4 (natural language derivation descriptions)
**Avoids:** M5 (reward hacking -- multi-dimensional reward with deterministic validation as primary signal), M6 (cold start -- pre-seeded with Phase 2-3 corrections, easy domains proven first)

### Phase Ordering Rationale

- **Phase 1 before Phase 2:** You cannot build agents without typed interfaces and reference data. The data models are the contract between all components.
- **Phase 2 is single-domain (DM):** DM is the simplest domain (mostly direct carries). Proving the full pipeline end-to-end on one domain catches architectural issues before investing in 15+ domain implementations.
- **Phase 3 is the bulk of the work:** Domain expansion is parallelizable once the pattern is proven. Transpose logic (LB, VS) is the hardest technical challenge in the entire project.
- **Phase 4 after Phase 3:** define.xml must reflect final dataset metadata. Building it before datasets stabilize wastes effort.
- **Phase 5 last:** Learning is premature optimization without data. The correction database accumulates naturally during Phases 2-4.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (eCRF Parsing):** The actual ECRF.pdf may have parsing-resistant table structures. Need to prototype pymupdf4llm extraction on the real document and assess quality before committing to a parsing strategy. Consider Claude vision as fallback.
- **Phase 3 (Transpose Logic):** Lab data transpose is the hardest transformation. Need to examine the actual Fakedata lab files (lb_biochem, lb_coagulation, lb_hem, lb_urin) to understand their structure before designing the transpose template.
- **Phase 3 (SUPPQUAL):** SUPPQUAL decision logic (main domain vs SUPPQUAL vs FA vs custom domain) has nuanced rules. Need to review CDISC guidance and real-world examples during planning.
- **Phase 4 (define.xml):** define.xml v2.0 has a complex XML schema. Need to evaluate existing Python libraries or confirm building from mapping spec metadata is feasible.
- **Phase 5 (DSPy Integration):** DSPy optimization with Claude requires testing. GEPA optimizer for textual feedback is newer and less battle-tested.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** SAS I/O via pyreadstat, Pydantic models, Typer CLI, JSON reference data loading -- all well-documented, established patterns.
- **Phase 2 (LangGraph Pipeline):** LangGraph StateGraph with HITL interrupts is well-documented with production examples. Standard multi-agent orchestration pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All libraries are mature, well-documented, and verified against multiple sources. Python 3.12 constraint is confirmed. LangGraph v1.0 is production-ready. |
| Features | MEDIUM-HIGH | Table stakes are authoritative (CDISC standards, FDA requirements). Competitive landscape based on vendor marketing -- actual capabilities may differ. The 9 mapping scenarios are well-established in the domain. |
| Architecture | HIGH | LangGraph StateGraph is the consensus pattern for deterministic multi-step agent pipelines. Component boundaries map naturally to the SDTM mapping workflow. Tool-based lookup over RAG for structured reference data is well-supported. |
| Pitfalls | HIGH | SDTM/clinical pitfalls backed by regulatory guidance and industry experience. Multi-agent failure modes backed by 2025 academic research (MAST taxonomy). RL pitfalls backed by RLHF literature. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **eCRF PDF parsing quality:** The actual ECRF.pdf has not been tested with pymupdf4llm. The ECRF_text.txt suggests semi-garbled extraction. Prototype early in Phase 2 and have a fallback plan (manual JSON input, Claude vision).
- **CDISC Library API access:** The cdisc-library-client requires an API key. Need to confirm API availability and rate limits. Fallback: bundle SDTM-IG metadata as static JSON files.
- **CDISC Rules Engine compatibility:** Requires Python 3.12 specifically. Need to verify all other dependencies (especially LangGraph, DSPy, ChromaDB) work with Python 3.12. Test early.
- **Token cost estimation:** No concrete cost modeling done. A study with 36 datasets and 15+ domains could involve hundreds of LLM calls. Need to profile token usage in Phase 2 and set budgets.
- **Real P21 validation comparison:** Internal validator must be tested against actual Pinnacle 21 output. Without this comparison, validation confidence is theoretical. Plan for this in Phase 3.
- **Multi-study generalization:** All research assumes single-study processing. Cross-study learning (Phase 5) needs validation that mapping patterns actually transfer between studies in different therapeutic areas.

## Sources

### Primary (HIGH confidence)
- [CDISC Controlled Terminology](https://www.cdisc.org/standards/terminology/controlled-terminology)
- [SDTM-IG v3.4 Official Standard](https://sastricks.com/cdisc/SDTMIG%20v3.4-FINAL_2022-07-21.pdf)
- [FDA Study Data Technical Conformance Guide](https://www.fda.gov/media/122913/download)
- [cdisc-rules-engine GitHub](https://github.com/cdisc-org/cdisc-rules-engine)
- [LangGraph Official Documentation](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [pyreadstat GitHub (Roche)](https://github.com/Roche/pyreadstat)
- [DSPy Optimizers Documentation](https://dspy.ai/learn/optimization/optimizers/)
- [Pinnacle 21 SDTM Validation Rules](https://standards.pinnacle21.certara.net/validation-rules/sdtm)

### Secondary (MEDIUM confidence)
- [Why Multi-Agent LLM Systems Fail (MAST Taxonomy, UC Berkeley 2025)](https://arxiv.org/html/2503.13657v1)
- [Context Rot: How Increasing Input Tokens Impacts LLM Performance (Chroma Research)](https://research.trychroma.com/context-rot)
- [LangGraph vs AutoGen vs CrewAI Comparison (Latenode)](https://latenode.com/blog/platform-comparisons-alternatives/automation-platform-comparisons/langgraph-vs-autogen-vs-crewai-complete-ai-agent-framework-comparison-architecture-analysis-2025)
- [Efficient CDISC CT Mapping (PharmaSUG 2025)](https://pharmasug.org/proceedings/2025/DS/PharmaSUG-2025-DS-338.pdf)
- [Automating SDTM Programming with GenAI (PharmaSUG China 2025)](https://www.lexjansen.com/pharmasug-cn/2025/AI/Pharmasug-China-2025-AI144.pdf)
- [Pinnacle 21 + Formedix Platform Documentation](https://www.certara.com/pinnacle-21-enterprise-software/sdtm-specification-management/)

### Tertiary (LOW confidence)
- [AI + HITL for SDTM (Applied Clinical Trials)](https://www.appliedclinicaltrialsonline.com/view/the-future-of-sdtm-transformation-ai-and-hitl) -- 403 error, could not access
- [ML Approach to SDTM Spec Automation (PHUSE 2025)](https://www.lexjansen.com/phuse-us/2025/ml/PAP_ML20.pdf) -- PDF could not be parsed
- Claims about "35-45 hours manual vs <10 hours AI-assisted" -- single source, unverified

---
*Research completed: 2026-02-26*
*Ready for roadmap: yes*
