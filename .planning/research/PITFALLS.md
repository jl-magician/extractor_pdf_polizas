# Pitfalls Research

**Domain:** PDF extraction pipeline — v1.1 additions (async batch, file upload API, golden dataset, Sonnet evaluator, Alembic migrations, Excel export) onto existing Python system
**Researched:** 2026-03-18
**Confidence:** HIGH (critical pitfalls verified against official docs and GitHub issues; integration pitfalls from confirmed real-world reports)

---

## Critical Pitfalls — v1.1 Additions

These are specific to adding the v1.1 features to the existing v1.0 system. The v1.0 pitfalls (OCR routing, schema validation, multi-insured, provenance, etc.) are addressed and resolved — see the v1.0 section at the bottom.

---

### Pitfall 1: UploadFile Closed Before Background Task Reads It

**What goes wrong:**
The FastAPI route handler returns a response, FastAPI/Starlette closes the `UploadFile` object, and then the background task tries to read from it — getting an empty or already-closed file. This is a deliberate behavioral change introduced in FastAPI >= 0.106.0. The extraction produces no content or raises `ValueError: I/O operation on closed file`. The background task runs to completion with empty data and writes nothing to the DB — the failure is silent unless logs are checked.

**Why it happens:**
The natural pattern is `background_tasks.add_task(process_pdf, file)` where `file` is the `UploadFile`. This worked in older FastAPI but is now broken by design. `UploadFile` wraps a temporary spooled file that Starlette owns and closes immediately after the response body is sent. The object reference passed to the background task points to a closed file descriptor.

**How to avoid:**
Read the full file bytes inside the route handler, before returning, and pass `bytes` (or a path to a saved temp file) to the background task. Never pass the `UploadFile` object itself.

```python
# WRONG — file is closed before process_pdf runs
@app.post("/upload")
async def upload(file: UploadFile, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_pdf, file)
    return {"status": "queued"}

# CORRECT — read bytes while the connection is still open
@app.post("/upload")
async def upload(file: UploadFile, background_tasks: BackgroundTasks):
    pdf_bytes = await file.read()
    original_name = file.filename
    background_tasks.add_task(process_pdf, pdf_bytes, original_name)
    return {"status": "queued", "filename": original_name}
```

**Warning signs:**
- Extraction runs but produces empty text or a `None` result
- `ValueError: I/O operation on closed file` in background task logs
- Works with small files (spooled entirely in memory) but fails with large PDFs
- Policy does not appear in DB after upload, but no 500 error is returned to client

**Phase to address:** PDF Upload API phase — first task that wires the upload endpoint to the extraction pipeline.

---

### Pitfall 2: SQLite "database is locked" Under Concurrent Background Tasks

**What goes wrong:**
Multiple background tasks each open their own SQLAlchemy session and try to write simultaneously. SQLite serializes all writes. Without WAL mode and a busy timeout, even a brief overlap produces `OperationalError: database is locked`. If exceptions in background tasks are not logged explicitly, these failures are silent — the policy is silently dropped.

**Why it happens:**
The current `database.py` creates the engine with no special pragmas:
```python
create_engine(f"sqlite:///{db_path}", echo=False)
```
This uses SQLite's default DELETE journal mode, which is the most restrictive for concurrency. The existing sync CLI never triggered this because batch processing was sequential. Async tasks break this assumption.

**How to avoid:**
Enable WAL mode and set a `busy_timeout` immediately on engine creation. WAL allows concurrent reads while a single writer holds the lock, and `busy_timeout` makes SQLite retry automatically instead of immediately raising.

```python
from sqlalchemy import event

engine = create_engine(f"sqlite:///{db_path}", echo=False)

@event.listens_for(engine, "connect")
def set_sqlite_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")  # 5-second retry window
    cursor.close()
```

WAL does not eliminate serialized writes — only one writer at a time is still the constraint. Keep the semaphore on concurrent extraction tasks at 3-5 workers maximum.

**Warning signs:**
- `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked` in logs
- Batch jobs that complete fine at low concurrency fail at 5+ concurrent tasks
- Silent policy drops when background task exceptions are swallowed

