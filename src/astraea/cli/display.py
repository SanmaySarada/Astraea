"""Rich display helpers for terminal output.

Provides formatted display functions for dataset profiles, SDTM domain
specifications, controlled terminology codelists, validation reports,
and validation issues using Rich tables and panels.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from astraea.models.classification import ClassificationResult
from astraea.models.controlled_terms import Codelist
from astraea.models.ecrf import ECRFExtractionResult, ECRFForm
from astraea.models.mapping import ConfidenceLevel, DomainMappingSpec
from astraea.models.profiling import DatasetProfile
from astraea.models.sdtm import CoreDesignation, DomainSpec, VariableSpec
from astraea.validation.autofix import IssueClassification
from astraea.validation.fix_loop import FixLoopResult
from astraea.validation.report import ValidationReport
from astraea.validation.rules.base import RuleResult, RuleSeverity


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


def display_mapping_spec(spec: DomainMappingSpec, console: Console) -> None:
    """Print mapping specification results with Rich formatting.

    Shows a header panel with domain metadata, a variable mapping table
    with color-coded confidence, summary counts, unmapped/SUPPQUAL
    candidates, and output file paths.

    Args:
        spec: DomainMappingSpec to display.
        console: Rich Console for output.
    """
    # Header panel
    info_lines = [
        f"[bold]Domain:[/bold] {spec.domain} -- {spec.domain_label}",
        f"[bold]Study ID:[/bold] {spec.study_id}",
        f"[bold]Timestamp:[/bold] {spec.mapping_timestamp}",
        f"[bold]Model:[/bold] {spec.model_used}",
        f"[bold]Source:[/bold] {', '.join(spec.source_datasets)}",
    ]
    if spec.cross_domain_sources:
        info_lines.append(
            f"[bold]Cross-Domain:[/bold] {', '.join(spec.cross_domain_sources)}"
        )
    console.print(Panel("\n".join(info_lines), title=f"Mapping Spec: {spec.domain}"))

    # Variable mapping table
    table = Table(title=f"{spec.domain} Variable Mappings", show_lines=True)
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Variable", style="bold cyan", no_wrap=True)
    table.add_column("Label", max_width=30)
    table.add_column("Core", no_wrap=True)
    table.add_column("Source", no_wrap=True)
    table.add_column("Pattern", no_wrap=True)
    table.add_column("Confidence", justify="right")
    table.add_column("Logic", max_width=40)

    for idx, m in enumerate(spec.variable_mappings, start=1):
        core_text = _format_core(m.core)

        source_str = m.source_variable or ""
        if m.mapping_pattern.value == "assign" and m.assigned_value:
            source_str = f'="{m.assigned_value}"'

        conf_str = f"{m.confidence:.2f}"
        if m.confidence_level == ConfidenceLevel.HIGH:
            conf_text = Text(conf_str, style="green")
        elif m.confidence_level == ConfidenceLevel.MEDIUM:
            conf_text = Text(conf_str, style="yellow")
        else:
            conf_text = Text(conf_str, style="red")

        logic = m.mapping_logic
        if len(logic) > 40:
            logic = logic[:37] + "..."

        table.add_row(
            str(idx),
            m.sdtm_variable,
            m.sdtm_label[:30] if m.sdtm_label else "",
            core_text,
            source_str,
            m.mapping_pattern.value,
            conf_text,
            logic,
        )

    console.print(table)

    # Summary footer
    console.print(
        f"\n[bold]Total:[/bold] {spec.total_variables} variables mapped  "
        f"[green]HIGH: {spec.high_confidence_count}[/green]  "
        f"[yellow]MEDIUM: {spec.medium_confidence_count}[/yellow]  "
        f"[red]LOW: {spec.low_confidence_count}[/red]"
    )
    console.print(
        f"[bold]Required mapped:[/bold] {spec.required_mapped}  "
        f"[bold]Expected mapped:[/bold] {spec.expected_mapped}"
    )

    # Unmapped / SUPPQUAL candidates
    if spec.unmapped_source_variables:
        console.print(
            f"\n[dim]Unmapped source variables:[/dim] "
            f"{', '.join(spec.unmapped_source_variables)}"
        )
    if spec.suppqual_candidates:
        console.print(
            f"[dim]SUPPQUAL candidates:[/dim] "
            f"{', '.join(spec.suppqual_candidates)}"
        )


def display_validation_summary(
    report: ValidationReport, console: Console
) -> None:
    """Print a validation report summary with Rich formatting.

    Shows severity counts, pass rate, and submission readiness status
    in a structured table.

    Args:
        report: ValidationReport to display.
        console: Rich Console for output.
    """
    table = Table(title="Validation Summary", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Domains Validated", str(len(report.domains_validated)))
    table.add_row("Total Findings", str(report.total_rules_run))

    error_style = "bold red" if report.effective_error_count > 0 else "green"
    table.add_row(
        "Errors (effective)",
        Text(str(report.effective_error_count), style=error_style),
    )

    warn_style = "yellow" if report.effective_warning_count > 0 else "green"
    table.add_row(
        "Warnings (effective)",
        Text(str(report.effective_warning_count), style=warn_style),
    )

    table.add_row("Notices", str(report.notice_count))

    fp_count = len(report.known_false_positive_results)
    if fp_count > 0:
        table.add_row("Known False Positives", str(fp_count))

    table.add_row("Pass Rate", f"{report.pass_rate:.0%}")

    ready_text = (
        Text("READY", style="bold green")
        if report.submission_ready
        else Text("NOT READY", style="bold red")
    )
    table.add_row("Submission Status", ready_text)

    console.print(table)

    # Per-domain breakdown if available
    if report.summary_by_domain:
        domain_table = Table(title="Per-Domain Breakdown", show_lines=True)
        domain_table.add_column("Domain", style="bold cyan")
        domain_table.add_column("Errors", justify="right")
        domain_table.add_column("Warnings", justify="right")
        domain_table.add_column("Notices", justify="right")

        for domain_code in sorted(report.summary_by_domain):
            counts = report.summary_by_domain[domain_code]
            err_text = Text(
                str(counts["errors"]),
                style="bold red" if counts["errors"] > 0 else "green",
            )
            warn_text = Text(
                str(counts["warnings"]),
                style="yellow" if counts["warnings"] > 0 else "green",
            )
            domain_table.add_row(
                domain_code,
                err_text,
                warn_text,
                str(counts["notices"]),
            )

        console.print(domain_table)


def display_validation_issues(
    results: list[RuleResult],
    *,
    console: Console,
    limit: int = 20,
) -> None:
    """Print top validation issues sorted by severity.

    Shows the most important findings first (ERROR > WARNING > NOTICE),
    with secondary sort by affected count (descending).

    Args:
        results: List of RuleResult findings to display.
        console: Rich Console for output.
        limit: Maximum number of issues to show (default 20).
    """

    if not results:
        console.print("[dim]No validation issues found.[/dim]")
        return

    # Sort: ERROR first, then WARNING, then NOTICE, then by affected count desc
    sorted_results = sorted(
        results,
        key=lambda r: (
            0 if r.severity == RuleSeverity.ERROR else (
                1 if r.severity == RuleSeverity.WARNING else 2
            ),
            -r.affected_count,
        ),
    )

    # Filter out known false positives for display
    display_results = [r for r in sorted_results if not r.known_false_positive]
    display_results = display_results[:limit]

    table = Table(title=f"Top Issues ({len(display_results)} shown)", show_lines=True)
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Severity", no_wrap=True)
    table.add_column("Rule", style="bold", no_wrap=True)
    table.add_column("Domain", no_wrap=True)
    table.add_column("Variable", no_wrap=True)
    table.add_column("Message", max_width=50)

    for idx, r in enumerate(display_results, 1):
        if r.severity == RuleSeverity.ERROR:
            sev_text = Text("Error", style="bold red")
        elif r.severity == RuleSeverity.WARNING:
            sev_text = Text("Warning", style="yellow")
        else:
            sev_text = Text("Notice", style="dim")

        msg = r.message
        if len(msg) > 50:
            msg = msg[:47] + "..."

        table.add_row(
            str(idx),
            sev_text,
            r.rule_id,
            r.domain or "-",
            r.variable or "-",
            msg,
        )

    console.print(table)

    # Show count of suppressed false positives
    fp_count = sum(1 for r in sorted_results if r.known_false_positive)
    if fp_count > 0:
        console.print(
            f"[dim]{fp_count} known false positive(s) not shown[/dim]"
        )


def display_fix_loop_result(
    result: FixLoopResult,
    console: Console,
) -> None:
    """Print auto-fix loop results with Rich formatting.

    Shows a summary panel with iteration count, total fixes, and
    convergence status, followed by a per-iteration breakdown table
    and a table of applied fixes (first 10).

    Args:
        result: FixLoopResult from the fix loop engine.
        console: Rich Console for output.
    """
    # Summary panel
    converged_text = "[green]Yes[/green]" if result.converged else "[yellow]No[/yellow]"
    info_lines = [
        f"[bold]Iterations:[/bold] {result.iterations_run}/{result.max_iterations}",
        f"[bold]Total Fixed:[/bold] {result.total_fixed}",
        f"[bold]Converged:[/bold] {converged_text}",
        f"[bold]Remaining Issues:[/bold] {len(result.remaining_issues)}",
        f"[bold]Needs Human:[/bold] {len(result.needs_human_issues)}",
    ]
    console.print(Panel("\n".join(info_lines), title="Auto-Fix Results"))

    # Per-iteration breakdown
    if result.iteration_details:
        iter_table = Table(title="Per-Iteration Breakdown", show_lines=True)
        iter_table.add_column("Iteration", justify="right", style="bold")
        iter_table.add_column("Issues Found", justify="right")
        iter_table.add_column("Auto-Fixed", justify="right", style="green")
        iter_table.add_column("Remaining", justify="right")
        iter_table.add_column("Needs Human", justify="right", style="yellow")

        for detail in result.iteration_details:
            iter_table.add_row(
                str(detail.iteration),
                str(detail.issues_found),
                str(detail.auto_fixed),
                str(detail.remaining_auto_fixable),
                str(detail.needs_human),
            )

        console.print(iter_table)

    # Fixed issues table (first 10)
    if result.all_fix_actions:
        fix_table = Table(title="Fixed Issues", show_lines=True)
        fix_table.add_column("#", justify="right", style="dim", width=4)
        fix_table.add_column("Fix Type", style="bold cyan")
        fix_table.add_column("Domain", no_wrap=True)
        fix_table.add_column("Variable", no_wrap=True)
        fix_table.add_column("Before", max_width=30)
        fix_table.add_column("After", max_width=30)

        for idx, action in enumerate(result.all_fix_actions[:10], 1):
            before = action.before_value
            if len(before) > 30:
                before = before[:27] + "..."
            after = action.after_value
            if len(after) > 30:
                after = after[:27] + "..."

            fix_table.add_row(
                str(idx),
                action.fix_type,
                action.domain,
                action.variable or "-",
                before,
                after,
            )

        console.print(fix_table)

        if len(result.all_fix_actions) > 10:
            console.print(
                f"[dim]...and {len(result.all_fix_actions) - 10} more fix(es) "
                f"(see autofix_audit.json for full audit trail)[/dim]"
            )


def display_needs_human(
    issues: list[IssueClassification],
    console: Console,
) -> None:
    """Print issues requiring human review with Rich formatting.

    Groups issues by domain and displays each with severity color-coding,
    rule ID, variable, message, and suggested fix.

    Args:
        issues: List of IssueClassification items (needs-human only).
        console: Rich Console for output.
    """

    if not issues:
        console.print("[dim]No issues requiring human review.[/dim]")
        return

    # Group by domain
    by_domain: dict[str, list] = {}
    for ic in issues:
        domain = ic.result.domain or "GENERAL"
        by_domain.setdefault(domain, []).append(ic)

    table = Table(
        title=f"Issues Requiring Human Review ({len(issues)} total)",
        show_lines=True,
    )
    table.add_column("Severity", no_wrap=True)
    table.add_column("Rule", style="bold", no_wrap=True)
    table.add_column("Domain", no_wrap=True)
    table.add_column("Variable", no_wrap=True)
    table.add_column("Message", max_width=40)
    table.add_column("Suggested Fix", max_width=35)

    for domain in sorted(by_domain):
        for ic in by_domain[domain]:
            r = ic.result
            if r.severity == RuleSeverity.ERROR:
                sev_text = Text("Error", style="bold red")
            elif r.severity == RuleSeverity.WARNING:
                sev_text = Text("Warning", style="yellow")
            else:
                sev_text = Text("Notice", style="dim")

            msg = r.message
            if len(msg) > 40:
                msg = msg[:37] + "..."

            suggested = ic.suggested_fix or ""
            if len(suggested) > 35:
                suggested = suggested[:32] + "..."

            table.add_row(
                sev_text,
                r.rule_id,
                r.domain or "-",
                r.variable or "-",
                msg,
                suggested,
            )

    console.print(
        Panel(table, title="Issues Requiring Human Review", border_style="yellow")
    )


def display_learning_stats(
    report: dict,
    example_count: int,
    correction_count: int,
    console: Console,
) -> None:
    """Display learning system statistics with Rich formatting.

    Shows overall counts, per-domain accuracy table with trends,
    and improvement summary.

    Args:
        report: Output of compute_improvement_report().
        example_count: Total number of mapping examples.
        correction_count: Total number of corrections.
        console: Rich Console for output.
    """
    # Summary panel
    overall_accuracy = report.get("overall_accuracy", 0.0)
    info_lines = [
        f"[bold]Total Examples:[/bold] {example_count}",
        f"[bold]Total Corrections:[/bold] {correction_count}",
        f"[bold]Overall Accuracy:[/bold] {overall_accuracy:.1%}",
    ]
    console.print(Panel("\n".join(info_lines), title="Learning System Stats"))

    # Per-domain table
    by_domain = report.get("by_domain", {})
    if by_domain:
        table = Table(title="Per-Domain Accuracy", show_lines=True)
        table.add_column("Domain", style="bold cyan", no_wrap=True)
        table.add_column("Studies", justify="right")
        table.add_column("First", justify="right")
        table.add_column("Latest", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("Trend", no_wrap=True)

        for domain in sorted(by_domain):
            info = by_domain[domain]
            improvement = info.get("improvement", 0.0)

            if improvement > 0:
                change_text = Text(f"+{improvement:.1%}", style="green")
                trend_text = Text("improving", style="green")
            elif improvement < 0:
                change_text = Text(f"{improvement:.1%}", style="red")
                trend_text = Text("declining", style="red")
            else:
                change_text = Text("0.0%", style="dim")
                trend_text = Text("stable", style="dim")

            table.add_row(
                domain,
                str(info.get("studies", 0)),
                f"{info.get('first', 0.0):.1%}",
                f"{info.get('latest', 0.0):.1%}",
                change_text,
                trend_text,
            )

        console.print(table)
    else:
        console.print("[dim]No domain accuracy data available yet.[/dim]")


def display_ingestion_result(
    total_examples: int,
    total_corrections: int,
    domains: list[str],
    console: Console,
) -> None:
    """Display ingestion results with Rich formatting.

    Shows a simple panel summarizing what was ingested.

    Args:
        total_examples: Number of mapping examples ingested.
        total_corrections: Number of corrections ingested.
        domains: List of domain codes that were ingested.
        console: Rich Console for output.
    """
    unique_domains = sorted(set(domains))
    info_lines = [
        f"[bold]Examples Ingested:[/bold] {total_examples}",
        f"[bold]Corrections Ingested:[/bold] {total_corrections}",
        f"[bold]Domains:[/bold] {', '.join(unique_domains) if unique_domains else 'None'}",
    ]
    console.print(Panel("\n".join(info_lines), title="Ingestion Complete"))


def _format_core(core: CoreDesignation) -> Text:
    """Format a core designation with color coding."""
    if core == CoreDesignation.REQ:
        return Text("Req", style="bold red")
    elif core == CoreDesignation.EXP:
        return Text("Exp", style="yellow")
    else:
        return Text("Perm", style="green")
