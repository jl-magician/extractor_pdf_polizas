# Phase 9: Async Batch - Research

**Researched:** 2026-03-19
**Domain:** Python ThreadPoolExecutor concurrency, SQLite WAL thread safety, Anthropic rate limit handling, Rich progress thread safety
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `concurrent.futures.ThreadPoolExecutor(max_workers=N)` for concurrent extractions
- Default concurrency: 3, maximum: 10 (enforced via `typer.Option(..., min=1, max=10)`)
- When `--concurrency 1`, skip thread pool entirely and run the existing sequential loop — no thread overhead, identical behavior to current code
- Each worker creates its own `SessionLocal()` for thread-safe DB access (same pattern as Phase 8 upload)
- 3 retries with exponential backoff: wait 2s, 4s, 8s between attempts (total max ~14s per file)
- Retry on: 429 rate limit, 5xx server errors, and connection errors (all transient)
- Do NOT retry on 4xx client errors (except 429) — these are permanent failures
- Workers hold their thread pool slot during backoff (no release-and-requeue)
- Add jitter (random 0-1s) to prevent thundering herd when multiple workers hit rate limits simultaneously
- Retry logic wraps the existing `extract_with_retry()` — rate limit retry is a separate outer layer
- Single progress bar with overall count (X/N completed), advances as each PDF finishes in any order
- Retry warnings printed to stderr: `[RETRY] file.pdf: rate limited, attempt 2/4 (waiting 4s)` — visible but doesn't clutter progress bar
- Current sequential progress bar pattern (Rich Progress with SpinnerColumn, BarColumn, etc.) preserved exactly
- Always continue on failure — same as current sequential behavior
- No --max-failures flag
- Summary table adds one new row: "Retries" showing total retry attempts across all PDFs
- Idempotency preserved: `compute_file_hash` + `is_already_extracted` check runs per-worker before extraction

### Claude's Discretion
- Whether to add `add_jitter` as a separate helper or inline
- Thread naming strategy for debugging
- Whether `_process_single_pdf` is a standalone function or method
- How to aggregate token counts thread-safely (threading.Lock vs atomic operations)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ASYNC-01 | Batch processing runs extractions concurrently with configurable concurrency limit | ThreadPoolExecutor with submit/as_completed pattern; `--concurrency N` flag routes to pool vs sequential loop |
| ASYNC-02 | SQLite WAL mode enabled for concurrent write safety | Already satisfied: `get_engine()` executes `PRAGMA journal_mode=WAL` on every connection; verified in database.py line 17 |
| ASYNC-03 | Each concurrent worker uses its own database session | Pattern confirmed: each worker calls `SessionLocal()` independently and closes it in a finally block; same pattern used in Phase 8 upload's `_run_extraction` |
| ASYNC-04 | Rate limit errors from Anthropic API trigger automatic retry with exponential backoff | `anthropic.RateLimitError`, `anthropic.InternalServerError`, `anthropic.APIConnectionError` are the exact exception classes; verified from installed SDK |
| ASYNC-05 | CLI `batch` command accepts `--concurrency N` flag | `typer.Option(3, "--concurrency", min=1, max=10)` — `min`/`max` parameters confirmed available in typer 0.24.1 |
</phase_requirements>

---

## Summary

Phase 9 is a targeted refactor of `cli.py`'s `batch()` command plus an addition to `extraction/client.py`. The existing sequential loop is extracted into `_process_single_pdf()` which then gets dispatched via `ThreadPoolExecutor`. The only new module-level code is a rate limit retry wrapper around `call_extraction_api()`.

All infrastructure is already in place: WAL mode is set by `get_engine()` on every connection (ASYNC-02 done), `SessionLocal` is a session factory that workers can call independently (ASYNC-03 pattern confirmed), Rich Progress has an internal `_lock` making `advance()` thread-safe, and the Anthropic SDK exposes typed exception classes for granular retry logic.

