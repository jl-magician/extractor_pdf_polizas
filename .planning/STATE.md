---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Completed 11-01-PLAN.md
last_updated: "2026-03-19T22:17:21.784Z"
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 12
  completed_plans: 11
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-18)

**Core value:** Extract all available data from any insurance policy PDF automatically — regardless of insurer or format — and store it structured for query and integration.
**Current focus:** Phase 11 — regression-suite

## Current Position

Phase: 11 (regression-suite) — EXECUTING
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
| Phase 07-export P02 | 18m | 2 tasks | 2 files |
| Phase 08-pdf-upload-api P01 | 4m | 2 tasks | 4 files |
| Phase 08-pdf-upload-api P02 | 3min | 1 tasks | 2 files |
| Phase 09-async-batch P01 | 10m | 2 tasks | 5 files |
| Phase 09-async-batch P02 | 3m | 2 tasks | 2 files |
| Phase 10-quality-evaluator P01 | 4min | 1 tasks | 3 files |
| Phase 10 P02 | 4m 22s | 2 tasks | 4 files |
| Phase 11 P01 | 196s | 2 tasks | 7 files |

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
- [Phase 07-02]: ExportFormat enum at module level (not inside function) — importable and testable externally
- [Phase 07-02]: Spanish flags merged with English compat flags using "or" — Spanish takes precedence
- [Phase 07-02]: export_xlsx/export_csv lazy-imported inside fmt branches — avoids openpyxl import on JSON-only usage
- [Phase 07-02]: --output required check before DB query — fast fail without unnecessary I/O
- [Phase 08-pdf-upload-api]: Scoped override_db fixture in test_upload.py saves/restores app.dependency_overrides[get_db] to prevent contaminating test_api.py tests sharing the same app singleton
- [Phase 08-pdf-upload-api]: Lazy expiry purge on read (_get_job/_list_jobs) avoids background cleanup thread complexity for single-user local tool
- [Phase 08-pdf-upload-api]: Patch targets for lazy-import _run_extraction must be source module paths (e.g. policy_extractor.storage.database.SessionLocal), not upload module paths
- [Phase 08-pdf-upload-api]: Tests call _run_extraction directly and synchronously -- no thread spawning needed, isolates pipeline logic from HTTP layer
- [Phase 09-01]: Rate limit retry placed INSIDE extract_with_retry wrapping call_extraction_api to prevent broad except Exception swallowing transient errors before retry
- [Phase 09-01]: extract_with_retry returns 4-tuple (policy, raw_response, usage, rl_retries); extract_policy returns 3-tuple threading count to CLI callers
- [Phase 09-async-batch]: ThreadPoolExecutor with concurrency==1 bypass: sequential path skips thread pool entirely
- [Phase 09-async-batch]: Per-worker SessionLocal(): each _process_single_pdf() creates and closes its own session
- [Phase 09-async-batch]: threading.Lock guards counter aggregation in as_completed loop for thread-safe totals
- [Phase 10-quality-evaluator]: EVAL_MODEL_ID hardcoded to claude-sonnet-4-5-20250514 — no settings override, opt-in only
- [Phase 10-quality-evaluator]: evaluate_policy() returns None on any Exception — never raises — batch callers rely on this contract
- [Phase 10-quality-evaluator]: evaluation_json stored as TEXT string via json.dumps (not JSON column); score = (completeness + accuracy + (1-hallucination_risk)) / 3
- [Phase 10]: evaluate_policy lazy-imported inside if evaluate: branch in all three entry points — zero Sonnet overhead unless opt-in
- [Phase 10]: evaluation_score/evaluation_json always present in API result dict (None when not evaluated) — consistent shape for API callers
- [Phase 11-01]: PII_FIELDS as frozenset — explicit hardcoded list preferred over pattern matching; auditable and zero false positives on domain field names
- [Phase 11-01]: FieldDiffer operates on plain dicts (model_dump output) — decoupled from Pydantic models, testable with simple fixtures
- [Phase 11-01]: addopts = "-m 'not regression'" with inner single quotes — required for correct marker expression parsing on Windows/shlex

### Pending Todos

- Before Phase 6: Run `alembic stamp head` on existing polizas.db immediately after Alembic install
- Before Phase 11: Audit pdfs-to-test/ directory for PII before committing any fixture PDFs
- Validate Anthropic account rate limits before raising default concurrency above 3

### Blockers/Concerns

- [v1.0 carry-over]: Tesseract + Spanish language pack must be installed on Windows for OCR tests
- Async batch design needs empirical testing of Claude API rate limits at account tier
- WAL mode migration on existing polizas.db: RESOLVED — get_engine() now sets WAL on every connection

## Session Continuity

Last session: 2026-03-19T22:17:21.780Z
Stopped at: Completed 11-01-PLAN.md
Resume file: None
Next action: `/gsd:execute-phase` for next phase (08+)
