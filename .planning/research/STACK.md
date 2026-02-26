# Technology Stack

**Project:** Astraea-SDTM
**Domain:** Agentic AI system for clinical trial data mapping (raw data to CDISC SDTM)
**Researched:** 2026-02-26
**Overall Confidence:** MEDIUM-HIGH

---

## Recommended Stack

### Core LLM & Orchestration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `anthropic` | latest (pip) | Claude API access | Project specifies Claude as the LLM. Direct SDK gives full control over prompts, tool use, structured output. | HIGH |
| `langgraph` | >=1.0.7 | Multi-agent orchestration | Graph-based workflow with stateful execution. Best fit for a pipeline of specialized agents (parser -> classifier -> mapper -> validator) because it gives precise control over execution order, branching, conditional routing, and error recovery. Supports human-in-the-loop natively. | HIGH |
| `langchain-anthropic` | latest | Claude integration for LangGraph | Official LangChain adapter for Claude models. Required to use Claude within LangGraph nodes. | HIGH |
| `pydantic` | >=2.10 | Data validation & structured output | Schema definitions for SDTM domains, agent state, mapping rules. Industry standard; used by LangGraph internally. | HIGH |

**Why LangGraph over alternatives:**

- **vs CrewAI:** CrewAI is role-based and opinionated about agent collaboration patterns. Astraea needs a strict pipeline (parse -> classify -> map -> validate -> review), not a "crew" brainstorming together. CrewAI's logging/debugging is notoriously painful. LangGraph gives you explicit graph control over the exact flow, including conditional edges (e.g., skip derivation for certain domains).
- **vs AutoGen:** AutoGen is conversation-oriented -- agents chat with each other. Astraea agents are pipeline stages, not conversational partners. AutoGen adds overhead for a use case that doesn't need multi-agent debate.
- **vs DSPy (as orchestrator):** DSPy is a prompt optimization framework, not an orchestration framework. It optimizes individual LLM calls but doesn't manage multi-step agent pipelines with state, branching, and human-in-the-loop. Use DSPy _within_ LangGraph nodes for prompt optimization (see Learning Loop below), not as a replacement.
- **vs Custom:** LangGraph is now at v1.0 (stable). Building custom orchestration means reimplementing state management, checkpointing, human-in-the-loop, and error recovery. Not worth it unless you have very unusual requirements.

### SAS File I/O

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `pyreadstat` | >=1.3.3 | Read .sas7bdat files, write .xpt files | Fastest Python SAS reader (C-based, wraps ReadStat). Handles dates correctly (dates as dates, not datetimes). Auto-detects encoding. Can write XPT v5 and v8 with variable labels via `write_xport()`. Maintained by Roche (a pharma company). | HIGH |
| `pandas` | >=2.2 | DataFrame operations | Core data manipulation. pyreadstat returns pandas DataFrames natively. All SDTM transformations happen on DataFrames. | HIGH |

**Why pyreadstat over alternatives:**

- **vs `sas7bdat` package:** Slow, poor date handling (converts dates to datetimes), requires manual encoding specification, cannot read .sas7bcat catalog files. Effectively deprecated in favor of pyreadstat.
- **vs `pandas.read_sas()`:** Under the hood, pandas uses its own SAS reader which is slower than pyreadstat and cannot extract metadata (variable labels, formats). pyreadstat preserves all SAS metadata which is critical for SDTM mapping.
- **vs `xport` package (for writing):** The `xport` library can write XPT files but has limitations: cannot assign variable labels easily, and is less actively maintained. pyreadstat's `write_xport()` supports both v5 and v8 with full column labels, making it a one-library solution for both read and write.

**IMPORTANT CAVEAT:** pyreadstat's own documentation warns it is "not a validated package" and "should not be used for critical tasks such as reporting to authorities." For final regulatory submissions, XPT output should be validated against the CDISC rules engine (see Validation section). The XPT files pyreadstat produces are structurally correct but must pass independent validation.

### PDF Parsing (eCRF Extraction)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `pymupdf4llm` | >=0.3.4 | Primary PDF-to-Markdown extraction | Converts PDF pages to GitHub-flavored Markdown with table detection. Extremely fast (0.12s typical). Designed specifically for LLM consumption. The eCRF is 189 pages of mixed tables/text -- this is the sweet spot. | HIGH |
| `PyMuPDF` | >=1.25 | Underlying PDF engine (installed with pymupdf4llm) | Powers pymupdf4llm. Also provides fallback for fine-grained layout operations if needed (bounding boxes, image extraction). | HIGH |
| `pdfplumber` | >=0.11 | Fallback for complex tables | If pymupdf4llm misses table structure in specific eCRF pages, pdfplumber excels at table-to-DataFrame extraction. Keep as secondary tool, not primary. | MEDIUM |