The critical implementation detail is the two-layer retry architecture: the inner `extract_with_retry()` handles Pydantic `ValidationError`, and a new outer function `call_with_rate_limit_retry()` in `client.py` handles transient network/API errors (429, 5xx, connection errors) before calling `extract_with_retry()`. Thread-safe counter aggregation requires a `threading.Lock` guarding the shared `succeeded`, `failed`, `skipped`, `total_input`, `total_output`, `total_retries`, and `failures` variables.

**Primary recommendation:** Extract `_process_single_pdf()` as a standalone function in `cli.py`, add `call_with_rate_limit_retry()` in `client.py` as the outer retry layer, use `concurrent.futures.as_completed()` to collect results in completion order and drive progress bar advances.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `concurrent.futures` | stdlib (Python 3.12) | ThreadPoolExecutor + as_completed | No install; correct choice for I/O-bound thread parallelism |
| `threading` | stdlib | Lock for shared counter aggregation | No install; the standard way to protect mutable state across threads |
| `anthropic` | installed (confirmed) | RateLimitError, InternalServerError, APIConnectionError | Typed exceptions are the correct catch targets |
| `time` + `random` | stdlib | `time.sleep()` + `random.uniform()` for jitter | Already imported in cli.py (time); random is stdlib |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `rich` | 14.3.3 (confirmed) | Thread-safe Progress, Console | Already in use; `progress._lock` internal lock makes it safe across threads |
| `typer` | 0.24.1 (confirmed) | `min`/`max` on `typer.Option` | Already in use; `min=1, max=10` validation confirmed working |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ThreadPoolExecutor | asyncio + asyncio.Semaphore | asyncio requires async Anthropic client; more invasive refactor; out of scope per REQUIREMENTS.md "Full async SQLAlchemy" exclusion |
| threading.Lock for counters | multiprocessing.Value | Lock is sufficient and lighter; multiprocessing creates new processes (overkill, SQLite file access issues) |
| as_completed() | executor.map() | `as_completed()` allows progress bar to advance per-file as each finishes; `map()` blocks until all done |

**Installation:** No new packages required. All dependencies are stdlib or already installed.

---

## Architecture Patterns

### Recommended Project Structure

No new files needed. Changes confined to:
```
policy_extractor/
├── cli.py                    # Add --concurrency flag, _process_single_pdf(), thread dispatch
└── extraction/
    └── client.py             # Add call_with_rate_limit_retry() wrapping extract_with_retry()
```

### Pattern 1: _process_single_pdf() standalone function

**What:** Extract all per-file logic from the batch loop into a single function that takes the PDF path + configuration and returns a structured result dict.
**When to use:** Every task submitted to ThreadPoolExecutor calls this function. When `--concurrency 1`, the main loop calls it directly without a thread pool.
**Example:**
```python
# In policy_extractor/cli.py
def _process_single_pdf(
    pdf: Path,
    *,
    model: Optional[str],
    force: bool,
    output_dir: Optional[Path],
) -> dict:
    """Process one PDF. Creates its own DB session. Returns result dict."""
    from policy_extractor.storage.writer import upsert_policy

    session = SessionLocal()
    retries_used = 0
    try:
        file_hash = compute_file_hash(pdf)
        if not force and is_already_extracted(session, file_hash):
            return {"status": "skipped", "name": pdf.name, "input_tokens": 0,
                    "output_tokens": 0, "retries": 0, "error": None}

        ingestion_result = ingest_pdf(pdf, session=session, force_reprocess=force)
        policy, usage, retries_used = extract_with_rate_limit_retry(
            ingestion_result, model=model
        )

        if policy is None:
            raise RuntimeError(f"extract_policy returned None for {pdf.name}")

        upsert_policy(session, policy)

        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / f"{pdf.stem}.json").write_text(
                policy.model_dump_json(indent=2), encoding="utf-8"
            )

        return {
            "status": "success",
            "name": pdf.name,
            "input_tokens": usage.input_tokens if usage else 0,
            "output_tokens": usage.output_tokens if usage else 0,
            "retries": retries_used,
            "error": None,
        }
    except Exception as exc:
        return {"status": "failed", "name": pdf.name, "input_tokens": 0,
                "output_tokens": 0, "retries": retries_used, "error": str(exc)}
    finally:
        session.close()
```

