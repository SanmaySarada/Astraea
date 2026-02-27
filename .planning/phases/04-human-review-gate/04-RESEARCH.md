# Phase 4: Human Review Gate - Research

**Researched:** 2026-02-27
**Domain:** Interactive CLI review, session persistence, LangGraph interrupts
**Confidence:** HIGH

## Summary

Phase 4 adds the human review gate -- the quality control layer where a reviewer inspects proposed mappings per domain, approves or corrects them, and can resume interrupted sessions. This phase introduces two distinct capabilities: (1) an interactive review interface using Rich/Typer, and (2) session persistence so reviews can be interrupted and resumed.

The critical finding is that **LangGraph is not currently used anywhere in the codebase**. The mapping engine (`MappingEngine.map_domain()`) is a synchronous function that returns a `DomainMappingSpec` directly. The architecture documents prescribe LangGraph StateGraph with interrupts for HITL, but introducing LangGraph as the orchestrator in Phase 4 would mean simultaneously building the review interface AND refactoring the entire pipeline into a graph -- too much scope for one phase.

**Primary recommendation:** Build the review interface and session persistence as standalone modules first, using SQLite for session state and Rich/Typer for the interactive CLI. Design the session persistence layer to be compatible with future LangGraph checkpoint migration, but do NOT introduce LangGraph StateGraph in this phase. LangGraph orchestration should come in a later phase when the full multi-domain pipeline exists.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `rich` | >=13.9 (installed) | Table display, prompts, panels for review UI | Already used in `cli/display.py`; has `Prompt.ask()` with choices, `Confirm.ask()`, styled tables |
| `typer` | >=0.15 (installed) | CLI command structure for `review` and `resume` commands | Already used in `cli/app.py`; standard for project CLI |
| `pydantic` | >=2.10 (installed) | HumanCorrection model, ReviewSession state model | Already used for all data models in the project |
| `sqlite3` | stdlib | Session persistence (review state, corrections) | Zero dependencies; compatible with future LangGraph `SqliteSaver` migration |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `langgraph-checkpoint-sqlite` | 3.0.3 | LangGraph SQLite checkpointer | NOT for Phase 4 -- install when full LangGraph pipeline is built |
| `uuid` | stdlib | Generate session IDs | Every new review session needs a unique ID |
| `json` | stdlib | Serialize review state to SQLite | DomainMappingSpec already has `model_dump_json()` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQLite session store | LangGraph SqliteSaver | LangGraph requires refactoring entire pipeline into StateGraph -- too much scope for Phase 4 |
| Rich Prompt.ask() | `questionary` or `prompt_toolkit` | Extra dependency; Rich already provides what we need (choices, confirmation, text input) |
| File-based session JSON | SQLite | SQLite handles concurrent access, partial updates, and querying better; also aligns with future LangGraph migration |

**Installation:**
```bash
# No new dependencies needed -- everything is already installed
# Future (when LangGraph pipeline is built):
pip install langgraph-checkpoint-sqlite
```

## Architecture Patterns

### Recommended Project Structure
```
src/astraea/
  review/                    # NEW module for Phase 4
    __init__.py
    models.py                # HumanCorrection, ReviewSession, ReviewDecision models
    session.py               # SQLite-backed session persistence (create, save, load, resume)
    display.py               # Review-specific Rich display (extends cli/display.py patterns)
    reviewer.py              # Core review loop logic (present spec, collect decisions)
  cli/
    app.py                   # ADD: review-domain and resume commands
    display.py               # EXTEND: add review-specific display helpers
  models/
    mapping.py               # EXTEND: add ReviewStatus enum, reviewed flag to VariableMapping
```

### Pattern 1: Review Loop with Domain-Scoped Processing

