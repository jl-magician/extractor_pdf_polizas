---
phase: 02-ingestion
plan: 02
subsystem: ingestion
tags: [ocrmypdf, pytesseract, pdf2image, pymupdf, sqlalchemy, pydantic, sha256, cache, tdd]

requires:
  - phase: 02-01
    provides: [IngestionResult, PageResult, IngestionCache ORM model, classify_all_pages, digital_sample.pdf, scanned_sample.pdf, conftest session fixture]
  - phase: 01-foundation
    provides: [SQLAlchemy Base, SessionLocal, init_db, Pydantic base patterns, Settings config]
provides:
  - "ingest_pdf(pdf_path, session, force_reprocess) -> IngestionResult — single public entry point for full PDF ingestion pipeline"
  - "run_ocr(input_path, language) — ocrmypdf wrapper with already_done_ocr handling"
  - "ocr_with_fallback(input_path) — Spanish OCR with automatic English retry on low confidence"
  - "extract_text_by_page(pdf_path) -> list[(page_num, text)] — per-page text extraction from text-layer PDF"
  - "get_page_confidence(pdf_path, page_num, lang) -> float — pytesseract confidence scorer using pdf2image"
  - "compute_file_hash(file_path) -> str — SHA-256 hex digest of file content"
  - "lookup_cache(session, file_hash) -> IngestionResult | None — cache lookup with from_cache=True flag"
  - "save_cache(session, result) — idempotent cache persistence; duplicate hash is a no-op"
affects: [03-extraction (ingest_pdf is the input provider for Phase 3 LLM extraction)]

tech-stack:
  added: []  # all libraries added in Plan 01; no new installs in this plan
  patterns:
    - "TDD red-green — failing tests committed first, implementation committed second"
    - "ocrmypdf Python API with ExitCode enum for already_done_ocr detection"
    - "Confidence threshold (60) gates English fallback: get_page_confidence via pdf2image + pytesseract.image_to_data"
    - "SHA-256 path-independent cache key: hashlib.sha256(bytes).hexdigest()"
    - "Idempotent save_cache: check-before-insert prevents duplicate rows on re-call"
    - "Session-optional orchestration: ingest_pdf works without caching if session=None"

key-files:
  created:
    - policy_extractor/ingestion/ocr_runner.py
    - policy_extractor/ingestion/cache.py
    - tests/test_ocr_cache.py
  modified:
    - policy_extractor/ingestion/__init__.py
    - tests/test_ingestion.py

key-decisions:
  - "test_ocr_english_fallback: mock output path must differ from input_path to avoid early-return on already_done_ocr branch — test fixed to use tmp_path copy"
  - "Corrupted PDF detection: ingest_pdf checks doc.is_pdf after fitz.open() in addition to try/except, matching classify_all_pages behavior"
  - "Cache hit updates file_path to current location (informational only) but does not re-save — path is not part of the cache key"

patterns-established:
  - "ocr_runner: run_ocr returns (output_path, lang_str) tuple so callers always know which language was used"
  - "ocr_runner: already_done_ocr returns input_path directly — no temp file created; caller must not unlink input"
  - "cache: lookup_cache returns fully constructed IngestionResult — callers don't need to reconstruct it"
  - "ingest_pdf: orchestrates classify -> OCR -> result build -> cache in a single function; each step is independently testable"

requirements-completed: [ING-02, ING-05]

duration: 4min
completed: 2026-03-18
---

# Phase 02 Plan 02: OCR Runner, Cache, and ingest_pdf() Orchestrator Summary

**ocrmypdf-backed OCR runner with Spanish/English confidence fallback, SHA-256 SQLite cache, and ingest_pdf() single-entry-point orchestrator wiring classifier + OCR + cache into typed IngestionResult output**

## Performance

- **Duration:** ~4 minutes
- **Started:** 2026-03-18T17:07:04Z
- **Completed:** 2026-03-18T17:11:12Z
- **Tasks:** 2
- **Files modified:** 5 (2 created, 2 modified, 1 new test file)

## Accomplishments

- OCR runner wraps ocrmypdf.ocr() with deskew=True, skip_text=True; handles already_done_ocr exit code by returning input path unchanged
- English fallback triggered when pytesseract confidence on first page < 60: re-runs ocrmypdf with ["spa", "eng"]
- SHA-256 cache prevents reprocessing: same content at any path returns cached IngestionResult; force_reprocess=True bypasses cache
- ingest_pdf() is the complete pipeline: classify pages, OCR scanned pages, build IngestionResult, persist to cache — all in one call

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1 RED: OCR runner and cache tests** - `aa8b829` (test)
2. **Task 1 GREEN: OCR runner and cache implementation** - `2153071` (feat)
3. **Task 2 RED: ingest_pdf orchestrator tests** - `fae6727` (test)
4. **Task 2 GREEN: ingest_pdf orchestrator implementation** - `8f5f8e5` (feat)

