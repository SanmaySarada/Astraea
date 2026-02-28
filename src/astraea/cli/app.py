"""Astraea CLI application entry point.

Provides commands for profiling SAS datasets, querying SDTM-IG domain
specifications, looking up CDISC controlled terminology, parsing eCRF PDFs,
classifying raw datasets to SDTM domains, reviewing mapping specifications,
executing mapping specs to produce SDTM XPT files, running SDTM validation,
and generating submission artifacts (define.xml, cSDRG).

Usage:
    astraea profile <data-folder>
    astraea reference <domain>
    astraea codelist <code>
    astraea parse-ecrf <ecrf-path>
    astraea classify <data-dir>
    astraea map-domain <data-folder> <ecrf-pdf> <domain>
    astraea review-domain <spec-file>
    astraea resume [session-id]
    astraea sessions
    astraea execute-domain <spec-path> <data-dir>
    astraea validate <output-dir>
    astraea generate-define <output-dir>
    astraea generate-csdrg <output-dir>
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console

if TYPE_CHECKING:
    from astraea.models.mapping import DomainMappingSpec
    from astraea.review.models import ReviewDecision

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


# Cross-domain dataset lookup for mapping
_CROSS_DOMAIN_DATASETS: dict[str, list[str]] = {
    "DM": ["ex", "ie", "irt", "ds"],
}


@app.command(name="map-domain")
def map_domain(
    data_folder: Annotated[
        Path,
        typer.Argument(help="Folder containing raw SAS files"),
    ],
    ecrf_pdf: Annotated[
        Path,
        typer.Argument(help="Path to annotated eCRF PDF"),
    ],
    domain: Annotated[
        str,
        typer.Argument(help="SDTM domain to map (e.g., 'DM')"),
    ],
    study_id: Annotated[
        str,
        typer.Option("--study-id", help="Study identifier"),
    ] = "PHA022121-C301",
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Output directory for mapping spec"),
    ] = Path("output"),
    source_file: Annotated[
        str | None,
        typer.Option(
            "--source-file",
            help=(
                "Override primary SAS file name (e.g., 'dm.sas7bdat'). "
                "Default: auto-detect by domain name."
            ),
        ),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Directory for caching eCRF extraction"),
    ] = None,
) -> None:
    """Map a raw SAS dataset to an SDTM domain.

    Profiles the primary SAS file, parses the eCRF, calls the LLM-based
    mapping engine, and exports results to JSON and Excel.

    The primary SAS file is auto-detected from the domain name (e.g., DM
    looks for dm.sas7bdat). Use --source-file to override.

    Requires ANTHROPIC_API_KEY to be set.
    """
    from astraea.cli.display import display_mapping_spec
    from astraea.io.sas_reader import read_sas_with_metadata
    from astraea.llm.client import AstraeaLLMClient
    from astraea.mapping.engine import MappingEngine
    from astraea.mapping.exporters import export_to_excel, export_to_json
    from astraea.models.mapping import StudyMetadata
    from astraea.models.profiling import DatasetProfile
    from astraea.parsing.ecrf_parser import load_extraction, parse_ecrf
    from astraea.parsing.form_dataset_matcher import match_all_forms
    from astraea.profiling.profiler import profile_dataset
    from astraea.reference import load_ct_reference, load_sdtm_reference

    # Validate inputs
    if not data_folder.is_dir():
        console.print(f"[bold red]Error:[/bold red] Directory not found: {data_folder}")
        raise typer.Exit(code=1)
    if not ecrf_pdf.exists():
        console.print(f"[bold red]Error:[/bold red] eCRF file not found: {ecrf_pdf}")
        raise typer.Exit(code=1)

    # API key required
    if not _check_api_key():
        raise typer.Exit(code=1)

    domain_upper = domain.upper()

    # Step 1: Identify primary SAS file
    primary_sas = _find_primary_sas(data_folder, domain_upper, source_file)
    if primary_sas is None:
        raise typer.Exit(code=1)

    console.print(
        f"\n[bold blue][1/5][/bold blue] Profiling primary dataset: "
        f"[cyan]{primary_sas.name}[/cyan]"
    )
    try:
        df, meta = read_sas_with_metadata(primary_sas)
        primary_profile = profile_dataset(df, meta)
    except Exception as e:
        console.print(f"[bold red]Error profiling {primary_sas.name}:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    # Step 2: Profile cross-domain datasets
    cross_domain_profiles: dict[str, DatasetProfile] = {}
    cross_domain_names = _CROSS_DOMAIN_DATASETS.get(domain_upper, [])
    if cross_domain_names:
        console.print(
            f"[bold blue][2/5][/bold blue] Profiling cross-domain sources: "
            f"{', '.join(cross_domain_names)}"
        )
        for cd_name in cross_domain_names:
            cd_path = data_folder / f"{cd_name.lower()}.sas7bdat"
            if cd_path.exists():
                try:
                    cd_df, cd_meta = read_sas_with_metadata(cd_path)
                    cross_domain_profiles[cd_name] = profile_dataset(cd_df, cd_meta)
                except Exception as e:
                    console.print(
                        f"[yellow]Warning: Could not profile {cd_name}: {e}[/yellow]"
                    )
    else:
        console.print("[bold blue][2/5][/bold blue] No cross-domain sources for this domain")

    # Step 3: Parse eCRF
    console.print("[bold blue][3/5][/bold blue] Parsing eCRF...")
    ecrf_result = None
    form_matches = None

    # Try cache first
    if cache_dir is not None:
        ecrf_cache = cache_dir / f"{ecrf_pdf.stem}_extraction.json"
        if ecrf_cache.exists():
            console.print(f"[dim]Loading cached eCRF extraction from {ecrf_cache}[/dim]")
            try:
                ecrf_result = load_extraction(ecrf_cache)
            except Exception:
                ecrf_result = None

    if ecrf_result is None:
        try:
            ecrf_result = parse_ecrf(ecrf_pdf)
        except Exception as e:
            console.print(f"[yellow]Warning: eCRF parsing failed: {e}[/yellow]")
            console.print("[dim]Continuing without eCRF context...[/dim]")

    # Match forms to the primary profile
    ecrf_forms = []
    if ecrf_result is not None:
        form_matches = match_all_forms(ecrf_result.forms, [primary_profile])
        # Find forms that match this domain's primary dataset
        for form_name, matches in form_matches.items():
            for match_file, _score in matches:
                if match_file == primary_profile.filename:
                    # Find the form object
                    for form in ecrf_result.forms:
                        if form.form_name == form_name:
                            ecrf_forms.append(form)
                            break

    # Step 4: Run mapping engine
    console.print(
        f"[bold blue][4/5][/bold blue] Mapping domain [bold]{domain_upper}[/bold]..."
    )
    try:
        sdtm_ref = load_sdtm_reference()
        ct_ref = load_ct_reference()
        llm_client = AstraeaLLMClient()
        engine = MappingEngine(llm_client, sdtm_ref, ct_ref)

        study_meta = StudyMetadata(study_id=study_id)
        spec = engine.map_domain(
            domain=domain_upper,
            source_profiles=[primary_profile],
            ecrf_forms=ecrf_forms,
            study_metadata=study_meta,
            cross_domain_profiles=cross_domain_profiles if cross_domain_profiles else None,
        )
    except Exception as e:
        console.print(f"[bold red]Error during mapping:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    # Step 5: Export and display
    console.print("[bold blue][5/5][/bold blue] Exporting results...")
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = export_to_json(spec, output_dir / f"{domain_upper}_mapping.json")
    excel_path = export_to_excel(spec, output_dir / f"{domain_upper}_mapping.xlsx")

    console.print()
    display_mapping_spec(spec, console)

    console.print(f"\n[green]JSON saved to:[/green]  {json_path}")
    console.print(f"[green]Excel saved to:[/green] {excel_path}")


@app.command(name="execute-domain")
def execute_domain(
    spec_path: Annotated[
        Path,
        typer.Argument(help="Path to mapping spec JSON file"),
    ],
    data_dir: Annotated[
        Path,
        typer.Argument(help="Path to raw data directory"),
    ],
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Output directory for XPT files"),
    ] = Path("output"),
    dm_path: Annotated[
        Path | None,
        typer.Option(
            "--dm-path",
            help="Path to DM dataset (for RFSTDTC cross-domain context)",
        ),
    ] = None,
) -> None:
    """Execute a mapping spec against raw data to produce an SDTM XPT file.

    Loads a mapping specification JSON (from map-domain or review-domain),
    reads the raw SAS source files, executes the mapping, and writes the
    resulting SDTM dataset as an XPT v5 file.

    Optionally provide --dm-path to enable cross-domain features like
    study day (--DY) derivation using RFSTDTC from the DM domain.
    """
    from astraea.execution.executor import CrossDomainContext, DatasetExecutor
    from astraea.io.sas_reader import read_sas_with_metadata
    from astraea.models.mapping import DomainMappingSpec
    from astraea.reference import load_ct_reference, load_sdtm_reference

    # Validate spec file
    if not spec_path.exists():
        console.print(f"[bold red]Error:[/bold red] Spec file not found: {spec_path}")
        raise typer.Exit(code=1)

    # Validate data directory
    if not data_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] Directory not found: {data_dir}")
        raise typer.Exit(code=1)

    # Step 1: Load spec
    console.print("[bold blue][1/4][/bold blue] Loading mapping specification...")
    try:
        spec = DomainMappingSpec.model_validate_json(spec_path.read_text())
    except Exception as e:
        console.print(f"[bold red]Error loading spec:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    domain = spec.domain.upper()
    console.print(
        f"  Domain: [bold]{domain}[/bold] ({spec.domain_label}), "
        f"{len(spec.variable_mappings)} variables"
    )

    # Step 2: Load raw data
    console.print("[bold blue][2/4][/bold blue] Loading raw datasets...")
    raw_dfs: dict[str, __import__("pandas").DataFrame] = {}
    for source_name in spec.source_datasets:
        # Try exact name, then without extension
        source_path = data_dir / source_name
        if not source_path.exists():
            stem = source_name.replace(".sas7bdat", "")
            source_path = data_dir / f"{stem}.sas7bdat"
        if source_path.exists():
            try:
                df, _meta = read_sas_with_metadata(source_path)
                raw_dfs[source_name] = df
                console.print(f"  Loaded {source_path.name}: {len(df)} rows")
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not read {source_name}: {e}[/yellow]"
                )
        else:
            console.print(
                f"[yellow]Warning: Source dataset not found: {source_name}[/yellow]"
            )

    if not raw_dfs:
        console.print("[bold red]Error:[/bold red] No source datasets could be loaded")
        raise typer.Exit(code=1)

    # Step 3: Build cross-domain context
    cross_domain = None
    if dm_path is not None:
        if not dm_path.exists():
            console.print(f"[yellow]Warning: DM path not found: {dm_path}[/yellow]")
        else:
            console.print("[bold blue][3/4][/bold blue] Loading DM for cross-domain context...")
            try:
                dm_df, _dm_meta = read_sas_with_metadata(dm_path)
                rfstdtc_lookup: dict[str, str] = {}
                if "USUBJID" in dm_df.columns and "RFSTDTC" in dm_df.columns:
                    for _, row in dm_df.iterrows():
                        if row.get("USUBJID") and row.get("RFSTDTC"):
                            rfstdtc_lookup[str(row["USUBJID"])] = str(row["RFSTDTC"])
                cross_domain = CrossDomainContext(rfstdtc_lookup=rfstdtc_lookup)
                console.print(f"  RFSTDTC lookup: {len(rfstdtc_lookup)} subjects")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load DM: {e}[/yellow]")
    else:
        console.print("[bold blue][3/4][/bold blue] No DM path provided, skipping cross-domain")

    # Step 4: Execute
    console.print("[bold blue][4/4][/bold blue] Executing mapping...")
    try:
        sdtm_ref = load_sdtm_reference()
        ct_ref = load_ct_reference()
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)

        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        xpt_path = output_dir_path / f"{domain.lower()}.xpt"

        executor.execute_to_xpt(
            spec,
            raw_dfs,
            xpt_path,
            cross_domain=cross_domain,
        )
    except Exception as e:
        console.print(f"[bold red]Error during execution:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    # Display summary
    console.print("\n[bold green]Execution complete:[/bold green]")
    console.print(f"  Domain:  {domain} ({spec.domain_label})")
    console.print(f"  Output:  {xpt_path}")
    console.print(f"  Sources: {len(raw_dfs)} dataset(s)")

    # Show char width summary
    if executor._last_char_widths:
        max_width = max(executor._last_char_widths.values())
        console.print(
            f"  Char widths: {len(executor._last_char_widths)} column(s), "
            f"max {max_width} bytes"
        )


@app.command(name="validate")
def validate_cmd(
    output_dir: Annotated[
        Path,
        typer.Argument(help="Directory containing generated .xpt files"),
    ],
    study_id: Annotated[
        str,
        typer.Option("--study-id", help="Study identifier"),
    ] = "UNKNOWN",
    specs_dir: Annotated[
        Path | None,
        typer.Option(
            "--specs-dir",
            help="Directory with *_spec.json files (defaults to output-dir)",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option("--format", help="Output format: table, json, or markdown"),
    ] = "table",
) -> None:
    """Run SDTM validation on generated datasets.

    Loads .xpt files and mapping specs from the output directory, runs the
    full validation pipeline (per-domain rules, cross-domain consistency,
    FDA TRC pre-checks, package size/naming checks), and displays results.

    Exit code 0 if submission-ready, 1 if blocking issues found.
    """
    import pandas as pd
    import pyreadstat

    from astraea.cli.display import display_validation_issues, display_validation_summary
    from astraea.reference import load_ct_reference, load_sdtm_reference
    from astraea.submission.package import (
        check_submission_size,
        validate_file_naming,
    )
    from astraea.validation.engine import ValidationEngine
    from astraea.validation.report import ValidationReport
    from astraea.validation.rules.fda_trc import TRCPreCheck

    # Validate directory
    if not output_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] Directory not found: {output_dir}")
        raise typer.Exit(code=1)

    # Step 1: Load .xpt files
    console.print("[bold blue][1/4][/bold blue] Loading datasets...")
    xpt_files = sorted(output_dir.glob("*.xpt"))
    if not xpt_files:
        console.print(f"[bold red]Error:[/bold red] No .xpt files found in {output_dir}")
        raise typer.Exit(code=1)

    domain_dfs: dict[str, pd.DataFrame] = {}
    for xpt_path in xpt_files:
        try:
            df, _meta = pyreadstat.read_xport(str(xpt_path))
            domain_code = xpt_path.stem.upper()
            domain_dfs[domain_code] = df
            console.print(f"  Loaded {xpt_path.name}: {len(df)} rows, {len(df.columns)} vars")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read {xpt_path.name}: {e}[/yellow]")

    # Step 2: Load mapping specs
    console.print("[bold blue][2/4][/bold blue] Loading mapping specs...")
    from astraea.models.mapping import DomainMappingSpec

    search_dir = specs_dir or output_dir
    spec_files = sorted(search_dir.glob("*_spec.json")) + sorted(
        search_dir.glob("*_mapping.json")
    )
    domain_specs: dict[str, DomainMappingSpec] = {}
    for spec_path in spec_files:
        try:
            spec = DomainMappingSpec.model_validate_json(spec_path.read_text())
            domain_specs[spec.domain.upper()] = spec
            console.print(f"  Loaded spec: {spec.domain} ({spec_path.name})")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load spec {spec_path.name}: {e}[/yellow]")

    # Step 3: Run validation
    console.print("[bold blue][3/4][/bold blue] Running validation...")
    sdtm_ref = load_sdtm_reference()
    ct_ref = load_ct_reference()
    engine = ValidationEngine(sdtm_ref=sdtm_ref, ct_ref=ct_ref)

    # Build domain tuples for domains that have both data and specs
    domains_to_validate: dict[str, tuple[pd.DataFrame, DomainMappingSpec]] = {}
    for domain_code in domain_dfs:
        if domain_code in domain_specs:
            domains_to_validate[domain_code] = (
                domain_dfs[domain_code],
                domain_specs[domain_code],
            )

    all_results = engine.validate_all(domains_to_validate) if domains_to_validate else []

    # TRC pre-checks
    trc = TRCPreCheck()
    trc_results = trc.check_all(domain_dfs, output_dir, study_id)
    all_results.extend(trc_results)

    # Package checks
    expected_domains = list(domain_specs.keys()) if domain_specs else list(domain_dfs.keys())
    size_results = check_submission_size(output_dir)
    naming_results = validate_file_naming(output_dir, expected_domains)
    all_results.extend(size_results)
    all_results.extend(naming_results)

    # Step 4: Generate report
    console.print("[bold blue][4/4][/bold blue] Generating report...")
    all_domains = sorted(set(list(domain_dfs.keys()) + list(domain_specs.keys())))
    report = ValidationReport.from_results(study_id, all_results, all_domains)

    # Display results
    console.print()
    display_validation_summary(report, console)
    console.print()
    display_validation_issues(all_results, console=console)

    # Export if requested
    if format == "markdown":
        md_path = output_dir / "validation_report.md"
        md_path.write_text(report.to_markdown())
        console.print(f"\n[green]Markdown report saved to:[/green] {md_path}")
    elif format == "json":
        json_path = output_dir / "validation_report.json"
        json_path.write_text(report.model_dump_json(indent=2))
        console.print(f"\n[green]JSON report saved to:[/green] {json_path}")

    if not report.submission_ready:
        console.print(
            f"\n[bold red]NOT READY:[/bold red] "
            f"{report.effective_error_count} blocking error(s)"
        )
        raise typer.Exit(code=1)
    else:
        console.print("\n[bold green]SUBMISSION READY[/bold green]")


@app.command(name="generate-define")
def generate_define_cmd(
    output_dir: Annotated[
        Path,
        typer.Argument(help="Directory containing mapping specs and .xpt files"),
    ],
    study_id: Annotated[
        str,
        typer.Option("--study-id", help="Study identifier"),
    ] = "UNKNOWN",
    study_name: Annotated[
        str,
        typer.Option("--study-name", help="Human-readable study name"),
    ] = "Clinical Study",
    specs_dir: Annotated[
        Path | None,
        typer.Option("--specs-dir", help="Directory with spec files (defaults to output-dir)"),
    ] = None,
) -> None:
    """Generate define.xml 2.0 from mapping specifications.

    Loads mapping specs and optionally .xpt files (for ValueListDef test code
    extraction), then generates a standards-compliant define.xml.
    """
    import pandas as pd
    import pyreadstat

    from astraea.models.mapping import DomainMappingSpec
    from astraea.reference import load_ct_reference
    from astraea.submission.define_xml import generate_define_xml

    if not output_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] Directory not found: {output_dir}")
        raise typer.Exit(code=1)

    # Load mapping specs
    console.print("[bold blue][1/3][/bold blue] Loading mapping specs...")
    search_dir = specs_dir or output_dir
    spec_files = sorted(search_dir.glob("*_spec.json")) + sorted(
        search_dir.glob("*_mapping.json")
    )
    specs: list[DomainMappingSpec] = []
    for spec_path in spec_files:
        try:
            spec = DomainMappingSpec.model_validate_json(spec_path.read_text())
            specs.append(spec)
            console.print(f"  Loaded: {spec.domain} ({spec_path.name})")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load {spec_path.name}: {e}[/yellow]")

    if not specs:
        console.print("[bold red]Error:[/bold red] No mapping specs found")
        raise typer.Exit(code=1)

    # Load .xpt files for ValueListDef
    console.print("[bold blue][2/3][/bold blue] Loading datasets for value-level metadata...")
    generated_dfs: dict[str, pd.DataFrame] = {}
    for xpt_path in sorted(output_dir.glob("*.xpt")):
        try:
            df, _meta = pyreadstat.read_xport(str(xpt_path))
            generated_dfs[xpt_path.stem.upper()] = df
        except Exception:
            pass

    # Generate define.xml
    console.print("[bold blue][3/3][/bold blue] Generating define.xml...")
    ct_ref = load_ct_reference()
    define_path = output_dir / "define.xml"

    try:
        result_path = generate_define_xml(
            specs=specs,
            ct_ref=ct_ref,
            study_id=study_id,
            study_name=study_name,
            output_path=define_path,
            generated_dfs=generated_dfs if generated_dfs else None,
        )
    except Exception as e:
        console.print(f"[bold red]Error generating define.xml:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    # Count elements for display
    from lxml import etree

    tree = etree.parse(str(result_path))
    odm_ns = "http://www.cdisc.org/ns/odm/v1.3"
    def_ns = "http://www.cdisc.org/ns/def/v2.0"
    n_ig = len(tree.findall(f".//{{{odm_ns}}}ItemGroupDef"))
    n_id = len(tree.findall(f".//{{{odm_ns}}}ItemDef"))
    n_cl = len(tree.findall(f".//{{{odm_ns}}}CodeList"))
    n_md = len(tree.findall(f".//{{{odm_ns}}}MethodDef"))
    n_vl = len(tree.findall(f".//{{{def_ns}}}ValueListDef"))

    from rich.panel import Panel

    info_lines = [
        f"[bold]File:[/bold] {result_path}",
        f"[bold]ItemGroupDefs:[/bold] {n_ig} domains",
        f"[bold]ItemDefs:[/bold] {n_id} variables",
        f"[bold]CodeLists:[/bold] {n_cl}",
        f"[bold]MethodDefs:[/bold] {n_md}",
        f"[bold]ValueListDefs:[/bold] {n_vl}",
    ]
    console.print(Panel("\n".join(info_lines), title="define.xml Generated"))


@app.command(name="generate-csdrg")
def generate_csdrg_cmd(
    output_dir: Annotated[
        Path,
        typer.Argument(help="Directory containing mapping specs"),
    ],
    study_id: Annotated[
        str,
        typer.Option("--study-id", help="Study identifier"),
    ] = "UNKNOWN",
    specs_dir: Annotated[
        Path | None,
        typer.Option("--specs-dir", help="Directory with spec files (defaults to output-dir)"),
    ] = None,
) -> None:
    """Generate a cSDRG (Clinical Study Data Reviewer's Guide) template.

    Loads mapping specs and any existing validation report, then generates
    a PHUSE-structured cSDRG Markdown document.
    """
    from astraea.models.mapping import DomainMappingSpec
    from astraea.submission.csdrg import generate_csdrg
    from astraea.validation.report import ValidationReport

    if not output_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] Directory not found: {output_dir}")
        raise typer.Exit(code=1)

    # Load mapping specs
    console.print("[bold blue][1/2][/bold blue] Loading mapping specs...")
    search_dir = specs_dir or output_dir
    spec_files = sorted(search_dir.glob("*_spec.json")) + sorted(
        search_dir.glob("*_mapping.json")
    )
    specs: list[DomainMappingSpec] = []
    for spec_path in spec_files:
        try:
            spec = DomainMappingSpec.model_validate_json(spec_path.read_text())
            specs.append(spec)
            console.print(f"  Loaded: {spec.domain} ({spec_path.name})")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load {spec_path.name}: {e}[/yellow]")

    if not specs:
        console.print("[bold red]Error:[/bold red] No mapping specs found")
        raise typer.Exit(code=1)

    # Load existing validation report if available
    validation_report: ValidationReport | None = None
    report_json = output_dir / "validation_report.json"
    if report_json.exists():
        try:
            validation_report = ValidationReport.model_validate_json(report_json.read_text())
            console.print(f"  Loaded validation report: {report_json.name}")
        except Exception:
            pass

    if validation_report is None:
        # Create empty report
        validation_report = ValidationReport.from_results(
            study_id=study_id,
            results=[],
            domains=[s.domain for s in specs],
        )

    # Generate cSDRG
    console.print("[bold blue][2/2][/bold blue] Generating cSDRG...")
    csdrg_path = output_dir / "csdrg.md"

    try:
        result_path = generate_csdrg(
            specs=specs,
            validation_report=validation_report,
            study_id=study_id,
            output_path=csdrg_path,
        )
    except Exception as e:
        console.print(f"[bold red]Error generating cSDRG:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    from rich.panel import Panel

    console.print(
        Panel(
            f"[bold]File:[/bold] {result_path}\n"
            f"[bold]Domains:[/bold] {len(specs)}",
            title="cSDRG Generated",
        )
    )


def _find_primary_sas(
    data_folder: Path, domain: str, source_file_override: str | None
) -> Path | None:
    """Find the primary SAS file for a domain.

    Strategy:
    1. If source_file_override is given, use it directly.
    2. Look for exact match: {domain.lower()}.sas7bdat
    3. Look for prefix match: {domain.lower()}_*.sas7bdat
    4. If none found, list available files and show error.

    Returns:
        Path to the SAS file, or None if not found (error printed).
    """
    if source_file_override is not None:
        path = data_folder / source_file_override
        if not path.exists():
            console.print(
                f"[bold red]Error:[/bold red] Specified source file not found: {path}"
            )
            return None
        return path

    # Exact match
    exact = data_folder / f"{domain.lower()}.sas7bdat"
    if exact.exists():
        return exact

    # Prefix match
    prefix_matches = sorted(data_folder.glob(f"{domain.lower()}_*.sas7bdat"))
    if prefix_matches:
        console.print(
            f"[dim]No exact match for {domain.lower()}.sas7bdat, "
            f"using {prefix_matches[0].name}[/dim]"
        )
        return prefix_matches[0]

    # Not found
    available = sorted(f.name for f in data_folder.glob("*.sas7bdat"))
    console.print(
        f"[bold red]Error:[/bold red] Could not identify primary SAS file for "
        f"domain {domain}.\n"
        f"Available files: {', '.join(available[:15])}\n"
        f"Use [bold]--source-file[/bold] to specify."
    )
    return None


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


@app.command(name="review-domain")
def review_domain_cmd(
    spec_file: Annotated[
        Path,
        typer.Argument(help="Path to mapping spec JSON from map-domain"),
    ],
    session: Annotated[
        str | None,
        typer.Option("--session", help="Resume existing session by ID"),
    ] = None,
    db: Annotated[
        Path,
        typer.Option("--db", help="Session database location"),
    ] = Path(".astraea/sessions.db"),
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Where to save reviewed spec"),
    ] = Path("output"),
) -> None:
    """Interactively review a domain mapping specification.

    Loads a mapping spec JSON (from map-domain), starts an interactive review
    session with two-tier review (batch approve HIGH confidence, individual
    review MEDIUM/LOW), and exports the reviewed spec as JSON.

    Use --session to resume an existing session by ID.
    """
    from astraea.models.mapping import DomainMappingSpec
    from astraea.review.reviewer import DomainReviewer, ReviewInterrupted
    from astraea.review.session import SessionStore

    # Validate spec file
    if not spec_file.exists():
        console.print(f"[bold red]Error:[/bold red] Spec file not found: {spec_file}")
        raise typer.Exit(code=1)

    # Load mapping spec
    try:
        spec = DomainMappingSpec.model_validate_json(spec_file.read_text())
    except Exception as e:
        console.print(f"[bold red]Error loading spec:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    domain = spec.domain

    # Open session store
    store = SessionStore(db)
    try:
        if session is not None:
            # Resume existing session
            try:
                _session = store.load_session(session)
            except ValueError:
                console.print(
                    f"[bold red]Error:[/bold red] Session '{session}' not found"
                )
                raise typer.Exit(code=1) from None
            session_id = session
        else:
            # Create new session with this single domain
            _session = store.create_session(
                study_id=spec.study_id,
                domains=[domain],
                specs={domain: spec},
            )
            session_id = _session.session_id
            console.print(
                f"[green]Created review session:[/green] {session_id}"
            )

        # Run review
        reviewer = DomainReviewer(store, console)
        try:
            domain_review = reviewer.review_domain(session_id, domain)
        except ReviewInterrupted as exc:
            console.print(
                f"\n[yellow]Review interrupted.[/yellow] "
                f"Session saved: [bold]{exc.session_id}[/bold]"
            )
            console.print(
                f"Resume with: [bold]astraea resume {exc.session_id} "
                f"--db {db}[/bold]"
            )
            return

        # Export reviewed spec
        output_dir.mkdir(parents=True, exist_ok=True)
        reviewed_path = output_dir / f"{domain}_reviewed.json"

        # Build reviewed spec: apply corrections to original
        reviewed_spec = _apply_corrections(spec, domain_review.decisions)
        reviewed_path.write_text(reviewed_spec.model_dump_json(indent=2))

        console.print(
            f"\n[green]Reviewed spec saved to:[/green] {reviewed_path}"
        )
    finally:
        store.close()


@app.command(name="resume")
def resume_cmd(
    session_id: Annotated[
        str | None,
        typer.Argument(help="Session ID to resume (omit for most recent)"),
    ] = None,
    db: Annotated[
        Path,
        typer.Option("--db", help="Session database location"),
    ] = Path(".astraea/sessions.db"),
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Where to save reviewed specs"),
    ] = Path("output"),
) -> None:
    """Resume an interrupted review session.

    If no session ID is provided, resumes the most recent in-progress session.
    Continues reviewing domains from where it left off.
    """
    from astraea.review.models import DomainReviewStatus
    from astraea.review.reviewer import DomainReviewer, ReviewInterrupted
    from astraea.review.session import SessionStore

    if not db.exists():
        console.print("[bold red]Error:[/bold red] No session database found.")
        console.print(
            "Start a review first with: "
            "[bold]astraea review-domain <spec.json>[/bold]"
        )
        raise typer.Exit(code=1)

    store = SessionStore(db)
    try:
        if session_id is None:
            # Find most recent in-progress session
            sessions = store.list_sessions()
            in_progress = [
                s for s in sessions if s["status"] == "in_progress"
            ]
            if not in_progress:
                console.print(
                    "[yellow]No in-progress sessions found.[/yellow]"
                )
                raise typer.Exit(code=0)
            session_id = in_progress[0]["session_id"]
            console.print(
                f"Resuming most recent session: [bold]{session_id}[/bold]"
            )

        try:
            session = store.load_session(session_id)
        except ValueError:
            console.print(
                f"[bold red]Error:[/bold red] Session '{session_id}' not found"
            )
            raise typer.Exit(code=1) from None

        # Find pending domains
        reviewer = DomainReviewer(store, console)
        for domain in session.domains:
            domain_review = session.domain_reviews.get(domain)
            if domain_review is None:
                continue
            if domain_review.status in (
                DomainReviewStatus.COMPLETED,
                DomainReviewStatus.SKIPPED,
            ):
                continue

            # Review this domain
            try:
                domain_review = reviewer.review_domain(session_id, domain)
            except ReviewInterrupted as exc:
                console.print(
                    f"\n[yellow]Review interrupted.[/yellow] "
                    f"Session saved: [bold]{exc.session_id}[/bold]"
                )
                console.print(
                    f"Resume with: [bold]astraea resume {exc.session_id} "
                    f"--db {db}[/bold]"
                )
                return

        # All domains complete -- export reviewed specs
        session = store.load_session(session_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        for domain in session.domains:
            domain_review = session.domain_reviews[domain]
            reviewed_spec = _apply_corrections(
                domain_review.original_spec, domain_review.decisions
            )
            reviewed_path = output_dir / f"{domain}_reviewed.json"
            reviewed_path.write_text(reviewed_spec.model_dump_json(indent=2))
            console.print(
                f"[green]Exported:[/green] {reviewed_path}"
            )

        console.print("\n[bold green]Session complete.[/bold green]")
    finally:
        store.close()


@app.command(name="sessions")
def list_sessions_cmd(
    db: Annotated[
        Path,
        typer.Option("--db", help="Session database location"),
    ] = Path(".astraea/sessions.db"),
    study: Annotated[
        str | None,
        typer.Option("--study", help="Filter by study ID"),
    ] = None,
) -> None:
    """List all review sessions.

    Shows session IDs, study IDs, status, creation dates, and domain counts.
    Use --study to filter by study ID.
    """
    from astraea.review.display import display_session_list
    from astraea.review.session import SessionStore

    if not db.exists():
        console.print("[dim]No review sessions found.[/dim]")
        return

    store = SessionStore(db)
    try:
        sessions = store.list_sessions(study_id=study)
        if not sessions:
            console.print("[dim]No review sessions found.[/dim]")
            return
        display_session_list(sessions, console)
    finally:
        store.close()


def _apply_corrections(
    spec: DomainMappingSpec,
    decisions: dict[str, ReviewDecision],
) -> DomainMappingSpec:
    """Build a reviewed spec by applying corrections to the original.

    For each variable mapping:
    - If corrected with a new mapping, use the corrected mapping.
    - If rejected, exclude from the reviewed spec.
    - Otherwise, keep the original mapping.

    Args:
        spec: The original mapping specification.
        decisions: Per-variable review decisions.

    Returns:
        A new DomainMappingSpec with corrections applied.
    """
    from astraea.models.mapping import DomainMappingSpec
    from astraea.review.models import CorrectionType, ReviewStatus

    reviewed_mappings = []
    for mapping in spec.variable_mappings:
        decision = decisions.get(mapping.sdtm_variable)
        if decision is None:
            # No decision yet, keep original
            reviewed_mappings.append(mapping)
        elif decision.status == ReviewStatus.CORRECTED:
            if decision.correction_type == CorrectionType.REJECT:
                # Rejected -- exclude from reviewed spec
                continue
            elif decision.corrected_mapping is not None:
                reviewed_mappings.append(decision.corrected_mapping)
            else:
                reviewed_mappings.append(mapping)
        else:
            # Approved or skipped -- keep original
            reviewed_mappings.append(mapping)

    # Rebuild spec with reviewed mappings
    return DomainMappingSpec(
        domain=spec.domain,
        domain_label=spec.domain_label,
        domain_class=spec.domain_class,
        structure=spec.structure,
        study_id=spec.study_id,
        source_datasets=spec.source_datasets,
        cross_domain_sources=spec.cross_domain_sources,
        variable_mappings=reviewed_mappings,
        total_variables=len(reviewed_mappings),
        required_mapped=sum(
            1 for m in reviewed_mappings
            if m.core.value == "Req"
        ),
        expected_mapped=sum(
            1 for m in reviewed_mappings
            if m.core.value == "Exp"
        ),
        high_confidence_count=sum(
            1 for m in reviewed_mappings
            if m.confidence_level.value == "HIGH"
        ),
        medium_confidence_count=sum(
            1 for m in reviewed_mappings
            if m.confidence_level.value == "MEDIUM"
        ),
        low_confidence_count=sum(
            1 for m in reviewed_mappings
            if m.confidence_level.value == "LOW"
        ),
        mapping_timestamp=spec.mapping_timestamp,
        model_used=spec.model_used,
        unmapped_source_variables=spec.unmapped_source_variables,
        suppqual_candidates=spec.suppqual_candidates,
    )
