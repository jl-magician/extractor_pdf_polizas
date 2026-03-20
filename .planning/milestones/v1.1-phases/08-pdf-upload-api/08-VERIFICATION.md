---
phase: 08-pdf-upload-api
verified: 2026-03-19T00:00:00Z
status: passed
score: 14/14 must-haves verified
re_verification: false
---

# Phase 8: PDF Upload API Verification Report

**Phase Goal:** External systems can POST a PDF over HTTP and receive structured extraction results without running the CLI
**Verified:** 2026-03-19
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | POST /polizas/upload with a valid PDF returns 202 with job_id and status=pending | VERIFIED | `upload.py` line 157: `@router.post("/polizas/upload", status_code=202)`; `_create_job` returns status="pending"; test `test_upload_valid_pdf_returns_202` passes |
| 2  | POST /polizas/upload with a non-PDF file returns 422 | VERIFIED | `upload.py` lines 167-168: extension check; lines 171-172: magic bytes check; tests `test_upload_non_pdf_extension_rejected` and `test_upload_non_pdf_magic_bytes_rejected` pass |
| 3  | POST /polizas/upload with a file over 50 MB returns 413 | VERIFIED | `upload.py` lines 175-176: `HTTPException(status_code=413, ...)`; test `test_upload_oversized_file_rejected` passes |
| 4  | GET /jobs/{id} returns the job object with current status | VERIFIED | `upload.py` lines 194-200: `get_job` route; test `test_get_job_returns_job` passes |
| 5  | GET /jobs/{id} returns 404 for unknown job_id | VERIFIED | `upload.py` lines 198-199: `HTTPException(status_code=404, ...)`; test `test_get_job_unknown_returns_404` passes |
| 6  | GET /jobs returns a list of all non-expired jobs | VERIFIED | `upload.py` lines 203-206: `list_jobs` route; tests `test_list_jobs_returns_all` and `test_list_jobs_empty` pass |
| 7  | Expired jobs (1 hour after completion) are purged on next read | VERIFIED | `upload.py` lines 74-84: `_purge_expired()` called inside `_get_job` and `_list_jobs`; test `test_job_expiry_purges_expired` passes |
| 8  | Uploading a PDF triggers the full pipeline: ingest -> extract -> persist | VERIFIED | `_run_extraction` calls `ingest_pdf`, `extract_policy`, `upsert_policy` in sequence (lines 135-141); test `test_pipeline_success_sets_complete` asserts all three called |
| 9  | After extraction completes, job status is 'complete' with full poliza in result field | VERIFIED | `upload.py` line 141: `_update_job(job_id, status="complete", result=result)`; test `test_pipeline_success_sets_complete` asserts `status=="complete"` and `result is not None` |
| 10 | After extraction fails, job status is 'failed' with error detail | VERIFIED | `upload.py` line 144: `_update_job(job_id, status="failed", error=str(exc))`; test `test_pipeline_failure_sets_failed` asserts error contains exception message |
| 11 | Successful extraction deletes the uploaded PDF from uploads/ | VERIFIED | `upload.py` line 142: `pdf_path.unlink(missing_ok=True)` on success path; test `test_pdf_cleanup_on_success` asserts `not pdf_file.exists()` |
| 12 | Failed extraction keeps the uploaded PDF in uploads/ for debugging | VERIFIED | No `unlink` call in the except block; test `test_pdf_kept_on_failure` asserts `pdf_file.exists()` |
| 13 | Uploading a previously extracted PDF (same hash) without force=true resolves immediately from DB | VERIFIED | `upload.py` lines 124-133: idempotency branch; test `test_idempotent_upload_skips_extraction` asserts `ingest_pdf` and `extract_policy` not called |
| 14 | Uploading with force=true reprocesses even if hash exists in DB | VERIFIED | `upload.py` line 124: `if not force and ...`; `upload.py` line 135: `force_reprocess=force`; test `test_force_upload_reprocesses` asserts `ingest_pdf` called with `force_reprocess=True` |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `policy_extractor/api/upload.py` | Upload route, job store, job endpoints | VERIFIED | 207 lines; exports `router`, `UPLOADS_DIR`; contains `_job_store`, `_store_lock`, `_create_job`, `_update_job`, `_purge_expired`, `_get_job`, `_list_jobs`, `_run_extraction`, all three routes |
| `tests/test_upload.py` | Upload API test coverage (min 150 lines) | VERIFIED | 439 lines; 16 tests covering validation, job lifecycle, pipeline integration |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `policy_extractor/api/__init__.py` | `policy_extractor/api/upload.py` | `app.include_router(upload_router)` | WIRED | Line 230-232 of `__init__.py`: `from policy_extractor.api.upload import router as upload_router, UPLOADS_DIR` then `app.include_router(upload_router)`; routes `/polizas/upload`, `/jobs/{job_id}`, `/jobs` confirmed present via runtime check |
| `policy_extractor/api/__init__.py` | `uploads/` directory creation | `UPLOADS_DIR.mkdir(parents=True, exist_ok=True)` | WIRED | Line 42 of `__init__.py`: called inside `on_startup()` |
| `policy_extractor/api/upload.py` | `threading.Thread` | `_run_extraction dispatch` | WIRED | Lines 183-189: `t = threading.Thread(target=_run_extraction, ...)` followed by `t.start()` |
| `policy_extractor/api/upload.py` | `policy_extractor/ingestion/__init__.py` | `ingest_pdf()` in `_run_extraction` | WIRED | Line 114: `from policy_extractor.ingestion import ingest_pdf`; line 135: `ingest_pdf(pdf_path, session=session, force_reprocess=force)` |
| `policy_extractor/api/upload.py` | `policy_extractor/extraction/__init__.py` | `extract_policy()` in `_run_extraction` | WIRED | Line 115: `from policy_extractor.extraction import extract_policy`; line 136: `extract_policy(ingestion_result, model=model)` |
| `policy_extractor/api/upload.py` | `policy_extractor/storage/writer.py` | `upsert_policy()` in `_run_extraction` | WIRED | Line 116: `from policy_extractor.storage.writer import upsert_policy, orm_to_schema`; line 139: `upsert_policy(session, policy)` |
| `policy_extractor/api/upload.py` | `policy_extractor/ingestion/cache.py` | `compute_file_hash()` for idempotency | WIRED | Line 112: `from policy_extractor.ingestion.cache import compute_file_hash`; line 123: `compute_file_hash(pdf_path)` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| API-01 | 08-01-PLAN.md | User can POST a PDF file to `/polizas/upload` and receive extraction results | SATISFIED | Route exists, returns 202 with job object; job polls to completion with full poliza result |
| API-02 | 08-01-PLAN.md | Upload endpoint accepts multipart/form-data with PDF file | SATISFIED | `python-multipart>=0.0.9` installed; `UploadFile = File(...)` parameter in `upload_pdf` |
| API-03 | 08-02-PLAN.md | Upload triggers the full pipeline: ingest -> extract -> persist -> return structured result | SATISFIED | `_run_extraction` calls `ingest_pdf` -> `extract_policy` -> `upsert_policy`; result stored in job; test `test_pipeline_success_sets_complete` verifies full sequence |
| API-04 | 08-01-PLAN.md | Long-running uploads return 202 Accepted with a job ID | SATISFIED | `status_code=202`; response includes `job_id` and `status="pending"` |
| API-05 | 08-01-PLAN.md | User can poll `GET /jobs/{id}` for job status and results | SATISFIED | `GET /jobs/{job_id}` route returns job dict with status/result; 404 for unknown IDs |
| API-06 | 08-02-PLAN.md | Uploaded PDF temp files are cleaned up after extraction completes | SATISFIED | `pdf_path.unlink(missing_ok=True)` on success path; test `test_pdf_cleanup_on_success` verifies deletion |

