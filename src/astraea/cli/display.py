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

from astraea.models.classification import ClassificationResult
from astraea.models.controlled_terms import Codelist
from astraea.models.ecrf import ECRFExtractionResult, ECRFForm
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

    for _sv, term in sorted(codelist.terms.items()):
        table.add_row(
            term.submission_value,
            term.nci_preferred_term,
            term.definition[:50] + "..." if len(term.definition) > 50 else term.definition,
        )

    console.print(table)


def display_ecrf_summary(
    result: ECRFExtractionResult, console: Console
) -> None:
    """Print a summary table of eCRF extraction results.

    Columns: Form Name, Fields, Page Range.

    Args:
        result: ECRFExtractionResult from eCRF parsing.
        console: Rich Console for output.
    """
    table = Table(title="eCRF Extraction Summary", show_lines=True)
    table.add_column("Form Name", style="bold cyan", no_wrap=True)
    table.add_column("Fields", justify="right", style="green")
    table.add_column("Page Range", style="dim")

    for form in sorted(result.forms, key=lambda f: f.form_name):
        field_count = str(len(form.fields))
        if form.page_numbers:
            pages = sorted(form.page_numbers)
            page_range = str(pages[0]) if len(pages) == 1 else f"{pages[0]}-{pages[-1]}"
        else:
            page_range = ""

        table.add_row(form.form_name, field_count, page_range)

    console.print(table)
    console.print(
        f"\n[bold]Total:[/bold] {len(result.forms)} forms, "
        f"{result.total_fields} fields"
    )


def display_ecrf_form_detail(form: ECRFForm, console: Console) -> None:
    """Print field-level detail for a single eCRF form.

    Shows: #, Field Name, Type, SAS Label, Coded Values.

    Args:
        form: ECRFForm to display.
        console: Rich Console for output.
    """
    table = Table(
        title=f"{form.form_name} ({len(form.fields)} fields)", show_lines=True
    )
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Field Name", style="bold cyan", no_wrap=True)
    table.add_column("Type", no_wrap=True)
    table.add_column("SAS Label", max_width=40)
    table.add_column("Coded Values", max_width=35)

    for field in form.fields:
        coded_str = ""
        if field.coded_values:
            parts = [f"{k}={v}" for k, v in field.coded_values.items()]
            coded_str = ", ".join(parts)
            if len(coded_str) > 35:
                coded_str = coded_str[:32] + "..."

        table.add_row(
            str(field.field_number),
            field.field_name,
            field.data_type,
            field.sas_label,
            coded_str,
        )

    console.print(table)


def display_classification(
    result: ClassificationResult, console: Console
) -> None:
    """Print domain classification results.

    Shows: Dataset, Domain, Confidence, Reasoning. Confidence is color-coded:
    >=0.8 green, 0.5-0.8 yellow, <0.5 red. UNCLASSIFIED datasets in bold red.

    After the main table, shows merge groups if any DomainPlans have >1
    source dataset.

    Args:
        result: ClassificationResult from domain classification.
        console: Rich Console for output.
    """
    table = Table(title="Domain Classification", show_lines=True)
    table.add_column("Dataset", style="bold cyan", no_wrap=True)
    table.add_column("Domain", no_wrap=True)
    table.add_column("Confidence", justify="right")
    table.add_column("Reasoning", max_width=50)

    for cls in sorted(result.classifications, key=lambda c: c.raw_dataset):
        dataset_name = cls.raw_dataset.replace(".sas7bdat", "")

        if cls.primary_domain == "UNCLASSIFIED":
            domain_text = Text("UNCLASSIFIED", style="bold red")
        else:
            domain_text = Text(cls.primary_domain)

        conf_val = cls.confidence
        conf_str = f"{conf_val:.2f}"
        if conf_val >= 0.8:
            conf_text = Text(conf_str, style="green")
        elif conf_val >= 0.5:
            conf_text = Text(conf_str, style="yellow")
        else:
            conf_text = Text(conf_str, style="red")

        reasoning = cls.reasoning
        if len(reasoning) > 50:
            reasoning = reasoning[:47] + "..."

        table.add_row(dataset_name, domain_text, conf_text, reasoning)

    console.print(table)

    classified_count = len(result.classifications) - len(result.unclassified_datasets)
    console.print(
        f"\n[bold]{classified_count}[/bold] classified, "
        f"[bold]{len(result.unclassified_datasets)}[/bold] unclassified"
    )

    # Show merge groups
    merge_plans = [p for p in result.domain_plans if len(p.source_datasets) > 1]
    if merge_plans:
        lines: list[str] = []
        for plan in sorted(merge_plans, key=lambda p: p.domain):
            datasets = ", ".join(
                d.replace(".sas7bdat", "") for d in plan.source_datasets
            )
            lines.append(
                f"[bold]{plan.domain}[/bold] ({plan.mapping_pattern}): {datasets}"
            )
        console.print(
            Panel("\n".join(lines), title="Merge Groups", border_style="blue")
        )


def _format_core(core: CoreDesignation) -> Text:
    """Format a core designation with color coding."""
    if core == CoreDesignation.REQ:
        return Text("Req", style="bold red")
    elif core == CoreDesignation.EXP:
        return Text("Exp", style="yellow")
    else:
        return Text("Perm", style="green")
