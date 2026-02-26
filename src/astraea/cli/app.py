"""Astraea CLI application entry point."""

import typer

app = typer.Typer(
    name="astraea",
    help="Agentic AI system for mapping raw clinical trial data to CDISC SDTM format.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Show the current version."""
    from astraea import __version__

    typer.echo(f"astraea-sdtm {__version__}")