All 6 requirements satisfied. No orphaned requirements for Phase 8.

### Anti-Patterns Found

No anti-patterns found. Scan of `policy_extractor/api/upload.py` and `tests/test_upload.py` revealed:
- No TODO/FIXME/HACK/PLACEHOLDER comments
- No empty return stubs (`return null`, `return {}`, `return []`)
- No console.log-only handlers
- The "stub" note in `_run_extraction` docstring ("Full pipeline wired in Plan 02") is a historical comment — the body is fully implemented

### Human Verification Required

One item requires manual verification with a real PDF file and running server:

**End-to-end upload with real PDF**

**Test:** Start server with `uvicorn policy_extractor.api:app`, then `curl -F "file=@real_poliza.pdf" http://localhost:8000/polizas/upload`, poll the returned job_id via `curl http://localhost:8000/jobs/{job_id}` until status transitions from "pending" to "complete" or "failed".

**Expected:** status=complete, result field contains structured poliza data (numero_poliza, aseguradora, coberturas, etc.)

**Why human:** Real PDF requires Anthropic API credentials and an actual policy document. All mock-based tests pass but real OCR/LLM pipeline integration cannot be verified programmatically without external services.

### Gaps Summary

No gaps. All 14 observable truths verified, all artifacts substantive and wired, all 6 requirements satisfied, full test suite green (199 passed, 2 skipped, 0 failures).

---

_Verified: 2026-03-19_
_Verifier: Claude (gsd-verifier)_
