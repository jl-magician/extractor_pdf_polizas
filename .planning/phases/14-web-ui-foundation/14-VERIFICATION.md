---
phase: 14-web-ui-foundation
verified: 2026-03-21T00:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 14: Web UI Foundation Verification Report

**Phase Goal:** The agency team can upload PDFs, monitor job progress, browse polizas, and export data from a browser without using the CLI
**Verified:** 2026-03-21
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | User can drag-and-drop (or file-pick) a PDF, submit it, and watch an inline status indicator update to "complete" without refreshing | VERIFIED | `upload.html` has `hx-post="/ui/batch/upload"`, `batch_progress.html` polls `hx-trigger="every 2s"`, `batch_status` returns `HX-Trigger: batchDone` on completion |
| SC-2 | User can browse a paginated poliza list filtered by aseguradora, date range, and status, and open any record to see all extracted fields | VERIFIED | `poliza_views.py` has `Poliza.numero_poliza.ilike`, `PAGE_SIZE=25`, date filters; `poliza_list.html` has `#poliza-rows`, `poliza_rows.html` has "Cargar mas polizas" with `hx-swap="beforeend"`; `poliza_detail.html` has all field groups |
| SC-3 | User can view a dashboard page showing total polizas processed, breakdown by aseguradora, and count of records with validation warnings | VERIFIED | `dashboard_views.py` uses `func.count`, `func.avg`, `REVIEW_SCORE_THRESHOLD`; `dashboard_stats.html` shows "Total Polizas" and "Requieren revision" table |
| SC-4 | User can download a poliza's data as Excel or JSON directly from the detail page without opening a terminal | VERIFIED | `poliza_detail.html` links to `/ui/polizas/{id}/export/xlsx`, `/export/csv`, `/export/json`; `poliza_export` handler calls `export_xlsx`, `export_csv`, `orm_to_schema` and returns `FileResponse` |
| SC-5 | Uploaded PDFs are retained on disk at `data/pdfs/{poliza_id}.pdf` and remain accessible after the extraction job expires from memory | VERIFIED | `upload.py` defines `PDFS_RETENTION_DIR`, calls `shutil.copy2` in `_run_single_file_extraction` and the old `_run_extraction`; `poliza_views.py` serves PDFs via `/ui/polizas/{id}/pdf` |

