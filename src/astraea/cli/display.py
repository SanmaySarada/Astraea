"""Rich display helpers for terminal output.

Provides formatted display functions for dataset profiles, SDTM domain
specifications, and controlled terminology codelists using Rich tables
and panels.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from astraea.models.controlled_terms import Codelist
from astraea.models.profiling import DatasetProfile
from astraea.models.sdtm import CoreDesignation, DomainSpec, VariableSpec


def display_profile_summary(profiles: list[DatasetProfile], console: Console) -> None:
    """Print a summary table of all profiled datasets.

    Columns: Dataset, Rows, Columns, Clinical Cols, EDC Cols, Date Cols, Missing%

    Args:
        profiles: List of DatasetProfile objects.
        console: Rich Console for output.
    """
    table = Table(title="Dataset Summary", show_lines=True)
    table.add_column("Dataset", style="bold cyan", no_wrap=True)
    table.add_column("Rows", justify="right", style="green")
    table.add_column("Columns", justify="right")
    table.add_column("Clinical", justify="right", style="bold")
    table.add_column("EDC", justify="right", style="dim")
    table.add_column("Date", justify="right", style="yellow")
    table.add_column("Missing%", justify="right")

    for p in sorted(profiles, key=lambda x: x.filename):
        n_edc = len(p.edc_columns)
        n_clinical = p.col_count - n_edc
        n_date = len(p.date_variables)

        # Average missing percentage across clinical (non-EDC) variables
        clinical_vars = [v for v in p.variables if not v.is_edc_column]
        if clinical_vars:
            avg_missing = sum(v.missing_pct for v in clinical_vars) / len(clinical_vars)
        else:
            avg_missing = 0.0

        # Color-code missing percentage
        missing_str = f"{avg_missing:.1f}%"
        if avg_missing > 50:
            missing_style = "bold red"
        elif avg_missing > 20:
            missing_style = "yellow"
        else:
            missing_style = "green"

        table.add_row(
            p.filename.replace(".sas7bdat", ""),
            str(p.row_count),
            str(p.col_count),
            str(n_clinical),
            str(n_edc),
            str(n_date),
            Text(missing_str, style=missing_style),
        )

    console.print(table)
    console.print(
        f"\n[bold]{len(profiles)}[/bold] datasets profiled"
    )


def display_variable_detail(profile: DatasetProfile, console: Console) -> None:
    """Print variable-level detail for a single dataset.

    Shows: Variable, Label, Type, Format, Missing%, Unique, Top Values.
    EDC columns are dimmed. Date columns highlighted in yellow.

    Args:
        profile: DatasetProfile to display.
        console: Rich Console for output.
    """
    title = f"{profile.filename} ({profile.row_count} rows x {profile.col_count} cols)"
    table = Table(title=title, show_lines=True)
    table.add_column("Variable", style="bold", no_wrap=True)
    table.add_column("Label", max_width=35)
    table.add_column("Type", no_wrap=True)
    table.add_column("Format", no_wrap=True)
    table.add_column("Missing%", justify="right")
    table.add_column("Unique", justify="right")
    table.add_column("Top Values", max_width=40)

    for v in profile.variables:
        # Style based on column type
        if v.is_edc_column:
            row_style = "dim"
        elif v.is_date:
            row_style = "yellow"
        else:
            row_style = ""

        # Top values display
        if v.top_values:
            top_strs = [
                f"{tv.value} ({tv.count})" for tv in v.top_values[:3]
            ]
            top_display = ", ".join(top_strs)
        elif v.sample_values:
            top_display = ", ".join(v.sample_values[:3])
        else:
            top_display = ""

        table.add_row(
            v.name,
            v.label[:35] if v.label else "",
            v.dtype,
            v.sas_format or "",
            f"{v.missing_pct:.1f}%",
            str(v.n_unique),
            top_display,
            style=row_style,
        )

    console.print(table)


def display_domain_spec(spec: DomainSpec, console: Console) -> None:
    """Print an SDTM domain specification.

    Shows domain info (name, description, class, structure) and a
    variable table with core designations color-coded:
    Req=red, Exp=yellow, Perm=green.

    Args:
        spec: DomainSpec to display.
        console: Rich Console for output.
    """
    # Domain info panel
    info_lines = [
        f"[bold]Domain:[/bold] {spec.domain}",
        f"[bold]Description:[/bold] {spec.description}",
        f"[bold]Class:[/bold] {spec.domain_class.value}",
        f"[bold]Structure:[/bold] {spec.structure}",
    ]
    console.print(Panel("\n".join(info_lines), title=f"SDTM Domain: {spec.domain}"))

    # Variable table
    table = Table(title=f"{spec.domain} Variables", show_lines=True)
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Variable", style="bold cyan", no_wrap=True)
    table.add_column("Label", max_width=40)
    table.add_column("Type", no_wrap=True)
    table.add_column("Core", no_wrap=True)
    table.add_column("Codelist", no_wrap=True)

    for v in spec.variables:
        core_text = _format_core(v.core)
        codelist_str = v.codelist_code or ""

        table.add_row(
            str(v.order),
            v.name,
            v.label,
            v.data_type,
            core_text,
            codelist_str,
        )

    console.print(table)


def display_variable_spec(var: VariableSpec, domain: str, console: Console) -> None:
    """Print detail for a single SDTM variable.

    Args:
        var: VariableSpec to display.
        domain: Domain code the variable belongs to.
        console: Rich Console for output.
    """
    core_text = _format_core(var.core)
    info_lines = [
        f"[bold]Variable:[/bold] {var.name}",
        f"[bold]Domain:[/bold] {domain}",
        f"[bold]Label:[/bold] {var.label}",
        f"[bold]Type:[/bold] {var.data_type}",
        f"[bold]Core:[/bold] {core_text}",
        f"[bold]Order:[/bold] {var.order}",
    ]
    if var.codelist_code:
        info_lines.append(f"[bold]Codelist:[/bold] {var.codelist_code}")
    if var.cdisc_notes:
        info_lines.append(f"[bold]Notes:[/bold] {var.cdisc_notes}")

    console.print(Panel("\n".join(info_lines), title=f"{domain}.{var.name}"))


def display_codelist(codelist: Codelist, console: Console) -> None:
    """Print a controlled terminology codelist.

    Args:
        codelist: Codelist to display.
        console: Rich Console for output.
    """
    ext_str = "[green]Yes[/green]" if codelist.extensible else "[red]No[/red]"
    info_lines = [
        f"[bold]Code:[/bold] {codelist.code}",
        f"[bold]Name:[/bold] {codelist.name}",
        f"[bold]Extensible:[/bold] {ext_str}",
    ]
    if codelist.variable_mappings:
        info_lines.append(
            f"[bold]Variables:[/bold] {', '.join(codelist.variable_mappings)}"
        )

    console.print(Panel("\n".join(info_lines), title=f"Codelist: {codelist.code}"))

    # Terms table
    table = Table(title=f"{codelist.name} Terms ({len(codelist.terms)} terms)", show_lines=True)
    table.add_column("Submission Value", style="bold cyan")
    table.add_column("NCI Preferred Term")
    table.add_column("Definition", max_width=50)

    for sv, term in sorted(codelist.terms.items()):
        table.add_row(
            term.submission_value,
            term.nci_preferred_term,
            term.definition[:50] + "..." if len(term.definition) > 50 else term.definition,
        )

    console.print(table)


def _format_core(core: CoreDesignation) -> Text:
    """Format a core designation with color coding."""
    if core == CoreDesignation.REQ:
        return Text("Req", style="bold red")
    elif core == CoreDesignation.EXP:
        return Text("Exp", style="yellow")
    else:
        return Text("Perm", style="green")
