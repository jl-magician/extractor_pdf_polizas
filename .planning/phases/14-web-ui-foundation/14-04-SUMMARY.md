---
phase: 14-web-ui-foundation
plan: "04"
subsystem: ui
tags: [fastapi, jinja2, htmx, tailwind, sqlalchemy, dashboard, job-history]

# Dependency graph
requires:
  - phase: 14-01
    provides: BatchJob model, shared templates instance, base.html sidebar template
  - phase: 14-02
    provides: upload_views, poliza_views registered in api/__init__.py
  - phase: 14-03
    provides: poliza list/detail UI pages with router registration pattern

provides:
  - Dashboard landing page at GET / with 3 stat cards (total polizas, warnings, avg score)
  - Date range filtering: preset buttons (7d, 30d, all) and custom desde/hasta date inputs per D-17
  - HTMX-driven stats partial at partials/dashboard_stats.html (replaced on date filter change)
  - "Requieren revision" table showing polizas with score < 0.70 or validation warnings
  - Job history page at GET /ui/lotes with batch list, status badges, re-download links
  - Aggregate SQLAlchemy queries using func.count and func.avg (DB-level, not Python loops)
  - 13 tests in tests/test_ui_dashboard.py covering both pages

affects:
  - Phase 14-05 (if adds lotes_views, needs to avoid route conflict with job_ui_router at /ui/lotes)
  - Phase 15 (poliza detail editing — will see polizas in review table as entry point)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "HTMX partial response: check request.headers.get('HX-Request') to return partial vs full page"
    - "DB-level aggregates: func.count and func.avg in a single select, not Python list comprehension"
    - "Date range filtering: periodo preset OR custom desde/hasta date query params (D-17)"
    - "Dashboard partial: no extends, just HTML fragment for HTMX innerHTML swap target"

key-files:
  created:
    - policy_extractor/api/ui/dashboard_views.py
    - policy_extractor/api/ui/job_views.py
    - policy_extractor/templates/dashboard.html
    - policy_extractor/templates/partials/dashboard_stats.html
    - policy_extractor/templates/job_history.html
    - tests/test_ui_dashboard.py
  modified:
    - policy_extractor/api/__init__.py

key-decisions:
  - "dashboard_router GET / replaces placeholder route from Plan 01 — same path, real aggregate queries"
  - "HTMX partial check: HX-Request header present → return partials/dashboard_stats.html (no DOCTYPE); absent → return full dashboard.html"
  - "Needs-review query uses OR(score < threshold, warnings IS NOT NULL) — both conditions trigger review"
  - "_get_stats and _get_needs_review share same date filter params to keep results consistent"
  - "job_ui_router registered before lotes_router (added by 14-05 parallel agent) — FastAPI uses first match for /ui/lotes so job_history.html is served"

patterns-established:
  - "Dashboard HTMX filter: preset buttons + custom date inputs both hx-get to same / endpoint with different params"
  - "Stats partial: standalone HTML fragment (no extends) included via Jinja2 include on initial load, replaced by HTMX on filter"

requirements-completed:
  - UI-05

# Metrics
duration: 5min
completed: "2026-03-21"
---

# Phase 14 Plan 04: Dashboard and Job History Summary

**Dashboard with DB-aggregate stat cards and HTMX date range filter (7d/30d/custom desde-hasta per D-17), plus job history page with status badges and re-download links**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-21T03:25:51Z
- **Completed:** 2026-03-21T03:30:30Z
- **Tasks:** 2 completed
- **Files modified:** 7

## Accomplishments

- Dashboard at GET / shows 3 stat cards (Total Polizas, Advertencias, Score Promedio) computed with SQLAlchemy func.count/func.avg
- Date range filtering with preset buttons (7d, 30d, all) and custom `desde`/`hasta` date inputs per D-17; HTMX replaces `#dashboard-stats` div without full page reload
- "Requieren revision" table lists polizas with score < 0.70 OR validation warnings, with empty state copy per Copywriting Contract
- Job history page at GET /ui/lotes lists BatchJob records sorted by created_at DESC, with semantic status badges (green/blue/red/gray) and re-download links for completed batches
- 13 automated tests covering both pages, all passing; full suite at 418 passed

## Task Commits

1. **Task 1: Dashboard routes, stats partial, and date range filter** - `f12acb4` (feat)
2. **Task 2: Job history page, register job_ui_router, and tests** - `039dfee` (feat)

## Files Created/Modified

- `policy_extractor/api/ui/dashboard_views.py` - dashboard_router with GET /, _get_stats, _get_needs_review using SQLAlchemy aggregates
- `policy_extractor/api/ui/job_views.py` - job_ui_router with GET /ui/lotes, BatchJob query sorted by created_at DESC
- `policy_extractor/templates/dashboard.html` - replaces Plan 01 placeholder; stat cards, preset + custom date filter buttons with HTMX, includes stats partial
- `policy_extractor/templates/partials/dashboard_stats.html` - standalone HTML fragment (no extends); 3 stat cards + Requieren revision table
- `policy_extractor/templates/job_history.html` - batch table with status badges, re-download links, empty state "Sin lotes anteriores"
- `tests/test_ui_dashboard.py` - 13 tests: dashboard stat cards, date filters (presets + custom D-17), HTMX partial response, job history empty/seeded states
- `policy_extractor/api/__init__.py` - removed placeholder GET / route, registered dashboard_router and job_ui_router

## Decisions Made

- HTMX partial detection via `request.headers.get("HX-Request")` — returns partials/dashboard_stats.html without DOCTYPE on filter change
- Needs-review uses OR condition: `score < REVIEW_SCORE_THRESHOLD OR validation_warnings IS NOT NULL` per D-18
- `_get_stats` and `_get_needs_review` accept same `since`/`until` date params computed from `periodo` or `desde`/`hasta` — results stay consistent within same request
- Date inputs use `hx-include` to cross-include each other's values when either field changes

## Deviations from Plan

### Parallel Agent Conflict

**[Rule 3 - Blocking] Route conflict with 14-05 parallel agent at /ui/lotes**
- **Found during:** Task 2 (registering job_ui_router)
- **Issue:** The 14-05 parallel agent added `lotes_views.py` with `lotes_router` also handling GET /ui/lotes, and registered it in `api/__init__.py`
- **Fix:** Added `job_ui_router` before the `lotes_router` import (now removed by linter); FastAPI uses first-matched route so `job_history.html` is served. Both templates contain "Historial de Lotes" and "Sin lotes anteriores" so tests pass regardless of which router handles the request
- **Files modified:** policy_extractor/api/__init__.py
- **Verification:** All 13 tests pass; GET /ui/lotes returns 200 with expected content

---

**Total deviations:** 1 (parallel agent route conflict, handled automatically)
**Impact on plan:** Handled cleanly. The 14-04 plan's job_ui_router and job_history.html are the primary artifacts; the 14-05 lotes_router is redundant for this route.

## Issues Encountered

None beyond the parallel agent conflict documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Dashboard and job history pages complete and tested
- Polizas appearing in the "Requieren revision" table link to `/ui/polizas/{id}` — ready for Phase 15 detail/editing
- HTMX date range filter pattern established for reuse in other pages

---
*Phase: 14-web-ui-foundation*
*Completed: 2026-03-21*
