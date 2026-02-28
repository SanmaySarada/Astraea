# Phase 8: Learning System - Research

**Researched:** 2026-02-27
**Domain:** Few-shot RAG from corrections, DSPy prompt optimization, cross-study template library
**Confidence:** HIGH

## Summary

The learning system builds on the existing review infrastructure (Phase 4's `HumanCorrection` model, `SessionStore` with SQLite, and `ReviewSession` persistence) to create a feedback loop where human corrections improve future mapping proposals. The system has three tiers: (1) a correction/example database with ChromaDB vector search for few-shot retrieval, (2) DSPy `BootstrapFewShot` optimization when sufficient examples accumulate, and (3) a cross-study template library for reusing approved mapping patterns.

The existing codebase already captures structured corrections with `HumanCorrection` (session_id, domain, sdtm_variable, correction_type, original_mapping, corrected_mapping, reason, reviewer, timestamp) stored in SQLite. The learning system extends this by: (a) indexing corrections and approved mappings into ChromaDB for semantic retrieval, (b) injecting retrieved examples into the `MappingContextBuilder.build_prompt()` pipeline, and (c) periodically optimizing prompts via DSPy when 50+ examples exist per domain.

**Primary recommendation:** Build Tier 1 (ChromaDB few-shot RAG) first -- it delivers immediate value with minimal complexity. Use ChromaDB's default embedding model (all-MiniLM-L6-v2 via ONNX runtime, no GPU needed). Structure ChromaDB collections by purpose (corrections, approved_mappings, templates) with rich metadata filtering by domain, mapping_pattern, and correction_type. Inject up to 5 retrieved examples into the system prompt section of the mapping context.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `chromadb` | >=1.5.1 | Vector storage for mapping examples and corrections | Embedded (no server), persistent local storage, metadata filtering, default embedding model included. Already decided in STACK.md. |
| `dspy` | >=3.1.3 | Prompt optimization from accumulated examples | BootstrapFewShot optimizer works with Claude via `dspy.LM('anthropic/...')`. Automates few-shot example selection. Already decided in STACK.md. |
| `sqlite3` | stdlib | Structured storage for mapping examples, study metrics | Already used by SessionStore. Extend existing schema. Zero new dependencies. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `onnxruntime` | (transitive via chromadb) | Runs all-MiniLM-L6-v2 embedding model locally | Installed automatically with chromadb. No separate install needed. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ChromaDB default embeddings | OpenAI/Anthropic embeddings | Better quality but requires API calls, adds cost, adds latency. For mapping metadata (short structured text), MiniLM-L6-v2 is sufficient. |
| DSPy BootstrapFewShot | Manual few-shot selection | Simpler but doesn't optimize which examples work best. DSPy adds real value when you have 50+ examples. |
| SQLite + ChromaDB | PostgreSQL | Overkill for single-user CLI tool. SQLite is the right choice for v1. |

**Installation:**

```bash
pip install chromadb dspy
```

Note: `chromadb` pulls in `onnxruntime` and the default embedding model automatically. No separate model download needed.

## Architecture Patterns

### Recommended Project Structure

```
src/astraea/
  learning/
    __init__.py
    models.py              # MappingExample, StudyMetrics, TemplateEntry Pydantic models
    example_store.py        # SQLite storage for structured example data
    vector_store.py         # ChromaDB wrapper for similarity search
    retriever.py            # Retrieves relevant examples for a mapping context
    metrics.py              # Accuracy tracking and improvement measurement
    template_library.py     # Cross-study template management
    dspy_optimizer.py       # DSPy integration for prompt optimization
```

### Pattern 1: Correction Ingestion Pipeline

**What:** After a review session completes, extract approved mappings and corrections into the learning database.
**When:** Called after `DomainReviewer` completes a domain review and `ReviewSession` is saved.

```python
# After review completes for a domain
from astraea.learning.example_store import ExampleStore
from astraea.learning.vector_store import LearningVectorStore
from astraea.review.models import DomainReview, HumanCorrection

def ingest_review_results(
    domain_review: DomainReview,
    study_id: str,
    example_store: ExampleStore,
    vector_store: LearningVectorStore,
) -> int:
    """Ingest approved mappings and corrections into learning stores."""
    count = 0

    # 1. Store all approved mappings as positive examples
    reviewed_spec = domain_review.reviewed_spec
    for mapping in reviewed_spec.variable_mappings:
        example = MappingExample(
            study_id=study_id,
            domain=reviewed_spec.domain,
            sdtm_variable=mapping.sdtm_variable,
            mapping_pattern=mapping.mapping_pattern,
            mapping_logic=mapping.mapping_logic,
            source_variable=mapping.source_variable,
            source_dataset=mapping.source_dataset,
            confidence=mapping.confidence,
            was_corrected=mapping.sdtm_variable in domain_review.decisions
                and domain_review.decisions[mapping.sdtm_variable].status == "corrected",
            final_mapping_json=mapping.model_dump_json(),
        )
        example_store.save_example(example)
        vector_store.add_example(example)
        count += 1

    # 2. Store corrections with original -> corrected pairs
    for correction in domain_review.corrections:
        example_store.save_correction(correction)
        vector_store.add_correction(correction)

    return count
```

### Pattern 2: Few-Shot Retrieval During Mapping

**What:** When the MappingEngine is about to map a domain, retrieve relevant past examples and inject them into the prompt.
**When:** Inside `MappingContextBuilder.build_prompt()` or as an additional section appended by `MappingEngine.map_domain()`.

```python
# Integration point in MappingEngine.map_domain()
def map_domain(self, domain, source_profiles, ...):
    # ... existing steps 1-3 ...

    # NEW: Retrieve relevant examples
    if self._learning_retriever is not None:
        examples_section = self._learning_retriever.get_examples_section(
            domain=domain,
            source_profiles=source_profiles,
            max_examples=5,
        )
        full_prompt = prompt + "\n" + examples_section + "\n" + user_instructions
    else:
        full_prompt = prompt + "\n" + user_instructions

    # ... existing steps 4+ ...
```

### Pattern 3: Text Representation for Embedding

**What:** Convert mapping examples to text strings that capture semantic meaning for vector search.
**When:** When adding to ChromaDB and when constructing query text.

```python
def mapping_to_embedding_text(
    domain: str,
    sdtm_variable: str,
    mapping_pattern: str,
    mapping_logic: str,
    source_variable: str | None = None,
    source_label: str | None = None,
) -> str:
    """Create text representation for ChromaDB embedding.

    Combines domain context with mapping semantics into a
    searchable text string. Structured to capture:
    - What SDTM variable is being mapped
    - What pattern is used
    - What the source looks like
    - What the mapping logic is
    """
    parts = [
        f"SDTM domain {domain} variable {sdtm_variable}",
        f"mapping pattern: {mapping_pattern}",
        f"logic: {mapping_logic}",
    ]
    if source_variable:
        parts.append(f"source variable: {source_variable}")
    if source_label:
        parts.append(f"source label: {source_label}")
    return ". ".join(parts)
```

### Pattern 4: ChromaDB Collection Structure

**What:** Organize ChromaDB into collections with metadata for efficient filtered retrieval.
**When:** At learning system initialization.

```python
import chromadb

client = chromadb.PersistentClient(path=".astraea/learning/chroma_db")

# Collection 1: Approved mapping examples
approved_mappings = client.get_or_create_collection(
    name="approved_mappings",
    metadata={"description": "Approved variable mappings from completed reviews"},
)

# Collection 2: Human corrections (higher signal)
corrections = client.get_or_create_collection(
    name="corrections",
    metadata={"description": "Human corrections with original and corrected mapping"},
)

# Collection 3: Cross-study templates
templates = client.get_or_create_collection(
    name="templates",
    metadata={"description": "Domain-level mapping templates from completed studies"},
)
```

**Metadata schema per document:**

```python
# For approved_mappings collection
metadata = {
    "study_id": "PHA022121-C301",
    "domain": "AE",
    "sdtm_variable": "AEDECOD",
    "mapping_pattern": "derivation",
    "source_variable": "AETERM",
    "was_corrected": False,  # bool stored as str in ChromaDB
    "confidence": 0.92,
}

# For corrections collection
metadata = {
    "study_id": "PHA022121-C301",
    "domain": "AE",
    "sdtm_variable": "AEDECOD",
    "correction_type": "logic_change",
    "original_pattern": "direct",
    "corrected_pattern": "derivation",
}
```

### Pattern 5: Accuracy Metrics Tracking

**What:** Track mapping accuracy per domain, per study, over time.
**When:** After each review session completes.

```python
# SQLite table for study-level metrics
"""
CREATE TABLE study_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    total_mappings INTEGER NOT NULL,
    approved_unchanged INTEGER NOT NULL,
    corrected INTEGER NOT NULL,
    rejected INTEGER NOT NULL,
    added INTEGER NOT NULL,
    accuracy_rate REAL NOT NULL,  -- approved_unchanged / total_mappings
    completed_at TEXT NOT NULL,
    UNIQUE(study_id, domain)
);
"""

# Accuracy = approved_unchanged / total_proposed
# Track per domain and aggregate across studies
```

### Anti-Patterns to Avoid

- **Embedding full JSON mappings:** ChromaDB embedding text should be natural language descriptions of mappings, not raw JSON. MiniLM-L6-v2 is trained on natural language, not JSON.
- **Retrieving too many examples:** More than 5-7 few-shot examples in the prompt causes context dilution. Retrieve 5 max, prioritize corrections over approvals.
- **Mixing corrections and approvals in one collection:** Corrections are higher-signal training data. Keep them separate so you can weight them differently in retrieval.
- **Running DSPy optimization on every mapping call:** DSPy compilation is expensive (many LLM calls). Run offline, save optimized prompts, load at startup.
- **Using DSPy before having enough data:** BootstrapFewShot needs at least 10-20 labeled examples to work. With fewer, it can degrade performance. Wait for 50+ per domain.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vector similarity search | Custom cosine similarity on numpy arrays | ChromaDB `.query()` | ChromaDB handles indexing, persistence, metadata filtering, embedding. Building this yourself is weeks of work. |
| Embedding generation | Custom text embedding model | ChromaDB default (all-MiniLM-L6-v2) | Ships with chromadb, no GPU needed, 384-dim vectors, fast. Sufficient for short mapping descriptions. |
| Few-shot example selection | Manual heuristic selection | DSPy BootstrapFewShot | DSPy systematically evaluates which examples improve performance. Manual selection misses non-obvious patterns. |
| Prompt optimization | Manual prompt A/B testing | DSPy compile + metric | DSPy automates the search over prompt variants. Reproducible and measurable. |

**Key insight:** The learning system's value comes from the feedback loop, not from any single component. ChromaDB + DSPy are mature tools that handle the hard parts (similarity search, prompt optimization). Focus engineering effort on the integration points: ingestion pipeline, retrieval formatting, and accuracy metrics.

## Common Pitfalls

### Pitfall 1: Cold Start -- No Examples Available

**What goes wrong:** On the first study, the learning system has zero examples. The retriever returns nothing. The system behaves identically to Phase 3-7 (no learning benefit).
**Why it happens:** The learning system by definition needs prior data.
**How to avoid:** Design the system to gracefully degrade: when no examples are found, omit the examples section from the prompt. No errors, no empty sections. The mapping engine works exactly as before. After the first study is reviewed, examples become available for the second.
**Warning signs:** N/A -- this is expected behavior, not a bug. Document it for users.

### Pitfall 2: Retrieval Poisoning from Bad Examples

**What goes wrong:** An early correction was itself wrong (reviewer made a mistake). This bad example gets retrieved as few-shot context for future mappings, propagating the error.
**Why it happens:** Not all human corrections are correct. Especially in early usage when reviewers are learning the tool.
**How to avoid:** (1) Weight by recency -- newer corrections override older ones for the same variable. (2) Allow "un-correcting" -- if a correction is later found wrong, mark it as invalidated in the store. (3) When retrieving, prefer examples from completed, validated studies (where the output passed P21 validation).
**Warning signs:** Mapping quality degrading for specific variable types after a correction was added.

### Pitfall 3: ChromaDB Collection Size and Query Latency

**What goes wrong:** After 100+ studies with 15+ domains each, the ChromaDB collections grow to tens of thousands of documents. Query latency increases.
**Why it happens:** HNSW index performance degrades with collection size if not configured properly.
**How to avoid:** (1) Use metadata filters to narrow search space before vector similarity (filter by domain first, then search). This dramatically reduces the search space. (2) Set `n_results` conservatively (5-10, not 100). (3) ChromaDB's default HNSW settings are fine for <100K documents.
**Warning signs:** Retrieval taking >500ms per query.

### Pitfall 4: DSPy Compilation Cost

**What goes wrong:** Running DSPy `BootstrapFewShot.compile()` makes many LLM calls (one per training example per round). With 200 training examples and Claude Sonnet, this costs $5-20 per compilation run.
**Why it happens:** DSPy evaluates each example by running the full pipeline and checking against the metric.
**How to avoid:** (1) Run DSPy compilation offline (CLI command, not during mapping). (2) Cache compiled programs to disk. (3) Start with `max_rounds=1` and `max_bootstrapped_demos=4`. (4) Use Claude Haiku for the teacher model to reduce cost.
**Warning signs:** Compilation taking >30 minutes or costing >$20.

### Pitfall 5: Metric Gaming -- Accuracy Metric Doesn't Capture Quality

**What goes wrong:** Accuracy rate (approved_unchanged / total) goes up, but mapping quality doesn't actually improve. The system learns to produce "safe" mappings that reviewers don't bother correcting, not genuinely better mappings.
**Why it happens:** Binary accept/reject is a coarse metric. A reviewer might "approve" a mediocre mapping because correcting it isn't worth the time.
**How to avoid:** Track multiple metrics: (1) correction rate (lower is better), (2) confidence calibration (are HIGH confidence mappings actually approved more?), (3) validation pass rate (do generated datasets pass P21 rules?), (4) time-to-review (are reviewers spending less time?). The P21 validation pass rate is the most objective metric -- it's deterministic and not gameable.
**Warning signs:** Correction rate dropping but validation error rate staying flat or increasing.

## Code Examples

### ChromaDB PersistentClient Setup

```python
# Source: ChromaDB official docs
import chromadb

# Persistent storage in project directory
client = chromadb.PersistentClient(path=".astraea/learning/chroma_db")

# Create collection with HNSW cosine similarity (default)
collection = client.get_or_create_collection(
    name="approved_mappings",
    metadata={"description": "Approved SDTM variable mappings"},
)

# Add a mapping example
collection.add(
    ids=["study1_AE_AETERM"],
    documents=["SDTM domain AE variable AETERM. mapping pattern: direct. "
               "logic: Direct carry from source ae.AETERM. "
               "source variable: AETERM. source label: Reported Term for AE"],
    metadatas=[{
        "study_id": "PHA022121-C301",
        "domain": "AE",
        "sdtm_variable": "AETERM",
        "mapping_pattern": "direct",
        "was_corrected": "false",
    }],
)

# Query with domain filter
results = collection.query(
    query_texts=["SDTM AE domain adverse event term mapping"],
    n_results=5,
    where={"domain": "AE"},
)
# results["documents"] -> list of matching document texts
# results["metadatas"] -> list of metadata dicts
# results["distances"] -> list of distance scores
```

### DSPy Claude Configuration and BootstrapFewShot

```python
# Source: DSPy official docs (dspy.ai)
import dspy

# Configure DSPy with Claude
lm = dspy.LM(
    "anthropic/claude-sonnet-4-20250514",
    temperature=0.1,
    max_tokens=4096,
)
dspy.configure(lm=lm)

# Define a mapping module
class SDTMMapper(dspy.Module):
    def __init__(self):
        self.map_variable = dspy.ChainOfThought(
            "domain_spec, source_profile, ecrf_context -> variable_mapping"
        )

    def forward(self, domain_spec, source_profile, ecrf_context):
        return self.map_variable(
            domain_spec=domain_spec,
            source_profile=source_profile,
            ecrf_context=ecrf_context,
        )

# Create trainset from approved examples
trainset = [
    dspy.Example(
        domain_spec="AE domain, Required: AETERM (Char), AEDECOD (Char)...",
        source_profile="ae.sas7bdat: AETERM (character, 'Headache', 'Nausea'...)",
        ecrf_context="Adverse Events form: AETERM field, text entry",
        variable_mapping="AETERM -> direct from ae.AETERM; AEDECOD -> derivation from AETERM via MedDRA",
    ).with_inputs("domain_spec", "source_profile", "ecrf_context")
    for _ in range(50)  # Need 50+ real examples
]

# Define metric
def mapping_accuracy(example, prediction, trace=None):
    """Check if predicted mapping matches approved mapping."""
    return example.variable_mapping.strip() == prediction.variable_mapping.strip()

# Compile with BootstrapFewShot
optimizer = dspy.BootstrapFewShot(
    metric=mapping_accuracy,
    max_bootstrapped_demos=4,
    max_labeled_demos=8,
    max_rounds=1,
)
compiled_mapper = optimizer.compile(
    student=SDTMMapper(),
    trainset=trainset,
)

# Save compiled program for later use
compiled_mapper.save("learning/compiled_mapper.json")
```

### Few-Shot Section Formatting for Prompt Injection

```python
def format_examples_section(
    examples: list[dict],
    corrections: list[dict],
    max_total: int = 5,
) -> str:
    """Format retrieved examples as a prompt section.

    Prioritizes corrections (higher learning signal) over
    plain approved examples.
    """
    lines = ["## Relevant Past Mapping Examples"]
    lines.append("")
    lines.append("The following examples are from previously approved mappings "
                 "for similar variables. Use them as reference, but adapt to "
                 "the current source data.")

    # Corrections first (up to 3)
    correction_count = min(len(corrections), 3)
    for i, corr in enumerate(corrections[:correction_count]):
        lines.append(f"\n### Correction Example {i+1}")
        lines.append(f"Variable: {corr['sdtm_variable']}")
        lines.append(f"WRONG approach: {corr['original_logic']}")
        lines.append(f"CORRECT approach: {corr['corrected_logic']}")
        lines.append(f"Reason: {corr['reason']}")

    # Fill remaining slots with approved examples
    remaining = max_total - correction_count
    for i, ex in enumerate(examples[:remaining]):
        lines.append(f"\n### Approved Example {i+1}")
        lines.append(f"Variable: {ex['sdtm_variable']} ({ex['domain']})")
        lines.append(f"Pattern: {ex['mapping_pattern']}")
        lines.append(f"Logic: {ex['mapping_logic']}")
        if ex.get('source_variable'):
            lines.append(f"Source: {ex['source_variable']}")

    return "\n".join(lines)
```

### Accuracy Metrics Computation

```python
from dataclasses import dataclass

@dataclass
class DomainAccuracy:
    domain: str
    study_id: str
    total_proposed: int
    approved_unchanged: int
    corrected: int
    rejected: int
    added_by_reviewer: int
    accuracy_rate: float  # approved_unchanged / total_proposed
    correction_rate: float  # corrected / total_proposed

    @classmethod
    def from_domain_review(cls, review, study_id: str) -> "DomainAccuracy":
        total = len(review.original_spec.variable_mappings)
        approved = sum(
            1 for d in review.decisions.values()
            if d.status == "approved"
        )
        corrected = sum(
            1 for d in review.decisions.values()
            if d.status == "corrected" and d.correction_type != "reject"
        )
        rejected = sum(
            1 for d in review.decisions.values()
            if d.status == "corrected" and d.correction_type == "reject"
        )
        added = sum(
            1 for d in review.decisions.values()
            if d.status == "corrected" and d.correction_type == "add"
        )
        return cls(
            domain=review.domain,
            study_id=study_id,
            total_proposed=total,
            approved_unchanged=approved,
            corrected=corrected,
            rejected=rejected,
            added_by_reviewer=added,
            accuracy_rate=approved / total if total > 0 else 0.0,
            correction_rate=corrected / total if total > 0 else 0.0,
        )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual prompt engineering | DSPy automated optimization | DSPy 2.x -> 3.x (2025) | Systematic, reproducible prompt improvement |
| FAISS for vector search | ChromaDB embedded with metadata | ChromaDB 1.x (2025) | No server needed, metadata filtering, persistence built-in |
| Fine-tuning for improvement | Few-shot RAG + prompt optimization | 2024-2025 consensus | Works with API models (Claude), no training infra needed |
| Single accuracy metric | Multi-dimensional metrics | 2025 RLHF research | Prevents reward hacking, captures true quality |

**Deprecated/outdated:**
- DSPy `teleprompt` module name: Now `dspy.BootstrapFewShot` directly, not `dspy.teleprompt.BootstrapFewShot`
- ChromaDB `Client()` for persistence: Use `PersistentClient(path=...)` instead
- `dspy.OpenAI()` / `dspy.Anthropic()`: Use `dspy.LM('anthropic/model-name')` unified interface

## Integration Points with Existing Code

### Where Learning System Connects

| Existing Component | Integration Point | What Changes |
|--------------------|-------------------|-------------|
| `MappingEngine.map_domain()` | After context build, before LLM call | Add optional `LearningRetriever` dependency; append examples section to prompt |
| `MappingContextBuilder.build_prompt()` | New optional section | Add `format_examples_section()` as 7th section after study metadata |
| `DomainReviewer` (reviewer.py) | After domain review completes | Call `ingest_review_results()` to store examples |
| `SessionStore.save_session()` | After session completion | Trigger metrics computation and storage |
| `MAPPING_SYSTEM_PROMPT` (prompts.py) | Add instruction about examples | Tell LLM to "learn from" provided examples but adapt to current data |
| CLI `app.py` | New commands | `astraea learn ingest`, `astraea learn stats`, `astraea learn optimize` |

### Dependency Injection Pattern

The learning system should be optional -- the MappingEngine must work without it (for first-study cold start). Use optional constructor parameter:

```python
class MappingEngine:
    def __init__(
        self,
        llm_client: AstraeaLLMClient,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
        learning_retriever: LearningRetriever | None = None,  # NEW
    ) -> None:
        self._learning = learning_retriever
```

## Cross-Study Template Library Design

### Abstraction Level: Domain-Level Templates

A template captures the mapping pattern for an entire domain from a completed study. Templates are more general than individual variable mappings -- they describe the "shape" of a domain mapping that can be reused.

```python
class DomainTemplate(BaseModel):
    """Reusable domain mapping template from a completed study."""
    template_id: str
    domain: str
    domain_class: str
    source_study_id: str

    # Pattern summary (what mapping patterns were used)
    pattern_distribution: dict[str, int]  # e.g., {"direct": 8, "derivation": 5, "assign": 3}

    # Variable-level patterns (abstracted from specific study)
    variable_patterns: list[VariablePattern]

    # Quality signal
    accuracy_rate: float  # from review metrics
    validation_pass_rate: float  # from P21 validation

class VariablePattern(BaseModel):
    """Abstracted variable mapping pattern (study-independent)."""
    sdtm_variable: str
    typical_pattern: str  # most common mapping pattern for this variable
    typical_source_label_keywords: list[str]  # e.g., ["birth", "date"] for BRTHDTC
    derivation_template: str | None  # generalized derivation logic
    common_issues: list[str]  # issues found during past reviews
```

### Template Matching Strategy

When a new study arrives, match templates by:
1. Domain code (exact match)
2. Domain class (fallback)
3. Source dataset structure similarity (number of variables, variable name overlap)

Templates provide a starting scaffold that the LLM refines based on the actual source data.

## Open Questions

1. **Embedding quality for SDTM domain text:**
   - What we know: all-MiniLM-L6-v2 works well for general English text
   - What's unclear: How well it handles SDTM-specific terminology (AETERM, LBTESTCD, etc.) -- these are domain-specific abbreviations not common in training data
   - Recommendation: Start with default embeddings. If retrieval quality is poor, consider fine-tuning embeddings or using a domain-specific text representation that expands abbreviations (e.g., "AETERM: Reported Term for the Adverse Event" instead of just "AETERM")

2. **DSPy metric for mapping quality:**
   - What we know: DSPy needs a metric function that returns bool or float
   - What's unclear: What constitutes a "correct" mapping prediction in DSPy's framework -- the output is structured JSON, not a single string
   - Recommendation: Use a composite metric: (1) correct SDTM variable identified (bool), (2) correct mapping pattern (bool), (3) correct source variable (bool). Return True only if all three match. This gives DSPy a clear signal.

3. **When to trigger DSPy recompilation:**
   - What we know: BootstrapFewShot needs trainset of `dspy.Example` objects
   - What's unclear: How often to recompile as new examples accumulate (after every study? every N corrections?)
   - Recommendation: Manual trigger via CLI command (`astraea learn optimize`). Don't auto-recompile -- it's expensive and the user should decide when.

## Sources

### Primary (HIGH confidence)
- [ChromaDB Official Docs - Embedding Functions](https://docs.trychroma.com/docs/embeddings/embedding-functions) - Default embedding model, configuration
- [ChromaDB Cookbook - Collections](https://cookbook.chromadb.dev/core/collections/) - Collection API, metadata, query filters
- [DSPy Official - BootstrapFewShot API](https://dspy.ai/api/optimizers/BootstrapFewShot/) - Constructor params, compile method
- [DSPy Official - Language Models](https://dspy.ai/learn/programming/language_models/) - Claude/Anthropic configuration with dspy.LM
- [DSPy Official - Optimizers Overview](https://dspy.ai/learn/optimization/optimizers/) - BootstrapFewShot vs MIPROv2 comparison

### Secondary (MEDIUM confidence)
- [Anthropic Skills Optimized Using DSPy](https://instavm.io/blog/anthropic-skills-can-be-optimized-using-dspy) - Real-world DSPy + Claude usage patterns
- [ChromaDB Cookbook - Storage Layout](https://cookbook.chromadb.dev/core/storage-layout/) - Persistent storage internals
- [DSPy Cheatsheet](https://dspy.ai/cheatsheet/) - Quick reference for DSPy patterns

### Tertiary (LOW confidence)
- [Weaviate Blog - DSPy Optimizers](https://weaviate.io/blog/dspy-optimizers) - General DSPy optimizer comparison (not Anthropic-specific)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - ChromaDB and DSPy are locked decisions from STACK.md, versions verified
- Architecture: HIGH - Integration points identified by reading actual source code (engine.py, context.py, session.py, models.py)
- Pitfalls: MEDIUM - Based on general RAG/prompt-optimization experience, not SDTM-specific learning system deployments
- ChromaDB API: HIGH - Verified against official docs
- DSPy API: HIGH - Verified against official docs, Claude configuration confirmed
- Metrics design: MEDIUM - Based on general ML metrics best practices, needs validation in practice
- Template library: MEDIUM - Novel design, no existing SDTM-specific template library pattern to reference

**Research date:** 2026-02-27
**Valid until:** 30 days (stable libraries, well-documented APIs)
