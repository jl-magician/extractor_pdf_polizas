---
phase: 02-ingestion
plan: 01
subsystem: ingestion
tags: [pydantic, sqlalchemy, pymupdf, classifier, tdd]
dependency_graph:
  requires: [01-foundation]
  provides: [PageResult, IngestionResult, IngestionCache, classify_page, classify_all_pages]
  affects: [02-02 (OCR runner and orchestrator)]
tech_stack:
  added: [pymupdf>=1.27.2, ocrmypdf>=17.3.0, pytesseract>=0.3.13, pdf2image>=1.17.0, loguru>=0.7]
  patterns: [TDD red-green, Pydantic v2 BaseModel, SQLAlchemy 2.0 Mapped[], image coverage ratio classification]
key_files:
  created:
    - policy_extractor/schemas/ingestion.py
    - policy_extractor/ingestion/classifier.py
    - tests/test_ingestion_contracts.py
    - tests/test_ingestion.py
    - tests/fixtures/digital_sample.pdf
    - tests/fixtures/scanned_sample.pdf
    - tests/create_fixtures.py
  modified:
    - pyproject.toml
    - policy_extractor/config.py
    - policy_extractor/storage/models.py
    - policy_extractor/storage/__init__.py
    - policy_extractor/ingestion/__init__.py
    - tests/conftest.py
decisions:
  - "get_image_rects() in PyMuPDF 1.27.2 returns list[Rect] not list[(Rect, Matrix)] — research docs were for older API; fixed inline"
  - "Added is_pdf check in classify_all_pages() because fitz.open() silently opens .txt files as 1-page documents without raising an error"
  - "Fixture PDFs committed to repository (tests/fixtures/) as stable test assets"
metrics:
  duration: "~4 minutes"
  completed_date: "2026-03-18"
  tasks_completed: 2
  files_created: 7
  files_modified: 6
---

# Phase 02 Plan 01: Ingestion Contracts and Classifier Summary

**One-liner:** Per-page PDF digital/scanned classifier using PyMuPDF image coverage ratio with smask filtering, plus Pydantic/SQLAlchemy typed contracts for the ingestion layer.

## What Was Built

### Pydantic Ingestion Models (`policy_extractor/schemas/ingestion.py`)

`PageResult` — typed per-page result with `classification: Literal["digital", "scanned"]`.
`IngestionResult` — full file result contract: file_hash, file_path, total_pages, pages list, file_size_bytes, created_at, ocr_applied, ocr_language, from_cache.

### SQLAlchemy Cache Model (`policy_extractor/storage/models.py`)

`IngestionCache` table added to existing Base with: file_hash (String(64), unique, indexed), file_path, total_pages, page_results (JSON), file_size_bytes, created_at, ocr_language.

### Config Extensions (`policy_extractor/config.py`)

Added OCR settings: TESSERACT_CMD, OCR_LANGUAGE, OCR_CONFIDENCE_THRESHOLD (60), PAGE_SCAN_THRESHOLD (0.80), DECORATIVE_IMAGE_MIN (0.10).

### Per-Page Classifier (`policy_extractor/ingestion/classifier.py`)

`classify_page(page)` — uses `page.get_images(full=True)`, skips images where smask != 0 (transparent overlays), skips images covering less than 10% of page area (decorative), returns "scanned" if remaining coverage >= 80%, else "digital".

`classify_all_pages(pdf_path)` — opens PDF with fitz, validates `doc.is_pdf`, checks for encryption, iterates pages, returns list of 1-based (page_num, classification) tuples. Raises RuntimeError on corrupted/non-PDF/password-protected files.

### Test Fixture PDFs

`tests/fixtures/digital_sample.pdf` — 1-page PDF with selectable Spanish insurance policy text, no images.
`tests/fixtures/scanned_sample.pdf` — 1-page PDF with a full-page raster image covering ~97% of page area.

### Dependencies Installed

pymupdf 1.27.2, ocrmypdf 17.3.0, pytesseract 0.3.13, pdf2image 1.17.0, loguru 0.7.3 — all added to pyproject.toml and installed via `pip install -e ".[dev]"`.

## Test Results

- 74 tests passing (42 pre-existing + 19 new contract tests + 13 new classifier tests)
- All acceptance criteria met

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PyMuPDF 1.27.2 get_image_rects() returns list[Rect] not list[(Rect, Matrix)]**
- **Found during:** Task 2, first GREEN test run
- **Issue:** Research documentation described `get_image_rects()` as returning `(rect, matrix)` tuples. In PyMuPDF 1.27.2 the method returns a plain list of `Rect` objects.
- **Fix:** Changed `for rect, _matrix in rects:` to `for rect in rects:` in classifier.py
- **Files modified:** `policy_extractor/ingestion/classifier.py`
- **Commit:** 175f23f

**2. [Rule 1 - Bug] fitz.open() silently opens non-PDF files without raising an exception**
- **Found during:** Task 2 `test_corrupted_pdf_raises_runtime_error`
- **Issue:** PyMuPDF opens .txt files as 1-page "documents" with `doc.is_pdf == False`. The original implementation's try/except was insufficient to catch this case.
- **Fix:** Added explicit `if not doc.is_pdf: raise RuntimeError(...)` check after opening
- **Files modified:** `policy_extractor/ingestion/classifier.py`
- **Commit:** 175f23f

## Self-Check

Files exist check:
- policy_extractor/schemas/ingestion.py: FOUND
- policy_extractor/ingestion/classifier.py: FOUND
- tests/test_ingestion.py: FOUND
- tests/fixtures/digital_sample.pdf: FOUND
- tests/fixtures/scanned_sample.pdf: FOUND

Commits exist check:
- 8629b28 (RED tests contracts): FOUND
- 00550e7 (GREEN contracts): FOUND
- aba10f8 (RED tests classifier): FOUND
- 175f23f (GREEN classifier): FOUND