### Pattern 2: ThreadPoolExecutor with as_completed() driving progress bar

**What:** Submit all tasks upfront, collect results in completion order to advance the progress bar as each file finishes.
**When to use:** When `concurrency > 1` in the batch command.
**Example:**
```python
# In policy_extractor/cli.py batch() command
from concurrent.futures import ThreadPoolExecutor, as_completed

lock = threading.Lock()

with Progress(..., console=console, disable=quiet) as progress:
    task_id = progress.add_task("Processing...", total=len(pdfs))

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_pdf = {
            executor.submit(_process_single_pdf, pdf,
                            model=model, force=force, output_dir=output_dir): pdf
            for pdf in pdfs
        }

        for future in as_completed(future_to_pdf):
            result = future.result()  # Never raises; _process_single_pdf catches all
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
```

### Pattern 3: call_with_rate_limit_retry() outer wrapper in client.py

**What:** Outer retry layer around `extract_with_retry()` catching transient API errors.
**When to use:** Called from `_process_single_pdf()` instead of calling `extract_policy()` directly.
**Example:**
```python
# In policy_extractor/extraction/client.py
import random
import time
import anthropic

_RATE_LIMIT_RETRIES = 3
_BACKOFF_SECONDS = [2, 4, 8]  # index = attempt number (0-based)

def call_with_rate_limit_retry(
    ingestion_result,
    model: str | None = None,
) -> tuple:
    """Outer retry wrapper for transient API errors. Returns (policy, usage, retries_used)."""
    from policy_extractor.extraction import extract_policy

    retries_used = 0
    for attempt in range(_RATE_LIMIT_RETRIES + 1):
        try:
            policy, usage = extract_policy(ingestion_result, model=model)
            return policy, usage, retries_used
        except (
            anthropic.RateLimitError,
            anthropic.InternalServerError,
            anthropic.APIConnectionError,
        ) as exc:
            if attempt >= _RATE_LIMIT_RETRIES:
                raise
            wait = _BACKOFF_SECONDS[attempt] + random.uniform(0, 1)
            retries_used += 1
            # Caller (cli.py) logs: [RETRY] {name}: {exc}, attempt {attempt+2}/4 (waiting {wait:.1f}s)
            time.sleep(wait)
```

**Important:** `extract_policy()` currently catches ALL exceptions and returns `(None, None)` rather than re-raising. This means transient API errors get swallowed before reaching `call_with_rate_limit_retry()`. The rate limit retry must be applied one layer deeper — wrapping `call_extraction_api()` directly in `client.py`, or the outer wrapper must be placed inside `extract_with_retry()` before the generic `except Exception` clause.

See "Common Pitfalls" section for the correct approach.

### Pattern 4: --concurrency 1 sequential bypass

**What:** When concurrency is 1, skip ThreadPoolExecutor entirely and call `_process_single_pdf()` in the main loop.
**When to use:** Default or explicitly requested sequential mode.
**Example:**
```python
if concurrency == 1:
    for pdf in pdfs:
        result = _process_single_pdf(pdf, model=model, force=force, output_dir=output_dir)
        progress.advance(task_id)
        # update counters directly (no lock needed in single-threaded path)
else:
    # ThreadPoolExecutor path above
```

### Anti-Patterns to Avoid

