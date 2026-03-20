# Project Research Summary

**Project:** extractor_pdf_polizas v2.0 — Web UI, PDF Reports, Extraction Quality, Human Review
**Domain:** Insurance policy PDF extraction — human-in-the-loop document processing
**Researched:** 2026-03-20
**Confidence:** HIGH

## Executive Summary

This project extends a fully operational v1.1 CLI/API insurance policy extractor (FastAPI + SQLite + Claude Haiku + OCR pipeline) with three interrelated capabilities: a browser-based web UI for daily agency use, human-in-the-loop (HITL) field correction with an audit trail, and extraction quality improvements targeting documented systematic errors. Research confirms a clear, conservative architectural path: add Jinja2 templates and HTMX directly onto the existing FastAPI app (no SPA framework, no build pipeline), use fpdf2 for PDF report generation (pure Python, no system dependencies on Windows 11), and fix two confirmed extraction bugs (auto-OCR fallback threshold, ocrmypdf argument error) before building any UI — otherwise the UI corrects systematic failures that should not exist.

The highest-risk decision is the PDF report generation library. WeasyPrint is the intuitive choice but has documented Windows 11 installation failures involving GTK DLLs, PATH ordering conflicts with the existing Tesseract install, and Windows Defender false positives. Research unambiguously recommends fpdf2 as the alternative: pure Python, pip-installable, zero native dependencies. The HTMX + Jinja2 front-end stack eliminates the CORS problem entirely (server-rendered HTML from the same FastAPI process), simplifies deployment to a single `uvicorn` process, and avoids a Node.js build pipeline for a local single-user tool.

The human review correction system carries an architectural trap that must be addressed before implementation: saving corrections directly to the `polizas` table overwrites the original LLM-extracted values, permanently destroying the data needed for quality analytics, prompt improvement, and golden dataset growth. The `corrections` audit table must be designed and migrated before any correction endpoint is written. Financial cross-field validation (the most common error class in real extraction data) must similarly be built before the HITL UI, so the UI surfaces pre-computed warnings rather than expecting reviewers to detect value swaps manually.

---

## Key Findings

### Recommended Stack

The v2.0 additions require only two new pip dependencies: `jinja2>=3.1.6` (HTML templates) and `fpdf2>=2.8.3` (PDF reports). All other new capabilities — extraction validation, correction storage, quality evaluator extensions — use the existing stack. Frontend assets (HTMX 2.0.4, Alpine.js 3.x, Tailwind CSS 4.x) are loaded from CDN with no build step, and PDF.js is downloaded as a prebuilt zip and copied into `static/pdfjs/`.

**Core technologies:**
- `jinja2>=3.1.6`: HTML template rendering — FastAPI's `Jinja2Templates` uses this directly; enables server-rendered pages and HTMX partial fragments without a JS framework
- `fpdf2>=2.8.3`: PDF report generation — pure Python, pip-only install, Windows-safe; per-insurer Jinja2-rendered HTML strings feed into `write_html()`
- HTMX 2.0.4 (CDN): partial page updates — converts FastAPI endpoints to HTML fragment endpoints with no architectural change; handles upload progress, live table updates, inline field saves
- Alpine.js 3.x (CDN): client-side micro-state — toggle edit mode per field, confirm dialogs; pairs with HTMX (HTMX owns server roundtrips, Alpine.js owns local in-page state)
- PDF.js 5.5.207 (self-hosted static): in-browser PDF rendering for the review UI — embedded as `<iframe>` pointing to the prebuilt viewer; handles both digital and scanned PDFs
- Pydantic `@model_validator(mode='after')`: cross-field financial validation — no new library; warns on value swaps between prima_total/primer_pago/subsecuentes/financiamiento

**What NOT to add:**
- WeasyPrint: MSYS2 + GTK + Tesseract DLL conflict on Windows 11 — use fpdf2 instead
- React/Vue/Svelte: requires Node.js, build pipeline, CORS setup — unnecessary for a local single-user tool
- Celery/Redis: already ruled out in v1.1; 200 polizas/month does not justify a queue system

See `.planning/research/STACK.md` for complete rationale and version compatibility table.

### Expected Features