**What:** Process one domain at a time. For each domain, display the full mapping spec, then iterate through variables collecting approve/correct/skip decisions.
**When to use:** Always -- this matches the existing domain-scoped architecture.
**Example:**
```python
# Core review flow
def review_domain(spec: DomainMappingSpec, session: ReviewSession) -> ReviewResult:
    """Present a domain mapping for human review."""
    # 1. Display full mapping table (reuse display_mapping_spec pattern)
    display_review_table(spec, console)

    # 2. Offer batch or per-variable review
    action = Prompt.ask(
        "Review action",
        choices=["approve-all", "review", "skip", "quit"],
        default="review",
    )

    if action == "approve-all":
        return approve_all(spec, session)
    elif action == "review":
        return review_per_variable(spec, session)
    elif action == "skip":
        return skip_domain(spec, session)
    else:  # quit
        save_session(session)
        raise ReviewInterrupted(session.session_id)
```

### Pattern 2: Session Persistence with SQLite

**What:** Store review state in SQLite so sessions survive process exit and can be resumed.
**When to use:** Every review session.
**Example:**
```python
import sqlite3
from pathlib import Path

class SessionStore:
    """SQLite-backed review session persistence."""

    def __init__(self, db_path: Path) -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                study_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'in_progress',
                current_domain_index INTEGER DEFAULT 0,
                domains_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS domain_reviews (
                session_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                spec_json TEXT NOT NULL,
                reviewed_spec_json TEXT,
                reviewed_at TEXT,
                PRIMARY KEY (session_id, domain),
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
            CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                sdtm_variable TEXT NOT NULL,
                correction_type TEXT NOT NULL,
                original_json TEXT NOT NULL,
                corrected_json TEXT NOT NULL,
                reason TEXT NOT NULL,
                reviewer TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
        """)
        self._conn.commit()

    def create_session(self, study_id: str, domains: list[str]) -> str:
        """Create a new review session. Returns session_id."""
        ...

    def save_domain_review(self, session_id: str, domain: str, spec: DomainMappingSpec) -> None:
        """Save reviewed spec for a domain."""
        ...

    def load_session(self, session_id: str) -> ReviewSession:
        """Load session state for resume."""
        ...

    def list_sessions(self, study_id: str | None = None) -> list[SessionSummary]:
        """List all sessions, optionally filtered by study."""
        ...
```

### Pattern 3: Correction Capture with Structured Metadata

**What:** Every human correction is captured as a structured record linking the original mapping to the corrected version with a reason.
**When to use:** Every time a reviewer modifies a mapping.
**Example:**
```python
class CorrectionType(StrEnum):
    SOURCE_CHANGE = "source_change"        # Different source variable
    LOGIC_CHANGE = "logic_change"          # Different mapping logic
    PATTERN_CHANGE = "pattern_change"      # Different mapping pattern
    CT_CHANGE = "ct_change"               # Different codelist/term
    CONFIDENCE_OVERRIDE = "confidence_override"  # Reviewer disagrees with confidence
    REJECT = "reject"                      # Variable should not be mapped
    ADD = "add"                           # Variable was missing from proposal

class HumanCorrection(BaseModel):
    session_id: str
    domain: str
    sdtm_variable: str
    correction_type: CorrectionType
    original_mapping: VariableMapping
    corrected_mapping: VariableMapping | None  # None for REJECT
    reason: str
    reviewer: str = ""
    timestamp: str  # ISO 8601
```

### Pattern 4: Two-Tier Review (Batch + Per-Variable)

**What:** Offer batch approval for high-confidence mappings and per-variable review for low/medium confidence.
**When to use:** Default review mode. Statistical programmers do not want to approve 25 obvious ASSIGN mappings one by one.
**Example:**
```
=== Review: DM (Demographics) ===
Source: dm.sas7bdat | 23 variables mapped

  HIGH confidence (18): Approve all? [Y/n]
  > Y

  Reviewing 5 MEDIUM/LOW confidence mappings:

  #3  AGE  <-- BRTHDAT  [derive]  conf=0.72
      Logic: Calculate AGE from BRTHDAT and RFSTDTC
      [a]pprove / [c]orrect / [s]kip? >
```