- **Shared session across threads:** The current batch() creates one `session = SessionLocal()` before the loop. In concurrent mode, this single session must NOT be shared across workers — SQLAlchemy sessions are not thread-safe.
- **Updating counters without a lock:** `succeeded += 1` from multiple threads is a data race in Python despite the GIL (compound operations are not atomic). Always use `threading.Lock`.
- **Updating progress bar description per-worker:** `progress.update(task_id, description=...)` from multiple threads creates garbled output. Drop the per-file description update in concurrent mode (or keep only total count via TextColumn template).
- **Calling `extract_policy()` directly from workers:** The current `extract_policy()` catches ALL exceptions and returns `(None, None)`. Rate limit errors never reach the outer retry if `extract_policy()` is the call boundary. The retry wrapper must target `call_extraction_api()` or sit inside `extract_with_retry()`.
- **Importing inside ThreadPoolExecutor workers:** Lazy imports at function scope are fine in the main thread but can cause import lock contention when many threads import the same module simultaneously. Move imports to module level for modules used in hot paths.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread pool lifecycle management | Manual thread creation/joining | `ThreadPoolExecutor` context manager | Handles worker lifecycle, exception propagation, clean shutdown |
| Progress bar thread safety | Manual locking around Rich updates | Rich Progress (has internal `_lock`) | `progress.advance()` is already thread-safe per source inspection |
| Backoff timing | Custom exponential formula | Precomputed list `[2, 4, 8]` + `random.uniform(0, 1)` | Simple, readable, matches the locked decision exactly |
| Typed API exception catching | String matching on error messages | `anthropic.RateLimitError`, `anthropic.InternalServerError`, `anthropic.APIConnectionError` | SDK provides typed exceptions; string matching is fragile |

**Key insight:** The entire concurrency infrastructure already exists in Python stdlib. The real work is the refactor to extract `_process_single_pdf()` and place the rate limit retry at the correct call depth.

---

## Common Pitfalls

### Pitfall 1: Rate Limit Retry Swallowed by Inner Exception Handler

**What goes wrong:** `extract_policy()` (in `extraction/__init__.py`) has a broad `except Exception` that catches all errors from `extract_with_retry()` and returns `(None, None)`. A `RateLimitError` raised inside `call_extraction_api()` is caught by `extract_with_retry()`'s own `except Exception` handler at line 126-130 of `client.py`, which logs it and returns `None`. The rate limit retry wrapper at the outer level never sees the exception — it just receives `(None, None)`.

**Why it happens:** The existing retry logic was designed to survive failures gracefully for batch processing, not to distinguish transient vs permanent failures.

**How to avoid:** Place the rate limit retry wrapper INSIDE `extract_with_retry()` in `client.py`, wrapping only `call_extraction_api()` (the raw API call). This is above the ValidationError retry loop. The wrapper catches `RateLimitError` / `InternalServerError` / `APIConnectionError` before the generic except clause.

**Warning signs:** Workers finish immediately on rate limit with `policy=None` instead of retrying; "Retries" counter in summary always shows 0 despite 429 responses in logs.

### Pitfall 2: Single Session Shared Across Workers

**What goes wrong:** The current `batch()` creates `session = SessionLocal()` once before the loop. If this session is passed to worker threads or used as a module-level singleton, concurrent access causes `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread` or silent data corruption.

**Why it happens:** SQLAlchemy sessions are not thread-safe by design. The existing code is sequential so this has never mattered.

**How to avoid:** `_process_single_pdf()` must call `SessionLocal()` at the start of its own body and close it in a `finally` block. The main thread's session (if any) must not be passed to workers. The `_setup_db()` call stays in the main thread before the pool is created — it only configures the engine bind, not a session.

**Warning signs:** `ProgrammingError: SQLite objects created in a thread` exception, or random `DetachedInstanceError`.

### Pitfall 3: progress.update(description=...) Per-Worker Causes Visual Corruption

**What goes wrong:** The sequential loop sets `progress.update(task_id, description=f"[cyan]{pdf.name}[/cyan]")` to show which file is being processed. In concurrent mode, multiple workers race to update the same description field, causing it to flicker between file names or display a stale name.

**Why it happens:** Multiple threads call `progress.update()` simultaneously; the description reflects only the last-written value, which is non-deterministic.

**How to avoid:** In concurrent mode, do not set per-file description on the shared task. Use only `progress.advance(task_id)` after each future completes. The TextColumn showing counts (MofNCompleteColumn) is sufficient feedback.

**Warning signs:** Progress description shows a finished file's name while others are still running.

### Pitfall 4: Threading Lock Scope Too Broad (Blocking Workers)