**Why this combination over alternatives:**

- **vs Unstructured.io:** Unstructured is heavier (1.29s vs 0.12s), designed for heterogeneous document pipelines. The eCRF is a single known document type. pymupdf4llm is faster and produces cleaner Markdown for LLM consumption.
- **vs LLM-based extraction only:** Sending 189 pages to Claude for extraction is expensive and slow. Extract text/tables with pymupdf4llm first, then use Claude to _interpret_ the extracted content (classify form types, identify variable mappings). This is the standard RAG-style approach.
- **vs OCR-based approaches:** The eCRF appears to be a digital PDF (not scanned), based on the text extraction in ECRF_text.txt. OCR is unnecessary overhead.

**Recommended approach:** Extract all 189 pages to Markdown with pymupdf4llm. Chunk by form/section. Store chunks in vector DB for retrieval during mapping. Use Claude to interpret specific chunks when the mapper agent needs eCRF context.

### CDISC Validation

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `cdisc-rules-engine` | latest (requires Python 3.12) | SDTM conformance validation | Official CDISC open-source validation engine (CORE). MIT licensed. Validates datasets against CDISC Library rules. This is the industry standard -- Pinnacle21 is the commercial equivalent. | HIGH |
| `cdisc-library-client` | latest | CDISC Library API access | Official Python client for accessing CDISC Library metadata (domain specifications, controlled terminology, variable definitions). Essential for looking up valid SDTM domains, required variables, codelists. | MEDIUM |

**CRITICAL NOTE on Python version:** The cdisc-rules-engine requires Python 3.12 specifically. Other Python versions "are not supported and may cause unexpected errors or incorrect validation results." This constrains the entire project to Python 3.12. Plan for this.

**Why not Pinnacle21:** Pinnacle21 is the commercial desktop tool most pharma companies use. It has no Python API. The CDISC rules engine (CORE) is the open-source equivalent maintained by CDISC itself. For an automated pipeline, CORE is the only viable option.

### Vector Database (Mapping Memory)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `chromadb` | >=1.5.1 | Store past mappings, corrections, eCRF chunks | Embedded (no server needed), simple Python API, supports metadata filtering, integrates with LangChain. Perfect for a CLI tool that runs locally. Stores mapping examples for few-shot retrieval and human corrections for the learning loop. | HIGH |

**Why ChromaDB over alternatives:**

- **vs FAISS:** FAISS is a similarity search _library_, not a database. No metadata storage, no persistence API, no query filtering. You'd have to build all that yourself. FAISS is 1000x faster for pure vector search, but Astraea needs metadata (domain, study, correction type) not just similarity.
- **vs Pinecone:** Cloud-hosted, requires API key and internet. Clinical trial data has regulatory sensitivity -- running vector search against an external cloud service adds compliance complexity. ChromaDB runs locally.
- **vs Qdrant/Milvus:** More powerful but heavier. Qdrant needs a separate server process. Overkill for a CLI tool processing one study at a time. ChromaDB embeds directly in the Python process.

**What to store in ChromaDB:**
1. eCRF page chunks (for RAG during mapping)
2. Successful mapping examples (variable X in source -> variable Y in SDTM domain Z)
3. Human corrections (original mapping, correction, rationale)
4. SDTM domain specifications (for retrieval during classification)

### Learning Loop (Agent Improvement)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `dspy` | >=3.1.3 | Prompt optimization from examples | DSPy's optimizers (MIPROv2, GEPA) can systematically improve prompts using collected examples of correct mappings. GEPA specifically supports textual feedback. | MEDIUM |
| `chromadb` (shared) | >=1.5.1 | Correction storage & retrieval | Store human corrections as retrievable examples. The mapper agent retrieves similar past corrections during inference (few-shot RAG). | HIGH |

**Recommended learning approach (pragmatic, not academic RLHF):**

The system does NOT need reinforcement learning or fine-tuning in the traditional ML sense. Here is what actually works for an agentic system improving from human feedback:

1. **Few-shot RAG from corrections (Phase 1 -- do this first):**
   - Human reviewer corrects a mapping
   - Store correction in ChromaDB: (source_variable, incorrect_mapping, correct_mapping, domain, rationale)
   - On future similar mappings, retrieve top-k similar corrections as few-shot examples in the prompt
   - This is simple, effective, and requires no ML training infrastructure
   - **Confidence: HIGH** -- this pattern is well-established

2. **DSPy prompt optimization (Phase 2 -- do this when you have 50+ corrections):**
   - Collect (input, correct_output) pairs from validated mappings
   - Use DSPy MIPROv2 or GEPA to optimize the mapper agent's prompt
   - GEPA can incorporate textual feedback (e.g., "always map RACE to DM domain, not SC")
   - Run periodically (not real-time) to update system prompts
   - **Confidence: MEDIUM** -- DSPy optimization is powerful but requires tuning

