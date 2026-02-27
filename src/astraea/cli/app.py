"""Astraea CLI application entry point.

Provides commands for profiling SAS datasets, querying SDTM-IG domain
specifications, looking up CDISC controlled terminology, parsing eCRF PDFs,
and classifying raw datasets to SDTM domains.

Usage:
    astraea profile <data-folder>
    astraea reference <domain>
    astraea codelist <code>
    astraea parse-ecrf <ecrf-path>
    astraea classify <data-dir>
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
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
        Path | None,
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
    for _name, (df, meta) in sorted(datasets.items()):
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
        str | None,
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
        str | None,
        typer.Argument(help="Codelist code (e.g., C66731) or omit to list all"),
    ] = None,
    variable: Annotated[
        str | None,
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


def _check_api_key() -> bool:
    """Check if ANTHROPIC_API_KEY is set. Print error and return False if not."""
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print(
            "[bold red]Error:[/bold red] ANTHROPIC_API_KEY environment variable is not set.\n"
            "Set it with: [bold]export ANTHROPIC_API_KEY=sk-...[/bold]"
        )
        return False
    return True


@app.command(name="parse-ecrf")
def parse_ecrf_cmd(
    ecrf_path: Annotated[
        Path,
        typer.Argument(help="Path to eCRF PDF file"),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Save extraction result as JSON"),
    ] = None,
    detail: Annotated[
        bool,
        typer.Option("--detail", "-d", help="Show field-level detail for each form"),
    ] = False,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Directory for caching extraction results"),
    ] = None,
) -> None:
    """Parse an eCRF PDF and extract structured form metadata.

    Extracts form definitions, field names, data types, SAS labels, and coded
    values from an annotated eCRF PDF using LLM-based structured extraction.

    Requires ANTHROPIC_API_KEY to be set.
    """
    from astraea.cli.display import display_ecrf_form_detail, display_ecrf_summary
    from astraea.parsing.ecrf_parser import (
        load_extraction,
        parse_ecrf,
        save_extraction,
    )

    # Validate path
    if not ecrf_path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {ecrf_path}")
        raise typer.Exit(code=1)
    if ecrf_path.suffix.lower() != ".pdf":
        console.print(f"[bold red]Error:[/bold red] Expected a PDF file, got: {ecrf_path.suffix}")
        raise typer.Exit(code=1)

    # Check for cached result
    if cache_dir is not None:
        cache_file = cache_dir / f"{ecrf_path.stem}_extraction.json"
        if cache_file.exists():
            console.print(f"[bold blue]Loading cached extraction from {cache_file}[/bold blue]")
            try:
                result = load_extraction(cache_file)
                console.print()
                display_ecrf_summary(result, console)
                if detail:
                    for form in sorted(result.forms, key=lambda f: f.form_name):
                        console.print()
                        display_ecrf_form_detail(form, console)
                if output is not None:
                    output.write_text(result.model_dump_json(indent=2))
                    console.print(f"\n[green]Extraction saved to {output}[/green]")
                return
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load cache: {e}[/yellow]")

    # API key required for fresh extraction
    if not _check_api_key():
        raise typer.Exit(code=1)

    # Step 1: Extract PDF
    console.print("\n[bold blue][1/2][/bold blue] Extracting PDF...")
    from astraea.parsing.pdf_extractor import extract_ecrf_pages, group_pages_by_form

    try:
        pages = extract_ecrf_pages(ecrf_path)
        form_groups = group_pages_by_form(pages)
        n_forms = len({k for k in form_groups if k not in {"HEADER", "UNKNOWN"}})
    except Exception as e:
        console.print(f"[bold red]Error extracting PDF:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    # Step 2: Parse forms (pass pre-extracted pages to avoid double extraction)
    console.print(f"[bold blue][2/2][/bold blue] Parsing {n_forms} forms...")
    try:
        result = parse_ecrf(ecrf_path, pre_extracted_pages=pages)
    except Exception as e:
        console.print(f"[bold red]Error parsing eCRF:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    # Display results
    console.print()
    display_ecrf_summary(result, console)

    if detail:
        for form in sorted(result.forms, key=lambda f: f.form_name):
            console.print()
            display_ecrf_form_detail(form, console)

    # Save output
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.model_dump_json(indent=2))
        console.print(f"\n[green]Extraction saved to {output}[/green]")

    # Cache result
    if cache_dir is not None:
        cache_file = cache_dir / f"{ecrf_path.stem}_extraction.json"
        save_extraction(result, cache_file)
        console.print(f"[dim]Cached to {cache_file}[/dim]")


@app.command()
def classify(
    data_dir: Annotated[
        Path,
        typer.Argument(help="Directory containing .sas7bdat files"),
    ],
    ecrf: Annotated[
        Path | None,
        typer.Option("--ecrf", help="Path to eCRF PDF for enhanced classification"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Save classification result as JSON"),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Directory for caching results"),
    ] = None,
) -> None:
    """Classify raw SAS datasets to SDTM domains.

    Profiles all .sas7bdat files and classifies each to an SDTM domain using
    heuristic analysis and LLM-based semantic matching.

    If --ecrf is provided, parses the eCRF PDF (or loads cached result) and
    uses form-dataset matching for better classification context.

    Requires ANTHROPIC_API_KEY to be set.
    """
    from astraea.classification.classifier import (
        classify_all,
        load_classification,
        save_classification,
    )
    from astraea.cli.display import display_classification
    from astraea.io.sas_reader import read_all_sas_files
    from astraea.models.profiling import DatasetProfile
    from astraea.parsing.ecrf_parser import load_extraction, parse_ecrf
    from astraea.parsing.form_dataset_matcher import match_all_forms
    from astraea.profiling.profiler import profile_dataset

    # Validate directory
    if not data_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] Directory not found: {data_dir}")
        raise typer.Exit(code=1)

    sas_files = list(data_dir.glob("*.sas7bdat"))
    if not sas_files:
        console.print(f"[bold red]Error:[/bold red] No .sas7bdat files found in {data_dir}")
        raise typer.Exit(code=1)

    # Check for cached classification result
    if cache_dir is not None:
        cache_file = cache_dir / "classification.json"
        if cache_file.exists():
            console.print(f"[bold blue]Loading cached classification from {cache_file}[/bold blue]")
            try:
                result = load_classification(cache_file)
                console.print()
                display_classification(result, console)
                if output is not None:
                    output.write_text(result.model_dump_json(indent=2))
                    console.print(f"\n[green]Classification saved to {output}[/green]")
                return
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load cache: {e}[/yellow]")

    # API key required for fresh classification
    if not _check_api_key():
        raise typer.Exit(code=1)

    # Step 1: Profile datasets
    console.print(f"\n[bold blue][1/3][/bold blue] Profiling {len(sas_files)} datasets...")
    try:
        datasets = read_all_sas_files(data_dir)
    except Exception as e:
        console.print(f"[bold red]Error reading SAS files:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    profiles: list[DatasetProfile] = []
    for _name, (df, meta) in sorted(datasets.items()):
        p = profile_dataset(df, meta)
        profiles.append(p)

    # Handle eCRF context
    ecrf_result = None
    form_matches = None
    if ecrf is not None:
        if not ecrf.exists():
            console.print(f"[bold red]Error:[/bold red] eCRF file not found: {ecrf}")
            raise typer.Exit(code=1)

        # Try loading cached eCRF extraction
        if cache_dir is not None:
            ecrf_cache = cache_dir / f"{ecrf.stem}_extraction.json"
            if ecrf_cache.exists():
                console.print("[dim]Loading cached eCRF extraction...[/dim]")
                try:
                    ecrf_result = load_extraction(ecrf_cache)
                except Exception:
                    ecrf_result = None

        if ecrf_result is None:
            console.print("[bold blue]Parsing eCRF PDF...[/bold blue]")
            try:
                ecrf_result = parse_ecrf(ecrf)
            except Exception as e:
                console.print(f"[yellow]Warning: eCRF parsing failed: {e}[/yellow]")
                console.print("[dim]Continuing without eCRF context...[/dim]")

        if ecrf_result is not None:
            form_matches = match_all_forms(ecrf_result.forms, profiles)

    # Step 2: Classify
    console.print(f"[bold blue][2/3][/bold blue] Classifying {len(profiles)} datasets...")
    try:
        result = classify_all(
            profiles=profiles,
            ecrf_result=ecrf_result,
            form_matches=form_matches,
        )
    except Exception as e:
        console.print(f"[bold red]Error during classification:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    # Step 3: Display
    console.print("[bold blue][3/3][/bold blue] Detecting merge groups...")
    console.print()
    display_classification(result, console)

    # Save output
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.model_dump_json(indent=2))
        console.print(f"\n[green]Classification saved to {output}[/green]")

    # Cache result
    if cache_dir is not None:
        cache_file = cache_dir / "classification.json"
        save_classification(result, cache_file)
        console.print(f"[dim]Cached to {cache_file}[/dim]")
