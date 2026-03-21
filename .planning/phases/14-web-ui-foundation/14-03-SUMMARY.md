---
phase: 14
plan: 03
subsystem: web-ui-foundation
tags: [jinja2, fastapi, htmx, templates, poliza-list, poliza-detail, export, search, pagination]
requirements_completed: [UI-02]
dependency_graph:
  requires: [14-01]
  provides: [poliza-list-page, poliza-detail-page, poliza-rows-partial, poliza-ui-router]
  affects: [14-04, 14-05]
tech_stack:
  added: []
  patterns: [HTMX search with debounce, StaticPool in-memory DB for FastAPI tests, FileResponse + BackgroundTasks for export cleanup, poliza_ui_router APIRouter]
key_files:
  created:
    - policy_extractor/api/ui/poliza_views.py
    - policy_extractor/templates/poliza_list.html
    - policy_extractor/templates/poliza_detail.html
    - policy_extractor/templates/partials/poliza_rows.html
    - tests/test_ui_pages.py
  modified:
    - policy_extractor/api/__init__.py
key_decisions:
  - "StaticPool used in test_ui_pages.py for in-memory SQLite so all session factory connections share the same DB — without it, each new connection gets an empty DB"
  - "test_upload.py::test_pipeline_success_sets_complete is a pre-existing failure (fails on commit beb2dfb-1, before any 14-03 code was written) — deferred, out of scope"
  - "poliza_export BackgroundTasks parameter kept optional (= None) per plan spec — callers without background_tasks won't crash on file cleanup failure"
metrics:
  duration_seconds: 312
  completed_date: "2026-03-21"
  tasks_completed: 2
  files_created: 5
  files_modified: 1
---

# Phase 14 Plan 03: Poliza List and Detail Pages Summary

**One-liner:** Poliza list page with HTMX search/filter/load-more pagination, detail page with grouped field display and xlsx/csv/json export downloads.

## What Was Built

### Task 1: Poliza List and Detail Routes

- **policy_extractor/api/ui/poliza_views.py** — `poliza_ui_router` APIRouter with 4 endpoints:
  - `GET /ui/polizas` — Poliza list with filters (q, aseguradora, desde, hasta), 25-record pagination via `skip`, summary bar stats (total/warnings/review counts). Returns `poliza_list.html` for full requests, `partials/poliza_rows.html` for HTMX requests.
  - `GET /ui/polizas/{id}` — Poliza detail page with all field groups, has_pdf check, validation_warnings display.
  - `GET /ui/polizas/{id}/export/{fmt}` — Export as xlsx, csv, or json via FileResponse + BackgroundTasks temp file cleanup.
  - `GET /ui/polizas/{id}/pdf` — Serve retained PDF from `data/pdfs/{id}.pdf` for future iframe viewer.
- **policy_extractor/api/__init__.py** — Added `app.include_router(poliza_ui_router)`.

### Task 2: Templates, Rows Partial, and Tests

- **policy_extractor/templates/poliza_list.html** — Extends base.html. Summary bar (3 stat badges), collapsible filter panel (free-text search with 300ms HTMX debounce, aseguradora select, date range desde/hasta), full-width table with `id="poliza-rows"` target, empty state ("Sin polizas registradas").
- **policy_extractor/templates/partials/poliza_rows.html** — Bare `<tr>` elements (no `{% extends %}`). Score coloring (red below 0.70). "Cargar mas polizas" load-more button with `hx-swap="beforeend"` pattern.
- **policy_extractor/templates/poliza_detail.html** — Extends base.html. Export buttons (Descargar Excel/CSV/JSON), validation warnings yellow alert box, 8 field groups rendered as `<dl>` definition lists: Informacion General, Vigencia, Financiero, Personas, Asegurados, Coberturas, Campos Adicionales, Proveniencia, Evaluacion.
- **tests/test_ui_pages.py** — 10 tests using StaticPool in-memory SQLite DB + `autouse` fixtures for DB override and table cleanup per test. Covers: list 200/heading/rows-id, HTMX partial (no DOCTYPE), detail 200/404, search 200/finds record, detail shows numero_poliza and Descargar Excel.

## Test Results

- 10/10 `tests/test_ui_pages.py` tests pass
- 345/345 total tests pass (excluding pre-existing test_upload.py failure, 3 skipped)
- No regressions introduced by this plan

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLite cross-thread error in tests**
- **Found during:** Task 2 verification (first test run)
- **Issue:** Using per-fixture `create_engine("sqlite:///:memory:")` without `StaticPool` caused each session factory connection to create a new empty DB — the polizas table wasn't visible to route handlers running in TestClient's thread.
- **Fix:** Used `StaticPool` (from `sqlalchemy.pool`) so all connections share the same in-memory database. Added `check_same_thread=False` per the existing pattern in `tests/test_upload.py`. Restructured fixtures to use module-level engine + session factory pattern matching `test_upload.py`.
- **Files modified:** `tests/test_ui_pages.py`
- **Commit:** e182be5

### Pre-existing Failures (Out of Scope)

- `tests/test_upload.py::test_pipeline_success_sets_complete` — Confirmed failing before any 14-03 code was written (verified by running against beb2dfb-1 baseline). This is a pre-existing issue, not caused by this plan. Deferred.

## Known Stubs

None — all data is wired to live DB queries. Empty states display correctly when no records exist.

## Commits

| Hash | Message |
|------|---------|
| beb2dfb | feat(14-03): poliza list/detail routes with search, filter, pagination, and export |
| e182be5 | feat(14-03): poliza list template, detail template, rows partial, and page tests |

## Self-Check: PASSED

All created files verified:
- `policy_extractor/api/ui/poliza_views.py` — exists, contains `poliza_ui_router = APIRouter()`, `PAGE_SIZE = 25`, `Poliza.numero_poliza.ilike`, all 4 route decorators
- `policy_extractor/templates/poliza_list.html` — exists, contains `poliza-rows`, `hx-trigger="keyup changed delay:300ms"`, `Sin polizas registradas`, `Filtros`
- `policy_extractor/templates/partials/poliza_rows.html` — exists, contains `Cargar mas polizas`, `hx-swap="beforeend"`, NO `{% extends`
- `policy_extractor/templates/poliza_detail.html` — exists, contains `Descargar Excel`, `Descargar JSON`, `{% extends "base.html" %}`
- `tests/test_ui_pages.py` — exists, 10 tests all pass

Both task commits verified in git log: beb2dfb, e182be5