### Anti-Patterns to Avoid
- **Full LangGraph refactor in Phase 4:** Do not introduce StateGraph, compile(), or checkpoint-based interrupts. The pipeline is not yet multi-domain and the added complexity is not justified.
- **Blocking the entire pipeline on review:** Each domain should be reviewable independently. Do not require all domains to be mapped before review starts.
- **Unstructured corrections:** Never capture corrections as free-text only. Always use the structured HumanCorrection model -- this is the training data for the Phase 8 learning system.
- **Re-running LLM on correction:** When a reviewer corrects a mapping, save the corrected VariableMapping directly. Do not re-invoke the LLM to "fix" the mapping -- that defeats the purpose of human review.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI prompts with validation | Custom input() loops | `rich.prompt.Prompt.ask(choices=...)` | Handles retries, case sensitivity, default values |
| Yes/no confirmation | Manual Y/N parsing | `rich.prompt.Confirm.ask()` | Already handles variations (y/Y/yes/YES) |
| Color-coded confidence display | Custom ANSI codes | Rich `Text(style=...)` pattern from `display.py` | Already established in `display_mapping_spec()` |
| Session ID generation | Custom ID schemes | `uuid.uuid4().hex[:12]` | Short, unique, filesystem-safe |
| JSON serialization of Pydantic | Manual dict construction | `model.model_dump_json()` / `Model.model_validate_json()` | Round-trip safe, handles enums and nested models |
| SQLite migrations | Manual ALTER TABLE | Create tables with IF NOT EXISTS on init | Sufficient for v1 single-user CLI |

**Key insight:** Rich already provides everything needed for the interactive review UI. The project already uses Rich tables, panels, and styled text extensively in `cli/display.py`. Phase 4 extends these patterns, it does not introduce new UI libraries.

## Common Pitfalls

### Pitfall 1: Trying to Build LangGraph Pipeline and Review UI Simultaneously
**What goes wrong:** Phase 4 scope balloons because you try to refactor the sync `MappingEngine.map_domain()` into a LangGraph StateGraph while also building the review interface. Both are complex; doing them together causes neither to work well.
**Why it happens:** ARCHITECTURE.md prescribes LangGraph interrupts for HITL. But the current codebase has zero LangGraph usage -- the mapping engine is a simple function call.
**How to avoid:** Build review as a standalone module. The `review-domain` command takes a mapping spec JSON file (already exported by `map-domain`) and presents it for review. Session persistence uses SQLite directly. When the full LangGraph pipeline is built in a later phase, the review node can call the same review logic.
**Warning signs:** If the plan includes `graph.compile()`, `StateGraph`, or `interrupt()`, scope is too large.

### Pitfall 2: Losing Context When Resuming Sessions
**What goes wrong:** Session resume loads the last checkpoint but loses which specific variables were already reviewed within a domain. The reviewer has to re-review variables they already approved.
**Why it happens:** Session state is saved at domain granularity but not at variable granularity.
**How to avoid:** Track per-variable review status (pending/approved/corrected/skipped) in the session state. On resume, skip already-reviewed variables and present only pending ones.
**Warning signs:** Reviewers complaining about seeing the same mappings again after resuming.

### Pitfall 3: Correction Model Too Rigid or Too Flexible
**What goes wrong:** If corrections only capture "approve/reject," the learning system (Phase 8) has no signal. If corrections require filling 10 fields, reviewers skip corrections and just approve everything.
**Why it happens:** Overengineering the correction model before understanding real reviewer workflow.
**How to avoid:** Three correction paths: (1) approve (one keystroke), (2) quick-correct (change source variable or assigned value inline), (3) full-correct (opens structured form for complex changes). Most corrections are path 1 or 2.
**Warning signs:** Correction rate dropping to zero (reviewers giving up), or review time exceeding manual mapping time.

