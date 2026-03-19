# Phase 8: PDF Upload API - Research

**Researched:** 2026-03-19
**Domain:** FastAPI file upload, background threading, in-memory job tracking
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Upload endpoint design**
- `POST /polizas/upload` accepts multipart/form-data with PDF file
- File size limit: 50 MB
- Accepts optional query parameters: `model` (override extraction model) and `force` (boolean, reprocess even if already extracted) — full parity with CLI `extract` command
- Returns 202 Accepted with full job object: `{ "job_id": "...", "status": "pending", "created_at": "...", "filename": "..." }`
- Validates uploaded file: check PDF magic bytes (`%PDF-`) AND `.pdf` extension; reject non-PDFs with 422

**Job lifecycle & polling**
- 4 job states: `pending` → `processing` → `complete` | `failed`
- `GET /jobs/{id}` returns full job object; when complete, includes the full extracted poliza inline in a `result` field: `{ "status": "complete", "result": { poliza data... } }`
- `GET /jobs` lists all non-expired jobs (useful for debugging/monitoring)
- Completed and failed jobs expire from in-memory store after 1 hour
- No job cancellation endpoint — jobs run to completion or failure
- In-memory dict for job storage (already decided in STATE.md — lost on restart is acceptable)

**Pipeline integration**
- Background extraction via `threading.Thread` — one thread per upload, sync pipeline runs as-is
- Uploaded PDFs saved to `uploads/` directory under project root (not OS temp) — easier to debug
- Idempotency: always return 202 with a job, but if file hash already in DB and force=false, the job resolves immediately to existing poliza (consistent async interface, no extraction cost)
- Each background thread creates its own `SessionLocal()` for DB access (thread-safe)

**Error handling & edge cases**
- Failed extraction → job status `failed` with error detail in response: `{ "status": "failed", "error": "Claude API rate limited" }`
- No auto-retry on failure — client decides whether to re-upload
- Temp PDF files: cleaned up on success, **kept on failure** for debugging (`uploads/` directory)
- Server restart during processing: in-progress jobs are lost; re-uploading the same PDF works (idempotent via hash cache)

### Claude's Discretion
- Job ID format (UUID vs short ID)
- Exact job object schema fields beyond the discussed ones
- Thread naming/logging strategy
- How to structure the upload route module (inline in `api/__init__.py` vs separate `api/upload.py`)
- Job expiry implementation (lazy cleanup on access vs periodic sweep)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| API-01 | User can POST a PDF file to `/polizas/upload` and receive extraction results | FastAPI `UploadFile` + `Form` pattern; 202 response with job object |
| API-02 | Upload endpoint accepts multipart/form-data with PDF file | `python-multipart` dependency (not yet in pyproject.toml); FastAPI `File(...)` parameter |
| API-03 | Upload triggers the full pipeline: ingest → extract → persist → return structured result | Threading pattern; existing `ingest_pdf`, `extract_policy`, `upsert_policy` reused as-is |
| API-04 | Long-running uploads return 202 Accepted with a job ID | `JSONResponse(content=..., status_code=202)` consistent with existing route style |
| API-05 | User can poll `GET /jobs/{id}` for job status and results | In-memory dict + lazy expiry; `orm_to_schema` for result serialization |
| API-06 | Uploaded PDF temp files are cleaned up after extraction completes | `Path.unlink(missing_ok=True)` in thread's finally block on success path; kept on failure |
</phase_requirements>

---

## Summary

This phase extends the existing FastAPI app with three new endpoints: `POST /polizas/upload` (receive PDF + return 202), `GET /jobs/{id}` (poll for result), and `GET /jobs` (list all active jobs). The implementation is purely additive — no existing routes or pipeline code change.

The entire extraction stack (`ingest_pdf`, `extract_policy`, `upsert_policy`) already exists and runs synchronously. The only new infrastructure needed is: (1) saving the uploaded file to `uploads/`, (2) a thread that runs the pipeline, (3) an in-memory dict to track job state, and (4) a FastAPI `UploadFile` parameter. The idempotency logic mirrors the CLI `extract` command exactly — `compute_file_hash` + `is_already_extracted` — already in `cli_helpers.py`.

