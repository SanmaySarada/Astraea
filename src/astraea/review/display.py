"""Rich display helpers for the human review gate.

Provides formatted display functions for review tables, variable detail
panels, review summaries, and session lists. Extends patterns from
cli/display.py for review-specific use cases.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from astraea.models.mapping import ConfidenceLevel, DomainMappingSpec, VariableMapping
from astraea.models.sdtm import CoreDesignation
from astraea.review.models import (
    DomainReview,
    ReviewDecision,
    ReviewStatus,
)


def _format_core(core: CoreDesignation) -> Text:
    """Format a core designation with color coding."""
    if core == CoreDesignation.REQ:
        return Text("Req", style="bold red")
    elif core == CoreDesignation.EXP:
        return Text("Exp", style="yellow")
    else:
        return Text("Perm", style="green")


def _format_status(status: ReviewStatus | None) -> Text:
    """Format a review status indicator."""
    if status is None or status == ReviewStatus.PENDING:
        return Text("...", style="dim")
    elif status == ReviewStatus.APPROVED:
        return Text("OK", style="bold green")
    elif status == ReviewStatus.CORRECTED:
        return Text("FIX", style="bold yellow")
    elif status == ReviewStatus.SKIPPED:
        return Text("--", style="dim")
    return Text("?", style="dim")


def display_review_table(
    spec: DomainMappingSpec,
    decisions: dict[str, ReviewDecision],
    console: Console,
) -> None:
    """Display a domain's variable mappings in review table format.

    Shows domain header panel and a table with status, variable name,
    label, core designation, source, pattern, confidence, and logic.

    Args:
        spec: The domain mapping specification to display.
        decisions: Per-variable review decisions keyed by sdtm_variable.
        console: Rich Console for output.
    """
    # Header panel
    info_lines = [
        f"[bold]Domain:[/bold] {spec.domain} -- {spec.domain_label}",
        f"[bold]Study:[/bold] {spec.study_id}",
        f"[bold]Source:[/bold] {', '.join(spec.source_datasets)}",
        f"[bold]Timestamp:[/bold] {spec.mapping_timestamp}",
    ]
    console.print(Panel("\n".join(info_lines), title=f"Review: {spec.domain}"))

    # Variable mapping table
    table = Table(title=f"{spec.domain} Mappings", show_lines=True)
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Status", no_wrap=True, width=6)
    table.add_column("Variable", style="bold cyan", no_wrap=True)
    table.add_column("Label", max_width=30)
    table.add_column("Core", no_wrap=True)
    table.add_column("Source", no_wrap=True)
    table.add_column("Pattern", no_wrap=True)
    table.add_column("Confidence", justify="right")
    table.add_column("Logic", max_width=40)

    for idx, m in enumerate(spec.variable_mappings, start=1):
        # Status from decisions
        decision = decisions.get(m.sdtm_variable)
        status_text = _format_status(decision.status if decision else None)

        core_text = _format_core(m.core)

        # Source display
        source_str = m.source_variable or ""
        if m.mapping_pattern.value == "assign" and m.assigned_value:
            source_str = f'="{m.assigned_value}"'

        # Confidence with color
        conf_str = f"{m.confidence:.2f}"
        if m.confidence_level == ConfidenceLevel.HIGH:
            conf_text = Text(conf_str, style="green")
        elif m.confidence_level == ConfidenceLevel.MEDIUM:
            conf_text = Text(conf_str, style="yellow")
        else:
            conf_text = Text(conf_str, style="red")

        # Logic truncation
        logic = m.mapping_logic
        if len(logic) > 40:
            logic = logic[:37] + "..."

        table.add_row(
            str(idx),
            status_text,
            m.sdtm_variable,
            m.sdtm_label[:30] if m.sdtm_label else "",
            core_text,
            source_str,
            m.mapping_pattern.value,
            conf_text,
            logic,
        )

    console.print(table)

    # Summary counts
    approved = sum(1 for d in decisions.values() if d.status == ReviewStatus.APPROVED)
    corrected = sum(1 for d in decisions.values() if d.status == ReviewStatus.CORRECTED)
    skipped = sum(1 for d in decisions.values() if d.status == ReviewStatus.SKIPPED)
    pending = spec.total_variables - approved - corrected - skipped

    console.print(
        f"\n[bold]Progress:[/bold] "
        f"[green]{approved} approved[/green]  "
        f"[yellow]{corrected} corrected[/yellow]  "
        f"[dim]{skipped} skipped[/dim]  "
        f"{pending} pending"
    )


def display_variable_detail(mapping: VariableMapping, console: Console) -> None:
    """Display full detail for a single variable mapping.

    Shows a panel with all mapping attributes including source,
    pattern, confidence, logic, derivation rule, codelist, and rationale.

    Args:
        mapping: The VariableMapping to display in detail.
        console: Rich Console for output.
    """
    lines: list[str] = [
        f"[bold cyan]{mapping.sdtm_variable}[/bold cyan]",
        f"[bold]Label:[/bold] {mapping.sdtm_label}",
        f"[bold]Core:[/bold] {mapping.core.value}",
    ]

    # Source info
    if mapping.mapping_pattern.value == "assign" and mapping.assigned_value:
        lines.append(f'[bold]Source:[/bold] Assigned: "{mapping.assigned_value}"')
    elif mapping.source_dataset and mapping.source_variable:
        lines.append(f"[bold]Source:[/bold] {mapping.source_dataset}.{mapping.source_variable}")
    elif mapping.source_variable:
        lines.append(f"[bold]Source:[/bold] {mapping.source_variable}")
    else:
        lines.append("[bold]Source:[/bold] (none)")

    lines.append(f"[bold]Pattern:[/bold] {mapping.mapping_pattern.value}")
    lines.append(
        f"[bold]Confidence:[/bold] {mapping.confidence:.2f} ({mapping.confidence_level.value})"
    )
    lines.append(f"[bold]Mapping Logic:[/bold] {mapping.mapping_logic}")

    if mapping.derivation_rule:
        lines.append(f"[bold]Derivation Rule:[/bold] {mapping.derivation_rule}")

    if mapping.codelist_code:
        codelist_display = mapping.codelist_code
        if mapping.codelist_name:
            codelist_display += f" ({mapping.codelist_name})"
        lines.append(f"[bold]Codelist:[/bold] {codelist_display}")

    if mapping.confidence_rationale:
        lines.append(f"[bold]Rationale:[/bold] {mapping.confidence_rationale}")

    console.print(Panel("\n".join(lines), title=f"Variable: {mapping.sdtm_variable}"))


def display_review_summary(domain_review: DomainReview, console: Console) -> None:
    """Display a summary of the review for a single domain.

    Shows total variables, approved/corrected/skipped/pending counts,
    and lists any corrections made.

    Args:
        domain_review: The DomainReview to summarize.
        console: Rich Console for output.
    """
    total = len(domain_review.original_spec.variable_mappings)
    approved = sum(1 for d in domain_review.decisions.values() if d.status == ReviewStatus.APPROVED)
    corrected = sum(
        1 for d in domain_review.decisions.values() if d.status == ReviewStatus.CORRECTED
    )
    skipped = sum(1 for d in domain_review.decisions.values() if d.status == ReviewStatus.SKIPPED)
    pending = total - approved - corrected - skipped

    lines = [
        f"[bold]Domain:[/bold] {domain_review.domain}",
        f"[bold]Status:[/bold] {domain_review.status.value}",
        f"[bold]Total Variables:[/bold] {total}",
        f"[green]Approved:[/green] {approved}",
        f"[yellow]Corrected:[/yellow] {corrected}",
        f"[dim]Skipped:[/dim] {skipped}",
        f"Pending: {pending}",
    ]

    if domain_review.corrections:
        lines.append("")
        lines.append("[bold]Corrections:[/bold]")
        for c in domain_review.corrections:
            lines.append(f"  {c.sdtm_variable} -> {c.correction_type.value}: {c.reason}")

    console.print(Panel("\n".join(lines), title=f"Review Summary: {domain_review.domain}"))


def display_session_list(sessions: list[dict], console: Console) -> None:
    """Display a table of review sessions.

    Shows session ID, study, status (color-coded), created/updated
    timestamps, and domain count.

    Args:
        sessions: List of session summary dicts from SessionStore.list_sessions().
        console: Rich Console for output.
    """
    table = Table(title="Review Sessions", show_lines=True)
    table.add_column("Session ID", style="bold cyan", no_wrap=True)
    table.add_column("Study", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Created", no_wrap=True)
    table.add_column("Updated", no_wrap=True)
    table.add_column("Domains", justify="right")

    for s in sessions:
        status_val = s.get("status", "")
        if status_val == "in_progress":
            status_text = Text("in_progress", style="yellow")
        elif status_val == "completed":
            status_text = Text("completed", style="green")
        elif status_val == "abandoned":
            status_text = Text("abandoned", style="red")
        else:
            status_text = Text(status_val)

        table.add_row(
            s.get("session_id", ""),
            s.get("study_id", ""),
            status_text,
            s.get("created_at", ""),
            s.get("updated_at", ""),
            str(s.get("domain_count", 0)),
        )

    console.print(table)

    if not sessions:
        console.print("[dim]No review sessions found.[/dim]")
