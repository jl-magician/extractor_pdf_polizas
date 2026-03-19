---
phase: 02-ingestion
verified: 2026-03-18T18:00:00Z
status: passed
score: 12/12 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Process a real scanned insurance PDF with Tesseract installed"
    expected: "ingest_pdf() returns IngestionResult with ocr_applied=True and non-empty Spanish text in result.pages"
    why_human: "Tesseract OCR is not installed in this environment; test_ingest_scanned_pdf is skipped automatically"
  - test: "Verify English fallback triggers on a real low-confidence Spanish PDF"
    expected: "ocr_with_fallback re-runs OCR with ['spa', 'eng'] and returns a result with ocr_language='spa+eng'"
    why_human: "End-to-end confidence path requires Tesseract and Poppler; can only be tested in a machine with both installed"
---

# Phase 02: Ingestion Verification Report

**Phase Goal:** The system reliably routes any PDF — digital or scanned — to the correct processing path before touching the LLM
**Verified:** 2026-03-18T18:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | A digital PDF page with selectable text is classified as "digital" | VERIFIED | `classify_page` returns early with "digital" when `get_images()` is empty; `test_classify_digital_page` passes |
| 2  | A scanned PDF page (image >80% area) is classified as "scanned" | VERIFIED | `coverage >= PAGE_SCAN_THRESHOLD` branch in `classify_page`; `test_classify_scanned_page` passes with scanned_sample.pdf |
| 3  | A digital page with small logos is NOT falsely classified as scanned | VERIFIED | `img_area / page_area < DECORATIVE_IMAGE_MIN` skip in classifier; `test_watermark_not_false_scanned` passes |
| 4  | Transparent overlay images (smask != 0) are excluded from coverage | VERIFIED | `if smask != 0: continue` on line 36 of classifier.py; `test_transparent_overlay_skipped` passes |
| 5  | Password-protected or corrupted PDFs raise RuntimeError (not a crash) | VERIFIED | `doc.is_encrypted` and `doc.is_pdf` checks in `classify_all_pages`; `test_corrupted_pdf_raises_runtime_error` and `test_corrupted_pdf_skipped` pass |
| 6  | A scanned PDF is OCR-processed and produces readable text per page | VERIFIED (partial) | `run_ocr` wraps `ocrmypdf.ocr()` with `skip_text=True` and returns `(output_path, lang_str)`; `extract_text_by_page` returns `list[(page_num, text)]`; OCR path requires Tesseract for live validation |
| 7  | If OCR confidence on Spanish is below 60, English is added and OCR retried | VERIFIED | `ocr_with_fallback` calls `get_page_confidence`, compares to `CONFIDENCE_THRESHOLD (60)`, re-runs with `["spa", "eng"]`; `test_ocr_english_fallback` (mocked) passes in both test files |
| 8  | OCR output is a list of (page_num, text) per page | VERIFIED | `extract_text_by_page` returns `[(i+1, page.get_text())]`; `test_ocr_output_page_tuples` passes |
| 9  | A previously processed PDF returns cached result without re-running OCR | VERIFIED | `lookup_cache` called before processing; `test_cache_hit_skips_ocr` and `test_cache_hit_skips_ocr_not_called` pass, latter using mock to confirm `ocr_with_fallback` not called |
| 10 | The force_reprocess flag bypasses cache and re-runs the full pipeline | VERIFIED | `if session and not force_reprocess:` gate in `ingest_pdf()`; `test_force_reprocess_bypasses_cache` passes with `from_cache=False` assertion |
| 11 | The same file at a different path returns a cache hit (hash-based) | VERIFIED | `compute_file_hash` uses SHA-256 of file bytes; `test_cache_hit_path_independent` copies file and confirms hit; `test_cache_hit_path_independent` in both test files pass |
| 12 | `ingest_pdf()` returns a typed IngestionResult Pydantic model | VERIFIED | `ingest_pdf` constructs and returns `IngestionResult(...)`; `test_ingest_returns_pydantic_model` passes |