### Pitfall 4: Rich Prompt Blocking in Tests
**What goes wrong:** Tests that call review functions hang because `Prompt.ask()` waits for terminal input.
**Why it happens:** Rich prompts read from stdin, which is unavailable in pytest.
**How to avoid:** Accept a `Console` parameter (already the pattern in `display.py`). In tests, use `Console(file=io.StringIO())` and mock prompt inputs via monkeypatch or by injecting a response callback. The reviewer module should accept an optional `input_callback` for testability.
**Warning signs:** Integration tests hanging indefinitely.

### Pitfall 5: Session Database Corruption on Ctrl+C
**What goes wrong:** Reviewer presses Ctrl+C mid-save, leaving SQLite in an inconsistent state.
**Why it happens:** Writing to SQLite without proper transaction handling.
**How to avoid:** Use SQLite transactions (BEGIN/COMMIT) around all writes. Save session state before presenting each variable (not after). Register a signal handler for SIGINT that commits pending transactions before exit.
**Warning signs:** "database is locked" or "malformed database" errors on resume.

## Code Examples

Verified patterns from the existing codebase:

### Extending display_mapping_spec for Review Mode
```python
# Source: existing pattern from src/astraea/cli/display.py lines 376-467
# Extend with review-specific columns (status, action)
def display_review_table(
    spec: DomainMappingSpec,
    decisions: dict[str, str],  # variable -> "pending"/"approved"/"corrected"
    console: Console,
) -> None:
    """Display mapping spec with review status column."""
    table = Table(title=f"Review: {spec.domain} ({spec.domain_label})", show_lines=True)
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Status", no_wrap=True, width=6)
    table.add_column("Variable", style="bold cyan", no_wrap=True)
    table.add_column("Source", no_wrap=True)
    table.add_column("Pattern", no_wrap=True)
    table.add_column("Conf", justify="right")
    table.add_column("Logic", max_width=40)

    for idx, m in enumerate(spec.variable_mappings, start=1):
        status = decisions.get(m.sdtm_variable, "pending")
        status_icon = {
            "pending": Text("...", style="dim"),
            "approved": Text("OK", style="bold green"),
            "corrected": Text("FIX", style="bold yellow"),
            "skipped": Text("--", style="dim"),
        }.get(status, Text("?"))

        # Color-code confidence (existing pattern)
        conf_str = f"{m.confidence:.2f}"
        if m.confidence_level == ConfidenceLevel.HIGH:
            conf_text = Text(conf_str, style="green")
        elif m.confidence_level == ConfidenceLevel.MEDIUM:
            conf_text = Text(conf_str, style="yellow")
        else:
            conf_text = Text(conf_str, style="red")

        source = m.source_variable or ""
        if m.mapping_pattern.value == "assign" and m.assigned_value:
            source = f'="{m.assigned_value}"'

        table.add_row(
            str(idx), status_icon, m.sdtm_variable, source,
            m.mapping_pattern.value, conf_text,
            m.mapping_logic[:40] if m.mapping_logic else "",
        )
    console.print(table)
```

### Rich Prompt for Variable Review
```python
# Source: Rich Prompt docs (https://rich.readthedocs.io/en/latest/prompt.html)
from rich.prompt import Prompt, Confirm

# Per-variable review
def review_variable(mapping: VariableMapping, console: Console) -> str:
    """Present a single variable mapping for review. Returns decision."""
    console.print(f"\n  [bold cyan]{mapping.sdtm_variable}[/bold cyan]"
                  f"  <--  {mapping.source_variable or 'N/A'}")
    console.print(f"  Pattern: {mapping.mapping_pattern.value} | "
                  f"Confidence: {mapping.confidence:.2f}")
    console.print(f"  Logic: {mapping.mapping_logic}")

    action = Prompt.ask(
        "  Action",
        choices=["a", "c", "s"],  # approve, correct, skip
        default="a",
    )
    return {"a": "approved", "c": "correct", "s": "skipped"}[action]
```

