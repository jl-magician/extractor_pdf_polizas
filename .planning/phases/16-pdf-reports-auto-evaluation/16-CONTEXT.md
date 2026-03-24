# Phase 16: PDF Reports & Auto-Evaluation - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can download a formatted PDF summary for any poliza, and Sonnet quality evaluation runs automatically on a sample of each batch. This phase delivers:
- PDF report generation via WeasyPrint (HTML->PDF) with per-insurer templates
- A "Descargar Reporte" button on detail and review pages
- Auto-triggered Sonnet evaluation on batch extractions (10+ polizas)
- Extended evaluation prompt for campos_adicionales swap detection with suggested corrections

</domain>

<decisions>
## Implementation Decisions

### PDF Generation Approach
- **D-01:** Use WeasyPrint for PDF generation — renders Jinja2 HTML templates to PDF, reusing existing template skills. CSS-styled, professional output.
- **D-02:** Generate PDFs on-the-fly per request (no disk caching). Always reflects latest corrected data. Must complete under 5 seconds (SC-1).
- **D-03:** "Descargar Reporte" button appears on both the poliza detail page and the review page.
- **D-04:** Report uses corrected values from the polizas table (post-HITL corrections). No indicators for corrected vs original values.
- **D-05:** Paper size is Letter (8.5x11 inches) — standard for Mexican business documents.
- **D-06:** Filename format: `poliza_{numero_poliza}_{aseguradora}.pdf` — e.g., `poliza_12345_zurich.pdf`.

### Report Content & Layout
- **D-07:** Report sections (in order): header with insurer branding, general info block, financial summary, asegurados table, coverage table, campos_adicionales key-value list.
- **D-08:** Asegurados appear as a full table with nombre, parentesco, fecha_nacimiento, RFC.
- **D-09:** Campos_adicionales shown as a simple key: value list. Always included (even if section would be empty — show "Sin campos adicionales").
- **D-10:** Per-insurer differentiation via config files with brand_color, field_order, and section toggles. One base Jinja2 template handles all insurers.
- **D-11:** Per-insurer config files stored at `policy_extractor/reports/configs/` as YAML files (e.g., `zurich.yaml`, `axa.yaml`). Version-controlled inside the package.

### Auto-Evaluation Trigger
- **D-12:** Auto-evaluation triggers after any extraction (batch or single) when the total number of extractions in the recent window reaches >= 10. Default sample percentage: 20%.
- **D-13:** Sample percentage is configurable via settings (e.g., `EVAL_SAMPLE_PERCENT = 20`).
- **D-14:** Evaluation runs in the same thread as extraction, right after extraction completes. No separate background thread — adds ~3-5s per evaluated record.
- **D-15:** Evaluation scores surface in the web UI in two places: (a) colored score badge (green/yellow/red) on poliza list rows and detail page header, (b) aggregate stats (avg score, % evaluated) on the dashboard page.

### Campo Swap Detection
- **D-16:** Campo swap detection is integrated into the existing evaluation prompt — extended criteria, not a separate Sonnet pass. One API call covers quality scoring AND swap detection.
- **D-17:** Swap warnings are appended to the `validation_warnings` JSON array on the Poliza row — consistent with financial cross-validation warnings from Phase 13.
- **D-18:** Swap detection includes suggested corrections — warning text describes the suspected swap and recommends which field the value should move to. Human reviews and applies the fix via HITL.

### Claude's Discretion
- WeasyPrint installation and CSS print stylesheet design
- Exact color scheme per insurer (can use brand-standard colors)
- Evaluation sampling algorithm (random, stratified by insurer, etc.)
- Score badge color thresholds (e.g., green >= 0.8, yellow >= 0.6, red < 0.6)
- Dashboard aggregate stats layout and positioning
- Swap detection prompt engineering (how to instruct Sonnet to identify swaps)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Evaluation Module
- `policy_extractor/evaluation.py` — Full Sonnet evaluation pipeline: evaluate_policy(), EvaluationResult, EVAL_SYSTEM_PROMPT, build_evaluation_tool()
- `tests/test_evaluation.py` — Existing evaluation tests

### Upload & Batch Pipeline
- `policy_extractor/api/upload.py` — _run_extraction() and _run_batch_extraction() — where auto-evaluation hook goes
- `policy_extractor/cli.py` — CLI extract/batch commands with --evaluate flag

### Data Models
- `policy_extractor/storage/models.py` — Poliza model with evaluation_score, evaluation_json, evaluated_at, evaluated_model_id, validation_warnings columns
- `alembic/versions/002_evaluation_columns.py` — Migration that added evaluation columns

### Web UI Templates
- `policy_extractor/templates/poliza_detail.html` — Detail page where "Descargar Reporte" button goes
- `policy_extractor/templates/poliza_review.html` — Review page where "Descargar Reporte" button goes
- `policy_extractor/templates/poliza_list.html` — List page where score badges go
- `policy_extractor/templates/dashboard.html` — Dashboard where aggregate eval stats go
- `policy_extractor/api/ui/poliza_views.py` — Detail/list routes
- `policy_extractor/api/ui/dashboard_views.py` — Dashboard routes

### Export Patterns
- `policy_extractor/export.py` — Existing Excel/CSV export patterns (POLIZA_COLUMNS, formatting constants)

### Requirements
- `.planning/REQUIREMENTS.md` RPT-01 — PDF report generation
- `.planning/REQUIREMENTS.md` RPT-02 — Per-insurer report templates
- `.planning/REQUIREMENTS.md` QA-02 — Auto-triggered Sonnet evaluation on batch samples
- `.planning/REQUIREMENTS.md` QA-03 — Targeted Sonnet review for campos_adicionales field swaps

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `evaluation.py:evaluate_policy()` — Complete evaluation pipeline, just needs prompt extension for swap detection and auto-trigger wiring
- `evaluation.py:build_evaluation_tool()` — Tool schema for Sonnet, needs campos_swap_suggestions field added
- `evaluation.py:EVAL_SYSTEM_PROMPT` — Base prompt to extend with swap detection criteria
- Jinja2 template infrastructure — all templates extend `base.html`, HTMX + Tailwind patterns
- `export.py:POLIZA_COLUMNS` — Field list for report content reference
- `poliza_detail.html` — Field groups (General, Vigencia, Financiero, etc.) to mirror in PDF report

### Established Patterns
- Jinja2 templates extending `base.html` with `{% block content %}`
- HTMX for partial page updates
- FastAPI APIRouter per feature area registered in `__init__.py`
- SQLAlchemy 2.0 with `select()` + `selectinload()` for eager loading
- Alembic migrations with `render_as_batch=True` for SQLite
- Settings via `policy_extractor/config.py` — add EVAL_SAMPLE_PERCENT here

### Integration Points
- New `policy_extractor/reports/` module with WeasyPrint rendering, base template, per-insurer configs
- New route in `poliza_views.py` for PDF download (e.g., `/ui/polizas/{id}/report`)
- "Descargar Reporte" button added to `poliza_detail.html` and `poliza_review.html`
- Auto-evaluation hook wired into `_run_extraction()` and `_run_batch_extraction()` in upload.py
- Score badge partial added to `poliza_list.html` rows
- Aggregate eval stats added to `dashboard_views.py` and `dashboard.html`
- Extended EVAL_SYSTEM_PROMPT with swap detection instructions
- `build_evaluation_tool()` schema extended with swap suggestions output

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-pdf-reports-auto-evaluation*
*Context gathered: 2026-03-23*