The one missing dependency is `python-multipart`, which FastAPI requires for multipart form data. Everything else (`fastapi`, `uvicorn`, `sqlalchemy`, `threading`) is already installed.

**Primary recommendation:** Add `python-multipart` to `pyproject.toml`, create a new `api/upload.py` module with the three routes, import and mount them in `api/__init__.py`. Reuse the CLI extract pattern verbatim inside the background thread.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.135.1 (installed) | Route definitions, `UploadFile`, `File`, `Form` | Already in project |
| python-multipart | latest (not yet installed) | Enables multipart/form-data parsing in FastAPI | Required by FastAPI for file uploads; FastAPI raises error without it |
| threading (stdlib) | stdlib | Background extraction per upload | Chosen in CONTEXT.md; sync pipeline needs no async |
| uuid (stdlib) | stdlib | Job ID generation | Collision-free, no dependency |
| pathlib (stdlib) | stdlib | `uploads/` directory management, file cleanup | Already used throughout project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| datetime (stdlib) | stdlib | `created_at`, `expires_at` timestamps in job object | Job lifecycle tracking |
| loguru | 0.7+ (installed) | Thread-level logging with job_id context | Consistent with project logging style |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| threading.Thread | asyncio + run_in_executor | Asyncio version more complex; sync pipeline has no benefit; CONTEXT.md locked threading |
| in-memory dict | Redis / SQLite jobs table | Overkill for local single-user app; CONTEXT.md locked in-memory |
| uuid4 | short ID (nanoid) | UUID is stdlib, no extra dependency; format is Claude's discretion |

**Installation (missing dependency only):**
```bash
pip install python-multipart
```

Add to `pyproject.toml` dependencies:
```
"python-multipart>=0.0.9",
```

**Version verification:** `python-multipart` latest stable is `0.0.20` (March 2026). Use `>=0.0.9` minimum constraint as FastAPI docs recommend. (MEDIUM confidence — based on pip registry patterns; version pinning is safe at `>=0.0.9`.)

---

## Architecture Patterns

### Recommended Project Structure

New files for this phase:
```
policy_extractor/
└── api/
    ├── __init__.py       # existing — add 3 imports at bottom
    └── upload.py         # NEW — upload route, job store, background worker
uploads/                  # NEW — created at startup; holds in-flight PDFs
tests/
└── test_upload.py        # NEW — upload API tests
```

### Pattern 1: FastAPI File Upload (multipart/form-data)

**What:** Accept PDF binary via `UploadFile`, optional query params for model/force override.
**When to use:** Every POST to `/polizas/upload`.
**Example:**
```python
# Source: FastAPI official docs — https://fastapi.tiangolo.com/tutorial/request-files/
from fastapi import APIRouter, File, UploadFile, Query, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

@router.post("/polizas/upload", status_code=202)
async def upload_pdf(
    file: UploadFile = File(...),
    model: str | None = Query(None),
    force: bool = Query(False),
) -> JSONResponse:
    contents = await file.read()
    # validate, save, dispatch thread
    ...
```

**Key details:**
- `UploadFile.read()` is async — must `await` it
- Check magic bytes on `contents[:4]` (`b"%PDF"`) before saving
- Check `file.filename.lower().endswith(".pdf")` for extension
- Reject with `raise HTTPException(status_code=422, detail="...")` on invalid files
- 50 MB limit: check `len(contents) > 50 * 1024 * 1024` and reject with 413

### Pattern 2: In-Memory Job Store

**What:** Module-level dict protected by a lock for concurrent thread access.
**When to use:** All job read/write operations.
**Example:**
```python
import threading
import uuid
from datetime import datetime, timezone

_job_store: dict[str, dict] = {}
_store_lock = threading.Lock()

def _create_job(filename: str) -> dict:
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
        "result": None,
        "error": None,
        "expires_at": None,  # set when complete/failed
    }
    with _store_lock:
        _job_store[job_id] = job
    return job
```

**Why a lock matters:** The main thread writes the job at upload time; the background thread updates `status`, `result`, `error`; a polling request reads it. Without a lock, dict mutation can produce torn reads on CPython — even though CPython's GIL makes simple key assignment atomic, multi-field updates require explicit locking.

### Pattern 3: Background Thread Extraction