**Must have (table stakes) — v2.0 in scope:**
- Web UI: PDF upload (drag-and-drop), polizas list, single-poliza detail view — replaces CLI for non-technical users
- Inline field editing + PATCH endpoint — primary daily correction workflow
- Side-by-side PDF viewer + extraction editor — core HITL pattern; prevents tab-switching
- Extraction job status display with polling — upload is async (202 + job_id)
- Auto-OCR fallback for zero-text pages — fixes error #9 (silent all-null extraction on digital PDFs with vector-path text)
- OCR call bug fix for scanned PDFs with spaces/special chars — fixes error #10 (entire PDF silently fails)
- Financial field cross-validation — most common error class; value swaps between primer_pago/subsecuentes/financiamiento
- Export from UI — replaces CLI export workflow

**Should have (differentiators) — v2.0 if time allows:**
- Confidence-based field flagging — reduces review time by 60-80%; requires prompt engineering to self-report field confidence; MEDIUM confidence finding (needs empirical validation)
- Correction storage + feedback loop — `field_corrections` table enables quality analytics and golden dataset growth
- PDF report generation per insurer — Jinja2 HTML templates + fpdf2 renderer; one template per aseguradora
- Dashboard with extraction metrics — volume by insurer, most-corrected fields, error rate over time
- Field exclusion list (configurable) — blocks `agencia_responsable`-type fields from extraction output

**Defer to v3.0:**
- Policy comparison / coverage gap analysis
- Automated golden dataset expansion from production
- Authentication / multi-user (only if deployment model changes)
- Mobile responsive layout

See `.planning/research/FEATURES.md` for full dependency graph and complexity estimates.

### Architecture Approach

v2.0 adds a Jinja2/HTMX server-rendered frontend directly onto the existing FastAPI app (same process, same port, no CORS), extends the SQLAlchemy models with a `corrections` table and two new columns on `polizas` (`source_pdf_path`, `validation_warnings`), retains uploaded PDFs to `data/pdfs/{poliza_id}.pdf` instead of deleting them after extraction, and adds a `reports/` module for fpdf2-based PDF generation. The critical change in existing code is `upload.py` line 164, which currently deletes the PDF on extraction success — this must be converted to a retention step.

**Major components:**
1. `api/web.py` (new): HTML-returning routes for dashboard, poliza list, detail, and review pages via `Jinja2Templates`
2. `api/reports.py` (new): streams fpdf2-generated PDF bytes; wraps synchronous render in `run_in_executor` to avoid blocking the event loop
3. `api/pdf_proxy.py` (new): serves retained source PDF from `data/pdfs/` as `FileResponse` for the browser's native PDF viewer (`<iframe>`)
4. `api/corrections.py` (new): `PATCH /polizas/{id}` writes to `corrections` table (never overwrites `polizas` fields directly); `GET /polizas/{id}/corrections` returns audit history
5. `storage/models.py` (extended): adds `Correction` ORM model; adds `source_pdf_path`, `validation_warnings`, `has_corrections` columns to `Poliza`
6. `extraction/verification.py` (extended): adds `validate_financial_fields()` with cross-field invariant checks based on known error patterns from real Zurich/AXA/MAPFRE extractions
7. `reports/renderer.py` (new): fpdf2 report generator with per-insurer template dispatch
8. Alembic migration `003_v2_schema.py` (new): `corrections` table + new poliza columns

See `.planning/research/ARCHITECTURE.md` for file layout, route patterns, ORM schemas, and integration gotchas.

### Critical Pitfalls

1. **WeasyPrint GTK/Tesseract DLL conflict on Windows 11** — Use fpdf2 instead. WeasyPrint appears to install successfully but raises `OSError: cairo` at runtime on Windows 11. The project's existing Tesseract install adds a DLL shadowing conflict not commonly documented. Never start template code before a Windows validation smoke test passes. (Pitfall v2-1)

2. **Corrections overwriting LLM-extracted values** — Design the `corrections` table before writing any correction endpoint. The natural PATCH implementation updates `polizas` in place and permanently loses original values. Retrofitting after corrections have been saved loses all pre-migration history with no recovery path. (Pitfall v2-5)

