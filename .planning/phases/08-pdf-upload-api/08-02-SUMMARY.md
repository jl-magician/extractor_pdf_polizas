---
phase: 08-pdf-upload-api
plan: 02
subsystem: testing
tags: [pytest, mock, fastapi, background-thread, pdf-upload, idempotency]

# Dependency graph
requires:
  - phase: 08-01
    provides: "_run_extraction worker with full pipeline integration (ingest->extract->upsert)"
provides:
  - "8 integration tests verifying _run_extraction pipeline: success, failure, cleanup, idempotency, force, session lifecycle"
  - "uploads/ excluded from git via .gitignore"
affects: [08-pdf-upload-api, future API phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Direct synchronous call to background worker function in tests (not via thread) isolates extraction logic"
    - "Patch at import source (policy_extractor.storage.database.SessionLocal) not at usage site for lazy-import functions"
    - "MagicMock at module-level import shared across test file"

key-files:
  created: []
  modified:
    - tests/test_upload.py
    - .gitignore

key-decisions:
  - "Patch targets are source module paths (e.g. policy_extractor.storage.database.SessionLocal) because _run_extraction uses lazy imports inside the function body"
  - "Tests call _run_extraction directly and synchronously -- no thread spawning needed, isolates pipeline logic from HTTP layer"

patterns-established:
  - "Background worker tests: call worker function directly with mocked dependencies, assert job store state afterward"

requirements-completed: [API-03, API-06]

# Metrics
duration: 4min
completed: 2026-03-19
---

# Phase 8 Plan 02: PDF Upload API Pipeline Integration Tests Summary

**8 pytest integration tests verifying _run_extraction pipeline: success/failure status, PDF cleanup, idempotency, force reprocess, and thread-safe session creation — plus uploads/ added to .gitignore**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-19T18:20:56Z
- **Completed:** 2026-03-19T18:24:30Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Added 8 pipeline integration tests directly calling `_run_extraction` with mocked pipeline functions
- Verified full pipeline sequence (ingest_pdf -> extract_policy -> upsert_policy) is called on success
- Verified PDF cleanup on success (file deleted) and PDF preservation on failure (file kept for debugging)
- Verified idempotency path skips extraction when hash exists and force=False
- Verified force=True bypasses idempotency and passes force_reprocess=True to ingest_pdf
- Verified each extraction run creates its own SessionLocal() and closes it in finally block
- Added uploads/ to .gitignore
- Full test suite remains green (199 passed, 2 skipped)

## Task Commits

Each task was committed atomically:

1. **Task 1: Pipeline integration tests + gitignore** - `153effd` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `tests/test_upload.py` - Added 8 pipeline integration tests, moved MagicMock to top-level import
- `.gitignore` - Added uploads/ entry

## Decisions Made
- Patch targets are source module paths (e.g. `policy_extractor.storage.database.SessionLocal`) not `policy_extractor.api.upload.SessionLocal` — because `_run_extraction` uses lazy imports inside the function body, the patch must be applied at the original module
- Tests call `_run_extraction` directly and synchronously rather than spawning a thread — this isolates the extraction logic from FastAPI/threading complexity and is consistent with Plan 01's approach of mocking `_run_extraction` at the HTTP layer

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed NameError: MagicMock not imported at module level**
- **Found during:** Task 1 (running tests)
- **Issue:** `MagicMock` used in `test_pdf_kept_on_failure` without import; the plan's test template showed per-function imports but the existing file only had `patch` at top level
- **Fix:** Added `MagicMock` to the top-level `from unittest.mock import` statement and removed redundant per-function imports
- **Files modified:** tests/test_upload.py
- **Verification:** `pytest tests/test_upload.py -x -q` passes (16/16)
- **Committed in:** `153effd` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Trivial import fix. No scope creep.

## Issues Encountered
None beyond the MagicMock import fix noted above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 08 (pdf-upload-api) is complete. Both plans shipped: upload endpoint with validation/job store (Plan 01) and pipeline integration tests (Plan 02).
- The full upload flow is verified: POST /polizas/upload -> background _run_extraction -> ingest_pdf -> extract_policy -> upsert_policy -> job status update -> file cleanup.
- Ready for next phase.

---
*Phase: 08-pdf-upload-api*
*Completed: 2026-03-19*

## Self-Check: PASSED
- tests/test_upload.py: FOUND
- .gitignore: FOUND
- 08-02-SUMMARY.md: FOUND
- Commit 153effd: FOUND
