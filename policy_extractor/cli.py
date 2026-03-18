"""Typer CLI app for poliza-extractor — Phase 4.

Subcommands:
  extract  — process a single PDF and print JSON to stdout
  batch    — process all PDFs in a directory with progress bar and summary
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from policy_extractor.cli_helpers import estimate_cost, is_already_extracted
from policy_extractor.config import settings
from policy_extractor.extraction import extract_policy
from policy_extractor.ingestion import ingest_pdf
from policy_extractor.ingestion.cache import compute_file_hash
from policy_extractor.storage.database import SessionLocal, init_db

app = typer.Typer(name="poliza-extractor", help="Extract insurance policy data from PDFs.")
console = Console(stderr=True)  # Rich output to stderr; JSON data goes to stdout


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_db() -> None:
    """Initialise the database engine and bind SessionLocal."""
    engine = init_db(settings.DB_PATH)
    SessionLocal.configure(bind=engine)


def _print_cost(model_id: str, input_tokens: int, output_tokens: int) -> None:
    """Print token and cost summary to stderr."""
    cost = estimate_cost(model_id, input_tokens, output_tokens)
    console.print(
        f"Tokens: {input_tokens:,} input, {output_tokens:,} output | "
        f"Est. cost: ${cost:.4f} USD"
    )


# ---------------------------------------------------------------------------
# extract subcommand
# ---------------------------------------------------------------------------


@app.command()
def extract(
    file: Path = typer.Argument(..., help="Path to PDF file", exists=True),
    model: Optional[str] = typer.Option(None, "--model", help="Override extraction model"),
    force: bool = typer.Option(False, "--force", help="Reprocess even if already extracted"),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", help="Write JSON to directory"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed output"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress all output except JSON"),
) -> None:
    """Extract structured data from a single insurance policy PDF.

    JSON output is written to stdout. Progress and cost information go to stderr.
    """
    _setup_db()
    session = SessionLocal()
    effective_model = model or settings.EXTRACTION_MODEL

    try:
        # Idempotency check
        file_hash = compute_file_hash(file)
        if not force and is_already_extracted(session, file_hash):
            console.print(f"[SKIP] {file.name} -- already extracted")
            raise typer.Exit(0)

        # Ingestion
        ingestion_result = ingest_pdf(file, session=session, force_reprocess=force)

        # Extraction
        policy, usage = extract_policy(ingestion_result, model=model)

        if policy is None:
            console.print(f"[red]ERROR[/red] Extraction failed for {file.name}", style="bold")
            raise typer.Exit(1)

        # JSON to stdout
        print(policy.model_dump_json(indent=2))

        # Auto-persist to DB (STOR-01)
        try:
            from policy_extractor.storage.writer import upsert_policy
            upsert_policy(session, policy)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]WARN[/yellow] Persistence failed: {exc}")

        # Optionally write to file
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            out_file = output_dir / f"{file.stem}.json"
            out_file.write_text(policy.model_dump_json(indent=2), encoding="utf-8")
            if not quiet:
                console.print(f"Written: {out_file}")

        # Cost info
        if usage is not None and not quiet:
            _print_cost(effective_model, usage.input_tokens, usage.output_tokens)

    finally:
        session.close()


# ---------------------------------------------------------------------------
# batch subcommand
# ---------------------------------------------------------------------------


@app.command()
def batch(
    folder: Path = typer.Argument(..., help="Directory containing PDF files"),
    model: Optional[str] = typer.Option(None, "--model", help="Override extraction model"),
    force: bool = typer.Option(False, "--force", help="Reprocess even if already extracted"),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", help="Write JSON files to directory"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed output"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress all output except JSON"),
) -> None:
    """Extract structured data from all PDFs in a directory.

    Shows a Rich progress bar while processing. Prints a summary table to stderr
    after completion. Failures do not stop the batch — they are reported in the summary.
    """
    if not folder.exists() or not folder.is_dir():
        console.print(f"[red]ERROR[/red] Not a valid directory: {folder}")
        raise typer.Exit(1)

    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        console.print(f"[yellow]WARNING[/yellow] No PDF files found in {folder}")
        raise typer.Exit(0)

    _setup_db()
    effective_model = model or settings.EXTRACTION_MODEL

    # Counters
    succeeded = 0
    failed = 0
    skipped = 0
    total_input = 0
    total_output = 0
    failures: list[tuple[str, str]] = []

    start_time = time.time()
    session = SessionLocal()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
            disable=quiet,
        ) as progress:
            task_id = progress.add_task("Starting...", total=len(pdfs))

            for pdf in pdfs:
                progress.update(task_id, description=f"[cyan]{pdf.name}[/cyan]")

                try:
                    # Idempotency check
                    file_hash = compute_file_hash(pdf)
                    if not force and is_already_extracted(session, file_hash):
                        skipped += 1
                        progress.advance(task_id)
                        continue

                    # Ingestion
                    ingestion_result = ingest_pdf(pdf, session=session, force_reprocess=force)

                    # Extraction
                    policy, usage = extract_policy(ingestion_result, model=model)

                    if policy is None:
                        raise RuntimeError(f"extract_policy returned None for {pdf.name}")

                    succeeded += 1

                    if usage is not None:
                        total_input += usage.input_tokens
                        total_output += usage.output_tokens

                    # Auto-persist to DB (STOR-01)
                    try:
                        from policy_extractor.storage.writer import upsert_policy
                        upsert_policy(session, policy)
                    except Exception as exc:  # noqa: BLE001
                        console.print(
                            f"[yellow]WARN[/yellow] Persistence failed for {pdf.name}: {exc}"
                        )

                    # Optionally write JSON
                    if output_dir is not None:
                        output_dir.mkdir(parents=True, exist_ok=True)
                        out_file = output_dir / f"{pdf.stem}.json"
                        out_file.write_text(policy.model_dump_json(indent=2), encoding="utf-8")

                    if verbose:
                        console.print(f"[green]OK[/green] {pdf.name}")

                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    failures.append((pdf.name, str(exc)))
                    console.print(
                        f"[yellow]WARN[/yellow] {pdf.name}: {exc}", highlight=False
                    )

                progress.advance(task_id)

    finally:
        session.close()

    elapsed = time.time() - start_time
    total_cost = estimate_cost(effective_model, total_input, total_output)

    # ------------------------------------------------------------------
    # Summary table
    # ------------------------------------------------------------------
    summary_table = Table(title="Batch Summary", show_header=True, header_style="bold cyan")
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value", justify="right")

    summary_table.add_row("Processed", str(len(pdfs)))
    summary_table.add_row("Succeeded", str(succeeded))
    summary_table.add_row("Failed", str(failed))
    summary_table.add_row("Skipped", str(skipped))
    summary_table.add_row("Total Time", f"{elapsed:.1f}s")
    summary_table.add_row("Input Tokens", f"{total_input:,}")
    summary_table.add_row("Output Tokens", f"{total_output:,}")
    summary_table.add_row("Est. Cost (USD)", f"${total_cost:.4f}")

    console.print(summary_table)

    # Failure details table
    if failures:
        fail_table = Table(
            title="Failed Files", show_header=True, header_style="bold red"
        )
        fail_table.add_column("File")
        fail_table.add_column("Error")
        for fname, reason in failures:
            fail_table.add_row(fname, reason)
        console.print(fail_table)

        raise typer.Exit(1)
