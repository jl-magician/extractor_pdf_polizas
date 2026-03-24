---
phase: 15-hitl-review-workflow
plan: "01"
subsystem: hitl-review-backend
tags: [hitl, corrections, audit-trail, fastapi, sqlalchemy, alembic, htmx]
dependency_graph:
  requires: [14-web-ui-foundation]
  provides: [corrections-orm, review-routes, dual-write-patch]
  affects: [policy_extractor/storage/models.py, policy_extractor/api/__init__.py]
tech_stack:
  added: []
  patterns:
    - Correction ORM model with poliza_id FK, field_path, old_value, new_value, corrected_at
    - Dot-notation field_path scheme for top-level / nested / campos_adicionales updates
    - Dual-write PATCH: single transaction updates ORM row + logs Correction
    - Inspector-guard pattern in Alembic upgrade() to avoid duplicate-table errors
    - Form(default="") for nullable string form fields in PATCH endpoints
key_files:
  created:
    - alembic/versions/005_corrections.py
    - policy_extractor/api/ui/review_views.py
    - policy_extractor/templates/poliza_review.html
    - policy_extractor/templates/partials/field_row.html
    - policy_extractor/templates/partials/correction_history.html
    - tests/test_ui_review.py
  modified:
    - policy_extractor/storage/models.py
    - policy_extractor/api/__init__.py
decisions:
  - "Form(default='') used for value param in PATCH endpoint — FastAPI treats empty string as missing with Form(...); default='' correctly accepts blank submissions for nullable-column null-setting"
  - "Stub templates created for poliza_review.html, field_row.html, correction_history.html — allow tests to pass on Plan 01; Plan 02 replaces with full implementations"
  - "_coerce_value returns None for empty string on non-required fields; raises 422 for non-nullable columns"
metrics:
  duration_seconds: 207
  completed_date: "2026-03-23"
  tasks_completed: 3
  files_created: 6
  files_modified: 2
---

# Phase 15 Plan 01: HITL Review Backend — Correction ORM, Routes, Tests Summary

**One-liner:** Corrections audit table with Alembic migration 005, three FastAPI review routes (GET/PATCH/GET-partial) with dual-write, and 15 integration tests covering all three field_path namespaces.

## What Was Built

### Correction ORM Model (models.py)
Added `Correction` class after `BatchJob`: poliza_id FK with CASCADE delete, field_path String, old_value Text, new_value Text, corrected_at DateTime. Added `corrections` back-reference to `Poliza` with `order_by="Correction.corrected_at"` and `cascade="all, delete-orphan"`.

### Alembic Migration 005 (005_corrections.py)
Follows the inspector-guard pattern from 004_batch_jobs.py. `revision = "c7f2e43b1d5a"`, `down_revision = "a3f8c91d0e2b"`. Creates corrections table with all required columns. Skips creation if table already exists (fresh DB via create_all).

### Review Routes (review_views.py)
Three routes registered under `review_router`:
- `GET /ui/polizas/{poliza_id}/review` — loads poliza with asegurados, coberturas, corrections; checks PDF existence at `data/pdfs/{id}.pdf`; builds field_groups; returns `poliza_review.html`
- `PATCH /ui/polizas/{poliza_id}/review/field` — dual-write: `_apply_field_update()` resolves field_path (3 namespaces), applies to ORM, logs `Correction` in one `db.commit()`; returns `partials/field_row.html` with `HX-Trigger: correctionSaved` header when value changed
- `GET /ui/polizas/{poliza_id}/corrections-partial` — returns `partials/correction_history.html` for HTMX refresh

### Stub Templates
Minimal stubs that allow test assertions (status codes + content) to pass until Plan 02 creates full implementations:
- `poliza_review.html` — shows numero_poliza + iframe src + field groups
- `partials/field_row.html` — div with field_path id and value
- `partials/correction_history.html` — details element with correction field_paths

### Integration Tests (test_ui_review.py)
15 passing tests + 2 xfail (Plan 02 template additions):
- GET review 200/404 (PDF present/absent)
- PATCH top-level, nested asegurado, nested cobertura, campos_adicionales
- PATCH logs correction, no duplicate on unchanged value
- PATCH empty string → null, empty non-nullable → 422
- corrections-partial 200 + 404

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Form(default="") for nullable PATCH value parameter**
- **Found during:** Task 3 — test_patch_empty_string_sets_null failed with 422
- **Issue:** FastAPI's `Form(...)` treats empty string body field as missing/required and rejects with 422 before the handler runs
- **Fix:** Changed `value: str = Form(...)` to `value: str = Form(default="")` in PATCH endpoint
- **Files modified:** `policy_extractor/api/ui/review_views.py`
- **Commit:** d46c7a5

## Known Stubs

| File | Stub | Reason |
|------|------|--------|
| `policy_extractor/templates/poliza_review.html` | Minimal HTML structure | Full split-pane layout + click-to-edit JS delivered in Plan 02 |
| `policy_extractor/templates/partials/field_row.html` | Single div | Full editable field row with HTMX attributes delivered in Plan 02 |
| `policy_extractor/templates/partials/correction_history.html` | Basic details element | Full styled history panel delivered in Plan 02 |

These stubs are intentional — they satisfy test assertions (HTTP status + content) and will be replaced by Plan 02.

## Self-Check: PASSED

Files confirmed present:
- alembic/versions/005_corrections.py: FOUND
- policy_extractor/api/ui/review_views.py: FOUND
- policy_extractor/templates/poliza_review.html: FOUND
- policy_extractor/templates/partials/field_row.html: FOUND
- policy_extractor/templates/partials/correction_history.html: FOUND
- tests/test_ui_review.py: FOUND

Commits confirmed:
- 873204d feat(15-01): Correction ORM model, Poliza back-reference, Alembic migration 005
- 3b68ed0 feat(15-01): review_views.py routes and router registration
- d46c7a5 test(15-01): integration tests for review endpoints + stub templates
