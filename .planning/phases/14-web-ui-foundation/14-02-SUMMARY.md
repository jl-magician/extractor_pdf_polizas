---
phase: 14
plan: 02
subsystem: web-ui-foundation
tags: [htmx, jinja2, fastapi, batch-upload, pdf-retention, export]
requirements_completed: [UI-01, UI-06]
dependency_graph:
  requires: [14-01]
  provides: [batch-upload-endpoint, progress-polling, batch-summary, pdf-retention, batch-export]
  affects: [14-03, 14-04, 14-05]
tech_stack:
  added: []
  patterns: [threading.Thread for batch background work, HTMX polling with hx-trigger every 2s, HX-Trigger response header to stop polling, FileResponse for batch exports, best-effort PDF retention copy-then-unlink]
key_files:
  created:
    - policy_extractor/api/ui/upload_views.py
    - policy_extractor/templates/upload.html
    - policy_extractor/templates/partials/batch_progress.html
    - policy_extractor/templates/partials/batch_summary.html
    - tests/test_ui_upload.py
  modified:
    - policy_extractor/api/upload.py
    - policy_extractor/api/__init__.py
key_decisions:
  - "PDF retention in _run_extraction is best-effort (try/except non-fatal) — job status set to complete before retention attempt so mock failures in tests do not break job state"
  - "UPLOADS_DIR for UI batch upload is data/uploads/ (not top-level uploads/) to separate batch UI uploads from JSON API uploads"
  - "threading.Thread (not BackgroundTasks) for batch extraction — keeps same pattern as existing single-file upload, avoids FastAPI lifecycle coupling"
  - "HX-Trigger: batchDone response header signals HTMX to stop polling when batch is complete or failed"
metrics:
  duration_seconds: 385
  completed_date: "2026-03-20"
  tasks_completed: 3
  files_created: 5
  files_modified: 2
---

# Phase 14 Plan 02: Batch Upload Workflow Summary

**One-liner:** Batch PDF upload with DB-backed BatchJob, HTMX polling progress bar, per-file summary table, PDF retention to data/pdfs/, and xlsx/csv/json export from results.

## What Was Built

### Task 1: upload.py — Batch Worker, Single-File Helper, PDF Retention

- **PDFS_RETENTION_DIR** constant added: `data/pdfs/{poliza_id}.pdf`
- **`_run_single_file_extraction(session, pdf_path, model, force)`** — runs the full extraction pipeline (ingest_pdf, extract_policy, upsert_policy) for a single file, copies PDF to retention dir, returns `("complete", {poliza_id, numero_poliza, aseguradora})` or `("failed", {error})`
- **`_run_batch_extraction(batch_id, file_entries, model, force)`** — iterates file_entries, calls `_run_single_file_extraction`, uses atomic SQLAlchemy `update().values(completed_files=BatchJob.completed_files + 1)` (Pitfall 5), stores per-file summaries in `results_json`, sets `status="complete"` with `completed_at` at the end. Per D-06: individual file failures do not stop remaining files.
- **`_run_extraction` modified** — also retains PDFs to `data/pdfs/{poliza_id}.pdf` (best-effort, non-fatal)

### Task 2: upload_views.py — Batch Upload UI Handlers

- **`upload_ui_router`** — APIRouter with 4 routes
- **GET `/subir`** — renders upload.html with `active_page="upload"`
- **POST `/ui/batch/upload`** — validates PDF files, auto-generates batch name if empty (`Lote YYYY-MM-DD HH:MM`), creates BatchJob in DB, saves PDFs to `data/uploads/{batch_id}_{filename}`, spawns `threading.Thread` calling `_run_batch_extraction`, returns `batch_progress.html` partial
- **GET `/ui/batch/{batch_id}/status`** — returns progress partial (pct calculated as `completed_files/total_files`) or summary partial with `HX-Trigger: batchDone` header when complete/failed
- **GET `/ui/batch/{batch_id}/export/{fmt}`** — validates format (xlsx/csv/json), loads BatchJob, extracts `poliza_ids` from `results_json`, queries full Poliza rows with relationships, returns `FileResponse` (xlsx/csv) or JSON dump of `orm_to_schema` outputs
- **Registered `upload_ui_router`** in `policy_extractor/api/__init__.py`

### Task 3: Templates and Tests

- **`upload.html`** — extends base.html, centered `max-w-2xl` layout, drag-and-drop zone with `border-blue-500 bg-blue-50` toggle on dragover, file list display via JS, batch name input, submit button disabled until files selected, `hx-post="/ui/batch/upload"` with `hx-encoding="multipart/form-data"`, `<div id="batch-status">` target
- **`partials/batch_progress.html`** — NO extends, polling div with `hx-trigger="every 2s"`, progress bar `width: {{ pct }}%`
- **`partials/batch_summary.html`** — NO extends, heading "Resultados del lote — {{ batch.batch_name }}", export links (Descargar Excel, Descargar CSV, Descargar JSON), per-file results table with status badges (green/red), poliza number, aseguradora, detail link
- **`tests/test_ui_upload.py`** — 17 tests covering all endpoints, all 17 pass

## Test Results

- 17/17 `tests/test_ui_upload.py` tests pass
- 363/363 total tests pass (3 skipped — pre-existing Tesseract/fixture dependencies)
- No regressions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PDF retention in _run_extraction broke existing test_pipeline_success_sets_complete**
- **Found during:** Full test suite run after Task 3
- **Issue:** `_run_extraction` was changed to use `poliza = upsert_policy(...)` to get `poliza.id` for retention path. The existing test mocks `upsert_policy` returning a MagicMock, so `poliza.id` was a MagicMock object — causing `shutil.copy2` to fail, which (being inside the main try block) set job status to "failed" instead of "complete"
- **Fix:** Wrapped PDF retention in a nested `try/except` — retention is best-effort and non-fatal. Job status is set to "complete" before retention attempt, so retention errors do not affect job outcome. On retention failure, the temp PDF is still deleted.
- **Files modified:** `policy_extractor/api/upload.py`
- **Commit:** 14692cd

## Known Stubs

None — all handler bodies are fully implemented. The batch_progress.html and batch_summary.html partials render real DB data (BatchJob fields and results_json array).

## Commits

| Hash | Message |
|------|---------|
| c8149f1 | feat(14-02): batch extraction worker, single-file helper, PDF retention in upload.py |
| d6052e7 | feat(14-02): upload_views.py with batch upload, status polling, export handlers |
| dccc7ef | feat(14-02): upload.html, batch_progress.html, batch_summary.html templates and upload tests |
| 14692cd | fix(14-02): make PDF retention best-effort in _run_extraction to not break existing tests |

## Self-Check: PASSED