**Phase to address:** Async batch processing phase — before any concurrency is introduced, as the very first step.

---

### Pitfall 3: Alembic `stamp head` Skipped When Retrofitting — Schema Drift Forever

**What goes wrong:**
Developer adds Alembic, runs `alembic autogenerate`. The generated migration is empty because the tables already exist from `create_all()`. Developer concludes "nothing to migrate" and continues. The `alembic_version` table is never populated. Future migrations are generated correctly against the current schema, but `alembic upgrade head` on a fresh database tries to apply all migrations including the empty "initial" one — and the resulting schema is wrong or incomplete because the initial migration does not create the tables that `create_all()` previously created.

**Why it happens:**
Alembic and `create_all()` are parallel schema owners. When both coexist, there is no single source of truth about current state. Alembic's revision chain is disconnected from the live schema. The `alembic_version` table simply does not exist yet.

**How to avoid:**
Immediately after installing Alembic on this codebase:
1. Create an "initial baseline" revision — either empty or containing the full `CREATE TABLE` statements for the existing schema.
2. Run `alembic stamp head` against the existing database to declare "this DB is already at this revision."
3. From this point forward, all schema changes go exclusively through Alembic migrations.
4. Remove `Base.metadata.create_all()` from the production `on_startup` handler. Keep it only in tests that use in-memory SQLite.

**Warning signs:**
- `alembic current` returns nothing on the live database
- `alembic autogenerate` produces an empty migration on a DB that has tables
- New developer clones repo, runs `alembic upgrade head`, gets `OperationalError: table already exists`

**Phase to address:** Alembic migrations phase — `alembic stamp head` must be the very first action, before any other migration is created.

---

### Pitfall 4: SQLite Column Modification Requires `batch_alter_table`, Not Standard `ALTER COLUMN`

**What goes wrong:**
A migration that changes a column's type, adds a constraint, or renames a column uses standard Alembic `op.alter_column()`. SQLite does not support `ALTER COLUMN`. Alembic raises `NotImplementedError` at migration time, or (worse) silently ignores the change, leaving the schema in a partially applied state.

**Why it happens:**
Alembic autogenerate produces standard `op.alter_column()` calls that work on PostgreSQL and MySQL. Developers apply the generated migration without reviewing it for SQLite compatibility. The SQLite limitation is not obvious from the Alembic docs unless you specifically read the SQLite section.

**How to avoid:**
Any migration that modifies an existing column on SQLite must use `op.batch_alter_table()` — this is Alembic's built-in mechanism for SQLite's `ALTER TABLE` limitation (it creates a new table, copies data, and drops the old one).

```python
# WRONG — fails on SQLite
def upgrade():
    op.alter_column("polizas", "prima_total", nullable=False)

# CORRECT — works on SQLite
def upgrade():
    with op.batch_alter_table("polizas") as batch_op:
        batch_op.alter_column("prima_total", nullable=False)
```

Set `render_as_batch=True` in `alembic.ini` or `env.py` to make autogenerate produce batch-compatible migrations by default.

**Warning signs:**
- `NotImplementedError` during `alembic upgrade head`
- Migration completes without error but the column type did not change (check with `PRAGMA table_info(...)`)
- Autogenerated migration contains bare `op.alter_column()` calls

**Phase to address:** Alembic migrations phase — configure `render_as_batch=True` before generating any migration that touches existing columns.

---

### Pitfall 5: Anthropic Rate Limit Storm When Asyncio Batch Has No Backoff

**What goes wrong:**
`asyncio.gather()` launches N concurrent extractions simultaneously. Each sends an Anthropic API request. Anthropic enforces per-minute limits on requests (RPM), input tokens (ITPM), and output tokens (OTPM). Exceeding any dimension returns HTTP 429. Without a bounded semaphore and exponential backoff, all concurrent tasks receive 429 simultaneously and immediately retry — amplifying the rate limit storm. All tasks return `None` and the batch silently produces no results.

**Why it happens:**
The existing `extract_with_retry` catches `ValidationError` but not `anthropic.RateLimitError`. Moving to async without updating the retry logic means 429 errors surface as unhandled exceptions that return `None` — silently dropping the PDF from batch results.

