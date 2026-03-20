# Phase 9: Async Batch - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the existing sequential `batch` CLI command run extractions concurrently with a `--concurrency N` flag. Add rate limit retry with exponential backoff. No new extraction capabilities — same pipeline, faster throughput.

</domain>

<decisions>
## Implementation Decisions

### Concurrency mechanism
- `concurrent.futures.ThreadPoolExecutor(max_workers=N)` for concurrent extractions
- Default concurrency: 3, maximum: 10 (enforced via `typer.Option(..., min=1, max=10)`)
- When `--concurrency 1`, skip thread pool entirely and run the existing sequential loop — no thread overhead, identical behavior to current code
- Each worker creates its own `SessionLocal()` for thread-safe DB access (same pattern as Phase 8 upload)

### Rate limit retry strategy
- 3 retries with exponential backoff: wait 2s, 4s, 8s between attempts (total max ~14s per file)
- Retry on: 429 rate limit, 5xx server errors, and connection errors (all transient)
- Do NOT retry on 4xx client errors (except 429) — these are permanent failures
- Workers hold their thread pool slot during backoff (no release-and-requeue)
- Add jitter (random 0-1s) to prevent thundering herd when multiple workers hit rate limits simultaneously
- Retry logic wraps the existing `extract_with_retry()` which handles ValidationError retries — rate limit retry is a separate outer layer

### Progress bar behavior
- Single progress bar with overall count (X/N completed), advances as each PDF finishes in any order
- Retry warnings printed to stderr: `[RETRY] file.pdf: rate limited, attempt 2/4 (waiting 4s)` — visible but doesn't clutter progress bar
- Current sequential progress bar pattern (Rich Progress with SpinnerColumn, BarColumn, etc.) preserved exactly

### Error handling & partial failure
- Always continue on failure — same as current sequential behavior. Failures logged, batch continues, summary shows all failures at end
- No --max-failures flag (keep it simple)
- Summary table adds one new row: "Retries" showing total retry attempts across all PDFs
- Idempotency preserved: `compute_file_hash` + `is_already_extracted` check runs per-worker before extraction

### Claude's Discretion
- Whether to add `add_jitter` as a separate helper or inline
- Thread naming strategy for debugging
- Whether `_process_single_pdf` is a standalone function or method
- How to aggregate token counts thread-safely (threading.Lock vs atomic operations)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing batch implementation
- `policy_extractor/cli.py` lines 140-277 — Current sequential `batch` command with Rich progress, counters, idempotency check, and summary table
- `policy_extractor/cli.py` lines 73-132 — `extract` single-file command showing the pipeline flow (ingest → extract → persist)

### Extraction pipeline with retry
- `policy_extractor/extraction/client.py` — `extract_with_retry()` with ValidationError retry logic, `call_extraction_api()` for raw Anthropic call
- `policy_extractor/extraction/__init__.py` — `extract_policy()` function that orchestrates ingestion result → API call → PolicyExtraction

### Database & session safety
- `policy_extractor/storage/database.py` — `get_engine()` with WAL mode, `SessionLocal` factory, `init_db()` with auto-migration
- `policy_extractor/storage/writer.py` — `upsert_policy()` for thread-safe persistence (each thread needs own session)

### Idempotency
- `policy_extractor/ingestion/cache.py` — `compute_file_hash()` for hash-based dedup
- `policy_extractor/cli_helpers.py` — `is_already_extracted()` check

### Requirements
- `.planning/REQUIREMENTS.md` §Async Batch Processing — ASYNC-01 through ASYNC-05

### Project decisions
- `.planning/STATE.md` §Accumulated Context — Documents asyncio.Semaphore(3) default, WAL mode, per-thread session pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `batch()` in `cli.py`: Current sequential loop with Rich Progress, counters, idempotency — refactor to extract `_process_single_pdf()` then dispatch via ThreadPool
- `extract_with_retry()` in `client.py`: Handles ValidationError retry — rate limit retry wraps this as an outer layer
- `compute_file_hash()` + `is_already_extracted()`: Idempotency check, called per-worker
- `SessionLocal`: Scoped session factory, each thread calls `SessionLocal()` independently
- `get_engine()`: Already sets WAL mode (ASYNC-02 satisfied)
- Rich Progress components: SpinnerColumn, BarColumn, MofNCompleteColumn, TimeElapsedColumn — all importable

### Established Patterns
- Lazy imports inside CLI command functions
- `_setup_db()` called once at batch start (before thread pool)
- `console = Console(stderr=True)` for Rich output
- Counters tracked via local variables (need thread-safe aggregation for concurrent mode)
- `typer.Option(None, ...)` with Optional types for CLI flags

### Integration Points
- `batch()` function in `cli.py` — add `--concurrency` flag, refactor body for thread dispatch
- `extraction/client.py` — add rate limit retry wrapper around `call_extraction_api()`
- Summary table in `batch()` — add "Retries" row

</code_context>

<specifics>
## Specific Ideas

- The agency processes 200+ PDFs/month — concurrent batch with default 3 workers should cut batch time by ~60-70%
- Rate limit retry is critical because Anthropic rate limits vary by account tier — the agency may hit them during large batches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 09-async-batch*
*Context gathered: 2026-03-19*