**What:** `threading.Thread(target=_run_extraction, args=(...), daemon=True)` dispatched immediately after 202 response.
**When to use:** Every upload after validation passes.
**Example:**
```python
from policy_extractor.storage.database import SessionLocal
from policy_extractor.ingestion import ingest_pdf
from policy_extractor.extraction import extract_policy
from policy_extractor.storage.writer import upsert_policy, orm_to_schema
from policy_extractor.ingestion.cache import compute_file_hash
from policy_extractor.cli_helpers import is_already_extracted

def _run_extraction(job_id: str, pdf_path: Path, model: str | None, force: bool) -> None:
    _update_job(job_id, status="processing")
    session = SessionLocal()
    try:
        # Idempotency — mirrors CLI extract command
        file_hash = compute_file_hash(pdf_path)
        if not force and is_already_extracted(session, file_hash):
            # Resolve immediately from DB without extraction
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            from policy_extractor.storage.models import Poliza
            poliza = session.execute(
                select(Poliza)
                .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
                .where(Poliza.source_file_hash == file_hash)
            ).scalar_one()
            result = orm_to_schema(poliza).model_dump(mode="json")
            _update_job(job_id, status="complete", result=result)
            pdf_path.unlink(missing_ok=True)  # cleanup on success
            return

        ingestion_result = ingest_pdf(pdf_path, session=session, force_reprocess=force)
        policy, _ = extract_policy(ingestion_result, model=model)
        if policy is None:
            raise RuntimeError("Extraction returned None")
        upsert_policy(session, policy)
        result = policy.model_dump(mode="json")
        _update_job(job_id, status="complete", result=result)
        pdf_path.unlink(missing_ok=True)  # cleanup on success only (API-06)
    except Exception as exc:
        _update_job(job_id, status="failed", error=str(exc))
        # PDF kept for debugging — do NOT unlink on failure
    finally:
        session.close()
        _mark_expiry(job_id)  # set expires_at = now + 1 hour
```

**daemon=True** is important: if the server process exits, threads don't block shutdown.

### Pattern 4: Lazy Job Expiry

**What:** On every read of `/jobs/{id}` or `/jobs`, check `expires_at` and purge expired entries.
**When to use:** Read operations on the job store.
**Example:**
```python
def _get_job(job_id: str) -> dict | None:
    _purge_expired()
    with _store_lock:
        return dict(_job_store.get(job_id, {})) or None

def _purge_expired() -> None:
    now = datetime.now(timezone.utc)
    with _store_lock:
        expired = [
            k for k, v in _job_store.items()
            if v.get("expires_at") and datetime.fromisoformat(v["expires_at"]) < now
        ]
        for k in expired:
            del _job_store[k]
```

This is simpler than a background sweep thread and sufficient for the single-user local use case.

### Pattern 5: Integrating New Router into Existing App

**What:** `APIRouter` in `upload.py`, included in `app` in `__init__.py`.
**When to use:** This is the project pattern for adding route groups.
**Example:**
```python
# In api/__init__.py — add at the bottom, after existing routes
from policy_extractor.api.upload import router as upload_router
app.include_router(upload_router)
```

And in `api/upload.py`:
```python
from fastapi import APIRouter
router = APIRouter()
```

This keeps `__init__.py` readable and test_api.py untouched.

### Anti-Patterns to Avoid
- **Reading UploadFile synchronously:** `file.read()` without `await` hangs in async context — always use `await file.read()`.
- **Sharing a single Session across threads:** SQLite sessions are not thread-safe. Each thread MUST create its own `SessionLocal()` and close it in a `finally` block.
- **Writing to OS temp dir:** CONTEXT.md locked `uploads/` under project root. Do not use `tempfile.mkstemp` or `tempfile.NamedTemporaryFile`.
- **Using `UploadFile` after the handler returns:** The file object closes when the handler exits. Always read bytes eagerly into memory or save to disk before returning the 202.
- **Mutating job dict in-place without lock:** Use a dedicated `_update_job()` helper that acquires the lock, to avoid torn reads.
- **Forgetting to create `uploads/` at startup:** `mkdir(parents=True, exist_ok=True)` in the `on_startup` event, alongside `init_db`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multipart parsing | Custom request body parser | `python-multipart` + FastAPI `UploadFile` | RFC 2388 has many edge cases (boundaries, encoding, large files) |
| PDF magic byte check | Manual byte parser | `contents[:4] == b"%PDF"` one-liner | PDF spec: all valid PDFs start with `%PDF-` |
| File hash | Custom hash function | `compute_file_hash(path)` (already exists in `ingestion/cache.py`) | SHA-256, already used for idempotency everywhere |
| Idempotency logic | New DB query | `is_already_extracted(session, file_hash)` (already in `cli_helpers.py`) | Exact same check CLI uses |
| Pipeline orchestration | New extraction wrapper | CLI `extract` command flow (lines 92-128 of `cli.py`) | Copy verbatim into thread worker |
| ORM-to-JSON for result | Custom serializer | `orm_to_schema(poliza).model_dump(mode="json")` | Already handles Decimal, datetime, relationships |