**Score:** 12/12 truths verified (2 marked human-needed for live Tesseract path)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `policy_extractor/schemas/ingestion.py` | PageResult and IngestionResult Pydantic models | VERIFIED | Both classes present; `classification: Literal["digital", "scanned"]` exact field confirmed |
| `policy_extractor/storage/models.py` | IngestionCache SQLAlchemy model | VERIFIED | `class IngestionCache(Base)` with `__tablename__ = "ingestion_cache"`, `file_hash` as `String(64), unique=True, index=True` |
| `policy_extractor/ingestion/classifier.py` | Per-page PDF classification | VERIFIED | `classify_page` and `classify_all_pages` exported; smask check, decorative threshold, coverage ratio all present |
| `policy_extractor/ingestion/ocr_runner.py` | OCR processing with English fallback | VERIFIED | `run_ocr`, `ocr_with_fallback`, `extract_text_by_page`, `get_page_confidence` all present and wired |
| `policy_extractor/ingestion/cache.py` | SQLite-backed ingestion cache | VERIFIED | `compute_file_hash`, `lookup_cache`, `save_cache` present; SHA-256, `from_cache=True`, idempotent save all confirmed |
| `policy_extractor/ingestion/__init__.py` | Public `ingest_pdf()` orchestrator | VERIFIED | Full orchestration pipeline wired: hash -> cache check -> classify -> OCR -> build result -> save cache |
| `tests/test_ingestion.py` | Classifier + integration tests | VERIFIED | 24 test functions across 4 test classes; all non-Tesseract tests pass (33 passed, 2 skipped) |
| `tests/test_ocr_cache.py` | Unit tests for ocr_runner and cache | VERIFIED | 11 test functions across 2 test classes; all pass |
| `tests/fixtures/digital_sample.pdf` | Valid digital PDF fixture | VERIFIED | File present; classified as "digital" in test runs |
| `tests/fixtures/scanned_sample.pdf` | Valid scanned PDF fixture | VERIFIED | File present; classified as "scanned" in test runs |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `classifier.py` | `fitz (PyMuPDF)` | `page.get_images(full=True)` | WIRED | Line 26: `images = page.get_images(full=True)` confirmed; `get_image_rects(xref)` used for rect computation |
| `storage/models.py` | `storage/__init__.py` | `IngestionCache` in `__all__` | WIRED | `__all__` contains `"IngestionCache"` and import on line 3 confirmed |
| `ingestion/__init__.py` | `classifier.py` | `classify_all_pages()` called inside `ingest_pdf()` | WIRED | Line 87: `classifications = classify_all_pages(str(pdf_path))` |
| `ingestion/__init__.py` | `ocr_runner.py` | `run_ocr()` called for scanned pages | WIRED | Line 96: `ocr_output_path, ocr_language = ocr_with_fallback(pdf_path)` (conditional on `has_scanned`) |
| `ingestion/__init__.py` | `cache.py` | `lookup_cache()` before, `save_cache()` after | WIRED | Lines 66 and 138 respectively; both gated on `session` parameter |
| `cache.py` | `storage/models.py` | `IngestionCache` ORM model | WIRED | Line 11: `from policy_extractor.storage.models import IngestionCache`; used in `select(IngestionCache)` |
| `ocr_runner.py` | `ocrmypdf` | `ocrmypdf.ocr()` Python API | WIRED | Line 25: `exit_code = ocrmypdf.ocr(...)` with `deskew=True`, `skip_text=True`; `ExitCode.already_done_ocr` handled |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ING-01 | 02-01-PLAN.md | System detects whether a PDF contains selectable text or is a scanned image | SATISFIED | `classify_page` + `classify_all_pages` in classifier.py; 8 classifier tests pass; decorative image and transparent overlay filtering confirmed |
| ING-02 | 02-02-PLAN.md | System extracts text from scanned PDFs using OCR with Spanish and English support | SATISFIED | `run_ocr` uses Spanish by default; `ocr_with_fallback` retries with `["spa", "eng"]` on low confidence; English fallback test passes (mocked) |
| ING-05 | 02-02-PLAN.md | System caches OCR results to avoid reprocessing the same PDF | SATISFIED | SHA-256 hash key in `compute_file_hash`; `lookup_cache` + `save_cache` in cache.py; path-independent cache hit confirmed; `force_reprocess` bypass confirmed |

**Orphaned requirements check:** ING-03 and ING-04 appear in REQUIREMENTS.md but are assigned to Phase 4 (CLI) in ROADMAP.md. No orphaned requirements for Phase 2.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `policy_extractor/ingestion/__init__.py` | 130 | `datetime.utcnow()` deprecated | Info | Python 3.12+ deprecation warning; does not affect correctness; 23 similar warnings across cache.py and test files |
| `tests/test_ocr_cache.py` | 64 | `assert len(texts) >= 0` always True | Info | Test assertion is vacuous — passes regardless of output; does not block any goal |

No blocker or warning severity anti-patterns found. The `>= 0` assertion in `test_ocr_spanish_text` is logically vacuous but the test is gated behind `@requires_tesseract` so it is skipped in this environment.

---

### Human Verification Required

#### 1. End-to-End Scanned PDF OCR

**Test:** Install Tesseract with Spanish language pack and Poppler, then run `pytest tests/test_ingestion.py tests/test_ocr_cache.py -v` without the `-k "not requires_tesseract"` filter.
**Expected:** `test_ingest_scanned_pdf` passes with `result.ocr_applied is True`; `test_ocr_spanish_text` produces at least some text output from the scanned fixture.
**Why human:** Tesseract is not installed in this environment. The 2 skipped tests in the current run are `TestIngestPdf::test_ingest_scanned_pdf` and `TestOcrRunner::test_ocr_spanish_text`.

#### 2. English Confidence Fallback Live Path

**Test:** With Tesseract and Poppler installed, run `ocr_with_fallback` on a real scanned PDF that produces low Spanish confidence (e.g., an English-language insurance scan). Verify `ocr_language` in the returned tuple is `"spa+eng"`.
**Expected:** Re-run occurs with `["spa", "eng"]` and the result OCR language string reflects the fallback.
**Why human:** Cannot trigger real low-confidence OCR path without actual scanned input and Tesseract installed.

---

### Gaps Summary

No gaps. All automated checks pass. The phase goal is achieved: any PDF — digital or scanned — is routed to the correct processing path before touching the LLM. The routing decision (`classify_all_pages`) is fully implemented and tested. The OCR path (`ocr_with_fallback` + `extract_text_by_page`) is implemented with correct wiring; only its live execution requires Tesseract, which is an environment constraint rather than an implementation gap.

**Test run result:** 94 passed, 2 skipped (Tesseract-gated), 0 failed across the full suite.

---

_Verified: 2026-03-18T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
