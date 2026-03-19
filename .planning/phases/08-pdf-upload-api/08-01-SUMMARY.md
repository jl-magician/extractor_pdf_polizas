---
phase: 08-pdf-upload-api
plan: 01
subsystem: api
tags: [fastapi, python-multipart, file-upload, threading, job-store, sqlite]

# Dependency graph
requires:
  - phase: 05-storage-api
    provides: FastAPI app singleton, get_db dependency, SessionLocal, policy CRUD routes
  - phase: 03-extraction
    provides: ingest_pdf, extract_policy pipeline functions
provides:
  - POST /polizas/upload — PDF validation (magic bytes, extension, 50 MB limit), 202 + job object
  - GET /jobs/{job_id} — single job polling with expiry purge
  - GET /jobs — list all active (non-expired) jobs
  - In-memory thread-safe job store with 1-hour expiry after terminal state
  - Background threading worker stub (_run_extraction) ready for Plan 02 pipeline wiring
  - uploads/ directory created on startup
affects: [08-02-pipeline-integration, any phase using the FastAPI app]

# Tech tracking
tech-stack:
  added: [python-multipart>=0.0.9]
  patterns:
    - In-memory job store with threading.Lock for thread-safe CRUD
    - Lazy-purge pattern — expired jobs removed on _get_job / _list_jobs read access
    - Scoped dependency_overrides fixture to prevent cross-test contamination of shared app singleton

key-files:
  created:
    - policy_extractor/api/upload.py
    - tests/test_upload.py
  modified:
    - pyproject.toml
    - policy_extractor/api/__init__.py

key-decisions:
  - "Scoped override_db fixture in test_upload.py saves/restores app.dependency_overrides[get_db] to prevent contaminating test_api.py tests that share the same app singleton"
  - "Lazy expiry purge on read (_get_job/_list_jobs) avoids background cleanup thread complexity"
  - "save_path.parent.mkdir(parents=True, exist_ok=True) in upload route makes UPLOADS_DIR resilient even if startup event is skipped in tests"

patterns-established:
  - "Thread-safe in-memory store: dict + threading.Lock with copy-on-read for all accessors"
  - "Test isolation for shared FastAPI singletons: fixture saves/restores dependency_overrides rather than setting at module level"

requirements-completed: [API-01, API-02, API-04, API-05]

# Metrics
duration: 4min
completed: 2026-03-19
---

# Phase 8 Plan 01: PDF Upload API Summary

**FastAPI upload endpoint with in-memory job store: POST /polizas/upload validates PDF (magic bytes, extension, 50 MB), returns 202 job object, dispatches background extraction thread; GET /jobs/{id} and GET /jobs support polling with 1-hour expiry purge**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-19T18:14:23Z
- **Completed:** 2026-03-19T18:18:16Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `policy_extractor/api/upload.py` with thread-safe `_job_store`, full PDF validation (magic bytes `%PDF`, `.pdf` extension, 50 MB size limit), job lifecycle management, and background `threading.Thread` dispatch
- Wired upload router into existing FastAPI app, with `uploads/` directory creation on startup
- Created 9-test suite in `tests/test_upload.py` covering all validation paths, job polling, listing, and expiry purge; fixed cross-test contamination from shared `app` singleton
- Full test suite: 192 passing, 2 skipped, 0 failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Add upload module with job store, validation, and polling routes** - `0aa21a7` (feat)
2. **Task 2: Create upload API tests covering validation, job lifecycle, and polling** - `d7dc377` (test)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `policy_extractor/api/upload.py` — Upload router: POST /polizas/upload, GET /jobs/{id}, GET /jobs, _job_store, _run_extraction stub
- `tests/test_upload.py` — 9 tests for upload validation, job lifecycle, and expiry
- `pyproject.toml` — Added `python-multipart>=0.0.9` dependency
- `policy_extractor/api/__init__.py` — Wired `upload_router`, added `UPLOADS_DIR.mkdir()` to on_startup

## Decisions Made

- **Scoped override_db fixture:** `test_upload.py` saves and restores `app.dependency_overrides[get_db]` per test rather than setting it at module level. Both test files share the same `app` singleton; module-level override permanently overwrites whichever was set last, causing the other file's tests to query the wrong in-memory DB.
- **Lazy expiry purge on read:** `_purge_expired()` is called inside `_get_job` and `_list_jobs` rather than on a background timer, avoiding extra thread complexity for a single-user local tool.
- **UPLOADS_DIR mkdir in upload route:** `save_path.parent.mkdir(parents=True, exist_ok=True)` is also called at upload time, making the route resilient even if the startup event is bypassed in test scenarios.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed cross-test DB contamination from module-level dependency_overrides**
- **Found during:** Task 2 (test suite creation)
- **Issue:** Both `test_api.py` and `test_upload.py` override `app.dependency_overrides[get_db]` at module import time. Since both use the same `app` singleton, whichever is imported second permanently overwrites the first. `test_api.py`'s `seeded_poliza` fixture inserts into its engine, but the GET /polizas call then uses `test_upload.py`'s engine (empty), causing `test_get_polizas_with_data` to see 0 rows instead of 1.
- **Fix:** Replaced module-level `app.dependency_overrides[get_db] = override_get_db` in `test_upload.py` with an `autouse` fixture that saves the previous override, sets the upload test's override for the test duration, and restores the previous value after.
- **Files modified:** `tests/test_upload.py`
- **Verification:** `pytest tests/ -x -q` passes: 192 passing, 2 skipped, 0 failures
- **Committed in:** `d7dc377` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Fix essential for test suite correctness. No scope creep.

## Issues Encountered

None beyond the auto-fixed cross-contamination issue above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Upload route, job store, and all polling endpoints are production-ready
- `_run_extraction` stub dispatches thread immediately — Plan 02 replaces the stub body with the real ingestion + extraction pipeline
- `uploads/` directory will be created on first startup automatically
- 192 existing tests remain green; upload API adds 9 new tests

---
*Phase: 08-pdf-upload-api*
*Completed: 2026-03-19*
