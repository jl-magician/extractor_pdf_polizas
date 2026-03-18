# Phase 4: CLI & Batch - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can process one or many PDFs from the command line with full visibility into progress and cost. Single-file extraction, batch directory processing, progress display, idempotent reprocessing, and cost tracking. No web interface, no storage layer — pure CLI wrapping the ingestion + extraction pipeline.

</domain>

<decisions>
## Implementation Decisions

### CLI command design
- Command name: `poliza-extractor`
- Subcommands: `extract` (single file) and `batch` (directory)
  - `poliza-extractor extract file.pdf` — single file extraction
  - `poliza-extractor batch folder/` — process all PDFs in directory
- CLI framework: Typer (already decided in project research)
- Flags:
  - `--model` — override extraction model (default from config: claude-haiku-4-5-20251001)
  - `--force` — force reprocessing, bypass ingestion cache AND extraction dedup
  - `--output-dir` — write JSON results to directory (in addition to stdout)
  - `--verbose` / `--quiet` — control output verbosity

### Progress & output
- Rich library for progress bar — animated progress with current file name, X/Y count, percentage, elapsed time
- Single-file output: JSON to stdout (progress/errors to stderr). If --output-dir specified, also write to file.
- Batch summary: Rich table showing total processed, succeeded, failed, skipped, total time, total cost. Failed files listed with error reason.

### Idempotency strategy
- Check `source_file_hash` in polizas DB table before extracting — if SHA-256 hash already exists, skip
- Skip with notice: show `[SKIP] file.pdf — already extracted` in progress
- `--force` flag overrides and reprocesses everything
- Ingestion cache (Phase 2) handles OCR dedup separately; this is extraction-level dedup

### Cost tracking
- Per-file token count and cost in verbose mode; summary always shown
- Token counts from Anthropic API response `usage` field (input_tokens, output_tokens)
- Hardcoded price table as constants: Haiku ($1/M input, $5/M output), Sonnet ($3/M input, $15/M output)
- Update pricing manually when Anthropic changes prices
- Summary shows: total input tokens, total output tokens, estimated USD cost

### Claude's Discretion
- Exact Rich progress bar configuration and styling
- How to structure the Typer app (single file vs module)
- Error message formatting and colors
- JSON output formatting (indentation, encoding)
- How to handle non-PDF files in batch directory (skip with warning vs error)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 2 outputs (ingestion)
- `policy_extractor/ingestion/__init__.py` — `ingest_pdf()` function; the first step in the CLI pipeline
- `policy_extractor/ingestion/cache.py` — `compute_file_hash()` for SHA-256; reuse for idempotency check

### Phase 3 outputs (extraction)
- `policy_extractor/extraction/__init__.py` — `extract_policy()` function; the second step in the CLI pipeline
- `policy_extractor/extraction/client.py` — `call_extraction_api()` returns usage info for cost tracking

### Data contracts
- `policy_extractor/schemas/poliza.py` — PolicyExtraction model (CLI outputs this as JSON)
- `policy_extractor/schemas/ingestion.py` — IngestionResult model (intermediate result)

### Infrastructure
- `policy_extractor/config.py` — Settings class with EXTRACTION_MODEL, DB_PATH
- `policy_extractor/storage/database.py` — `get_engine()`, `init_db()`, `SessionLocal` for DB access
- `policy_extractor/storage/models.py` — Poliza model with `source_file_hash` for idempotency check

### Project scope
- `.planning/REQUIREMENTS.md` — ING-03, ING-04, CLI-01 through CLI-05
- `.planning/ROADMAP.md` — Phase 4 success criteria (5 criteria that must be TRUE)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ingest_pdf()` — takes file path + session, returns IngestionResult
- `extract_policy()` — takes IngestionResult, returns PolicyExtraction
- `compute_file_hash()` — SHA-256 of file bytes, reuse for idempotency
- `Settings` class — has DB_PATH, EXTRACTION_MODEL, all config needed
- `init_db()` / `get_engine()` / `SessionLocal` — DB access pattern established

### Established Patterns
- Pydantic models for all data contracts
- python-dotenv + Settings class for config
- loguru for logging (used in ingestion)
- pytest with mocked tests

### Integration Points
- CLI is the top-level entry point — imports from ingestion and extraction
- `policy_extractor/cli.py` or `policy_extractor/cli/` — new module for Typer app
- `pyproject.toml` `[project.scripts]` — register `poliza-extractor` command
- DB session needed for: ingestion cache, idempotency check (query polizas table)
- Note: Phase 4 does NOT persist extraction results to DB — that's Phase 5 (STOR-01). Phase 4 only reads DB for idempotency.

</code_context>

<specifics>
## Specific Ideas

- The CLI should feel professional — Rich progress bars and summary tables make it look polished for the agency team
- `--force` flag is important because the same PDF might need re-extraction after prompt version update
- Idempotency check is at the extraction level (source_file_hash in polizas table), NOT ingestion level — ingestion cache is a separate optimization layer
- Cost tracking with per-file detail in verbose mode helps the agency understand per-insurer extraction costs

</specifics>

<deferred>
## Deferred Ideas

- Async/concurrent batch processing with semaphore for API rate limits — Phase 4 does sequential processing; async optimization if needed later
- Export batch results to CSV/Excel — v2 (RPT-01)
- Watch mode for monitoring a folder for new PDFs — out of scope

</deferred>

---

*Phase: 04-cli-batch*
*Context gathered: 2026-03-18*
