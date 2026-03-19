# Phase 4: CLI & Batch - Research

**Researched:** 2026-03-18
**Domain:** Typer CLI framework, Rich progress/tables, idempotency patterns, cost tracking
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Command name: `poliza-extractor`
- Subcommands: `extract` (single file) and `batch` (directory)
  - `poliza-extractor extract file.pdf`
  - `poliza-extractor batch folder/`
- CLI framework: Typer (already decided in project research)
- Flags:
  - `--model` — override extraction model (default from config: claude-haiku-4-5-20251001)
  - `--force` — force reprocessing, bypass ingestion cache AND extraction dedup
  - `--output-dir` — write JSON results to directory (in addition to stdout)
  - `--verbose` / `--quiet` — control output verbosity
- Rich library for progress bar — animated progress with current file name, X/Y count, percentage, elapsed time
- Single-file output: JSON to stdout (progress/errors to stderr). If `--output-dir` specified, also write to file.
- Batch summary: Rich table showing total processed, succeeded, failed, skipped, total time, total cost. Failed files listed with error reason.
- Idempotency: check `source_file_hash` in polizas DB table before extracting — if SHA-256 hash already exists, skip
- Skip with notice: show `[SKIP] file.pdf — already extracted` in progress
- `--force` flag overrides and reprocesses everything
- Cost tracking: hardcoded price table as constants: Haiku ($1/M input, $5/M output), Sonnet ($3/M input, $15/M output)
- Summary always shown; per-file token detail in verbose mode

### Claude's Discretion

- Exact Rich progress bar configuration and styling
- How to structure the Typer app (single file vs module)
- Error message formatting and colors
- JSON output formatting (indentation, encoding)
- How to handle non-PDF files in batch directory (skip with warning vs error)

### Deferred Ideas (OUT OF SCOPE)

- Async/concurrent batch processing with semaphore for API rate limits — sequential only in Phase 4
- Export batch results to CSV/Excel — v2 (RPT-01)
- Watch mode for monitoring a folder for new PDFs
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ING-03 | User can process a single PDF file via CLI | Typer `extract` subcommand; `ingest_pdf()` + `extract_policy()` pipeline |
| ING-04 | User can process a directory of PDFs in batch via CLI | Typer `batch` subcommand; `Path.glob("*.pdf")` enumeration |
| CLI-01 | User can invoke single-file extraction from command line | `poliza-extractor extract file.pdf` via pyproject.toml `[project.scripts]` entry |
| CLI-02 | User can invoke batch extraction from command line | `poliza-extractor batch folder/` subcommand |
| CLI-03 | Batch processing displays progress (current file, total, percentage) | Rich `Progress` with `SpinnerColumn`, `BarColumn`, `MofNCompleteColumn`, `TimeElapsedColumn` |
| CLI-04 | System skips PDFs that have already been extracted (idempotent reprocessing) | Query `polizas.source_file_hash` before extraction; SHA-256 via `compute_file_hash()` |
| CLI-05 | System tracks and reports token usage and estimated API cost per execution | Requires extracting `usage` from Anthropic `Message`; needs `extract_with_retry` return shape change |
</phase_requirements>

---

## Summary

Phase 4 wires the existing ingestion + extraction pipeline into a user-facing CLI. The two building blocks — `ingest_pdf()` and `extract_policy()` — are complete; this phase adds the command-line surface, progress visibility, idempotency guard, and cost reporting on top of them.

