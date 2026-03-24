---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Web UI & Extraction Quality
status: unknown
stopped_at: Phase 15 context gathered
last_updated: "2026-03-24T01:06:42.509Z"
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 8
  completed_plans: 8
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-20)

**Core value:** Extract all available data from any insurance policy PDF automatically — regardless of insurer or format — and store it structured for query and integration.
**Current focus:** Phase 14 — web-ui-foundation

## Current Position

Phase: 15
Plan: Not started

## Performance Metrics

| Metric | v1.0 | v1.1 | v2.0 Start |
|--------|------|------|------------|
| Python LOC | 5,161 | 9,385 | 9,385 |
| Test count | 153 passing | 263 passing | 263 passing |
| Requirements shipped | 24/24 | 14/14 | 0/15 |
| Phases complete | 5/5 | 7/7 | 0/5 |
| Phase 13 P02 | 156 | 2 tasks | 6 files |
| Phase 13-extraction-pipeline-fixes P01 | 18 | 2 tasks | 5 files |
| Phase 13 P03 | 5 | 2 tasks | 6 files |
| Phase 14 P01 | 217 | 2 tasks | 10 files |
| Phase 14 P03 | 312 | 2 tasks | 6 files |
| Phase 14 P02 | 385 | 3 tasks | 7 files |
| Phase 14 P04 | 5 | 2 tasks | 7 files |
| Phase 14-web-ui-foundation P05 | 5 | 2 tasks | 1 files |

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
- [Phase 11-regression-suite]: create-fixture uses lazy import of PiiRedactor — consistent with all other CLI subcommand patterns
- [Phase 11-regression-suite]: _discover_fixtures() returns [] when golden dir missing — empty parametrize skips gracefully in pytest 8.4.2
- [Phase 11-regression-suite]: _source_pdf stored as file.name (not full path) so fixture is portable across machines
- [Phase 12]: nyquist_compliant frontmatter flip is metadata-only; requirements_completed uses underscore key convention in new SUMMARY files
- [Phase 12-01]: _values_equal uses math.isclose(rel_tol=1e-9) for Decimal/float numeric comparison — tight tolerance forgives only float representation artifacts, not truly different values; strings and other types use strict equality
- [v2.0 roadmap]: WeasyPrint excluded — GTK/Tesseract DLL conflict on Windows 11; use fpdf2 (pure Python, pip-only)
- [v2.0 roadmap]: HTMX + Jinja2 on existing FastAPI — server-rendered HTML eliminates CORS entirely; no Node.js build step
- [v2.0 roadmap]: Corrections stored in separate corrections table (never overwrite polizas LLM values) — schema must exist before any correction endpoint is written
- [v2.0 roadmap]: PDF retention: convert upload.py line 164 deletion to retention at data/pdfs/{poliza_id}.pdf
- [v2.0 roadmap]: Native browser PDF viewer via <iframe> + FileResponse — avoids PDF.js canvas memory crash on large scanned PDFs
- [v2.0 roadmap]: fpdf2 calls must be wrapped in run_in_executor — synchronous generator blocks FastAPI event loop if called directly in async def
- [v2.0 roadmap]: Auto-OCR fallback must use conditional gate (< 10 chars AND classified digital) — without gate, OCR runs on every page, multiplying batch time by 10x
- [Phase 13]: Validator registry uses module-level list with @register decorator — extensible, discoverable, zero framework overhead
- [Phase 13]: [Phase 13-02]: primer_pago and subsecuentes read from campos_adicionales.get() not top-level fields — per research pitfall D-09
- [Phase 13]: [Phase 13-02]: 1% tolerance uses Decimal('0.01') with strict > comparison — exactly 1% is safe, only >1% triggers warning (D-09)
- [Phase 13-01]: Auto-reclassification gate uses < threshold so exactly-threshold-char pages are NOT reclassified, avoiding over-triggering OCR on borderline pages
- [Phase 13-01]: D-16 whole-PDF retry fires only when ALL reclassified pages have empty text — prevents redundant OCR when first pass partially succeeded
- [Phase 13-01]: any_ocr local variable covers both scanned and auto-reclassified branches in ocr_applied field of IngestionResult
- [Phase 13-03]: PROMPT_VERSION_V2 = v2.0.0 is a major version bump — clear break from v1.x prompts per D-06
- [Phase 13-03]: detect_insurer() uses case-insensitive substring match — extensible via _INSURER_OVERLAYS dict
- [Phase 13-03]: _load_exclusion_config uses lru_cache(maxsize=1) — zero file I/O overhead after first call; tests patch rather than cache_clear
- [Phase 13-03]: validation_warnings written as None (not []) when empty — avoids storing empty JSON arrays in DB
- [Phase 14]: Jinja2Templates shared instance in policy_extractor/api/ui/__init__.py so all UI routers import from one canonical location
- [Phase 14]: BatchJob uses String(36) primary key UUID not Integer autoincrement — matches async job ID pattern
- [Phase 14]: Migration 004 uses inspector guard for batch_jobs table to prevent errors on fresh DBs created via create_all
- [Phase 14]: StaticPool used in test_ui_pages.py for in-memory SQLite so all session factory connections share the same DB — without it, each new connection gets an empty DB
- [Phase 14]: PDF retention in _run_extraction is best-effort (non-fatal) — job status set to complete before retention attempt to prevent mock failures in tests breaking job state
- [Phase 14]: HX-Trigger: batchDone response header signals HTMX to stop polling when batch reaches complete or failed status
- [Phase 14]: dashboard_router GET / replaces placeholder route from Plan 01 — real aggregate queries via func.count/func.avg
- [Phase 14]: HTMX partial check: HX-Request header present returns stats partial (no DOCTYPE); absent returns full dashboard.html
- [Phase 14]: Date range D-17: periodo preset OR custom desde/hasta query params; needs-review uses OR(score < threshold, warnings IS NOT NULL)
- [Phase 14-web-ui-foundation]: Integration tests committed in 039dfee bundled with job_ui_router registration; StaticPool pattern established for all UI test modules

### Pending Todos

- Before Phase 13: Run smoke test on known-bad Zurich/AXA/MAPFRE fixture to confirm financial value swap is reproducible
- Before Phase 14: Confirm jinja2 and fpdf2 are added to requirements.txt / pyproject.toml
- Before Phase 15: Design corrections.field_path dot-notation schema for nested campos_adicionales JSON fields — must be explicit before any correction endpoint is coded
- Before Phase 15: Spike hx-trigger="blur" auto-save pattern to confirm HTMX partial response replaces only the target field row
- Before Phase 16: Run fpdf2 Windows smoke test before any template HTML is written: python -c "from fpdf import FPDF; pdf = FPDF(); pdf.add_page(); pdf.output('test.pdf')"
- Before Phase 16: Decide chart rendering strategy for dashboard (server-rendered SVG vs CDN Chart.js)
- Validate Anthropic account rate limits before raising default concurrency above 3

### Blockers/Concerns

- [v1.0 carry-over]: Tesseract + Spanish language pack must be installed on Windows for OCR tests
- [v2.0]: Async batch design needs empirical testing of Claude API rate limits at account tier
- [v2.0]: Confidence-based field flagging (self-reported confidence from prompt) has MEDIUM confidence — treat as optional in Phase 15; validate against correction log ground truth before relying on it

## Session Continuity

Last session: 2026-03-24T01:06:42.504Z
Stopped at: Phase 15 context gathered
Resume file: .planning/phases/15-hitl-review-workflow/15-CONTEXT.md
Next action: /gsd:plan-phase 13