**Score: 5/5 truths verified**

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `policy_extractor/templates/base.html` | Sidebar layout shell with CDN scripts | VERIFIED | Contains `tailwindcss/browser@4`, `htmx.org@2.0.8`, `w-60 bg-gray-800`, `lang="es"`, all 4 nav items |
| `policy_extractor/storage/models.py` | BatchJob ORM model with 9 columns | VERIFIED | Contains `class BatchJob`, `__tablename__ = "batch_jobs"`, all 9 columns (id, batch_name, status, total_files, completed_files, failed_files, created_at, completed_at, results_json) |
| `alembic/versions/004_batch_jobs.py` | Migration for batch_jobs table | VERIFIED | Contains `batch_jobs`, `inspector.get_table_names()` guard |
| `policy_extractor/api/ui/__init__.py` | Shared Jinja2Templates instance | VERIFIED | `templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))` |
| `policy_extractor/api/upload.py` | Batch extraction worker + PDF retention | VERIFIED | `PDFS_RETENTION_DIR`, `shutil.copy2`, `_run_batch_extraction`, `_run_single_file_extraction` |
| `policy_extractor/api/ui/upload_views.py` | HTML upload routes with full handler bodies | VERIFIED | `upload_ui_router`, 4 routes, `BatchJob(` creation, `threading.Thread` spawn, `export_xlsx`/`export_csv`, `FileResponse`, `HX-Trigger` header |
| `policy_extractor/templates/upload.html` | Upload page with drop zone and HTMX | VERIFIED | "Arrastra tus PDFs aqui", "Procesar Lote", `hx-post="/ui/batch/upload"`, `multiple accept=".pdf"` |
| `policy_extractor/templates/partials/batch_progress.html` | HTMX polling partial | VERIFIED | `hx-trigger="every 2s"`, no `{% extends %}` |
| `policy_extractor/templates/partials/batch_summary.html` | Batch results table | VERIFIED | "Resultados del lote", "Descargar Excel", "Descargar JSON", no `{% extends %}` |
| `policy_extractor/api/ui/poliza_views.py` | Poliza list, detail, export routes | VERIFIED | `poliza_ui_router`, `PAGE_SIZE=25`, `Poliza.numero_poliza.ilike`, `/ui/polizas`, `/ui/polizas/{id}`, `/ui/polizas/{id}/export/{fmt}`, `/ui/polizas/{id}/pdf` |
| `policy_extractor/templates/poliza_list.html` | Poliza list with filter panel | VERIFIED | `#poliza-rows`, `hx-trigger="keyup changed delay:300ms"`, "Sin polizas registradas", "Filtros" |
| `policy_extractor/templates/poliza_detail.html` | Poliza detail with export buttons | VERIFIED | "Descargar Excel", "Descargar JSON", `{% extends "base.html" %}`, export links point to real routes |
| `policy_extractor/templates/partials/poliza_rows.html` | Table rows partial | VERIFIED | "Cargar mas polizas", `hx-swap="beforeend"`, no `{% extends %}` |
| `policy_extractor/api/ui/dashboard_views.py` | Dashboard routes with aggregate queries | VERIFIED | `dashboard_router`, `func.count(Poliza.id)`, `func.avg(Poliza.evaluation_score)`, `REVIEW_SCORE_THRESHOLD`, `@dashboard_router.get("/")`, `desde`/`hasta` params |
| `policy_extractor/templates/dashboard.html` | Dashboard with stat cards + date filter | VERIFIED | `#dashboard-stats`, "Ultimos 7 dias", `type="date"`, `id="desde"`, `id="hasta"`, `hx-include="#hasta"`, `{% extends "base.html" %}` |
| `policy_extractor/templates/partials/dashboard_stats.html` | Stats cards partial | VERIFIED | "Total Polizas", "Requieren revision", no `{% extends %}` |
| `policy_extractor/api/ui/job_views.py` | Job history routes | VERIFIED | `job_ui_router`, `@job_ui_router.get("/ui/lotes")`, `BatchJob.created_at.desc()` |
| `policy_extractor/templates/job_history.html` | Job history page | VERIFIED | "Historial de Lotes", "Sin lotes anteriores", `sr-only` accessibility text, `{% extends "base.html" %}` |
| `tests/test_ui_integration.py` | Integration tests (305 lines) | VERIFIED | Covers all 4 page routes, sidebar links, CDN tags, Spanish copy, SC-1 through SC-5 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `policy_extractor/api/__init__.py` | `policy_extractor/templates/` | `Jinja2Templates` mount (via ui/__init__.py import) | WIRED | `from policy_extractor.api.ui import templates` at line 47 |
| `policy_extractor/api/__init__.py` | `policy_extractor/static/` | `StaticFiles` mount | WIRED | `app.mount("/static", StaticFiles(directory=str(STATIC_DIR)))` line 44 |
| `policy_extractor/api/__init__.py` | all 4 UI routers | `app.include_router` | WIRED | Lines 257-260: all 4 routers registered |
| `upload.html` | `upload_views.py` | `hx-post="/ui/batch/upload"` | WIRED | Template line 10 hits `@upload_ui_router.post("/ui/batch/upload")` |
| `batch_progress.html` | `upload_views.py` | `hx-trigger="every 2s"` polling | WIRED | Polls `hx-get="/ui/batch/{{ batch.id }}/status"` which is handled by `batch_status` |
| `upload.py` | `data/pdfs/` | `shutil.copy2` PDF retention | WIRED | Lines 144-146, 181-183, 229-231, 246-248 |
| `upload_views.py` | `export.py` | `export_xlsx`/`export_csv` calls | WIRED | `batch_export` imports and calls both functions |
| `poliza_list.html` | `poliza_views.py` | `hx-get="/ui/polizas"` for search/filter | WIRED | Multiple `hx-get="/ui/polizas"` triggers wired to `poliza_list` handler |
| `poliza_views.py` | `storage/models.py` | `Poliza.numero_poliza.ilike` LIKE filter | WIRED | Line 40 in `poliza_views.py` |
| `dashboard.html` | `dashboard_views.py` | `hx-get="/?periodo=7d"` date range filter | WIRED | Buttons and inputs use `hx-get="/"` targeting `#dashboard-stats` |
| `dashboard_views.py` | `storage/models.py` | `func.count`/`func.avg` aggregate queries | WIRED | Lines 23-24 in `dashboard_views.py` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| UI-01 | 14-02, 14-05 | User can upload PDFs and view extraction results in a browser interface | SATISFIED | Upload page at `/subir`, batch workflow with HTMX polling, summary table with per-file results |
| UI-02 | 14-03, 14-05 | User can search and filter the policy list by aseguradora, date range, and status | SATISFIED | `poliza_list.html` with HTMX search (300ms debounce), aseguradora select, date inputs; `poliza_detail.html` with all fields |
| UI-05 | 14-04, 14-05 | User can view a dashboard with extraction statistics and quality metrics | SATISFIED | Dashboard at `/` with `func.count`, `func.avg`, `REVIEW_SCORE_THRESHOLD`, date range filter (presets + custom), "Requieren revision" table |
| UI-06 | 14-01, 14-02, 14-05 | System retains uploaded PDFs for review UI display | SATISFIED | `PDFS_RETENTION_DIR`, `shutil.copy2` in `_run_single_file_extraction`; PDF served at `/ui/polizas/{id}/pdf` |

