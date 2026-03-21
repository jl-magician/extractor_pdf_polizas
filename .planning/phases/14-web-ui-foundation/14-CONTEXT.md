# Phase 14: Web UI Foundation - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Read-only browser interface for the agency team: upload PDFs in batches, monitor extraction progress, browse and filter polizas, view detail pages, export data, and see a health dashboard. No inline editing, no corrections table, no PDF reports. Those are Phase 15 and 16.

</domain>

<decisions>
## Implementation Decisions

### Upload experience
- **D-01:** Upload supports multiple files at once — user loads all PDFs first, then submits the batch. No additional PDFs can be added while a batch is processing
- **D-02:** Both drag-and-drop and file picker supported for selecting PDFs
- **D-03:** While batch processes, show an overall progress bar (not per-file progress)
- **D-04:** When all PDFs in batch finish, show a summary table (one row per PDF: status, poliza number, aseguradora) with option to click into each detail
- **D-05:** Batch results are exportable in all supported formats (JSON, Excel, CSV) directly from the results screen
- **D-06:** If a file in the batch fails, continue processing remaining files — show failures in the summary at the end

### Job history
- **D-07:** Job history persists across server restarts (stored in database, not in-memory)
- **D-08:** User can name a batch job for easy identification
- **D-09:** Job history page shows past batches with option to re-download results

### Poliza list & filtering
- **D-10:** Default visible columns: numero_poliza, aseguradora, tipo_seguro, nombre_contratante, evaluation_score
- **D-11:** List summary bar shows: total PDFs processed, total warnings, count of low-score records needing review
- **D-12:** Collapsible filter panel (not always visible, toggleable)
- **D-13:** Free-text search across multiple fields (poliza number, contratante name, aseguradora)
- **D-14:** "Load more" pagination (not page numbers)

### Dashboard
- **D-15:** Dashboard is the landing page (default view when user opens the app)
- **D-16:** Quick health overview: total polizas, warning count, average evaluation score
- **D-17:** Date range selector (last 7 days, last 30 days, custom range)
- **D-18:** "Records needing review" shows polizas with evaluation_score below threshold OR any validation_warnings — both criteria

### Page structure & navigation
- **D-19:** Sidebar navigation (always visible on the left, like Linear/Notion)
- **D-20:** Five pages: Dashboard (landing), Upload (batch workflow), Poliza List, Poliza Detail, Job History
- **D-21:** Tailwind CSS via CDN — utility classes, no build step needed
- **D-22:** UI language: Spanish (matching domain terms and field names)

### Tech stack (locked from prior decisions)
- **D-23:** HTMX + Jinja2 on existing FastAPI — server-rendered HTML, no Node.js, no CORS
- **D-24:** Native browser PDF viewer via `<iframe>` + FileResponse (no PDF.js)
- **D-25:** PDF retention at `data/pdfs/{poliza_id}.pdf` — convert current post-extraction deletion in upload.py to retention

### Claude's Discretion
- Sidebar visual design (icons, colors, collapsed/expanded behavior)
- Tailwind component patterns (card styles, table styling, progress bar implementation)
- Dashboard health metric card layout and styling
- Free-text search implementation (client-side filtering vs server query)
- "Load more" batch size and scroll behavior
- Evaluation score threshold for "needs review" (suggest sensible default)
- Job history table columns and sort order
- Batch naming: auto-generated default name vs required user input
- HTMX polling interval for batch progress updates
- Error/empty state messaging and illustrations

</decisions>

<specifics>
## Specific Ideas

- Batch workflow is submit-all-then-wait, not upload-one-at-a-time — mirrors how the agency processes batches of policies monthly
- Job history with naming supports the agency's workflow of processing batches per aseguradora or per month ("Zurich Marzo 2026")
- Summary bar on poliza list acts as a quick triage tool — "how many need my attention?"
- Dashboard as landing page gives an at-a-glance health check before diving into specific records

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing API (routes to extend or serve HTML alongside)
- `policy_extractor/api/__init__.py` — FastAPI app instance, CRUD routes for polizas (GET /polizas with filters, GET /polizas/{id})
- `policy_extractor/api/upload.py` — Upload router, in-memory job store (must migrate to DB), background extraction thread

### Database models (for new job history table and dashboard queries)
- `policy_extractor/storage/models.py` — Poliza, Asegurado, Cobertura ORM models; validation_warnings JSON column
- `policy_extractor/storage/database.py` — Engine creation, init_db with Alembic auto-migration
- `policy_extractor/storage/writer.py` — upsert_policy, orm_to_schema conversion

### Export (reuse from batch results download)
- `policy_extractor/export.py` — export_xlsx, export_csv functions; ExportFormat enum

### Schemas (for template rendering data contracts)
- `policy_extractor/schemas/poliza.py` — PolicyExtraction with all fields, validation_warnings, campos_adicionales
- `policy_extractor/schemas/asegurado.py` — AseguradoExtraction
- `policy_extractor/schemas/cobertura.py` — CoberturaExtraction

### Configuration
- `policy_extractor/config.py` — Settings class (DB_PATH, model settings)
- `pyproject.toml` — Dependencies list (jinja2 and htmx not yet added)

### Prior phase context
- `.planning/phases/13-extraction-pipeline-fixes/13-CONTEXT.md` — Validation warnings schema, field exclusion, prompt versioning

### Research & pitfalls
- `.planning/research/PITFALLS.md` — Known pitfalls including auto-OCR threshold gate
- `.planning/STATE.md` §Pending Todos — "Before Phase 14: Confirm jinja2 and fpdf2 are added to requirements.txt / pyproject.toml"

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **FastAPI app** (`api/__init__.py`): Full CRUD + query filters already implemented — add Jinja2 template responses alongside JSON
- **Upload router** (`api/upload.py`): Job lifecycle (pending→processing→complete→failed) — extend with DB persistence and batch support
- **Export functions** (`export.py`): export_xlsx/export_csv — wire to download endpoints from batch results and detail page
- **CLI serve command** (`cli.py`): Already starts uvicorn — add static files mount and template directory
- **Database init** (`storage/database.py`): Alembic auto-migration — use for job history table migration

### Established Patterns
- Lazy imports inside function bodies (follow for jinja2, htmx dependencies)
- Pydantic BaseSettings for configuration
- Alembic render_as_batch=True for SQLite migrations
- Inspector guards on add_column for migration safety
- `model_dump(mode="json")` for template context serialization
- Dependency injection via `get_db()` for session management

### Integration Points
- `api/__init__.py` — Mount Jinja2Templates, StaticFiles; add HTML-returning routes
- `api/upload.py` line ~164 — Convert PDF deletion to retention at `data/pdfs/{poliza_id}.pdf`
- `storage/models.py` — Add BatchJob model for persistent job history
- `alembic/versions/` — New migration for batch_jobs table
- `pyproject.toml` — Add jinja2, python-multipart (already present), fpdf2 dependencies

</code_context>

<deferred>
## Deferred Ideas

- Inline field editing and corrections audit trail — Phase 15
- Side-by-side PDF + extraction review view — Phase 15
- PDF report generation with per-insurer templates — Phase 16
- Auto-triggered Sonnet evaluation on batch samples — Phase 16
- WebSocket/SSE for real-time progress (polling is sufficient for single-user) — Out of Scope per REQUIREMENTS.md
- Authentication/user management — Out of Scope per REQUIREMENTS.md

</deferred>

---

*Phase: 14-web-ui-foundation*
*Context gathered: 2026-03-20*