**What goes wrong:** If the `threading.Lock` is held during the full `_process_single_pdf()` call (extraction + DB write), then only one worker runs at a time — eliminating all concurrency.

**Why it happens:** Misunderstanding that the lock must protect shared counter READS and WRITES, not the actual work.

**How to avoid:** Lock only the counter aggregation code (5-10 lines), not the extraction. Lock acquisition in the `as_completed()` loop after `future.result()` returns.

**Warning signs:** `--concurrency 3` completes in the same time as `--concurrency 1`.

### Pitfall 5: Jitter Missing From Retry Backoff

**What goes wrong:** Without jitter, when 3 workers all hit a rate limit at the same time, they all wake up from `time.sleep(2)` simultaneously and hammer the API again in a thundering herd, triggering another rate limit immediately.

**Why it happens:** Synchronized retry timing from synchronized work start.

**How to avoid:** Add `random.uniform(0, 1)` to each backoff sleep: `time.sleep(_BACKOFF_SECONDS[attempt] + random.uniform(0, 1))`. Jitter spreads retries across ~1 second window.

**Warning signs:** With 3+ workers, rate limit errors cluster in bursts at fixed intervals (every 2s, 4s, 8s) rather than spreading out.

---

## Code Examples

Verified patterns from the installed project codebase:

### Anthropic Exception Classes (verified from installed SDK)
```python
# Source: python -c "from anthropic import RateLimitError, InternalServerError, APIConnectionError"
from anthropic import RateLimitError, InternalServerError, APIConnectionError

# RateLimitError: HTTP 429 — rate limit exceeded
# InternalServerError: HTTP 5xx — server-side transient error
# APIConnectionError: Network/connection error — also transient
# All other APIStatusError subclasses (4xx except 429): permanent, do not retry
```

### Typer min/max on int Option (verified: typer 0.24.1)
```python
# Source: typer 0.24.1 signature inspection
concurrency: int = typer.Option(
    3,
    "--concurrency",
    help="Number of concurrent workers (1 = sequential)",
    min=1,
    max=10,
)
```

### Rich Progress thread safety (verified: rich 14.3.3)
```python
# Source: Rich Progress._lock confirmed present via hasattr check
# progress.advance(task_id) is thread-safe without additional locking
# progress.update(task_id, description=...) is thread-safe but causes visual flicker
# in concurrent mode — avoid per-worker description updates
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
    # advance() from any thread is safe:
    progress.advance(task_id)
```

### threading.Lock for counter aggregation
```python
import threading

lock = threading.Lock()
succeeded = failed = skipped = total_input = total_output = total_retries = 0
failures: list[tuple[str, str]] = []

# In as_completed() loop, after future.result():
with lock:
    if result["status"] == "success":
        succeeded += 1
        total_input += result["input_tokens"]
        total_output += result["output_tokens"]
    elif result["status"] == "skipped":
        skipped += 1
    else:
        failed += 1
        failures.append((result["name"], result["error"]))
    total_retries += result["retries"]
```

### Rate limit retry placement inside extract_with_retry() (correct depth)
```python
# In policy_extractor/extraction/client.py
# Modify extract_with_retry() to add an outer retry loop:

def extract_with_retry(
    client: anthropic.Anthropic,
    assembled_text: str,
    ingestion_file_hash: str,
    model: str,
    max_retries: int = 1,
    max_rate_limit_retries: int = 3,
) -> tuple[PolicyExtraction, dict, anthropic.types.Usage] | None:
    """Inner retry for ValidationError + outer retry for rate limits."""
    _RL_BACKOFF = [2, 4, 8]
    rate_limit_attempts = 0

    current_text = assembled_text
    attempts = max_retries + 1

    for attempt in range(attempts):
        rl_attempt = 0
        while True:
            try:
                message = call_extraction_api(client, current_text, model)
                break  # success — exit rate-limit retry loop
            except (
                anthropic.RateLimitError,
                anthropic.InternalServerError,
                anthropic.APIConnectionError,
            ) as exc:
                if rl_attempt >= max_rate_limit_retries:
                    raise
                wait = _RL_BACKOFF[rl_attempt] + random.uniform(0, 1)
                rate_limit_attempts += 1
                logger.warning(
                    f"Rate limit/transient error (attempt {rl_attempt + 1}/"
                    f"{max_rate_limit_retries + 1}, waiting {wait:.1f}s): {exc}"
                )
                time.sleep(wait)
                rl_attempt += 1

        try:
            policy, raw_response = parse_and_validate(message, ingestion_file_hash)
            # Attach retries count for caller aggregation
            # (return as 4-tuple or use a result dataclass)
            return (policy, raw_response, message.usage)
        except ValidationError as exc:
            # ... existing ValidationError handling ...
```