3. **Fine-tuning (Phase 3 -- probably never needed):**
   - Only consider if you have 1000+ validated mappings and the above approaches plateau
   - Claude does not currently support fine-tuning via API
   - Would require switching to an open-source model (Llama, Mistral) for the fine-tuned component
   - **Confidence: LOW** -- likely unnecessary; few-shot RAG + DSPy should suffice

**Why NOT traditional RLHF:**
- Requires massive labeled datasets (thousands of preference pairs)
- Requires training infrastructure (GPUs, training loops)
- Claude API does not support RLHF
- Few-shot RAG achieves 80% of the benefit with 1% of the complexity

### CLI Interface

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `typer` | >=0.15 | CLI framework | Built on Click but uses Python type hints for auto-completion and validation. Less boilerplate than Click. Automatic help generation. Supports nested subcommands (e.g., `astraea map`, `astraea validate`, `astraea review`). | HIGH |
| `rich` | >=13.9 | Terminal output formatting | Tables, progress bars, colored output, panels. Essential for displaying mapping results, validation reports, and review interfaces in the terminal. Typer uses Rich internally. | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| `python-dotenv` | >=1.0 | Environment variable management | Store ANTHROPIC_API_KEY, CDISC_API_KEY securely | HIGH |
| `loguru` | >=0.7 | Structured logging | Debug agent pipeline execution, trace mapping decisions | HIGH |
| `pytest` | >=8.0 | Testing framework | Unit tests for mapping rules, integration tests for pipeline | HIGH |
| `pytest-asyncio` | >=0.24 | Async test support | LangGraph runs async; need async test fixtures | HIGH |
| `numpy` | >=1.26 | Numerical operations | Date calculations, statistical derivations in SDTM | HIGH |
| `tenacity` | >=9.0 | Retry logic | Claude API rate limiting, transient failures | MEDIUM |

---

## Alternatives Considered (Full Decision Log)

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| Agent Framework | LangGraph | CrewAI | Role-based, not pipeline-oriented. Poor debugging. |
| Agent Framework | LangGraph | AutoGen | Conversation-oriented, adds overhead for pipeline use case. |
| Agent Framework | LangGraph | DSPy (as orchestrator) | Prompt optimizer, not orchestrator. Use within LangGraph. |
| Agent Framework | LangGraph | Custom | Reimplements solved problems (state, checkpointing, HITL). |
| SAS Reader | pyreadstat | sas7bdat | Slow, bad date handling, effectively deprecated. |
| SAS Reader | pyreadstat | pandas.read_sas() | No metadata extraction (labels, formats). Slower. |
| XPT Writer | pyreadstat | xport | Less metadata support, less actively maintained. |
| PDF Parser | pymupdf4llm | Unstructured.io | Heavier, slower, designed for heterogeneous docs. |
| PDF Parser | pymupdf4llm | Pure LLM extraction | Expensive at 189 pages. Extract first, interpret second. |
| Vector DB | ChromaDB | FAISS | Library not database. No metadata, no persistence API. |
| Vector DB | ChromaDB | Pinecone | Cloud-hosted. Compliance risk with clinical data. |
| Vector DB | ChromaDB | Qdrant | Needs separate server. Overkill for single-study CLI tool. |
| Learning | Few-shot RAG + DSPy | RLHF | Needs massive data, training infra. Claude has no RLHF API. |
| Learning | Few-shot RAG + DSPy | Fine-tuning | Claude has no fine-tuning API. Premature optimization. |
| CLI | Typer | Click | More boilerplate. Typer wraps Click with type hints. |
| CLI | Typer | argparse | No auto-completion, no rich output, verbose. |

---

## Python Version Constraint

**Use Python 3.12 exactly.**

Rationale:
- `cdisc-rules-engine` requires Python 3.12 specifically (other versions cause incorrect validation)
- All other recommended libraries support Python 3.12
- LangGraph requires Python >=3.9
- This is a hard constraint driven by the validation engine

---

## Installation

```bash
# Create virtual environment with Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate

# Core LLM & Orchestration
pip install anthropic langgraph langchain-anthropic pydantic

# SAS File I/O
pip install pyreadstat pandas numpy

# PDF Parsing
pip install pymupdf4llm pdfplumber

# CDISC Validation
pip install cdisc-rules-engine cdisc-library-client

# Vector Database
pip install chromadb

# Learning Loop
pip install dspy

# CLI
pip install typer rich

# Supporting
pip install python-dotenv loguru tenacity

# Dev Dependencies
pip install pytest pytest-asyncio ruff mypy
```