3. **Auto-OCR fallback triggering universally** — The per-page char-count gate (< 10 chars AND classified as digital) must be part of the initial implementation. Without it, OCR runs on every page; a 5-page digital policy goes from 3 seconds to 30+ seconds, multiplying batch time by 10x. (Pitfall v2-6)

4. **LLM field value swaps passing type-only validation** — Cross-field financial invariants must be implemented and tested against the known-bad Zurich fixture before building the review UI. A validation layer that only checks nulls and Pydantic types provides false confidence while the review UI needs pre-computed warnings. (Pitfall v2-4)

5. **Browser tab freeze on large scanned PDFs with PDF.js** — Use the browser's native PDF viewer via `<iframe src="/api/polizas/{id}/pdf-proxy">` with `FileResponse`. A 31-page scanned policy allocates 60-90 MB of canvas memory in PDF.js and crashes the tab. The native viewer handles lazy page rendering with zero extra code. (Pitfall v2-7)

6. **Synchronous PDF generation blocking the FastAPI event loop** — Wrap fpdf2 call in `asyncio.get_event_loop().run_in_executor(None, partial(build_pdf_for_poliza, id))`. Calling it directly in `async def` blocks all coroutines including UI polling. (Pitfall v2-9)

7. **Unsaved corrections lost on in-app navigation** — Implement auto-save on field blur (each field saves independently when the user leaves the input). React Router route transitions do not trigger `beforeunload`; use `useBlocker` hook as a safety net for any multi-field forms. (Pitfall v2-8)

See `.planning/research/PITFALLS.md` for full warning signs, phase assignments, and the technical debt, performance trap, and UX pitfall tables.

---

## Implications for Roadmap

Based on combined research, the phase structure is unambiguous: fix the extraction pipeline first (errors are systematic and UI corrections would be wasted), then build the read-only web UI (unblocks daily use), then add HITL correction (highest-value workflow), then reporting and analytics.

### Phase 1: Extraction Pipeline Fixes

**Rationale:** Two confirmed bugs (auto-OCR fallback missing, ocrmypdf argument error) cause silent failures on entire document classes. Financial value swaps are systematic and repeat across extractions of the same insurer format. Building any UI on top of these failures means human reviewers correct bugs that should not exist. Fix root causes first.

**Delivers:** All extractions attempt OCR when text is missing; scanned PDFs with spaces in filenames no longer silently fail; financial field swaps are auto-detected and flagged in `validation_warnings`; excluded fields never appear in output.