**How to avoid:**
- Use `asyncio.Semaphore(3)` (configurable via `Settings`) to cap concurrent Anthropic calls.
- Use `anthropic.AsyncAnthropic` for true async; the sync `anthropic.Anthropic` blocks the event loop.
- Catch `anthropic.RateLimitError` explicitly and apply exponential backoff with jitter.
- Respect the `Retry-After` header if present.

```python
import asyncio, random
import anthropic

sem = asyncio.Semaphore(settings.MAX_CONCURRENT_EXTRACTIONS)  # default: 3

async def extract_async(client, text, file_hash, model, max_retries=5):
    async with sem:
        for attempt in range(max_retries):
            try:
                msg = await client.messages.create(...)
                return parse_and_validate(msg, file_hash)
            except anthropic.RateLimitError:
                wait = min(2 ** attempt + random.random(), 60)
                await asyncio.sleep(wait)
        return None
```

**Warning signs:**
- Batch of 10+ PDFs produces more `None` results than expected
- Logs show `RateLimitError` without any retry
- API dashboard shows usage that flatlines (throttled) in bursts

**Phase to address:** Async batch processing phase — implement semaphore and backoff before any concurrent extraction is tested.

---

### Pitfall 6: Sonnet Evaluator Costs Doubling Per-PDF Without a Trigger Boundary

**What goes wrong:**
The quality evaluator sends the Haiku extraction output plus the original PDF text to Sonnet for evaluation. Each PDF now costs two API calls: one Haiku extraction + one Sonnet evaluation. If the evaluator is wired into the default extraction path (inline in `extract_with_retry` or in the upload handler), every upload costs 2x more and takes 10-30 seconds longer. There is no opt-out.

**Why it happens:**
The evaluator feels like a natural quality gate to add at the end of the extraction pipeline. The path of least resistance is to call it inside the extraction function. This merges a debug/QA tool into the production hot path.

**How to avoid:**
The Sonnet evaluator is a separate, opt-in step with a defined trigger boundary:
- **Triggered by:** `poliza-extractor regression` CLI command, or `POST /upload?evaluate=true` API parameter.
- **Never triggered by:** default extraction, standard batch runs, or the upload endpoint without explicit opt-in.
- Track Sonnet token cost separately from Haiku extraction cost in logs.
- Set a hard budget ceiling per evaluation run (e.g., skip if batch > 50 PDFs without explicit confirmation).

**Warning signs:**
- API cost per PDF doubles after evaluator is added
- Upload endpoint latency increases by 10-30 seconds per PDF
- Evaluator is always triggered with no way to disable it

**Phase to address:** Sonnet evaluator phase — define the trigger boundary and opt-in mechanism before writing any evaluator code.

---

### Pitfall 7: Golden Dataset Fixtures Tied to Absolute File Paths

**What goes wrong:**
Golden dataset fixtures store absolute file paths (e.g., `C:\Users\josej\extractor_pdf_polizas\pdfs-to-test\axa_auto.pdf`). Tests pass on one machine and fail on another with `FileNotFoundError`. The existing `IngestionCache.file_path` column already stores absolute paths — copying this pattern into golden fixtures carries the same fragility.

**Why it happens:**
Developers copy the same convention from the cache table. Absolute paths feel stable during development on a single machine.

**How to avoid:**
- Golden dataset references use file hashes (SHA-256), not file paths. The hash is the stable, machine-independent identity.
- Store fixtures as `tests/golden/{sha256_hash}.json` files keyed by hash.
- The regression runner hashes the input PDF, looks up the expected output by hash, and compares field-by-field.
- PDFs used in golden tests live in `tests/fixtures/pdfs/` (checked into the repo if file size permits, or documented as downloads).
- Anonymize all golden fixtures before committing — replace real names, RFCs, CURPs, and phone numbers with synthetic values.

**Warning signs:**
- Tests fail on fresh clone with `FileNotFoundError`
- Fixture JSON contains any absolute path strings (catch with `grep -r "C:\\\\" tests/golden/`)
- Golden tests diverge in results between developer machines

