"""Typer CLI app for poliza-extractor — Phase 4 + Phase 5 + Phase 11 + Phase 17.

Subcommands:
  extract        — process a single PDF and print JSON to stdout
  batch          — process all PDFs in a directory with progress bar and summary
  export         — export stored policies to JSON, Excel, or CSV (stdout or file)
  import         — load JSON policies into DB
  serve          — start uvicorn with the FastAPI app
  create-fixture — extract a real PDF, redact PII, write golden JSON fixture
  batch-fixtures — process all PDFs in a directory and write golden JSON fixtures
"""

from __future__ import annotations

import enum
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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


class ExportFormat(str, enum.Enum):
    json = "json"
    xlsx = "xlsx"
    csv = "csv"


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
    evaluate: bool = typer.Option(False, "--evaluate", help="Run Sonnet quality evaluation after extraction"),
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
        policy, usage, _retries = extract_policy(ingestion_result, model=model)

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

        # Optional Sonnet quality evaluation (QAL-04: only runs when --evaluate flag given)
        if evaluate:
            from policy_extractor.evaluation import evaluate_policy
            from policy_extractor.storage.writer import update_evaluation_columns
            eval_result = evaluate_policy(ingestion_result, policy)
            if eval_result is not None:
                update_evaluation_columns(
                    session,
                    policy.numero_poliza,
                    policy.aseguradora,
                    eval_result.score,
                    eval_result.evaluation_json,
                    eval_result.evaluated_at,
                    eval_result.model_id,
                )
                if not quiet:
                    console.print(f"[bold]Quality score:[/bold] {eval_result.score:.2f}")
                    _print_cost(eval_result.model_id, eval_result.usage.input_tokens, eval_result.usage.output_tokens)
            else:
                console.print("[yellow]WARN[/yellow] Evaluation failed — extraction saved without evaluation")

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