---

## Architecture Implications

The stack choices imply this architecture:

```
CLI (Typer) -> LangGraph Pipeline -> Agent Nodes (Claude via anthropic SDK)
                                        |
                                   ChromaDB (RAG)
                                        |
                              pyreadstat (I/O) + pymupdf4llm (PDF)
                                        |
                              cdisc-rules-engine (validation)
```

Each LangGraph node is a specialized agent:
1. **Parser Agent** -- reads .sas7bdat via pyreadstat, extracts metadata
2. **eCRF Agent** -- parses PDF via pymupdf4llm, indexes in ChromaDB
3. **Domain Classifier** -- classifies source data to SDTM domains using Claude
4. **Mapper Agent** -- maps source variables to SDTM variables using Claude + ChromaDB RAG
5. **Derivation Engine** -- computes derived variables (STUDYDAY, AGE, etc.)
6. **Validator Agent** -- runs cdisc-rules-engine on output
7. **Human Review Gate** -- presents results via Rich, collects corrections
8. **Dataset Generator** -- writes .xpt files via pyreadstat

LangGraph manages the state passed between nodes and handles conditional routing (e.g., if validation fails, route back to mapper with error context).

---

## Sources

### Agent Frameworks
- [LangGraph PyPI](https://pypi.org/project/langgraph/) -- v1.0.7, Jan 2026
- [LangGraph vs AutoGen vs CrewAI (Latenode)](https://latenode.com/blog/platform-comparisons-alternatives/automation-platform-comparisons/langgraph-vs-autogen-vs-crewai-complete-ai-agent-framework-comparison-architecture-analysis-2025)
- [AI Agent Frameworks Compared (OpenAgents)](https://openagents.org/blog/posts/2026-02-23-open-source-ai-agent-frameworks-compared)
- [DataCamp Framework Comparison](https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen)
- [LangGraph v1 Changelog](https://docs.langchain.com/oss/python/releases/langgraph-v1)

### SAS/XPT I/O
- [pyreadstat GitHub (Roche)](https://github.com/Roche/pyreadstat) -- v1.3.3, Jan 2026
- [pyreadstat PyPI](https://pypi.org/project/pyreadstat/)
- [pyreadstat Documentation](https://ofajardo.github.io/pyreadstat_documentation/_build/html/index.html)
- [xport PyPI](https://pypi.org/project/xport/)

### PDF Parsing
- [pymupdf4llm PyPI](https://pypi.org/project/pymupdf4llm/) -- v0.3.4, Feb 2026
- [PDF Extractor Comparison (2025)](https://onlyoneaman.medium.com/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-c88013922257)
- [Python PDF Libraries Evaluation (2026)](https://unstract.com/blog/evaluating-python-pdf-to-text-libraries/)

### CDISC Validation
- [cdisc-rules-engine GitHub](https://github.com/cdisc-org/cdisc-rules-engine)
- [cdisc-rules-engine PyPI](https://pypi.org/project/cdisc-rules-engine/)
- [CDISC Library Client GitHub](https://github.com/cdisc-org/cdisc-library-client)
- [PharmaSUG 2025 CORE Paper](https://pharmasug.org/proceedings/2025/SD/PharmaSUG-2025-SD-044.pdf)

### Vector Database
- [ChromaDB PyPI](https://pypi.org/project/chromadb/) -- v1.5.1, Feb 2026
- [ChromaDB vs FAISS vs Pinecone (RisingWave)](https://risingwave.com/blog/chroma-db-vs-pinecone-vs-faiss-vector-database-showdown/)
- [Vector DB Comparison (LiquidMetal)](https://liquidmetal.ai/casesAndBlogs/vector-comparison/)

### Learning Loop
- [DSPy PyPI](https://pypi.org/project/dspy/) -- v3.1.3, Feb 2026
- [DSPy Optimizers Documentation](https://dspy.ai/learn/optimization/optimizers/)
- [GEPA Optimizer](https://dspy.ai/api/optimizers/GEPA/overview/)
- [Self-improving Agents with DSPy (Relevance AI)](https://relevanceai.com/blog/building-self-improving-agentic-systems-in-production-with-dspy)

### CLI
- [Typer Documentation](https://typer.tiangolo.com/)
- [Click vs Typer Comparison](https://oneuptime.com/blog/post/2025-07-02-python-cli-click-typer/view)

### Claude SDK
- [anthropic-sdk-python GitHub](https://github.com/anthropics/anthropic-sdk-python)
- [Anthropic Client SDKs](https://docs.claude.com/en/api/client-sdks)
- [LangChain Anthropic Integration](https://docs.langchain.com/oss/python/integrations/chat/anthropic)
