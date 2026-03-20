# Phase 8: PDF Upload API - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

HTTP endpoint to POST a PDF file and receive structured extraction results. Extends the existing FastAPI app with upload, job tracking, and polling endpoints. No new extraction capabilities — uses existing ingest → extract → persist pipeline.

</domain>

<decisions>
## Implementation Decisions

### Upload endpoint design
- `POST /polizas/upload` accepts multipart/form-data with PDF file
- File size limit: 50 MB
- Accepts optional query parameters: `model` (override extraction model) and `force` (boolean, reprocess even if already extracted) — full parity with CLI `extract` command
- Returns 202 Accepted with full job object: `{ "job_id": "...", "status": "pending", "created_at": "...", "filename": "..." }`
- Validates uploaded file: check PDF magic bytes (`%PDF-`) AND `.pdf` extension; reject non-PDFs with 422

### Job lifecycle & polling
- 4 job states: `pending` → `processing` → `complete` | `failed`
- `GET /jobs/{id}` returns full job object; when complete, includes the full extracted poliza inline in a `result` field: `{ "status": "complete", "result": { poliza data... } }`
- `GET /jobs` lists all non-expired jobs (useful for debugging/monitoring)
- Completed and failed jobs expire from in-memory store after 1 hour
- No job cancellation endpoint — jobs run to completion or failure
- In-memory dict for job storage (already decided in STATE.md — lost on restart is acceptable)

### Pipeline integration
- Background extraction via `threading.Thread` — one thread per upload, sync pipeline runs as-is
- Uploaded PDFs saved to `uploads/` directory under project root (not OS temp) — easier to debug
- Idempotency: always return 202 with a job, but if file hash already in DB and force=false, the job resolves immediately to existing poliza (consistent async interface, no extraction cost)
- Each background thread creates its own `SessionLocal()` for DB access (thread-safe)

### Error handling & edge cases
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing API implementation
- `policy_extractor/api/__init__.py` — Current FastAPI app with CRUD routes, `get_db` dependency, startup event, `SessionLocal` binding pattern
- `policy_extractor/storage/database.py` — `init_db()`, `SessionLocal`, `get_engine()` with WAL mode

### Existing extraction pipeline
- `policy_extractor/cli.py` lines 73-132 — `extract` command showing the full ingest → extract → persist flow, idempotency check, model override, force flag
- `policy_extractor/ingestion/__init__.py` — `ingest_pdf()` function signature (takes file Path + session)
- `policy_extractor/extraction/__init__.py` — `extract_policy()` function signature (takes IngestionResult, returns PolicyExtraction + usage)
- `policy_extractor/storage/writer.py` — `upsert_policy()` for persistence, `orm_to_schema()` for ORM→Pydantic conversion
- `policy_extractor/ingestion/cache.py` — `compute_file_hash()` for idempotency check
- `policy_extractor/cli_helpers.py` — `is_already_extracted()` for hash-based dedup check

### Requirements
- `.planning/REQUIREMENTS.md` §PDF Upload API — API-01 through API-06

### Project decisions
- `.planning/STATE.md` §Accumulated Context — Documents in-memory job_store decision, sync SQLAlchemy choice

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ingest_pdf(path, session, force_reprocess)` — full ingestion with OCR support, returns IngestionResult
- `extract_policy(ingestion_result, model)` — Claude API extraction, returns (PolicyExtraction, Usage)
- `upsert_policy(session, extraction)` — DB persistence with dedup by (numero_poliza, aseguradora)
- `orm_to_schema(poliza)` — ORM to Pydantic conversion for API responses
- `compute_file_hash(path)` — SHA-256 hash for idempotency
- `is_already_extracted(session, file_hash)` — check if hash already in DB
- `init_db(db_path)` — DB initialization with auto-migration
- `SessionLocal` — scoped session factory, already used in both CLI and API

### Established Patterns
- FastAPI routes return `JSONResponse` (not Pydantic response_model)
- `DbDep = Annotated[Session, Depends(get_db)]` for session injection
- `_setup_db()` called at startup (CLI) / `on_startup` event (API)
- Lazy imports inside functions for heavy dependencies
- `selectinload` for eager-loading relationships

### Integration Points
- `policy_extractor/api/__init__.py` — add upload route (or import from new module)
- `pyproject.toml` — `python-multipart` dependency needed for FastAPI file uploads
- Existing test patterns in `tests/test_api.py` (if exists) or `tests/test_cli.py`

</code_context>

<specifics>
## Specific Ideas

- The agency team may integrate this with external systems that send PDFs via HTTP — the upload API is the primary integration point for v1.1
- Keeping failed PDFs in `uploads/` allows manual inspection when extraction fails on unusual PDF formats

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-pdf-upload-api*
*Context gathered: 2026-03-19*
