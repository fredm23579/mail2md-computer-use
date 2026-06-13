"""Command-line interface for conversion and supervised export."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Annotated

import typer

from mail2md.browser_agent import ExportRequest, run_export
from mail2md.converter import convert

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer(
    no_args_is_help=True,
    help="Export Gmail/Outlook messages and convert email files to AI-ready Markdown.",
)


@app.command()
def convert_files(
    source: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("mail2md-output"),
    recursive: Annotated[bool, typer.Option("--recursive/--no-recursive")] = True,
) -> None:
    """
    Convert .eml, .msg, .mbox, and .mbx sources without network access.
    Surrounds conversion logic in try/catch to ensure robust operation.
    """
    try:
        generated = convert(source.resolve(), output.resolve(), recursive)
        typer.echo(f"Generated {len(generated)} Markdown file(s) in {output.resolve()}")
    except Exception as e:
        logger.error(f"Failed to complete file conversion: {e}")
        raise typer.Exit(code=1)


@app.command()
def browser_export(
    provider: Annotated[str, typer.Option(help="gmail or outlook")],
    query: Annotated[str, typer.Option(help="Mailbox search query")],
    download_dir: Annotated[Path, typer.Option()] = Path("mail-downloads"),
    profile_dir: Annotated[Path, typer.Option()] = Path(".mail2md-browser-profile"),
    max_messages: Annotated[int, typer.Option(min=1, max=100)] = 10,
    max_steps: Annotated[int, typer.Option(min=1, max=250)] = 80,
    model: Annotated[str, typer.Option()] = "gemini-2.5-computer-use-preview-10-2025",
    execute: Annotated[
        bool,
        typer.Option(
            "--execute", help="Required acknowledgement that browser downloads may occur."
        ),
    ] = False,
) -> None:
    """
    Use a visible Gemini Computer Use session to download original messages.
    Includes validation and robust error handling.
    """
    try:
        provider = provider.lower()
        if provider not in {"gmail", "outlook"}:
            raise typer.BadParameter("provider must be gmail or outlook")

        if not execute:
            typer.echo("DRY RUN: no browser or API call was started.")
            typer.echo(f"Provider: {provider}; query: {query!r}; maximum messages: {max_messages}")
            typer.echo("Re-run with --execute after reviewing the query and output directory.")
            return

        typer.confirm(
            "Screenshots may contain email data and will be sent to Gemini. Proceed with downloads?",
            abort=True,
        )
        request = ExportRequest(
            provider=provider,
            query=query,
            download_dir=download_dir.resolve(),
            profile_dir=profile_dir.resolve(),
            max_messages=max_messages,
            max_steps=max_steps,
            model=model,
        )
        downloads = run_export(request)
        typer.echo(f"Downloaded {len(downloads)} file(s) to {download_dir.resolve()}")
    except typer.Abort:
        typer.echo("Aborted.")
    except Exception as e:
        logger.error(f"Browser export failed: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_and_convert(
    provider: Annotated[str, typer.Option(help="gmail or outlook")],
    query: Annotated[str, typer.Option(help="Mailbox search query")],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("mail2md-output"),
    download_dir: Annotated[Path, typer.Option()] = Path("mail-downloads"),
    max_messages: Annotated[int, typer.Option(min=1, max=100)] = 10,
    execute: Annotated[bool, typer.Option("--execute")] = False,
) -> None:
    """
    Download original messages, then convert the resulting files locally.
    Contains robust error handling for uninterrupted execution.
    """
    try:
        if not execute:
            typer.echo("DRY RUN: browser export and conversion were not started.")
            return
            
        typer.confirm(
            "Screenshots may contain email data and will be sent to Gemini. Proceed?",
            abort=True,
        )
        request = ExportRequest(
            provider=provider.lower(),
            query=query,
            download_dir=download_dir.resolve(),
            profile_dir=Path(".mail2md-browser-profile").resolve(),
            max_messages=max_messages,
        )
        run_export(request)
        
        # Convert any successful downloads
        generated = convert(download_dir.resolve(), output.resolve())
        typer.echo(f"Generated {len(generated)} Markdown file(s) in {output.resolve()}")
    except typer.Abort:
        typer.echo("Aborted.")
    except Exception as e:
        logger.error(f"Export and convert workflow failed: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