### Session Persistence with SQLite
```python
# Source: Python stdlib sqlite3 + Pydantic serialization
import sqlite3
from datetime import UTC, datetime

def save_session_state(
    conn: sqlite3.Connection,
    session_id: str,
    domain: str,
    spec: DomainMappingSpec,
    status: str,
) -> None:
    """Persist domain review state to SQLite."""
    now = datetime.now(tz=UTC).isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO domain_reviews
           (session_id, domain, status, spec_json, reviewed_at)
           VALUES (?, ?, ?, ?, ?)""",
        (session_id, domain, status, spec.model_dump_json(), now),
    )
    conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
        (now, session_id),
    )
    conn.commit()
```

### CLI Commands for Review and Resume
```python
# Source: existing pattern from src/astraea/cli/app.py
@app.command(name="review-domain")
def review_domain_cmd(
    spec_file: Annotated[Path, typer.Argument(help="Path to mapping spec JSON")],
    session_id: Annotated[str | None, typer.Option("--session", help="Resume session")] = None,
    db_path: Annotated[Path, typer.Option("--db", help="Session database")] = Path(".astraea/sessions.db"),
) -> None:
    """Review a domain mapping specification interactively."""
    ...

@app.command(name="resume")
def resume_cmd(
    session_id: Annotated[str | None, typer.Argument(help="Session ID to resume")] = None,
    db_path: Annotated[Path, typer.Option("--db", help="Session database")] = Path(".astraea/sessions.db"),
) -> None:
    """Resume an interrupted review session."""
    ...

@app.command(name="sessions")
def list_sessions_cmd(
    db_path: Annotated[Path, typer.Option("--db", help="Session database")] = Path(".astraea/sessions.db"),
) -> None:
    """List all review sessions."""
    ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `interrupt_before`/`interrupt_after` (static) | `interrupt()` function (dynamic) | LangGraph v0.4 (Apr 2025) | Interrupts can now happen anywhere inside a node, not just at node boundaries |
| Single interrupt resume | Multiple simultaneous interrupt resume | LangGraph v0.4 | Can resume multiple parallel interrupts at once via interrupt ID mapping |
| Custom HITL polling | `Command(resume=...)` | LangGraph v0.4 | Clean API for passing human input back to interrupted graph |

**Important for Phase 4:** These LangGraph improvements are relevant for future migration but NOT for this phase, since we are building standalone review first.

## Open Questions

Things that could not be fully resolved:

1. **Review granularity: per-variable vs per-domain batch**
   - What we know: Statistical programmers review mappings in batch (like spec review in SAS). They do not want to click approve 25 times for obvious ASSIGN mappings.
   - What is unclear: Exact UX -- should high-confidence mappings auto-batch while low-confidence get individual attention?
   - Recommendation: Implement two-tier review (batch approve HIGH, individual review MEDIUM/LOW). Let reviewer override to per-variable if desired.

2. **Where to store the session database**
   - What we know: SQLite file needs a consistent location.
   - What is unclear: Should it be `.astraea/sessions.db` in the project root, or in the output directory?
   - Recommendation: Default to `.astraea/sessions.db` in CWD with `--db` override option. This keeps session data near the project.

3. **Correction input UI complexity**
   - What we know: Reviewers need to specify what is wrong and what the correct mapping should be. The `VariableMapping` model has many fields.
   - What is unclear: How much correction detail can a CLI reviewer reasonably provide?
   - Recommendation: For v1, support three correction types inline: (a) change source variable, (b) change assigned value, (c) reject mapping. For complex corrections (change derivation logic, add missing variable), accept free-text that gets stored as the `reason` field. The full structured correction comes in later phases.

4. **LangGraph migration path**
   - What we know: ARCHITECTURE.md prescribes LangGraph StateGraph. The current codebase does not use LangGraph at all despite it being installed.
   - What is unclear: When should the full LangGraph pipeline be introduced?
   - Recommendation: Phase 4 builds the review module standalone. A future phase (Phase 5 or later) introduces LangGraph as the orchestrator, and the review node wraps the existing review module. Design the review module's API to be callable from a LangGraph node.

## Design Decision: Standalone Review vs LangGraph Integration

This is the most important architectural decision for Phase 4.

### Option A: Build Full LangGraph StateGraph Now (REJECTED)
- Requires refactoring `MappingEngine`, classification, and profiling into graph nodes
- Introduces `interrupt()`, `Command(resume=...)`, `SqliteSaver` all at once
- Scope: essentially building the entire orchestration layer + review UI
- Risk: very high -- touching working code across multiple modules

### Option B: Standalone Review Module (RECOMMENDED)
- New `review/` module with its own SQLite session store
- CLI commands (`review-domain`, `resume`, `sessions`) work with mapping spec JSON files
- Review module has a clean API: `review_domain(spec) -> ReviewResult`
- Future LangGraph node wraps this API: `interrupt(spec.model_dump()) -> Command(resume=review_domain(spec))`
- Scope: contained to new code, does not touch existing pipeline
- Risk: low -- additive only

### Why Option B
1. The current pipeline works: `map-domain` produces correct specs. Do not break it.
2. LangGraph adds value when there is a multi-step pipeline to orchestrate. Today there is one step (map a domain).
3. The review module API (`review_domain(spec) -> ReviewResult`) is graph-framework-agnostic. It works equally well called from a LangGraph node or from a Typer command.
4. Session persistence via SQLite is compatible with LangGraph's `SqliteSaver` pattern -- same database, similar schema, easy migration.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `src/astraea/cli/display.py` -- established Rich display patterns
- Existing codebase: `src/astraea/cli/app.py` -- established Typer CLI patterns
- Existing codebase: `src/astraea/models/mapping.py` -- DomainMappingSpec, VariableMapping models
- [Rich Prompt documentation](https://rich.readthedocs.io/en/latest/prompt.html) -- Prompt.ask(), Confirm.ask() API
- [LangGraph Interrupts documentation](https://docs.langchain.com/oss/python/langgraph/interrupts) -- interrupt(), Command(resume=), checkpointer patterns
- [LangGraph Persistence documentation](https://docs.langchain.com/oss/python/langgraph/persistence) -- SqliteSaver, thread_id, StateSnapshot
- [langgraph-checkpoint-sqlite PyPI](https://pypi.org/project/langgraph-checkpoint-sqlite/) -- v3.0.3, Jan 2026

### Secondary (MEDIUM confidence)
- [LangGraph v0.4 Changelog](https://changelog.langchain.com/announcements/langgraph-v0-4-working-with-interrupts) -- interrupt API improvements
- [Typer Prompt tutorial](https://typer.tiangolo.com/tutorial/prompt/) -- Typer prompt integration patterns

### Tertiary (LOW confidence)
- [DEV.to LangGraph HITL article](https://dev.to/jamesbmour/interrupts-and-commands-in-langgraph-building-human-in-the-loop-workflows-4ngl) -- community tutorial, patterns verified against official docs
- [Medium: LangGraph HITL Design Patterns](https://medium.com/fundamentals-of-artificial-intelligence/langgraph-hitl-design-patterns-multiple-interrupts-45fc9b549ec5) -- multiple interrupt patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and used in the project
- Architecture: HIGH -- standalone review module is clearly the right scope; LangGraph API well-documented for future migration
- Review UI patterns: HIGH -- Rich Prompt API is simple and well-documented; existing display.py provides clear patterns to extend
- Session persistence: HIGH -- SQLite stdlib is straightforward; schema is simple
- LangGraph migration path: MEDIUM -- future migration depends on when/how the full pipeline is orchestrated
- Correction model: MEDIUM -- exact UX needs user testing; the model structure is clear but granularity may need adjustment

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable -- no fast-moving dependencies)