def _process_single_pdf(
    pdf: Path,
    *,
    model: str | None,
    force: bool,
    output_dir: Path | None,
    evaluate: bool = False,
) -> dict:
    """Process one PDF in its own thread. Creates its own DB session.

    Returns dict with keys: status, name, input_tokens, output_tokens, retries, error,
    eval_score, eval_input_tokens, eval_output_tokens.
    """
    session = SessionLocal()
    try:
        file_hash = compute_file_hash(pdf)
        if not force and is_already_extracted(session, file_hash):
            return {
                "status": "skipped",
                "name": pdf.name,
                "input_tokens": 0,
                "output_tokens": 0,
                "retries": 0,
                "error": None,
                "eval_score": None,
                "eval_input_tokens": 0,
                "eval_output_tokens": 0,
            }

        ingestion_result = ingest_pdf(pdf, session=session, force_reprocess=force)
        policy, usage, rl_retries = extract_policy(ingestion_result, model=model)

        if policy is None:
            raise RuntimeError(f"extract_policy returned None for {pdf.name}")

        # Persist
        from policy_extractor.storage.writer import upsert_policy
        upsert_policy(session, policy)

        # Optional JSON output
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / f"{pdf.stem}.json").write_text(
                policy.model_dump_json(indent=2), encoding="utf-8"
            )

        # Optional Sonnet quality evaluation
        eval_score = None
        eval_input_tokens = 0
        eval_output_tokens = 0
        if evaluate:
            from policy_extractor.evaluation import evaluate_policy
            from policy_extractor.storage.writer import update_evaluation_columns
            eval_result = evaluate_policy(ingestion_result, policy)
            if eval_result is not None:
                update_evaluation_columns(
                    session, policy.numero_poliza, policy.aseguradora,
                    eval_result.score, eval_result.evaluation_json,
                    eval_result.evaluated_at, eval_result.model_id,
                )
                eval_score = eval_result.score
                eval_input_tokens = eval_result.usage.input_tokens
                eval_output_tokens = eval_result.usage.output_tokens

        return {
            "status": "success",
            "name": pdf.name,
            "input_tokens": usage.input_tokens if usage else 0,
            "output_tokens": usage.output_tokens if usage else 0,
            "retries": rl_retries,
            "error": None,
            "eval_score": eval_score,
            "eval_input_tokens": eval_input_tokens,
            "eval_output_tokens": eval_output_tokens,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "failed",
            "name": pdf.name,
            "input_tokens": 0,
            "output_tokens": 0,
            "retries": 0,
            "error": str(exc),
            "eval_score": None,
            "eval_input_tokens": 0,
            "eval_output_tokens": 0,
        }
    finally:
        session.close()


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
    concurrency: int = typer.Option(
        3, "--concurrency", help="Number of concurrent workers (1 = sequential)", min=1, max=10
    ),
    evaluate: bool = typer.Option(False, "--evaluate", help="Run Sonnet quality evaluation after each extraction"),
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
    total_retries = 0
    failures: list[tuple[str, str]] = []

    # Evaluation counters
    total_eval_score = 0.0
    eval_count = 0
    low_score_count = 0
    total_eval_input = 0
    total_eval_output = 0

    start_time = time.time()

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
        task_id = progress.add_task("Batch processing...", total=len(pdfs))

        if concurrency == 1:
            # Sequential path -- identical behavior to pre-Phase 9
            for pdf in pdfs:
                progress.update(task_id, description=f"[cyan]{pdf.name}[/cyan]")
                result = _process_single_pdf(pdf, model=model, force=force, output_dir=output_dir, evaluate=evaluate)

                if result["status"] == "success":
                    succeeded += 1
                    total_input += result["input_tokens"]
                    total_output += result["output_tokens"]
                elif result["status"] == "skipped":
                    skipped += 1
                elif result["status"] == "failed":
                    failed += 1
                    failures.append((result["name"], result["error"]))
                total_retries += result["retries"]

                if result.get("eval_score") is not None:
                    from policy_extractor.evaluation import LOW_SCORE_THRESHOLD
                    total_eval_score += result["eval_score"]
                    eval_count += 1
                    if result["eval_score"] < LOW_SCORE_THRESHOLD:
                        low_score_count += 1
                total_eval_input += result.get("eval_input_tokens", 0)
                total_eval_output += result.get("eval_output_tokens", 0)

                if result["status"] == "failed":
                    console.print(
                        f"[yellow]WARN[/yellow] {result['name']}: {result['error']}",
                        highlight=False,
                    )
                elif verbose and result["status"] == "success":
                    console.print(f"[green]OK[/green] {result['name']}")

                progress.advance(task_id)
        else:
            # Concurrent path
            lock = threading.Lock()

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                future_to_pdf = {
                    executor.submit(
                        _process_single_pdf, pdf,
                        model=model, force=force, output_dir=output_dir, evaluate=evaluate,
                    ): pdf
                    for pdf in pdfs
                }

                for future in as_completed(future_to_pdf):
                    result = future.result()
                    progress.advance(task_id)

                    with lock:
                        if result["status"] == "success":
                            succeeded += 1
                            total_input += result["input_tokens"]
                            total_output += result["output_tokens"]
                        elif result["status"] == "skipped":
                            skipped += 1
                        elif result["status"] == "failed":
                            failed += 1
                            failures.append((result["name"], result["error"]))
                        total_retries += result["retries"]

                        if result.get("eval_score") is not None:
                            from policy_extractor.evaluation import LOW_SCORE_THRESHOLD
                            total_eval_score += result["eval_score"]
                            eval_count += 1
                            if result["eval_score"] < LOW_SCORE_THRESHOLD:
                                low_score_count += 1
                        total_eval_input += result.get("eval_input_tokens", 0)
                        total_eval_output += result.get("eval_output_tokens", 0)

                    if result["status"] == "failed":
                        console.print(
                            f"[yellow]WARN[/yellow] {result['name']}: {result['error']}",
                            highlight=False,
                        )
                    elif verbose and result["status"] == "success":
                        console.print(f"[green]OK[/green] {result['name']}")

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
    summary_table.add_row("Retries", str(total_retries))
    summary_table.add_row("Total Time", f"{elapsed:.1f}s")
    summary_table.add_row("Input Tokens", f"{total_input:,}")
    summary_table.add_row("Output Tokens", f"{total_output:,}")
    summary_table.add_row("Est. Cost (USD)", f"${total_cost:.4f}")

    if evaluate:
        from policy_extractor.evaluation import EVAL_MODEL_ID
        avg_score = total_eval_score / max(eval_count, 1)
        eval_cost = estimate_cost(EVAL_MODEL_ID, total_eval_input, total_eval_output)
        summary_table.add_row("Avg Score", f"{avg_score:.2f}")
        summary_table.add_row("Low Score Files", str(low_score_count))
        summary_table.add_row("Eval Cost (USD)", f"${eval_cost:.4f}")

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


