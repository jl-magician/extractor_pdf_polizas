---
phase: 14
plan: 01
subsystem: web-ui-foundation
tags: [jinja2, fastapi, templates, orm, migration, tailwind, htmx]
requirements_completed: [UI-06]
dependency_graph:
  requires: []
  provides: [base-template, batch-job-model, shared-templates-module, static-mount, dashboard-route]
  affects: [14-02, 14-03, 14-04, 14-05]
tech_stack:
  added: [jinja2>=3.1.6]
  patterns: [Jinja2Templates shared instance, StaticFiles mount, sidebar layout with Tailwind CDN, HTMX CDN, BatchJob ORM model]
key_files:
  created:
    - policy_extractor/templates/base.html
    - policy_extractor/templates/dashboard.html
    - policy_extractor/static/.gitkeep
    - alembic/versions/004_batch_jobs.py
    - policy_extractor/api/ui/__init__.py
    - tests/test_ui_infra.py
  modified:
    - pyproject.toml
    - policy_extractor/config.py
    - policy_extractor/storage/models.py
    - policy_extractor/api/__init__.py
key_decisions:
  - "Jinja2Templates shared instance in policy_extractor/api/ui/__init__.py so all UI routers import from one canonical location"
  - "StaticFiles mounted at /static before template import to avoid circular dependencies"
  - "TemplateResponse uses new positional request-first signature to avoid Starlette deprecation warnings"
  - "BatchJob uses String(36) primary key (UUID) not Integer autoincrement — matches async job ID pattern"
  - "Migration 004 uses inspector guard for batch_jobs table to prevent errors on fresh DBs created via create_all"
metrics:
  duration_seconds: 217
  completed_date: "2026-03-20"
  tasks_completed: 2
  files_created: 6
  files_modified: 4
---

# Phase 14 Plan 01: Web UI Infrastructure Summary

**One-liner:** Jinja2 + HTMX web UI foundation — BatchJob ORM model, migration 004, sidebar layout template, and shared templates module on existing FastAPI.

## What Was Built

### Task 1: Dependencies, Models, Migration, Config, Templates Module

- **pyproject.toml** — Added `jinja2>=3.1.6` dependency
- **policy_extractor/config.py** — Added `REVIEW_SCORE_THRESHOLD: float = 0.70`
- **policy_extractor/storage/models.py** — Added `BatchJob` ORM model with 9 columns: `id` (String UUID), `batch_name`, `status` (default "pending"), `total_files`, `completed_files`, `failed_files`, `created_at`, `completed_at`, `results_json`
- **alembic/versions/004_batch_jobs.py** — Migration creating `batch_jobs` table with inspector guard (`if "batch_jobs" not in inspector.get_table_names()`)
- **policy_extractor/api/ui/__init__.py** — Shared `Jinja2Templates` instance pointing at `policy_extractor/templates/`

### Task 2: Base Template, Static Mount, Dashboard Route

- **policy_extractor/templates/base.html** — Sidebar layout with `w-60 bg-gray-800` dark nav, Tailwind CDN (`@tailwindcss/browser@4`), HTMX CDN (`htmx.org@2.0.8`), Spanish nav labels (Dashboard, Subir PDFs, Polizas, Historial de Lotes), active page highlighting
- **policy_extractor/templates/dashboard.html** — Placeholder dashboard extending base.html
- **policy_extractor/static/.gitkeep** — Empty file ensuring static/ directory exists for StaticFiles mount
- **policy_extractor/api/__init__.py** — Added `StaticFiles` mount at `/static`, imported shared `templates`, added `GET /` dashboard route

## Test Results

- 9/9 `tests/test_ui_infra.py` tests pass
- 336/336 total tests pass (3 skipped — pre-existing Tesseract/fixture dependencies)
- No regressions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Starlette TemplateResponse deprecated signature**
- **Found during:** Task 2 verification
- **Issue:** `TemplateResponse(name, {"request": request})` triggers deprecation warning in Starlette — the new signature puts `request` as first positional parameter
- **Fix:** Changed to `templates.TemplateResponse(request, "dashboard.html", {"active_page": "dashboard"})`
- **Files modified:** `policy_extractor/api/__init__.py`
- **Commit:** ae041a7

## Known Stubs

- `policy_extractor/templates/dashboard.html` — Contains placeholder text "Contenido del dashboard se implementara en Plan 04." — intentional; Plan 04 (14-04) will implement the actual dashboard content

## Commits

| Hash | Message |
|------|---------|
| ed29972 | feat(14-01): BatchJob model, migration 004, jinja2 dep, REVIEW_SCORE_THRESHOLD, shared templates module |
| ae041a7 | feat(14-01): base template, static mount, dashboard route |

## Self-Check: PASSED

All created files verified:
- `policy_extractor/templates/base.html` — exists, contains `tailwindcss/browser@4`, `htmx.org@2.0.8`, `w-60 bg-gray-800`
- `policy_extractor/templates/dashboard.html` — exists, extends base.html
- `policy_extractor/static/.gitkeep` — exists
- `alembic/versions/004_batch_jobs.py` — exists, contains `batch_jobs` and `inspector.get_table_names`
- `policy_extractor/api/ui/__init__.py` — exists, contains `templates = Jinja2Templates(`
- `tests/test_ui_infra.py` — exists, 9 tests all passing

Both commits verified in git log: ed29972, ae041a7