The primary technical work is: (1) adding Typer 0.24.1 as a new dependency and creating the CLI module, (2) configuring a Rich `Progress` display for batch runs, (3) querying `polizas.source_file_hash` before extraction for idempotency (read-only DB access — writes are Phase 5's job), and (4) threading `usage` token counts out of the Anthropic API response — which requires a **minor surgery** to `extract_with_retry` since the current implementation discards the raw `Message` object.

The idempotency logic depends on Phase 5 having written rows into the `polizas` table. Since Phase 5 is not yet done, the idempotency check must gracefully handle an empty table (no rows = no skips = process everything). The `--force` flag bypasses the check entirely.

**Primary recommendation:** Create `policy_extractor/cli.py` as a single-file Typer app with `extract` and `batch` subcommands. Modify `extract_with_retry` to also return the raw `Message` (for `usage` tokens). Add `typer>=0.24.1` to `pyproject.toml` dependencies. Register `poliza-extractor = "policy_extractor.cli:app"` in `[project.scripts]`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typer | 0.24.1 | CLI framework — argument parsing, subcommands, help text | Already decided; wraps Click with type annotations; minimal boilerplate |
| rich | 14.3.3 | Progress bars, summary tables, styled output | Already installed; best-in-class terminal UI for Python |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| anthropic | 0.86.0 | SDK — `Message.usage` provides `input_tokens`, `output_tokens` | Already in project; no change needed |
| loguru | 0.7.x | Structured logging — info/warning/error traces per file | Already in project; CLI uses stderr stream |
| pathlib | stdlib | Directory traversal (`Path.glob("*.pdf")`) | Preferred over `os.walk` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Typer | Click directly | Typer IS Click under the hood; Typer's type-annotation style is cleaner for this codebase |
| Typer | argparse | argparse has no subcommand decorator pattern; more boilerplate |
| Rich Progress | tqdm | Rich is already installed; tqdm is lighter but plain text only |

**Installation:**
```bash
pip install "typer>=0.24.1"
```

Also add to `pyproject.toml` dependencies:
```toml
"typer>=0.24.1",
```

**Version verification:** Confirmed against pip registry on 2026-03-18.
- `typer`: latest is 0.24.1 (verified `pip index versions typer`)
- `rich`: 14.3.3 already installed (verified `pip show rich`)

---

## Architecture Patterns

### Recommended Project Structure
```
policy_extractor/
├── cli.py              # Typer app — app, extract command, batch command
tests/
├── test_cli.py         # CLI unit tests — mocked pipeline, idempotency, cost
```

Single-file `cli.py` is appropriate: the CLI is the top-level orchestrator calling into existing modules. A `cli/` package would be over-engineering for this scope.

### Pattern 1: Typer App with Subcommands

**What:** A single `app = typer.Typer()` instance with `@app.command()` decorators for `extract` and `batch`. Registered in `pyproject.toml`.

**When to use:** This is the only pattern for this phase.

**Example:**
```python
# policy_extractor/cli.py
import typer
from rich.console import Console

app = typer.Typer(name="poliza-extractor", help="Extract insurance policy data from PDFs.")
console = Console()
err_console = Console(stderr=True)

@app.command()
def extract(
    file: Path = typer.Argument(..., help="Path to PDF file"),
    model: str = typer.Option(None, "--model", help="Override extraction model"),
    force: bool = typer.Option(False, "--force", help="Reprocess even if already extracted"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir"),
    verbose: bool = typer.Option(False, "--verbose"),
    quiet: bool = typer.Option(False, "--quiet"),
):
    ...

@app.command()
def batch(
    folder: Path = typer.Argument(..., help="Directory containing PDFs"),
    model: str = typer.Option(None, "--model"),
    force: bool = typer.Option(False, "--force"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir"),
    verbose: bool = typer.Option(False, "--verbose"),
    quiet: bool = typer.Option(False, "--quiet"),
):
    ...

if __name__ == "__main__":
    app()
```

**pyproject.toml registration:**
```toml
[project.scripts]
poliza-extractor = "policy_extractor.cli:app"
```

After editing `pyproject.toml`, run `pip install -e .` to make the entry point available.

### Pattern 2: Rich Progress for Batch

**What:** Use `rich.progress.Progress` as a context manager wrapping the file loop.

**When to use:** For `batch` command only. Single-file `extract` command writes to stdout directly.

**Example:**
```python
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn, TimeElapsedColumn

pdf_files = sorted(folder.glob("*.pdf"))

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    MofNCompleteColumn(),
    TextColumn("{task.percentage:>3.0f}%"),
    TimeElapsedColumn(),
    console=err_console,  # progress to stderr, results to stdout
) as progress:
    task = progress.add_task("Processing...", total=len(pdf_files))
    for pdf in pdf_files:
        progress.update(task, description=f"[cyan]{pdf.name}[/cyan]")
        # ... process ...
        progress.advance(task)
```

**Key:** Pass `console=err_console` (stderr) to Progress so JSON output on stdout is not polluted by progress bar escape codes.

### Pattern 3: Rich Summary Table

**What:** After batch completes, print a `rich.table.Table` with per-run stats.

**Example:**
```python
from rich.table import Table

table = Table(title="Batch Summary", show_header=True)
table.add_column("Metric", style="bold")
table.add_column("Value")
table.add_row("Processed", str(total))
table.add_row("Succeeded", f"[green]{succeeded}[/green]")
table.add_row("Failed", f"[red]{failed}[/red]")
table.add_row("Skipped", f"[yellow]{skipped}[/yellow]")
table.add_row("Total Time", f"{elapsed:.1f}s")
table.add_row("Input Tokens", f"{total_input_tokens:,}")
table.add_row("Output Tokens", f"{total_output_tokens:,}")
table.add_row("Est. Cost (USD)", f"${total_cost:.4f}")
console.print(table)
```

### Pattern 4: Idempotency Check

**What:** Query `polizas.source_file_hash` before extracting. If hash found, skip.

**Critical context:** Phase 4 does NOT write to the `polizas` table — that is Phase 5 (STOR-01). The idempotency check is read-only. On a fresh system with no Phase 5 data, the table will be empty and every file will be processed. The `--force` flag is for future re-extraction after prompt version updates.

**Example:**
```python
from sqlalchemy import select
from policy_extractor.storage.models import Poliza
from policy_extractor.ingestion.cache import compute_file_hash

def is_already_extracted(session: Session, file_hash: str) -> bool:
    """Return True if source_file_hash exists in polizas table."""
    row = session.execute(
        select(Poliza.id).where(Poliza.source_file_hash == file_hash).limit(1)
    ).scalar_one_or_none()
    return row is not None
```

**DB session setup in CLI:**
```python
from policy_extractor.storage.database import init_db, SessionLocal, get_engine
from policy_extractor.config import settings

engine = init_db(settings.DB_PATH)
SessionLocal.configure(bind=engine)
with SessionLocal() as session:
    # use session
```

### Pattern 5: Cost Tracking — Required Change to extract_with_retry

**Critical finding:** The current `extract_with_retry` in `policy_extractor/extraction/client.py` returns `(PolicyExtraction, raw_input_dict)` where `raw_input_dict` is the *tool call input* dict, NOT the `Message` object. The Anthropic `Message.usage` (with `input_tokens`, `output_tokens`) is used inside `call_extraction_api` but **never returned** to the caller.

To implement CLI-05 (cost tracking), the implementation must surface `usage` to the CLI layer. Two approaches:

**Option A (recommended): Return usage alongside policy** — change `extract_with_retry` return type to `tuple[PolicyExtraction, dict, anthropic.types.Usage] | None`.

**Option B:** Extract usage from `campos_adicionales["_raw_response"]` if it were stored there — but currently only the input dict is stored, not the Message.

**Recommendation for planner:** Use Option A. The return shape change is backward-compatible if tests are updated. The CLI reads `usage.input_tokens` and `usage.output_tokens`.

**Confirmed field names** (verified from `anthropic.types.Usage.model_fields` with SDK 0.86.0):
```python
usage.input_tokens   # int
usage.output_tokens  # int
# Also present but not needed:
# usage.cache_creation_input_tokens
# usage.cache_read_input_tokens
```

**Cost calculation constants:**
```python
# Price per million tokens, USD
PRICING = {
    "haiku": {"input": 1.00, "output": 5.00},
    "sonnet": {"input": 3.00, "output": 15.00},
}

def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    key = "sonnet" if "sonnet" in model.lower() else "haiku"
    rates = PRICING[key]
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
```

### Anti-Patterns to Avoid

- **Mixing stdout and stderr:** JSON results go to stdout; all progress, logs, and tables go to stderr. Never mix them — this breaks piping.
- **Blocking on non-PDF files in batch:** Skip silently with a warning, not an error. Non-PDF files in a folder are expected (README, etc).
- **Printing Rich output when `--quiet`:** Suppress all Rich output (including progress bar) when `--quiet` is set.
- **Using `typer.echo` for JSON:** Use `print()` or `console.print_json()` directly to stdout for machine-readable output.
- **Opening DB session per file:** Create one session for the entire batch run, not one per file.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Progress bar animation | Custom ANSI loop | `rich.progress.Progress` | Handles terminal resize, ETA, color, Windows compat |
| Summary table rendering | String concatenation | `rich.table.Table` | Auto-column alignment, colors, unicode borders |
| Argument parsing with types | argparse setup | Typer decorators | Type annotations become CLI args automatically |
| Directory traversal | `os.walk` | `Path.glob("*.pdf")` | Cleaner, returns `Path` objects directly |
| SHA-256 file hashing | Custom `hashlib` code | `compute_file_hash()` from `policy_extractor.ingestion.cache` | Already implemented, tested, consistent |

**Key insight:** Rich's `Progress` context manager handles cursor management, thread-safety, and cleanup on exception — building this manually would produce fragile ANSI escape code sequences.

---

## Common Pitfalls

### Pitfall 1: Progress Bar Output Pollutes JSON on Stdout
**What goes wrong:** `Progress` renders to `Console()` which defaults to stdout. When user pipes `poliza-extractor extract file.pdf | jq .`, progress escape codes corrupt the JSON stream.
**Why it happens:** Rich's default `Console()` uses stdout.
**How to avoid:** Create `err_console = Console(stderr=True)` and pass it to `Progress(console=err_console)`. JSON always goes to `print()` (stdout).
**Warning signs:** `jq` parse errors when piping output.

### Pitfall 2: Entry Point Not Registered After pyproject.toml Edit
**What goes wrong:** `poliza-extractor` command not found after adding `[project.scripts]`.
**Why it happens:** `pip install -e .` must be re-run after any `pyproject.toml` change to rebuild entry points.
**How to avoid:** Include `pip install -e .` as an explicit step after updating `pyproject.toml`.
**Warning signs:** `bash: poliza-extractor: command not found`

### Pitfall 3: Idempotency Check Returns False Positives (wrong table)
**What goes wrong:** Phase 4 checks `polizas.source_file_hash` but Phase 5 (STOR-01) hasn't run yet, so the table is empty. Every run processes every file.
**Why it happens:** The idempotency check is future-proof — it only works after Phase 5 starts persisting rows.
**How to avoid:** This is expected behavior in Phase 4. Document it in CLI output. Do not query `ingestion_cache` table for extraction-level dedup — that table only tracks OCR results, not extractions.
**Warning signs:** No skips even after repeated runs (correct behavior pre-Phase 5).

### Pitfall 4: Usage Tokens Not Available from Current extract_with_retry
**What goes wrong:** `extract_with_retry` currently returns `(PolicyExtraction, raw_input_dict)`. The `raw_input_dict` is the Claude tool call input, not the Message. `Message.usage` is never surfaced.
**Why it happens:** The original Phase 3 design only needed the structured data, not token counts.
**How to avoid:** The `extract` command in CLI must also receive the `Message` object (or at minimum `usage`). Update `extract_with_retry` return type as part of Phase 4 implementation.
**Warning signs:** `AttributeError` when trying to access `result[1].input_tokens` — the second return value is a dict, not a `Usage` object.

### Pitfall 5: Rich Progress Bar Breaks in Non-TTY Environments
**What goes wrong:** Rich progress bars use ANSI escape codes that garble output when redirected to a file or piped.
**Why it happens:** Terminal capability detection is needed.
**How to avoid:** Rich handles this automatically — `Console` auto-detects TTY and falls back to plain text. No manual check needed. Verify with `poliza-extractor batch folder/ > out.txt` produces clean lines.

### Pitfall 6: glob("*.pdf") is Case-Sensitive on Linux
**What goes wrong:** Files named `POLIZA.PDF` are not found by `Path.glob("*.pdf")` on Linux.
**Why it happens:** `glob` is case-sensitive on Linux/Mac, case-insensitive on Windows.
**How to avoid:** Use `Path.glob("*.pdf")` + `Path.glob("*.PDF")` combined, or normalize with `[pP][dD][fF]` pattern. Since this project runs on Windows currently, standard `*.pdf` is fine for Phase 4.

---

## Code Examples

Verified patterns from official sources / existing codebase:

### DB Session Setup in CLI
```python
# Source: policy_extractor/storage/database.py pattern (existing)
from policy_extractor.storage.database import init_db, SessionLocal, get_engine
from policy_extractor.config import settings

def get_session():
    engine = init_db(settings.DB_PATH)
    SessionLocal.configure(bind=engine)
    return SessionLocal()
```

### Idempotency Query
```python
# Source: SQLAlchemy 2.0 ORM select pattern (same style as existing cache.py)
from sqlalchemy import select
from policy_extractor.storage.models import Poliza

def is_already_extracted(session: Session, file_hash: str) -> bool:
    row = session.execute(
        select(Poliza.id).where(Poliza.source_file_hash == file_hash).limit(1)
    ).scalar_one_or_none()
    return row is not None
```

### Modified extract_with_retry Signature (required for CLI-05)
```python
# Modified return type to include usage tokens
def extract_with_retry(
    client: anthropic.Anthropic,
    assembled_text: str,
    ingestion_file_hash: str,
    model: str,
    max_retries: int = 1,
) -> tuple[PolicyExtraction, dict, anthropic.types.Usage] | None:
    # Return (policy, raw_response, message.usage) instead of (policy, raw_response)
```

### Cost Calculation
```python
# Source: locked decision from CONTEXT.md
PRICING = {
    "haiku": {"input": 1.00, "output": 5.00},
    "sonnet": {"input": 3.00, "output": 15.00},
}

def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost from token counts. Returns 0.0 if model not recognized."""
    key = "sonnet" if "sonnet" in model_id.lower() else "haiku"
    rates = PRICING[key]
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
```

### Single-file extract Pipeline Flow
```python
# The CLI pipeline: ingest -> dedup check -> extract -> output
def run_extract(pdf_path: Path, session: Session, model: str, force: bool) -> ExtractionOutcome:
    file_hash = compute_file_hash(pdf_path)

    if not force and is_already_extracted(session, file_hash):
        return ExtractionOutcome(status="skipped", file=pdf_path)

    try:
        ingestion_result = ingest_pdf(pdf_path, session=session, force_reprocess=force)
        result = extract_policy(ingestion_result, model=model)  # model param needed
        return ExtractionOutcome(status="success", file=pdf_path, result=result)
    except Exception as exc:
        return ExtractionOutcome(status="failed", file=pdf_path, error=str(exc))
```

**Note:** `extract_policy()` currently doesn't accept a `model` parameter — it reads from `settings.EXTRACTION_MODEL`. The `--model` CLI flag requires either: (a) modifying `extract_policy()` to accept a model override, or (b) temporarily patching `settings.EXTRACTION_MODEL` before calling. Option (a) is cleaner.

### JSON Output (stdout)
```python
import json
from rich.console import Console

stdout_console = Console()  # stdout for JSON

# Single file: dump to stdout
print(result.model_dump_json(indent=2))

# With --output-dir: also write to file
if output_dir:
    output_file = output_dir / f"{pdf_path.stem}.json"
    output_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `click` directly | Typer (wraps Click) | ~2019 | Type-annotated CLI with zero boilerplate |
| `tqdm` for progress | Rich `Progress` | ~2021 | Richer display, multiple columns, no extra dep |
| `argparse` subparsers | Typer `@app.command()` | ~2019 | Declarative subcommand pattern |

**Deprecated/outdated:**
- `click.group()` with `@group.command()`: Still works but Typer's annotation style is preferred for new Python 3.10+ projects.
- `typer.run()` (single command): Not applicable here — we have subcommands, must use `typer.Typer()` app instance.

---

## Open Questions

1. **extract_policy() model override**
   - What we know: `extract_policy()` currently reads `settings.EXTRACTION_MODEL` directly; the `--model` flag must override this
   - What's unclear: Whether to add a `model` parameter to `extract_policy()`, or patch settings at CLI startup
   - Recommendation: Add `model: str | None = None` parameter to `extract_policy()` — pass through to `extract_with_retry`. Fallback to `settings.EXTRACTION_MODEL` if None. This is a small, clean change with no backward-compat issues.

2. **Non-PDF files in batch directory**
   - What we know: Claude's discretion is to skip with warning vs error
   - What's unclear: Whether hidden files (`.DS_Store`, etc.) need explicit filtering
   - Recommendation: Use `folder.glob("*.pdf")` (case-folded) which naturally excludes non-PDFs. Show a single warning line like `[yellow]Warning: skipped N non-PDF files[/yellow]` if any were found, but don't enumerate them.

3. **Behavior when polizas table doesn't exist**
   - What we know: `init_db()` runs `CREATE TABLE IF NOT EXISTS` — safe to call at CLI startup
   - What's unclear: Whether CLI should always call `init_db()` or only on demand
   - Recommendation: Always call `init_db(settings.DB_PATH)` at CLI startup — it's idempotent and ensures tables exist for the idempotency check.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (no version pin; installed in dev deps) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` testpaths = ["tests"] |
| Quick run command | `pytest tests/test_cli.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ING-03 / CLI-01 | `extract` subcommand processes single PDF | unit (mocked) | `pytest tests/test_cli.py::test_extract_single_file -x` | Wave 0 |
| ING-04 / CLI-02 | `batch` subcommand processes directory of PDFs | unit (mocked) | `pytest tests/test_cli.py::test_batch_directory -x` | Wave 0 |
| CLI-03 | Batch shows progress with file name, count, percentage | unit (mocked Progress) | `pytest tests/test_cli.py::test_batch_progress_display -x` | Wave 0 |
| CLI-04 | Skip PDF when source_file_hash exists in polizas table | unit (in-memory DB) | `pytest tests/test_cli.py::test_idempotency_skip -x` | Wave 0 |
| CLI-04 | `--force` bypasses idempotency skip | unit (in-memory DB) | `pytest tests/test_cli.py::test_force_reprocess -x` | Wave 0 |
| CLI-05 | Cost summary shows token counts and USD estimate | unit (mocked usage) | `pytest tests/test_cli.py::test_cost_tracking -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_cli.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cli.py` — covers ING-03, ING-04, CLI-01 through CLI-05 (new file)
- [ ] No new `conftest.py` entries needed — existing `engine`/`session` fixtures in `tests/conftest.py` are reusable for idempotency tests

---

## Sources

### Primary (HIGH confidence)
- Existing codebase — `policy_extractor/extraction/client.py`, `ingestion/__init__.py`, `ingestion/cache.py`, `storage/models.py`, `storage/database.py`, `config.py`, `schemas/poliza.py` — read directly
- `pip index versions typer` — confirmed latest is 0.24.1 (2026-03-18)
- `pip show rich` — confirmed 14.3.3 installed in project environment
- `python -c "from anthropic.types import Usage; print(Usage.model_fields.keys())"` — confirmed `input_tokens`, `output_tokens` field names in SDK 0.86.0

### Secondary (MEDIUM confidence)
- Rich documentation patterns (Console stderr, Progress context manager) — consistent with standard Rich 12+ API that is stable across versions

### Tertiary (LOW confidence)
- None — all findings are from verified local sources

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions confirmed from pip registry and installed packages
- Architecture: HIGH — patterns derived directly from existing codebase conventions + locked decisions in CONTEXT.md
- Pitfalls: HIGH — critical pitfall #4 (missing usage tokens) confirmed by reading extraction/client.py source; others confirmed from Rich/Typer documentation patterns

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable libraries; Anthropic pricing hardcoded so only needs update if prices change)
