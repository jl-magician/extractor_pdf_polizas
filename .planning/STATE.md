---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Phase 07-export Plan 01 complete
last_updated: "2026-03-19T17:05:00.000Z"
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 4
  completed_plans: 3
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-18)

**Core value:** Extract all available data from any insurance policy PDF automatically — regardless of insurer or format — and store it structured for query and integration.
**Current focus:** Phase 07 — export

## Current Position

Phase: 07 (export) — EXECUTING
Plan: 2 of 2

## Performance Metrics

| Metric | v1.0 | v1.1 Current |
|--------|------|--------------|
| Python LOC | 5,161 | 5,161 (start) |
| Test count | 153 passing | 153 passing (start) |
| Requirements shipped | 24/24 | 0/28 |
| Phases complete | 5/5 | 0/6 |
| Phase 06-migrations P01 | — | 2 tasks | 8 files |
| Phase 06-migrations P02 | 2m | 2 tasks | 2 files |
| Phase 07-export P01 | 12m | 1 task (TDD) | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v1.0]: Claude API chosen for extraction — user has existing API key; handles 50-70 formats without templates
- [v1.0]: Single-pass extraction — one API call per PDF, no templates
- [v1.0]: Haiku default, Sonnet configurable via --model flag
- [v1.0]: Upsert by (numero_poliza, aseguradora) for dedup
- [v1.0]: Spanish domain terms in field names — agency team reads JSON/DB directly
- [v1.0]: Per-page PDF classification with image coverage ratio
- [v1.1]: Split deferred features into v1.1 (backend/API/quality) and v2.0 (web UI/reports)
- [v1.1]: Alembic with render_as_batch=True required for SQLite ALTER TABLE support
- [v1.1]: Sonnet evaluator is opt-in only (--evaluate flag) — never in default extraction path
- [v1.1]: In-memory job_store for upload API (acceptable for single-user local use; lost on restart)
- [v1.1]: asyncio.Semaphore(3) as default concurrency — safe default pending account rate limit validation
- [v1.1]: openpyxl for Excel export (not pandas — avoids 30 MB binary dep for a 50-line operation)
- [Phase 06-01]: env.py URL isolation: only apply settings.DB_PATH fallback when alembic.ini has placeholder URL
- [Phase 06-01]: Baseline migration 001 uses separate engine for create_all due to SQLAlchemy 2.0 autobegin transaction isolation
- [Phase 06-01]: Migration 002 guards add_column with inspector check to prevent duplicate column error on fresh DBs
- [Phase 06-02]: _get_alembic_cfg resolves alembic.ini via Path(__file__).parent.parent.parent to work from any CWD
- [Phase 06-02]: Lazy alembic imports inside functions avoid overhead when migration not needed
- [Phase 06-02]: Backup created only when current_rev != head_rev to avoid unnecessary I/O on up-to-date DBs
- [Phase 07-01]: openpyxl lazy-imported inside export_xlsx body — keeps import cost out of CLI startup path
- [Phase 07-01]: number_format applied per-cell after ws.append() — column-level format before append has no effect in openpyxl 3.x
- [Phase 07-01]: Decimal-to-float coercion via _cell_value() helper — openpyxl writes Decimal as string otherwise
- [Phase 07-01]: auto_filter.ref only set when ws.max_row > 1 — ws.dimensions returns "A1:A1" on empty sheets

### Pending Todos

- Before Phase 6: Run `alembic stamp head` on existing polizas.db immediately after Alembic install
- Before Phase 11: Audit pdfs-to-test/ directory for PII before committing any fixture PDFs
- Validate Anthropic account rate limits before raising default concurrency above 3

### Blockers/Concerns

- [v1.0 carry-over]: Tesseract + Spanish language pack must be installed on Windows for OCR tests
- Async batch design needs empirical testing of Claude API rate limits at account tier
- WAL mode migration on existing polizas.db: RESOLVED — get_engine() now sets WAL on every connection

## Session Continuity

Last session: 2026-03-19T17:05:00.000Z
Stopped at: Completed 07-export-01-PLAN.md
Resume file: .planning/phases/07-export/07-02-PLAN.md
Next action: `/gsd:execute-phase` for 07-02 (CLI wiring)