**Phase to address:** Golden dataset phase — hash-keyed fixture design must be established before any fixture is created.

---

### Pitfall 8: Excel Export Decimal/Date Types Serialized as Text

**What goes wrong:**
`openpyxl` (used by `pandas.DataFrame.to_excel`) cannot serialize Python `Decimal` or `datetime.date` objects directly. The ORM models use `Numeric(precision=15, scale=2)` which returns `Decimal` objects, and `Date` columns return `datetime.date`. Passing them directly to a DataFrame produces `TypeError` during export, or silently writes string representations — breaking Excel SUM formulas, number formatting, and date sorting.

**Why it happens:**
The existing `orm_to_schema` already handles serialization correctly for the JSON API. But an Excel export path that reads ORM rows directly (for speed) bypasses this and hits the type incompatibility. Manual testing with small datasets looks correct because `str(Decimal("12500.00"))` renders as `12500.00`, but Excel receives a text cell, not a number cell.

**How to avoid:**
Route all Excel export through the same serialization layer used by the API:
1. Call `orm_to_schema(poliza)` to get a `PolicyExtraction` Pydantic model.
2. Call `.model_dump(mode="json")` to get JSON-serializable primitives (`float`, `str`, `None`).
3. Build the DataFrame from these dicts.

Write a dedicated `poliza_to_excel_row(poliza: Poliza) -> dict` function that controls the column mapping and handles the `Decimal` → `float` and `date` → `datetime` conversions explicitly.

**Warning signs:**
- Excel file opens but SUM formula on `prima_total` column returns 0 (stored as text)
- `TypeError: cannot convert Decimal to float` during DataFrame construction
- Date columns sort alphabetically instead of chronologically in Excel

**Phase to address:** Excel export phase — serialization handling must be the first task, before any column mapping is written.

---

### Pitfall 9: Background Task Provides No Job ID — Client Cannot Poll for Result

**What goes wrong:**
The upload endpoint returns `{"status": "queued"}` with no job ID. The client has no way to know when extraction is complete. They must poll `GET /polizas` and try to match the newly uploaded PDF to a newly created record — which is ambiguous when multiple uploads happen close together. If extraction fails, the client never finds out.

**Why it happens:**
BackgroundTasks in FastAPI is the simplest async pattern and returns immediately. Developers add it without thinking about the client's need to observe the task's outcome.

**How to avoid:**
Generate a UUID job ID at upload time and return it in the 202 response. Track job state (queued, processing, done, failed) in a lightweight in-memory dict (acceptable for single-process local deployment) or a `jobs` table in SQLite. Expose `GET /jobs/{job_id}` that returns current status and, on completion, the extracted policy ID.

```python
@app.post("/upload", status_code=202)
async def upload_pdf(file: UploadFile, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    pdf_bytes = await file.read()
    job_store[job_id] = {"status": "queued", "poliza_id": None}
    background_tasks.add_task(run_extraction, job_id, pdf_bytes, file.filename)
    return {"job_id": job_id, "status": "queued"}
```

**Warning signs:**
- Upload response contains no ID field
- Client must guess which newly-created policy corresponds to their upload
- Extraction failures are invisible to the client (no error reporting path)