**Addresses:** Table stakes — auto-OCR fallback (error #9), OCR bug fix (error #10), financial cross-validation, field exclusion list

**Avoids:** Pitfall v2-4 (false confidence from type-only validation), Pitfall v2-6 (universal OCR trigger without conditional gate)

**Stack:** Pydantic `@model_validator(mode='after')`, PyMuPDF char-count threshold gate, ocrmypdf path quoting fix — no new libraries required

**Research flag:** Standard patterns — skip `/gsd:research-phase`

---

### Phase 2: Web UI Foundation (Read-Only)

**Rationale:** Replace CLI workflow with browser UI before adding correction capabilities. Read-only first (upload, list, detail, job status, export) validates the HTMX + Jinja2 integration and unblocks daily use without requiring the correction schema or audit table. CORS is eliminated entirely because templates are served from the same FastAPI process.

**Delivers:** Agency team uploads PDFs, views extraction results, monitors job progress, and exports data from a browser without CLI knowledge.

**Addresses:** Table stakes — upload UI, polizas list, detail view, job status polling, export button

**Avoids:** Pitfall v2-2 (CORS from React dev server) — no CORS needed with server-rendered HTML; Pitfall v2-3 (SQLite lock from concurrent polling) — job status reads from in-memory `job_store`, never SQLite

**Stack:** `jinja2` (pip), HTMX 2.0.4 (CDN), Alpine.js 3.x (CDN), Tailwind CSS 4.x (CDN Play); PDF.js prebuilt zip into `static/pdfjs/`

**Research flag:** Standard patterns — FastAPI + Jinja2Templates is documented first-class integration; skip `/gsd:research-phase`

---

### Phase 3: HITL Review Workflow

**Rationale:** Highest-value capability. Side-by-side PDF viewing + field editing + correction audit log turns the tool from a batch processor into a quality-controlled extraction system. The `corrections` table schema must be the first task — retrofitting it loses all pre-migration correction data permanently.

**Delivers:** Reviewers see source PDF and extracted fields side by side; corrections are saved with full audit trail; correction frequency data is available for prompt improvement; reviewed polizas can become golden dataset fixtures.

**Addresses:** Table stakes — inline field editing, side-by-side review; differentiators — correction storage + feedback loop, confidence-based field flagging (if time allows)

**Avoids:** Pitfall v2-5 (corrections overwriting LLM values — `corrections` table before any endpoint); Pitfall v2-7 (PDF.js browser freeze — native viewer via `<iframe>` + `FileResponse`); Pitfall v2-8 (unsaved edits lost — auto-save on blur + `useBlocker`)

**Stack:** `api/corrections.py` (new), Alembic migration 003, `api/pdf_proxy.py` with `FileResponse`, HTMX `hx-trigger="blur"` for per-field auto-save

**Research flag:** Needs spike during planning — correction field_path design for nested `campos_adicionales` JSON fields needs explicit schema decision before implementation; auto-save-on-blur HTMX pattern needs smoke test before full review UI is built

---

### Phase 4: PDF Reports and Analytics Dashboard

**Rationale:** Reporting and analytics depend on stable extracted data and (for quality metrics) on the correction history that Phase 3 creates. The report generation library decision is already resolved by research — fpdf2, zero GTK friction. Dashboard aggregation queries require the corrections table to exist.

**Delivers:** Agency downloads per-insurer PDF summary for each poliza; dashboard shows extraction volume, most-corrected fields, error rate by insurer; Sonnet quality evaluation auto-runs on a configurable sample of batch extractions.

**Addresses:** Differentiators — PDF reports per insurer, dashboard with metrics, auto-evaluator on batch sample, expanded golden dataset (enabled by HITL review UI)

**Avoids:** Pitfall v2-1 (WeasyPrint GTK — resolved by choosing fpdf2); Pitfall v2-9 (synchronous PDF generation blocking event loop — `run_in_executor` from day one); technical debt — SQL aggregates for dashboard stats, never load all records into Python

**Stack:** `fpdf2` (pip), `reports/renderer.py` with per-insurer template dispatch, `api/reports.py` with `run_in_executor`, Jinja2 HTML templates in `reports/templates/{aseguradora}.html`

**Research flag:** Validate fpdf2 on Windows 11 before template work begins (smoke test: `python -c "from fpdf import FPDF; pdf = FPDF(); pdf.add_page(); pdf.output('test.pdf')"`) — dashboard chart rendering strategy (server-side SVG vs CDN Chart.js) needs a spike

---

### Phase Ordering Rationale

- **Pipeline before UI:** Systematic extraction errors documented in `.planning/v2-extraction-errors.md` repeat on every poliza of the same insurer format. UI corrections would be wasted effort correcting bugs, not edge cases.
- **Read-only before write:** Validating HTMX + Jinja2 rendering without correction complexity reduces integration risk and delivers business value faster.
- **Corrections schema before correction endpoint:** The audit table is irreversible to retrofit. The schema is the first implementation task in Phase 3, not the last.
- **Reports after corrections:** Dashboard quality metrics depend on the `corrections` table; PDF reports are independent but lower priority than the HITL workflow.

### Research Flags

Phases needing deeper research or spikes during planning:
- **Phase 3 (HITL):** Correction `field_path` dot-notation design for nested `campos_adicionales` JSON fields — needs explicit schema decision before any endpoint is coded
- **Phase 3 (HITL):** Auto-save-on-blur via `hx-trigger="blur"` — needs a smoke test to confirm the HTMX partial response replaces only the target field row correctly
- **Phase 4 (Dashboard):** Chart rendering strategy — server-rendered SVG vs CDN chart library (Chart.js) needs a spike; CDN approach aligns with no-build-step philosophy but requires Alpine.js data binding

Phases with standard, well-documented patterns (skip `/gsd:research-phase`):
- **Phase 1 (Pipeline):** Pydantic cross-field validators and PyMuPDF char threshold — official docs are clear
- **Phase 2 (Web UI):** FastAPI + Jinja2Templates + StaticFiles mount — documented FastAPI pattern; HTMX CDN load is trivial
- **Phase 4 (PDF Reports):** fpdf2 `write_html()` + FastAPI `StreamingResponse` — documented in fpdf2 official docs with working example

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI as of 2026-03-20; WeasyPrint Windows failure verified against GitHub issues #2105 and #2480 and official docs; fpdf2 FastAPI integration confirmed against official fpdf2 docs |
| Features | HIGH | Table stakes derived from real extraction error log (`.planning/v2-extraction-errors.md`); HITL priorities grounded in Parseur, Sensible, and Box documentation; anti-features explicitly called out with rationale |
| Architecture | HIGH | Integration points derived from direct inspection of v1.1 source (`upload.py` line 164 PDF deletion confirmed); patterns verified against FastAPI official docs and 2025/2026 community sources |
| Pitfalls | HIGH | Critical pitfalls verified against official docs and GitHub issues; Windows-specific DLL conflicts confirmed against WeasyPrint GitHub issue #2480 and this project's existing Tesseract setup |

**Overall confidence:** HIGH

### Gaps to Address

- **Confidence-based field flagging:** Claude's self-reported field confidence (HIGH/MEDIUM/LOW via prompt engineering) may not correlate with actual extraction accuracy. Research marks this MEDIUM confidence. Treat as optional in Phase 3; run an A/B test comparing self-reported confidence against correction log ground truth before relying on it to filter the review queue.
- **fpdf2 Windows smoke test:** Research confirms fpdf2 is pure Python and Windows-safe, but a live install test on the target machine should be the first action in Phase 4 before any template HTML is written.
- **HTMX auto-save-on-blur:** The `hx-trigger="blur"` pattern for per-field saves is documented in HTMX 2.x but the exact partial-response swap behavior with validation errors needs a small spike before the full review UI is built.
- **Dashboard chart library:** No definitive recommendation between server-rendered SVG and CDN Chart.js. Resolve during Phase 4 planning with a one-day spike.

---

## Sources

### Primary (HIGH confidence)
- PyPI: fpdf2 — v2.8.7 verified Feb 28, 2026; `write_html()` and FastAPI integration confirmed
- fpdf2 official docs (py-pdf.github.io/fpdf2) — `HTMLMixin`, `StreamingResponse` pattern confirmed
- PyPI: Jinja2 — v3.1.6 verified Mar 2025
- WeasyPrint first steps docs + GitHub issues #2105 and #2480 — Windows GTK requirements, DLL naming mismatch, and Tesseract conflict documented
- PDF.js GitHub releases — v5.5.207 latest stable Mar 2025
- HTMX docs (htmx.org) — v2.0.4 CDN pattern and `hx-trigger` options verified
- FastAPI templating docs — `Jinja2Templates` + `StaticFiles` mount pattern confirmed
- Pydantic validators docs — `@model_validator(mode='after')` cross-field pattern confirmed
- Internal: `.planning/v2-extraction-errors.md` — real extraction errors from Zurich/AXA/MAPFRE batch test (ground truth for pitfall and feature prioritization)
- Internal: `.planning/PROJECT.md` — v2.0 active requirements and constraints
- Internal: v1.1 source inspection — `upload.py` line 164 (PDF deletion), `models.py`, `config.py`

### Secondary (MEDIUM confidence)
- TestDriven.io: FastAPI + HTMX — HTML fragment pattern with FastAPI
- Parseur HITL best practices blog — confidence-based field flagging, review time reduction estimates
- Sensible.so: Human review for document processing — HITL UX patterns and correction workflow design
- Box Blog: Confidence scores for document extraction — correlation between self-reported and actual confidence caveats
- Practical Business Python: WeasyPrint + Jinja2 PDF report pattern

### Tertiary (needs validation)
- Claude self-reported field confidence via prompt engineering — no empirical data for this specific project; needs A/B validation against correction log before relying on it to prioritize review queue

---

*Research completed: 2026-03-20*
*Ready for roadmap: yes*