**Key insight:** The entire extraction pipeline is already written. The background thread is just the CLI `extract` command running inside a thread with job state mutations around it.

---

## Common Pitfalls

### Pitfall 1: `python-multipart` Not Installed
**What goes wrong:** FastAPI raises `RuntimeError: Form data requires "python-multipart" to be installed` at request time (not import time). The app starts fine but every upload returns a 500.
**Why it happens:** FastAPI lazily imports `python-multipart` only when a multipart route is called.
**How to avoid:** Add `"python-multipart>=0.0.9"` to `pyproject.toml` dependencies before writing any upload route. Verify with `pip show python-multipart`.
**Warning signs:** `RuntimeError` in server logs on first upload attempt.

### Pitfall 2: Session Shared Between Main Thread and Worker Thread
**What goes wrong:** SQLAlchemy raises `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.
**Why it happens:** `SessionLocal()` creates a connection bound to the creating thread. FastAPI's `get_db` dependency creates sessions in the main/worker thread pool — passing that session to a new thread violates SQLite's thread-safety contract.
**How to avoid:** Each background thread calls `session = SessionLocal()` at the start of its function. Never pass a session object from the route handler to the thread.
**Warning signs:** `ProgrammingError` in thread logs; intermittent failures on concurrent uploads.

### Pitfall 3: UploadFile Closed Before Thread Reads It
**What goes wrong:** Thread tries to read the file and gets empty bytes or a closed-file error.
**Why it happens:** FastAPI closes the `UploadFile` when the route handler returns. If you pass the `UploadFile` object to the thread instead of saving bytes/path first, the thread reads an empty/closed file.
**How to avoid:** In the route handler: `contents = await file.read()`, then save to `uploads/{uuid}.pdf`, then pass the `Path` to the thread. Never pass `UploadFile` across thread boundaries.
**Warning signs:** Extraction produces empty text; `ingest_pdf` raises RuntimeError on zero-byte PDF.

### Pitfall 4: Concurrent Dict Mutation Without Lock
**What goes wrong:** Intermittent `KeyError` or stale reads when multiple uploads happen simultaneously.
**Why it happens:** `_job_store[job_id]["status"] = "processing"` is a multi-step operation at the bytecode level. Although CPython's GIL serializes individual bytecodes, the logical update is not atomic.
**How to avoid:** Use `threading.Lock()` for all reads AND writes. Wrap mutations in `with _store_lock:`.
**Warning signs:** Job status appears as `pending` even after thread completes; KeyError on job lookup.

### Pitfall 5: 50 MB File Size Validation Placement
**What goes wrong:** Calling `await file.read()` to get size THEN rejecting a 50 MB file works, but `file.read()` already buffered 50 MB into memory. For files much larger than 50 MB this is wasteful.
**Why it happens:** FastAPI's `UploadFile` does not support streaming size checks natively.
**How to avoid:** Accept the behavior for this use case — 50 MB is the maximum and this is a local tool. Read all, check length, reject if too large. Document this is by design. Do NOT try to stream-check without changing to `Request` + manual body reading.
**Warning signs:** Memory spike on oversized uploads — acceptable given the 50 MB limit.

### Pitfall 6: Missing `uploads/` Directory on Fresh Install
**What goes wrong:** `open(uploads_dir / filename, "wb")` raises `FileNotFoundError` on first upload.
**Why it happens:** `uploads/` is not committed to git (it should be in `.gitignore`).
**How to avoid:** Create the directory in the `on_startup` event handler alongside `init_db`:
```python
@app.on_event("startup")
def on_startup() -> None:
    engine = init_db(settings.DB_PATH)
    SessionLocal.configure(bind=engine)
    Path("uploads").mkdir(exist_ok=True)