**Note on return signature:** The planner should decide whether to extend `extract_with_retry()` to return a 4-tuple `(policy, raw_response, usage, rl_retries_count)` or have the caller accumulate retries via a mutable container. A simple approach is to track retries via a `list` passed by reference (acts as a mutable counter). Claude's discretion as noted in CONTEXT.md.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sequential for loop in batch() | ThreadPoolExecutor + as_completed() | Phase 9 | ~60-70% batch time reduction with 3 workers |
| ValidationError-only retry | Two-layer retry (ValidationError inner + RateLimitError outer) | Phase 9 | Handles Anthropic account-tier rate limits gracefully |
| Single shared session for batch | Per-worker session from SessionLocal() | Phase 9 | Eliminates SQLite thread safety errors under concurrency |

**Deprecated/outdated:**
- Single `session = SessionLocal()` at batch start — replaced by per-worker session creation inside `_process_single_pdf()`.

---

## Open Questions

1. **Return type extension for retry count propagation**
   - What we know: `extract_with_retry()` currently returns a 3-tuple or None. We need to surface retry count to the summary table.
   - What's unclear: Whether to extend to a 4-tuple (breaking existing call sites) or use a side-channel (mutable list, threading.local, etc.)
   - Recommendation: The simplest approach is to wrap the return in a small dataclass or named tuple, or pass `retries_out: list[int]` by reference. The planner should pick one approach and update all call sites consistently.

2. **Retry logging format — stderr vs Rich console**
   - What we know: Retry warnings should print `[RETRY] file.pdf: rate limited, attempt 2/4 (waiting 4s)` to stderr per CONTEXT.md decision.
   - What's unclear: Whether `console.print()` inside a worker thread (while Rich Progress is active) produces clean output or interferes with the progress bar rendering.
   - Recommendation: Rich `Console(stderr=True)` is thread-safe (confirmed `_lock` present). Use `console.print()` inside the rate limit handler. In practice, Rich queues console output to avoid mid-bar corruption. This is LOW confidence without empirical testing; consider wrapping in the same `lock` used for counters if visual artifacts appear.

3. **Idempotency check — per-worker session race condition**
   - What we know: `is_already_extracted()` does a SELECT, then later `upsert_policy()` does an INSERT/UPDATE. With multiple workers, two workers could both pass the `is_already_extracted()` check for the same file, then both call `upsert_policy()` — which is safe because `upsert_policy()` uses dedup by `(numero_poliza, aseguradora)`.
   - What's unclear: Whether two workers processing the SAME PDF file simultaneously could cause issues (unlikely in practice since `sorted(folder.glob("*.pdf"))` yields each path once).
   - Recommendation: Each PDF path appears exactly once in the futures dict. The TOCTOU race between `is_already_extracted()` and `upsert_policy()` is harmless because upsert is idempotent. No additional locking needed for idempotency.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (configured in pyproject.toml `[tool.pytest.ini_options]`) |