**Phase to address:** PDF Upload API phase — job ID and polling endpoint are part of the API contract, not an afterthought.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `Base.metadata.create_all()` in `on_startup` after adding Alembic | No code change needed | Schema diverges silently; fresh-DB migrations produce wrong schema | Never — remove from production startup as soon as Alembic is stamped |
| Run extraction synchronously inside `async def` FastAPI route handler | Simpler code; reuse existing sync functions | Blocks entire event loop; concurrent uploads stall | Only if max 1 concurrent upload is guaranteed (it won't be) |
| Hardcode semaphore limit of 5 concurrent tasks | Fastest to ship | Overloads Anthropic rate limits for lower-tier accounts; breaks silently | Never hardcode — make it a `Settings` field with a safe default of 3 |
| Golden dataset as hand-curated JSON without source PDFs | Fast to create | Cannot re-run extraction to verify; becomes stale as prompt changes | Only if PDFs contain real PII that cannot be stored; document explicitly |
| Sonnet evaluator wired into default extraction pipeline | No separate CLI/API surface needed | Doubles cost and latency for every extraction; no opt-out | Never in the hot path |
| Excel export via `polizas` JSON dump → pandas → Excel (raw ORM objects) | Fast to implement | `Decimal`/`date` type issues; broken Excel formulas | Acceptable only if types are explicitly cast before DataFrame creation |
| In-memory `job_store` dict for background task state | No new DB table needed | State lost on server restart; no persistence across processes | Acceptable for single-user local deployment; document the limitation |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| FastAPI `UploadFile` + `BackgroundTasks` | Passing `UploadFile` object to background task | Read `bytes` in handler, pass bytes to task |
| SQLAlchemy sync Session + asyncio | Using `SessionLocal()` directly in `async def` route without executor | Use `run_in_executor` for sync DB calls, or switch to `async_sessionmaker` + `aiosqlite` |
| Anthropic SDK in asyncio context | Using sync `anthropic.Anthropic` in `asyncio.gather` | Use `anthropic.AsyncAnthropic` for true async; sync in thread pool is a fallback only |
| Alembic + existing `create_all()` database | Forgetting `alembic stamp head` on existing DB | Stamp first, then all future schema changes go through migrations |
| Alembic autogenerate on SQLite | Applying generated `op.alter_column()` directly | Always use `op.batch_alter_table()`; set `render_as_batch=True` in `env.py` |
| openpyxl / pandas + SQLAlchemy ORM | Passing ORM model instances directly to DataFrame | Serialize through Pydantic `.model_dump(mode="json")` first |
| Sonnet evaluator + Haiku extraction | Calling Sonnet evaluator in the same function as Haiku extraction | Evaluator is a separate opt-in step; never embedded in the extraction function |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `asyncio.gather(*tasks)` with no semaphore | All tasks hit Anthropic at once; mass 429 errors; batch result is mostly `None` | `asyncio.Semaphore(3)` minimum | Any batch > 5 PDFs |
| SQLite WAL checkpoint blocked by active readers | WAL file grows indefinitely; disk usage climbs; checkpoint never completes | Monitor WAL file size; ensure idle periods between batch runs | Continuous 24/7 ingestion |
| `orm_to_schema` called N times in bulk export | O(N) Pydantic object creation; slow for 200+ policies | Build rows in a single query with `yield_per`; serialize once | 100+ policies in a single export |
| Sonnet evaluator triggered per-PDF in a large batch | Cost and latency multiplied; Sonnet OTPM exhausted faster than Haiku | Evaluator as separate post-batch pass with its own rate limiting | Any batch > 20 PDFs |
| Background task shares engine with request handler (no session isolation) | Deadlocks when request holds a read session and task tries to write | Each background task creates and closes its own session scope | Any concurrent upload |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing uploaded PDF with original client filename on disk | Path traversal (`../../etc/passwd` in filename), filename collision between clients | Rename to `{uuid4()}.pdf` before saving; validate MIME type, not just file extension |
| No file size limit on `POST /upload` | 500 MB upload exhausts server memory or disk | Check `Content-Length` header and enforce `max_size` limit in a FastAPI dependency before reading bytes |
| No MIME type validation on upload | Non-PDF file crashes PyMuPDF or OCR pipeline | Check `file.content_type == "application/pdf"` and verify PDF magic bytes (`%PDF`) in first 4 bytes |
| Golden dataset contains real customer PII (RFC, CURP, nombres) | Data leak if repository is shared or made public | Anonymize all golden fixtures before committing; use synthetic names, hashed identifiers |
| Job store exposed without scoping | One client can poll or cancel another client's job (not relevant for local use) | Not a concern for single-user local deployment; document if API is ever exposed externally |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Upload API returns `{"status": "queued"}` with no job ID | Caller has no way to poll for result; must guess which new policy matches their upload | Return `{"job_id": "...", "status": "queued"}` with `202 Accepted` |
| Regression test failures reported as raw JSON diffs | Hard to read which fields regressed and by how much | Format failures as field-level diffs: `prima_total: expected 12500.00, got 12,500.00` |
| Excel export includes internal provenance fields | End users see `source_file_hash`, `model_id`, `prompt_version` — confusing to non-technical staff | Separate business fields from technical fields; default export omits technical columns |
| Sonnet evaluator score logged only to stdout | Cannot trend quality over time; no baseline to compare against | Persist evaluation scores to a `quality_evaluations` table with prompt version and timestamp |
| Batch progress shown only at completion | Large async batch feels frozen for minutes | Emit per-PDF progress via job status polling; show current count in CLI |

---

## "Looks Done But Isn't" Checklist

- [ ] **PDF Upload API:** Endpoint returns 202 and a job ID — verify the background task runs to completion and the policy appears in `GET /polizas` with correct data
- [ ] **PDF Upload API:** Verify uploaded file is renamed to UUID on disk — original filename must not appear in the file system
- [ ] **PDF Upload API:** Verify `GET /jobs/{job_id}` returns `"status": "done"` (not perpetually `"processing"`) after extraction completes
- [ ] **Async batch:** `asyncio.gather` with semaphore in place — verify zero `OperationalError: database is locked` with 5 concurrent uploads
- [ ] **Async batch:** Run batch of 10 PDFs — verify zero `RateLimitError` dropped tasks at default semaphore setting
- [ ] **Alembic setup:** `alembic current` returns a revision on the live database — not empty (empty = stamp was skipped)
- [ ] **Alembic first migration:** `alembic upgrade head` on a fresh SQLite file creates all tables correctly — verify with `PRAGMA table_info`
- [ ] **Alembic column change:** Any migration modifying an existing column uses `batch_alter_table` — verify by grep for bare `op.alter_column` calls
- [ ] **Golden dataset:** All fixtures are keyed by SHA-256 hash, no absolute paths — verify `grep -r "C:\\\\" tests/golden/` returns nothing
- [ ] **Golden dataset:** All PII anonymized — verify no real RFC, CURP, or full name appears in fixture files
- [ ] **Sonnet evaluator:** Default extraction path does NOT trigger the evaluator — verify API call count is unchanged from v1.0 baseline for a standard upload
- [ ] **Excel export:** Numeric columns are numeric in Excel, not text — verify SUM formula on `prima_total` returns a number, not 0
- [ ] **Excel export:** Date columns sort chronologically in Excel — verify date column cell type is Date, not General/Text

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| UploadFile closed in background task — extraction produced no data | LOW | Add `pdf_bytes = await file.read()` before returning; no data permanently lost if upload is retried |
| `database is locked` errors caused silent policy drops | MEDIUM | Enable WAL + busy_timeout; identify dropped PDFs from logs; re-submit failed uploads |
| Alembic stamp skipped — schema drift on fresh DB | HIGH | `alembic stamp head` on live DB; audit all pending migrations manually; test on a copy of DB before applying to production |
| Anthropic rate limit storm — batch returned all None | LOW | Re-submit batch with lower concurrency (`MAX_CONCURRENT_EXTRACTIONS=2`); implement backoff before next attempt |
| Golden dataset with absolute paths — CI failures | LOW | Replace paths with hashes; regenerate affected fixtures; 1-2 hours of work |
| Excel export with text-stored decimals — formulas broken | LOW | Fix serialization layer; re-export; no data loss in DB |
| Sonnet evaluator in hot path causing upload timeouts | MEDIUM | Move evaluator behind opt-in flag; rollback the route change; no data loss |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| UploadFile closed before background task reads it | PDF Upload API | Upload 5 MB PDF; check background task logs for successful extraction; verify policy in DB |
| No job ID for polling | PDF Upload API | Upload response contains `job_id`; `GET /jobs/{job_id}` returns correct status |
| File stored with original filename (path traversal risk) | PDF Upload API | Inspect filesystem; all uploaded files named `{uuid4()}.pdf` |
| SQLite locked under concurrent background tasks | Async batch | Run 5 concurrent uploads; confirm zero `OperationalError` in logs |
| Anthropic rate limit storm without backoff | Async batch | Batch of 10 PDFs completes with zero 429 errors in logs |
| Alembic stamp skipped — schema drift | Alembic migrations (first task) | `alembic current` returns a revision; `alembic upgrade head` on fresh DB creates all tables |
| SQLite `ALTER COLUMN` without `batch_alter_table` | Alembic migrations | All column-modifying migrations use `batch_alter_table`; verified in migration review |
| Sonnet evaluator cost doubling per-PDF | Sonnet evaluator | API call count per upload unchanged from v1.0 baseline without explicit `?evaluate=true` |
| Golden dataset tied to absolute file paths | Golden dataset | `grep -r "Users" tests/golden/` returns nothing; tests pass on clean clone |
| Excel Decimal/Date serialization as text | Excel export | Export 10 policies; SUM on `prima_total` returns numeric result in Excel |

---

## v1.0 Pitfalls (Resolved — For Reference)

These pitfalls were identified during v1.0 research and are now addressed in the shipped system. They remain here to inform regression verification during v1.1 development.

| Pitfall | v1.0 Resolution | v1.1 Regression Risk |
|---------|----------------|----------------------|
| Scanned PDFs sent raw to LLM | OCR routing via classifier + ocrmypdf | Low — pipeline unchanged in v1.1 |
| No output schema validation | Pydantic + tool_use forced structured output | Low — extraction layer unchanged |
| Generic prompt failing minority layouts | Single-pass adaptive extraction (no templates) | Low — prompt unchanged |
| Uncontrolled API costs from token bloat | Per-page assembly; Haiku default; cost tracking | Medium — async batch may increase total spend; monitor |
| Date/currency format inconsistency | Canonical Pydantic schema with ISO 8601 dates | Low — schema unchanged |
| No provenance metadata | `source_file_hash`, `model_id`, `prompt_version` stored per record | Low — provenance fields intact |
| Model drift / no regression tests | Golden dataset planned for v1.1 | Addressed by v1.1 golden dataset phase |
| Multi-insured flat schema | Separate `asegurados` and `coberturas` tables | Low — schema unchanged |

---

## Sources

- [FastAPI: UploadFile + BackgroundTasks file-closed issue (GitHub Discussion #10936)](https://github.com/fastapi/fastapi/discussions/10936)
- [FastAPI: Reading file into background task (GitHub Discussion #11177)](https://github.com/fastapi/fastapi/discussions/11177)
- [Patching uploaded files for usage in FastAPI background tasks — dida.do](https://dida.do/blog/patching-uploaded-files-for-usage-in-fastapi-background-tasks)
- [FastAPI Background Tasks — official docs](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [SQLite Write-Ahead Logging — official docs](https://www.sqlite.org/wal.html)
- [SQLite concurrent writes and "database is locked" errors — tenthousandmeters.com](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/)
- [Alembic Autogenerate documentation](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [Alembic Cookbook — working with existing databases](https://alembic.sqlalchemy.org/en/latest/cookbook.html)
- [Alembic Tutorial — stamp command](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Anthropic Concurrency Limit Reached — drdroid.io](https://drdroid.io/integration-diagnosis-knowledge/anthropic-concurrency-limit-reached)
- [Managing API Token Limits in Concurrent LLM Applications — Medium](https://amusatomisin65.medium.com/designing-for-scale-managing-api-token-limits-in-concurrent-llm-applications-84e8ccbce0dc)
- [Building a Golden Dataset for AI Evaluation — getmaxim.ai](https://www.getmaxim.ai/articles/building-a-golden-dataset-for-ai-evaluation-a-step-by-step-guide/)
- [Prompt regression testing: Preventing quality decay — statsig.com](https://www.statsig.com/perspectives/slug-prompt-regression-testing)
- [Understanding Pitfalls of Async Task Management in FastAPI — leapcell.io](https://leapcell.io/blog/understanding-pitfalls-of-async-task-management-in-fastapi-requests)

---
*Pitfalls research for: PDF extraction pipeline — v1.1 additions onto existing v1.0 system*
*Researched: 2026-03-18*
