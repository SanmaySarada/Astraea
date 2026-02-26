"""Astraea CLI application entry point.

Provides commands for profiling SAS datasets, querying SDTM-IG domain
specifications, and looking up CDISC controlled terminology.

Usage:
    astraea profile <data-folder>
    astraea reference <domain>
    astraea codelist <code>
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from loguru import logger
from rich.console import Console

app = typer.Typer(
    name="astraea",
    help="Agentic AI system for mapping raw clinical trial data to CDISC SDTM format.",
    no_args_is_help=True,
)

console = Console()


@app.command()
def version() -> None:
    """Show the current version."""
    from astraea import __version__

    console.print(f"astraea-sdtm {__version__}")


@app.command()
def profile(
    data_dir: Annotated[
        Path,
        typer.Argument(help="Directory containing .sas7bdat files"),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Write profiles as JSON to this file"),
    ] = None,
    detail: Annotated[
        bool,
        typer.Option("--detail", "-d", help="Show variable-level detail for each dataset"),
    ] = False,
) -> None:
    """Profile SAS datasets in a directory.

    Reads all .sas7bdat files, computes statistics, detects EDC columns
    and date variables, and displays a summary table.
    """
    from astraea.cli.display import display_profile_summary, display_variable_detail
    from astraea.io.sas_reader import read_all_sas_files
    from astraea.profiling.profiler import profile_dataset

    # Validate directory
    if not data_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] Directory not found: {data_dir}")
        raise typer.Exit(code=1)

    sas_files = list(data_dir.glob("*.sas7bdat"))
    if not sas_files:
        console.print(f"[bold red]Error:[/bold red] No .sas7bdat files found in {data_dir}")
        raise typer.Exit(code=1)

    # Stage 1: Read SAS files
    console.print(f"\n[bold blue][1/2][/bold blue] Reading {len(sas_files)} SAS files...")
    try:
        datasets = read_all_sas_files(data_dir)
    except Exception as e:
        console.print(f"[bold red]Error reading SAS files:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    # Stage 2: Profile datasets
    console.print(f"[bold blue][2/2][/bold blue] Profiling {len(datasets)} datasets...")
    from astraea.models.profiling import DatasetProfile

    profiles: list[DatasetProfile] = []
    for name, (df, meta) in sorted(datasets.items()):
        p = profile_dataset(df, meta)
        profiles.append(p)

    # Display summary
    console.print()
    display_profile_summary(profiles, console)

    # Display detail if requested
    if detail:
        for p in sorted(profiles, key=lambda x: x.filename):
            console.print()
            display_variable_detail(p, console)

    # Write JSON if requested
    if output is not None:
        import json

        json_data = [p.model_dump() for p in profiles]
        output.write_text(json.dumps(json_data, indent=2, default=str))
        console.print(f"\n[green]Profiles written to {output}[/green]")


@app.command()
def reference(
    domain: Annotated[
        str,
        typer.Argument(help="SDTM domain code (e.g., DM, AE, LB)"),
    ],
    variable: Annotated[
        Optional[str],
        typer.Option("--variable", "-v", help="Show detail for a specific variable"),
    ] = None,
) -> None:
    """Query SDTM-IG domain specifications.

    Shows the complete variable list for a domain, or detail for a
    single variable if --variable is provided.
    """
    from astraea.cli.display import display_domain_spec, display_variable_spec
    from astraea.reference import load_sdtm_reference

    ref = load_sdtm_reference()
    spec = ref.get_domain_spec(domain)

    if spec is None:
        console.print(
            f"[bold red]Error:[/bold red] Domain '{domain.upper()}' not found."
        )
        available = ref.list_domains()
        console.print(f"Available domains: {', '.join(available)}")
        raise typer.Exit(code=1)

    if variable is not None:
        var_spec = ref.get_variable_spec(domain, variable)
        if var_spec is None:
            console.print(
                f"[bold red]Error:[/bold red] Variable '{variable.upper()}' "
                f"not found in domain {domain.upper()}."
            )
            var_names = [v.name for v in spec.variables]
            console.print(f"Available variables: {', '.join(var_names)}")
            raise typer.Exit(code=1)
        display_variable_spec(var_spec, domain.upper(), console)
    else:
        display_domain_spec(spec, console)


@app.command()
def codelist(
    code: Annotated[
        Optional[str],
        typer.Argument(help="Codelist code (e.g., C66731) or omit to list all"),
    ] = None,
    variable: Annotated[
        Optional[str],
        typer.Option("--variable", "-v", help="Look up codelist by SDTM variable name"),
    ] = None,
) -> None:
    """Query CDISC controlled terminology codelists.

    Provide a codelist code to see its terms, or --variable to look up
    by SDTM variable name. With no arguments, lists all available codelists.
    """
    from astraea.cli.display import display_codelist
    from astraea.reference import load_ct_reference

    ct = load_ct_reference()

    if variable is not None:
        cl = ct.get_codelist_for_variable(variable)
        if cl is None:
            console.print(
                f"[bold red]Error:[/bold red] No codelist found for variable "
                f"'{variable.upper()}'."
            )
            raise typer.Exit(code=1)
        display_codelist(cl, console)
        return

    if code is not None:
        cl = ct.lookup_codelist(code)
        if cl is None:
            console.print(
                f"[bold red]Error:[/bold red] Codelist '{code}' not found."
            )
            available = ct.list_codelists()
            console.print(f"Available codelists: {', '.join(available[:20])}...")
            raise typer.Exit(code=1)
        display_codelist(cl, console)
        return

    # List all codelists
    all_codes = ct.list_codelists()
    table_widget = __import__("rich.table", fromlist=["Table"]).Table(
        title=f"Available Codelists ({len(all_codes)})", show_lines=False
    )
    table_widget.add_column("Code", style="bold cyan")
    table_widget.add_column("Name")
    table_widget.add_column("Extensible")
    table_widget.add_column("Terms", justify="right")

    for c in all_codes:
        cl = ct.lookup_codelist(c)
        if cl:
            ext = "[green]Yes[/green]" if cl.extensible else "[red]No[/red]"
            table_widget.add_row(cl.code, cl.name, ext, str(len(cl.terms)))

    console.print(table_widget)