```

---

## Code Examples

Verified patterns from the existing codebase and FastAPI official documentation:

### Saving UploadFile to Disk
```python
# Source: FastAPI docs + existing project pattern
async def upload_pdf(file: UploadFile = File(...)) -> JSONResponse:
    contents = await file.read()

    # Validate magic bytes (PDF-01 spec: every PDF starts with %PDF-)
    if not contents[:4] == b"%PDF":
        raise HTTPException(status_code=422, detail="File is not a valid PDF")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="File must have .pdf extension")
    if len(contents) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")

    job_id = str(uuid.uuid4())
    save_path = Path("uploads") / f"{job_id}.pdf"
    save_path.write_bytes(contents)
    ...
```

### Thread Dispatch After 202
```python
# Pattern: return 202 immediately, thread does the work
job = _create_job(filename=file.filename or "upload.pdf")
t = threading.Thread(
    target=_run_extraction,
    args=(job["job_id"], save_path, model, force),
    daemon=True,
    name=f"extract-{job['job_id'][:8]}",
)
t.start()
return JSONResponse(content=job, status_code=202)
```

### Dependency Override Pattern for Tests (from existing test_api.py)
```python
# Source: tests/test_api.py — established project pattern
from fastapi.testclient import TestClient
from policy_extractor.api import app, get_db

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)
```

### Testing Upload with TestClient
```python
# Source: FastAPI official docs — https://fastapi.tiangolo.com/tutorial/testing/
import io