No orphaned requirements found — all 4 requirement IDs declared in PLANs are accounted for in REQUIREMENTS.md with Phase 14 assignment.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_ui_infra.py` | 85-133 | Tests using real app without DB override fail when run in isolation (SQLAlchemy `UnboundExecutionError`) but pass in full suite due to test execution order | INFO | Tests pass in `python -m pytest tests/` (418 passed, 0 failed); only fail when `test_ui_infra.py` is run alone. Does not block goal achievement. |

No stub implementations, no placeholder returns, no hardcoded empty arrays flowing to renders. All partial templates correctly omit `{% extends %}`.

---

## Human Verification Required

The following items are confirmed to have been human-verified per the 14-05-SUMMARY.md checkpoint (user approved visual layout):

### 1. Drag-and-drop behavior

**Test:** Upload a PDF via drag-and-drop in the browser, confirm the drop zone highlights on dragover and the file appears in the list below.
**Expected:** Drop zone border turns blue on drag-over; file name appears with count in `#file-list`; "Procesar Lote" button becomes enabled.
**Why human:** JavaScript drag-and-drop event handlers (`dragover`, `dragleave`, `drop`) cannot be exercised via `TestClient`.

### 2. HTMX live polling

**Test:** Submit a batch of 2+ PDFs. Watch the progress bar update without a page refresh.
**Expected:** Progress bar advances from 0% to 100% as files complete; summary table replaces progress bar automatically.
**Why human:** Browser required to exercise real HTMX polling over HTTP.

### 3. Sidebar active-page highlighting

**Test:** Navigate to each of the 4 pages; confirm the current page's nav item has the `border-l-2 border-blue-400 bg-gray-700` style applied.
**Expected:** Only the current page's nav link is highlighted.
**Why human:** CSS class presence can be verified in HTML source (and is asserted in integration tests), but visual rendering requires browser inspection.

**Status:** Per 14-05-SUMMARY.md, the user visually approved all 5 pages, sidebar, Spanish copy, and styling on 2026-03-20.

---

## Gaps Summary

No gaps found. All 5 success criteria are fully implemented and verified:

- SC-1 (Upload + polling): Full batch upload workflow exists with HTMX polling, progress bar, and summary table.
- SC-2 (Poliza list + detail): Paginated, searchable, filterable poliza list and full detail page implemented.
- SC-3 (Dashboard): Aggregate stat cards with date range filtering and needs-review table.
- SC-4 (Export): Excel, CSV, and JSON export available from both poliza detail page and batch summary.
- SC-5 (PDF retention): `shutil.copy2` to `data/pdfs/{poliza_id}.pdf` implemented throughout the upload pipeline.

All 4 requirement IDs (UI-01, UI-02, UI-05, UI-06) are satisfied. Full test suite passes (418 passed, 3 skipped, 0 failed). One test isolation issue in `test_ui_infra.py` is a non-blocking informational finding — tests pass correctly when run in full suite order.

---

_Verified: 2026-03-21_
_Verifier: Claude (gsd-verifier)_