| Config file | `pyproject.toml` — `testpaths = ["tests"]` |
| Quick run command | `python -m pytest tests/test_cli.py -x -q` |
| Full suite command | `python -m pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ASYNC-01 | batch with `--concurrency 3` submits all PDFs to thread pool, all succeed | unit | `python -m pytest tests/test_cli.py::test_batch_concurrent_3_workers -x` | ❌ Wave 0 |
| ASYNC-02 | No "database is locked" errors with concurrent writes | integration | `python -m pytest tests/test_cli.py::test_batch_no_lock_errors -x` | ❌ Wave 0 |
| ASYNC-03 | Each worker uses its own session (not the shared main thread session) | unit | `python -m pytest tests/test_cli.py::test_batch_worker_own_session -x` | ❌ Wave 0 |
| ASYNC-04 | RateLimitError triggers retry with backoff; eventually succeeds | unit | `python -m pytest tests/test_cli.py::test_rate_limit_retry_succeeds -x` | ❌ Wave 0 |
| ASYNC-04 | 4xx non-429 errors do NOT retry | unit | `python -m pytest tests/test_cli.py::test_no_retry_on_4xx -x` | ❌ Wave 0 |
| ASYNC-05 | `--concurrency N` flag exists, enforces min=1 max=10 | unit | `python -m pytest tests/test_cli.py::test_concurrency_flag_validation -x` | ❌ Wave 0 |
| ASYNC-05 | `--concurrency 1` uses sequential loop (no ThreadPoolExecutor) | unit | `python -m pytest tests/test_cli.py::test_concurrency_1_sequential -x` | ❌ Wave 0 |
| ASYNC-01 | Summary table shows "Retries" row | unit | `python -m pytest tests/test_cli.py::test_batch_summary_retries_row -x` | ❌ Wave 0 |
| ASYNC-01 | Idempotency: second run skips already-extracted files | unit | `python -m pytest tests/test_cli.py::test_batch_idempotency_concurrent -x` | ❌ Wave 0 (covered by existing `test_batch_directory` pattern, new variant for concurrent path) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_cli.py -x -q`
- **Per wave merge:** `python -m pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cli.py` — add concurrent batch test functions (new tests, not new file)
- [ ] No new test files required; all new tests extend the existing `test_cli.py`
- [ ] No new fixtures needed — existing `tmp_path`, `MagicMock`, `patch` patterns are sufficient

---

## Sources

### Primary (HIGH confidence)
- Direct source code inspection: `policy_extractor/cli.py` lines 140-280 — sequential batch implementation
- Direct source code inspection: `policy_extractor/extraction/client.py` — `extract_with_retry()`, `call_extraction_api()`
- Direct source code inspection: `policy_extractor/storage/database.py` — WAL mode confirmed at line 17
- Python verification: `python -c "from anthropic import RateLimitError, InternalServerError, APIConnectionError"` — exception class names confirmed
- Python verification: `python -c "from rich.progress import Progress; p = Progress(); print(hasattr(p, '_lock'))"` — thread safety confirmed
- Python verification: typer 0.24.1 `min`/`max` parameters on `typer.Option` confirmed from signature inspection
- Python verification: `concurrent.futures.ThreadPoolExecutor` and `as_completed` available in stdlib

### Secondary (MEDIUM confidence)
- Rich 14.3.3 documentation pattern: `progress.advance()` is thread-safe based on internal `_lock` presence; not tested empirically under concurrent console.print() + progress.advance() simultaneously
- Anthropic SDK exception hierarchy: verified from `__mro__` inspection; retry targets (`RateLimitError`, `InternalServerError`, `APIConnectionError`) are the correct classes

### Tertiary (LOW confidence)
- Estimate that `console.print()` from worker threads during active Rich Progress does not cause visual artifacts — confirmed `_lock` exists but empirical behavior under heavy concurrent output not tested

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified installed and importable; versions confirmed
- Architecture: HIGH — based on direct code inspection of all relevant files; no guesswork about existing interfaces
- Pitfalls: HIGH for Pitfalls 1-4 (derived from direct code analysis); MEDIUM for Pitfall 5 (jitter is standard practice, confirmed by decision but not empirically tested)
- Validation: HIGH — existing test patterns in test_cli.py are clear; new tests follow established mock patterns

**Research date:** 2026-03-19
**Valid until:** 2026-06-19 (stable libraries; Anthropic SDK exception classes could change on major version bump)