def test_upload_valid_pdf(tmp_path):
    pdf_bytes = b"%PDF-1.4 minimal"  # valid magic bytes for test
    response = client.post(
        "/polizas/upload",
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan` context manager | FastAPI 0.93+ | Current code uses deprecated `on_event`; acceptable for this phase — adding new `on_event` hook is consistent with existing code |
| Sync `file.read()` | `await file.read()` | FastAPI always async upload handlers | Upload handler must be `async def` |

**Deprecated/outdated:**
- `@app.on_event("startup")`: Deprecated since FastAPI 0.93 in favor of `lifespan`. The existing API code already uses it, so this phase continues that pattern for consistency. Not a blocker.

---

## Open Questions

1. **`uploads/` path: absolute or relative to project root?**
   - What we know: CONTEXT.md says "under project root". The API is launched via `uvicorn` from the project root.
   - What's unclear: If `uvicorn` is launched from a different CWD, relative `Path("uploads")` resolves differently.
   - Recommendation: Use `Path(__file__).parent.parent.parent / "uploads"` (same pattern as `_get_alembic_cfg`) to anchor to the package root regardless of CWD.

2. **Job expiry: should the `expires_at` be set at completion or set to `created_at + 1h`?**
   - What we know: CONTEXT.md says "expire after 1 hour". Not explicit about when the clock starts.
   - What's unclear: "1 hour after completion" vs "1 hour after upload".
   - Recommendation: Set `expires_at = datetime.now(timezone.utc) + timedelta(hours=1)` at the moment the job transitions to `complete` or `failed`. This gives 1 hour of polling time after extraction finishes.

3. **Thread-safety of `SessionLocal` configuration during startup race**
   - What we know: `SessionLocal.configure(bind=engine)` is called in `on_startup`. Background threads call `SessionLocal()` after startup completes.
   - What's unclear: If a request arrives before startup finishes (edge case), `SessionLocal()` would use an unbound session.
   - Recommendation: Non-issue in practice — uvicorn runs startup synchronously before accepting requests. Document as a known limitation.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (installed) |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_upload.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| API-01 | POST /polizas/upload returns 202 with job object | unit (TestClient) | `pytest tests/test_upload.py::test_upload_returns_202 -x` | ❌ Wave 0 |
| API-02 | multipart/form-data with PDF file accepted | unit (TestClient) | `pytest tests/test_upload.py::test_upload_multipart -x` | ❌ Wave 0 |
| API-02 | non-PDF file rejected with 422 | unit (TestClient) | `pytest tests/test_upload.py::test_upload_non_pdf_rejected -x` | ❌ Wave 0 |
| API-03 | Pipeline triggered: job eventually reaches `complete` with result | unit (mocked pipeline) | `pytest tests/test_upload.py::test_upload_pipeline_called -x` | ❌ Wave 0 |
| API-04 | 202 Accepted with job_id, status=pending | unit (TestClient) | `pytest tests/test_upload.py::test_upload_returns_202 -x` | ❌ Wave 0 |
| API-05 | GET /jobs/{id} returns job with result when complete | unit (TestClient + mock thread) | `pytest tests/test_upload.py::test_job_polling -x` | ❌ Wave 0 |
| API-05 | GET /jobs/{id} returns 404 for unknown job_id | unit (TestClient) | `pytest tests/test_upload.py::test_job_not_found -x` | ❌ Wave 0 |
| API-05 | GET /jobs lists all active jobs | unit (TestClient) | `pytest tests/test_upload.py::test_list_jobs -x` | ❌ Wave 0 |
| API-06 | PDF file deleted from uploads/ after successful extraction | unit (tmp_path + mock) | `pytest tests/test_upload.py::test_pdf_cleanup_on_success -x` | ❌ Wave 0 |
| API-06 | PDF file kept in uploads/ after failed extraction | unit (tmp_path + mock) | `pytest tests/test_upload.py::test_pdf_kept_on_failure -x` | ❌ Wave 0 |

**Note on pipeline mocking:** The background thread calls `ingest_pdf`, `extract_policy`, `upsert_policy`. These should be mocked in tests — real extraction requires Anthropic API credentials and takes 10-30 seconds. Use `unittest.mock.patch` on the full function paths.

### Sampling Rate
- **Per task commit:** `pytest tests/test_upload.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_upload.py` — covers API-01 through API-06 (all new)
- [ ] `policy_extractor/api/upload.py` — new module (route + job store + worker)
- [ ] `uploads/` directory — created at startup, not committed to git
- [ ] `python-multipart` in `pyproject.toml` — `pip install python-multipart` needed

---

## Sources

### Primary (HIGH confidence)
- Existing codebase: `policy_extractor/api/__init__.py` — established route patterns, `JSONResponse`, `DbDep`, startup hook
- Existing codebase: `policy_extractor/cli.py` lines 73-132 — exact pipeline flow to replicate in thread
- Existing codebase: `policy_extractor/ingestion/__init__.py` — `ingest_pdf(path, session, force_reprocess)` signature confirmed
- Existing codebase: `policy_extractor/extraction/__init__.py` — `extract_policy(ingestion_result, model)` signature confirmed
- Existing codebase: `policy_extractor/storage/writer.py` — `upsert_policy`, `orm_to_schema` signatures confirmed
- Existing codebase: `policy_extractor/cli_helpers.py` — `is_already_extracted(session, file_hash)` confirmed
- Existing codebase: `tests/test_api.py` — `TestClient`, `dependency_overrides` patterns confirmed
- Python stdlib docs: `threading.Thread`, `threading.Lock`, `uuid.uuid4` — stable, HIGH confidence

### Secondary (MEDIUM confidence)
- FastAPI official docs: https://fastapi.tiangolo.com/tutorial/request-files/ — `UploadFile`, `File(...)` parameter pattern
- FastAPI official docs: https://fastapi.tiangolo.com/tutorial/testing/ — `TestClient` file upload with `files={}` dict
- `python-multipart` GitHub: https://github.com/Kludex/python-multipart — FastAPI dependency for form parsing

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed except `python-multipart`; FastAPI file upload is well-documented
- Architecture: HIGH — pipeline code is fully confirmed by reading source; threading pattern is straightforward stdlib
- Pitfalls: HIGH — all pitfalls are drawn from the actual codebase (SessionLocal threading behavior, UploadFile lifecycle) or FastAPI-documented behavior
- Test patterns: HIGH — `test_api.py` provides the exact pattern to follow

**Research date:** 2026-03-19
**Valid until:** 2026-06-19 (stable libraries; FastAPI upload API is not changing)