# ---------------------------------------------------------------------------
# export subcommand
# ---------------------------------------------------------------------------


@app.command(name="export")
def export_policies(
    # Existing JSON-compat English flags (DO NOT REMOVE)
    insurer: Optional[str] = typer.Option(None, "--insurer", help="Filter by insurer name (JSON compat)"),
    agent: Optional[str] = typer.Option(None, "--agent", help="Filter by agent name (JSON compat)"),
    from_date: Optional[str] = typer.Option(None, "--from-date", help="Filter start date YYYY-MM-DD (JSON compat)"),
    to_date: Optional[str] = typer.Option(None, "--to-date", help="Filter end date YYYY-MM-DD (JSON compat)"),
    policy_type: Optional[str] = typer.Option(None, "--type", help="Filter by insurance type (JSON compat)"),
    # New Spanish flags for xlsx/csv
    aseguradora: Optional[str] = typer.Option(None, "--aseguradora", help="Filtrar por aseguradora"),
    agente: Optional[str] = typer.Option(None, "--agente", help="Filtrar por agente"),
    desde: Optional[str] = typer.Option(None, "--desde", help="Fecha inicio YYYY-MM-DD"),
    hasta: Optional[str] = typer.Option(None, "--hasta", help="Fecha fin YYYY-MM-DD"),
    tipo: Optional[str] = typer.Option(None, "--tipo", help="Filtrar por tipo de seguro"),
    # Format + output
    fmt: ExportFormat = typer.Option(ExportFormat.json, "--format", help="Output format: json, xlsx, csv"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path (required for xlsx/csv)"),
) -> None:
    """Export stored policies. Supports JSON (default), Excel (.xlsx), and CSV formats."""
    from datetime import datetime

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from policy_extractor.storage.models import Poliza as PolizaModel
    from policy_extractor.storage.writer import orm_to_schema

    _setup_db()
    session = SessionLocal()
    try:
        # Merge Spanish and English flags (Spanish takes precedence)
        eff_insurer = aseguradora or insurer
        eff_agent = agente or agent
        eff_type = tipo or policy_type
        eff_from = desde or from_date
        eff_to = hasta or to_date

        # Validate --output is provided for non-JSON formats
        if fmt in (ExportFormat.xlsx, ExportFormat.csv) and output is None:
            console.print("[red]--output / -o is required for xlsx and csv formats[/red]")
            raise typer.Exit(1)

        stmt = (
            select(PolizaModel)
            .options(selectinload(PolizaModel.asegurados), selectinload(PolizaModel.coberturas))
        )
        if eff_insurer is not None:
            stmt = stmt.where(PolizaModel.aseguradora == eff_insurer)
        if eff_agent is not None:
            stmt = stmt.where(PolizaModel.nombre_agente == eff_agent)
        if eff_type is not None:
            stmt = stmt.where(PolizaModel.tipo_seguro == eff_type)
        if eff_from is not None:
            parsed_from = datetime.strptime(eff_from, "%Y-%m-%d").date()
            stmt = stmt.where(PolizaModel.inicio_vigencia >= parsed_from)
        if eff_to is not None:
            parsed_to = datetime.strptime(eff_to, "%Y-%m-%d").date()
            stmt = stmt.where(PolizaModel.fin_vigencia <= parsed_to)

        rows = session.execute(stmt).scalars().all()

        if fmt == ExportFormat.json:
            results = [orm_to_schema(p).model_dump(mode="json") for p in rows]
            json_str = json.dumps(results, indent=2, ensure_ascii=False)
            if output is not None:
                output.write_text(json_str, encoding="utf-8")
                console.print(f"Exported {len(results)} policy/policies to {output}")
            else:
                print(json_str)
        elif fmt == ExportFormat.xlsx:
            from policy_extractor.export import ExportError, export_xlsx
            try:
                count = export_xlsx(rows, output)
                console.print(f"Exported {count} policy/policies to {output}")
            except ExportError as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(1)
        elif fmt == ExportFormat.csv:
            from policy_extractor.export import ExportError, export_csv
            try:
                count = export_csv(rows, output)
                console.print(f"Exported {count} policy/policies to {output}")
            except ExportError as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(1)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# import subcommand
# ---------------------------------------------------------------------------


@app.command(name="import")
def import_json(
    file: Path = typer.Argument(..., help="JSON file to import", exists=True),
) -> None:
    """Import policies from a JSON file into the database."""
    from policy_extractor.schemas.poliza import PolicyExtraction
    from policy_extractor.storage.writer import upsert_policy

    raw = file.read_text(encoding="utf-8")
    data = json.loads(raw)
    records = [data] if isinstance(data, dict) else data

    _setup_db()
    session = SessionLocal()
    try:
        for record in records:
            extraction = PolicyExtraction.model_validate(record)
            upsert_policy(session, extraction)
        console.print(f"Imported {len(records)} policy/policies")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# serve subcommand
# ---------------------------------------------------------------------------


@app.command()
def serve(
    port: int = typer.Option(8000, "--port", help="Port number"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host address"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes"),
) -> None:
    """Start the FastAPI server with uvicorn."""
    import uvicorn
    uvicorn.run("policy_extractor.api:app", host=host, port=port, reload=reload)


# ---------------------------------------------------------------------------
# create-fixture subcommand
# ---------------------------------------------------------------------------


@app.command(name="create-fixture")
def create_fixture(
    file: Path = typer.Argument(..., help="Path to real PDF", exists=True),
    output: Path = typer.Option(
        Path("tests/fixtures/golden"), "--output", "-o", help="Output directory for fixture JSON"
    ),
    insurer: str = typer.Option(..., "--insurer", help="Insurer slug (e.g. axa, gnp, qualitas)"),
    policy_type: str = typer.Option(..., "--type", help="Policy type slug (e.g. auto, vida, gmm)"),
    model: Optional[str] = typer.Option(None, "--model", help="Override extraction model"),
) -> None:
    """Extract a real PDF, redact PII, and write a golden JSON fixture.

    The fixture is saved to the output directory as golden_{insurer}_{type}.json.
    PII fields (nombre_contratante, rfc, etc.) are replaced with '[REDACTED]'.
    Use this fixture with `pytest -m regression` for automated drift detection.
    """
    from policy_extractor.regression.pii_redactor import PiiRedactor

    _setup_db()
    session = SessionLocal()
    try:
        ingestion_result = ingest_pdf(file, session=session)
        policy, usage, _retries = extract_policy(ingestion_result, model=model)

        if policy is None:
            console.print("[red]Extraction failed[/red]")
            raise typer.Exit(1)

        raw = policy.model_dump(mode="json")
        raw["_source_pdf"] = file.name  # stores the PDF filename for test lookup
        redacted = PiiRedactor().redact(raw)

        output.mkdir(parents=True, exist_ok=True)
        out_file = output / f"golden_{insurer}_{policy_type}.json"
        out_file.write_text(
            json.dumps(redacted, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        console.print(f"[green]Fixture written:[/green] {out_file}")

        if usage:
            _print_cost(model or settings.EXTRACTION_MODEL, usage.input_tokens, usage.output_tokens)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# batch-fixtures subcommand helpers
# ---------------------------------------------------------------------------

_KNOWN_INSURERS = [
    "zurich",
    "qualitas",
    "mapfre",
    "axa",
    "gnp",
    "chubb",
    "ana",
    "hdi",
    "planseguro",
    "prudential",
]


_KNOWN_TYPES = [
    "auto",
    "vida",
    "gmm",
    "gastos_medicos",
    "hogar",
    "rc",
    "transporte",
    "accidentes",
    "dental",
    "viaje",
]


def _infer_insurer(filename: str) -> str:
    """Infer insurer slug from PDF filename. Returns 'unknown' if no match."""
    lower = filename.lower()
    for slug in _KNOWN_INSURERS:
        if slug in lower:
            return slug
    return "unknown"


def _infer_type(filename: str) -> str:
    """Infer policy type slug from PDF filename. Returns 'general' if no match."""
    lower = filename.lower()
    for slug in _KNOWN_TYPES:
        if slug in lower:
            return slug
    return "general"


# ---------------------------------------------------------------------------
# batch-fixtures subcommand
# ---------------------------------------------------------------------------


@app.command(name="batch-fixtures")
def batch_fixtures(
    pdf_dir: Path = typer.Argument(..., help="Directory containing real PDFs", exists=True),
    output: Path = typer.Option(
        Path("tests/fixtures/golden"),
        "--output",
        "-o",
        help="Output directory for fixture JSON files",
    ),
    insurer_map: Optional[Path] = typer.Option(
        None,
        "--insurer-map",
        help="JSON file mapping PDF filename patterns to {insurer, type} slugs",
    ),
    model: Optional[str] = typer.Option(None, "--model", help="Override extraction model"),
    run_tests: bool = typer.Option(
        False, "--run-tests", help="Run pytest -m regression after creating fixtures"
    ),
) -> None:
    """Process all PDFs in a directory, redact PII, and write golden JSON fixtures.

    Fixtures are written to the output directory following the naming convention
    {insurer}_{type}_{seq:03d}.json (e.g. zurich_auto_001.json).

    PII fields are redacted via PiiRedactor before writing.
    Failed extractions are skipped with a warning, not a crash.
    """
    import subprocess
    from datetime import datetime, timezone

    from policy_extractor.regression.pii_redactor import PiiRedactor

    # Load insurer map if provided
    mapping: dict[str, dict[str, str]] = {}
    if insurer_map is not None:
        mapping = json.loads(Path(insurer_map).read_text(encoding="utf-8"))

    # Discover PDFs
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        console.print(f"[yellow]No PDF files found in {pdf_dir}[/yellow]")
        return

    output.mkdir(parents=True, exist_ok=True)
    _setup_db()
    session = SessionLocal()

    total = len(pdf_files)
    succeeded = 0
    skipped = 0

    try:
        for pdf in pdf_files:
            # Resolve insurer and type slugs
            insurer_slug = "unknown"
            type_slug = "general"

            if mapping:
                lower_name = pdf.name.lower()
                for pattern, meta in mapping.items():
                    if pattern.lower() in lower_name:
                        insurer_slug = meta.get("insurer", "unknown")
                        type_slug = meta.get("type", "general")
                        break
            else:
                insurer_slug = _infer_insurer(pdf.name)
                type_slug = _infer_type(pdf.name)

            # Extract
            try:
                ingestion_result = ingest_pdf(pdf, session=session)
                policy, usage, _retries = extract_policy(ingestion_result, model=model)
            except Exception as exc:  # noqa: BLE001
                console.print(
                    f"[yellow]SKIP:[/yellow] {pdf.name} — ingestion/extraction error: {exc}"
                )
                skipped += 1
                continue

            if policy is None:
                console.print(
                    f"[yellow]SKIP:[/yellow] {pdf.name} — extraction failed"
                )
                skipped += 1
                continue

            # Build fixture dict
            raw: dict = policy.model_dump(mode="json")
            raw["_source_pdf"] = pdf.name
            raw["_insurer"] = insurer_slug
            raw["_tipo_seguro"] = type_slug
            raw["_created_at"] = datetime.now(timezone.utc).isoformat()

            redacted = PiiRedactor().redact(raw)

            # Determine sequence number
            existing = list(output.glob(f"{insurer_slug}_{type_slug}_*.json"))
            seq = len(existing) + 1
            out_file = output / f"{insurer_slug}_{type_slug}_{seq:03d}.json"
            out_file.write_text(
                json.dumps(redacted, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            console.print(f"[green]OK:[/green] {pdf.name} -> {out_file.name}")
            succeeded += 1
    finally:
        session.close()

    # Summary table
    table = Table(title="batch-fixtures summary")
    table.add_column("Total", justify="right")
    table.add_column("Succeeded", justify="right", style="green")
    table.add_column("Skipped", justify="right", style="yellow")
    table.add_row(str(total), str(succeeded), str(skipped))
    console.print(table)

    if run_tests:
        result = subprocess.run(["pytest", "-m", "regression", "-v"], check=False)
        if result.returncode != 0:
            console.print("[yellow]Regression tests had failures.[/yellow]")
