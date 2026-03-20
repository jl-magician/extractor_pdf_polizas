---
phase: 13-extraction-pipeline-fixes
plan: 01
subsystem: ingestion
tags: [ocr, pymupdf, ocrmypdf, pydantic, ingestion-pipeline, auto-reclassification]

requires:
  - phase: 02-ingestion-layer
    provides: ingest_pdf() orchestrator, PageResult schema, ocr_with_fallback()
  - phase: 03-ocr-runner
    provides: ocr_with_fallback, extract_text_by_page, run_ocr functions

provides:
  - Auto-OCR reclassification gate: digital pages with < OCR_MIN_CHARS_THRESHOLD chars are re-run through OCR
  - Extended PageResult classification Literal with "scanned (auto-reclassified)" value
  - Configurable OCR_MIN_CHARS_THRESHOLD setting (default 10, env-overridable)
  - Whole-PDF OCR retry (D-16): if all reclassified pages yield empty text, full re-run fires
  - try/except resilience wrapping all OCR calls in ingest_pdf()
  - Updated cache.py ocr_applied detection to cover "scanned (auto-reclassified)" pages
  - 8 new tests covering all reclassification and retry paths

affects:
  - downstream extraction (policy_extractor/extraction) — sees more non-empty page text
  - API upload path — ocr_applied field now more accurately reflects OCR usage
  - regression tests — updated PageResult Literal is backward-compatible

tech-stack:
  added: []
  patterns:
    - "Per-page char-count gate in else branch of ingest_pdf(): classify first, then check len(text.strip())"
    - "Whole-PDF OCR retry (D-16): check all(t.strip() == '' for t in reclassified_texts) before second ocr_with_fallback call"
    - "any_ocr derived variable replaces has_scanned in ocr_applied field — covers both code paths"

key-files:
  created: []
  modified:
    - policy_extractor/schemas/ingestion.py
    - policy_extractor/config.py
    - policy_extractor/ingestion/__init__.py
    - policy_extractor/ingestion/cache.py
    - tests/test_ingestion.py

key-decisions:
  - "Auto-reclassification gate uses < threshold (strictly less than) so pages with exactly threshold chars are NOT reclassified — avoids over-triggering OCR on borderline pages"
  - "Whole-PDF retry (D-16) fires only when ALL reclassified pages have empty text — not a single partial failure — preventing redundant OCR runs when first pass succeeded for some pages"
  - "try/except wraps each OCR call independently: per-page OCR failure preserves original text; whole-PDF retry failure is caught separately — two independent resilience layers"
  - "settings.OCR_MIN_CHARS_THRESHOLD imported inside else branch (not module level) to avoid circular import risk; already imported at module level via from policy_extractor.config import settings in __init__.py"

patterns-established:
  - "OCR failure resilience: each ocr_with_fallback() call in ingest_pdf() is wrapped in try/except — logs warning, continues with original/partial data"
  - "Auto-reclassify classification sentinel: 'scanned (auto-reclassified)' string distinguishes auto-triggered OCR from originally-scanned pages in audit trail"
  - "model_copy(update={...}) for immutable PageResult replacement: pages[i] = page.model_copy(update={...}) instead of mutating in-place"

requirements-completed: [EXT-03]

duration: 18min
completed: 2026-03-20
---

# Phase 13 Plan 01: Auto-OCR Fallback for Zero-Text Digital Pages Summary

**Per-page char-count gate auto-reclassifies digital pages with fewer than 10 characters as "scanned (auto-reclassified)" and applies OCR, with whole-PDF retry (D-16) when all reclassified pages still yield empty text**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-20T20:22:00Z
- **Completed:** 2026-03-20T20:40:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Extended `PageResult.classification` Literal to include `"scanned (auto-reclassified)"` for audit trail
- Added `OCR_MIN_CHARS_THRESHOLD` setting (default 10) configurable via environment variable
- Implemented per-page char-count gate in `ingest_pdf()` else branch: digital pages with `< threshold` chars are auto-reclassified and OCR is applied
- Implemented D-16 whole-PDF OCR retry: when all reclassified pages still have empty text after initial OCR pass, the full PDF is re-run through `ocr_with_fallback()`
- Wrapped all OCR calls in `try/except` — single OCR failure does not crash the batch
- Updated `cache.py` `ocr_applied` detection to include `"scanned (auto-reclassified)"` pages
- Added 8 new tests covering: low-char detection, threshold boundary, OCR failure resilience, schema validation, D-16 retry trigger, retry skip, and retry failure resilience

## Task Commits

Each task was committed atomically:

1. **Task 1: Add auto-OCR reclassification to ingestion pipeline** - `c6af42c` (feat)
2. **Task 2: Add tests for auto-OCR reclassification** - `721736f` (test)

## Files Created/Modified

- `policy_extractor/schemas/ingestion.py` — Extended PageResult classification Literal with "scanned (auto-reclassified)"
- `policy_extractor/config.py` — Added OCR_MIN_CHARS_THRESHOLD setting with default 10
- `policy_extractor/ingestion/__init__.py` — Per-page char count gate, auto-reclassification, whole-PDF retry (D-16), try/except resilience
- `policy_extractor/ingestion/cache.py` — Updated ocr_applied to detect "scanned (auto-reclassified)" pages
- `tests/test_ingestion.py` — 8 new tests in TestAutoOcrReclassification class

## Decisions Made

- Auto-reclassification gate uses `< threshold` (strictly less than) so pages with exactly threshold chars are NOT reclassified — avoids over-triggering OCR on borderline pages
- Whole-PDF retry (D-16) fires only when ALL reclassified pages have empty text — not a single partial failure — preventing redundant OCR runs when first pass partially succeeded
- `any_ocr` local variable derived after building pages replaces `has_scanned` in `ocr_applied` field, covering both the scanned branch and the auto-reclassified branch

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — all mocks behaved as expected, tests passed green on first run.

## User Setup Required

None - no external service configuration required. OCR_MIN_CHARS_THRESHOLD can be set via environment variable to override the default of 10.

## Next Phase Readiness

- Auto-OCR fallback is complete and tested — digital PDFs with vector graphics but no selectable text will now produce non-empty extractions
- D-16 whole-PDF retry covers edge cases where per-page OCR also fails to extract text
- Ready for Phase 13-02 (next plan in extraction pipeline fixes)

---
*Phase: 13-extraction-pipeline-fixes*
*Completed: 2026-03-20*