## Files Created/Modified

- `policy_extractor/ingestion/ocr_runner.py` — run_ocr(), ocr_with_fallback(), extract_text_by_page(), get_page_confidence()
- `policy_extractor/ingestion/cache.py` — compute_file_hash(), lookup_cache(), save_cache()
- `policy_extractor/ingestion/__init__.py` — ingest_pdf() orchestrator wiring all components; exports IngestionResult, PageResult, classify_page, classify_all_pages, compute_file_hash
- `tests/test_ocr_cache.py` — 10 unit tests for ocr_runner and cache modules
- `tests/test_ingestion.py` — 11 new integration tests for ingest_pdf and cache behavior (appended to existing 13 classifier tests)

## Decisions Made

- **test_ocr_english_fallback mock path:** The mock OCR output must be a different Path object than the input path. When `output_path == input_path`, `ocr_with_fallback` returns early (already_done_ocr branch). Fixed test to copy DIGITAL_PDF to tmp_path before mocking.
- **ingest_pdf corrupted PDF handling:** Added `doc.is_pdf` check after `fitz.open()` in addition to the try/except, so non-PDF files produce a RuntimeError matching the test expectation — mirrors the same fix from Plan 01 classifier.
- **Cache path update on hit:** When a cache hit is returned, `cached.file_path` is updated to the current call's path (informational). This does not re-save to DB — it's a convenience for the caller to know where the file was found now.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test mocking issue — test_ocr_english_fallback mock output must differ from input**
- **Found during:** Task 1, first GREEN test run
- **Issue:** Test used `DIGITAL_PDF` as both input and mock output for `run_ocr`. Since `output_path == input_path`, `ocr_with_fallback` returned early via the already_done_ocr branch, never calling `get_page_confidence`, so `run_ocr.call_count` stayed at 1.
- **Fix:** Changed test to copy `DIGITAL_PDF` to `tmp_path / "fake_ocr_output.pdf"` and use the copy as mock output. Input and output are now distinct paths.
- **Files modified:** `tests/test_ocr_cache.py`
- **Commit:** `2153071` (part of Task 1 GREEN)

---

**Total deviations:** 1 auto-fixed (Rule 1 — test logic bug)
**Impact on plan:** Fix was necessary for test correctness. No scope creep.

## Issues Encountered

None — implementation followed plan action spec exactly.

## User Setup Required

**External services require manual configuration for Tesseract-dependent tests:**
- Install Tesseract OCR (UB-Mannheim Windows build): `https://github.com/UB-Mannheim/tesseract/wiki`
- Install Spanish language pack during setup (select `spa`)
- Add `C:\Program Files\Tesseract-OCR` to system PATH
- Install Poppler for Windows: `https://github.com/oschwartz10612/poppler-windows/releases` — extract and add `bin/` to PATH

Tests marked `@requires_tesseract` will be skipped automatically when Tesseract is not installed.

## Next Phase Readiness

- `ingest_pdf()` is the Phase 3 entry point — call it with any PDF path and an optional SQLAlchemy session
- Returns typed `IngestionResult` with per-page `PageResult` objects (page_num, text, classification) ready for LLM consumption
- Cache prevents duplicate processing across sessions; DB path configured via `settings.DB_PATH`
- Phase 3 should call `init_db()` at startup to ensure `ingestion_cache` table exists before first `ingest_pdf()` call with a session
- Blocker from Phase 2 planning: Two-pass classification strategy for 50-70 insurer layouts is Phase 3's highest design risk

## Self-Check: PASSED

Files exist:
- policy_extractor/ingestion/ocr_runner.py: FOUND
- policy_extractor/ingestion/cache.py: FOUND
- policy_extractor/ingestion/__init__.py: FOUND
- tests/test_ocr_cache.py: FOUND
- .planning/phases/02-ingestion/02-02-SUMMARY.md: FOUND

Commits exist:
- aa8b829 (test RED ocr_runner/cache): FOUND
- 2153071 (feat GREEN ocr_runner/cache): FOUND
- fae6727 (test RED ingest_pdf): FOUND
- 8f5f8e5 (feat GREEN ingest_pdf): FOUND

---
*Phase: 02-ingestion*
*Completed: 2026-03-18*
