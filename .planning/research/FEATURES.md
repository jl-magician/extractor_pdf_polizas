# Feature Landscape

**Domain:** Insurance policy PDF extraction — web review UI, PDF report generation, extraction quality, human-in-the-loop correction
**Researched:** 2026-03-20
**Existing backend:** FastAPI REST API + SQLite + Alembic + async job system (v1.1 shipped)

---

## Context: What Already Exists (v1.1, NOT in scope here)

The following are fully shipped and stable. Do not re-implement:

- PDF ingestion with per-page digital/scanned classification (PyMuPDF + image coverage ratio)
- OCR via ocrmypdf + Tesseract; full pipeline: ingest -> extract -> persist
- Claude Haiku extraction with tool_use forced structured output
- CLI: extract, batch (concurrent), export (JSON/Excel/CSV), import-json, serve, create-fixture
- FastAPI: GET/POST/PUT/DELETE /polizas, POST /polizas/upload, GET /jobs/{id}
- SQLite persistence: polizas, asegurados, coberturas, ingestion_cache; Alembic migrations
- Sonnet quality evaluator (opt-in); golden dataset regression suite

This document covers only what is **new** for v2.0.

---

## Table Stakes

Features users expect from a document review tool at this stage. Missing = product feels incomplete for daily agency use.

| Feature | Why Expected | Complexity | Dependency |
|---------|--------------|------------|------------|
| Web UI — PDF upload | Agency team uses CLI; browser drag-and-drop replaces manual CLI invocation for non-technical users | Low | `POST /polizas/upload` already exists |
| Web UI — polizas list | Must see all extracted policies without querying SQLite directly | Low | `GET /polizas` already exists |
| Web UI — single-poliza detail view | Must read all extracted fields for a policy; table with Spanish field names | Low | `GET /polizas/{id}` already exists |
| Inline field editing + PATCH endpoint | Correcting wrong fields is the primary daily workflow; edit in browser, persist to DB | Medium | New `PATCH /polizas/{id}` endpoint needed |
| Side-by-side PDF + extraction review | Core HITL pattern: source document and extracted fields simultaneously; prevents constant tab-switching | Medium | PDF must be served temporarily for viewer; new storage/serving logic |
| Extraction job status display | Upload is async (202 + job_id); UI must show "processing" state and auto-refresh to result | Low | `GET /jobs/{id}` already exists |
| Auto-OCR fallback for zero-text pages | Zero-text digital PDFs silently return all-null (documented in v2-extraction-errors.md error #9) | Low-Med | Modifies PDF classifier threshold in existing ingestion pipeline |
| OCR call bug fix for scanned PDFs | `ocrmypdf.ocr()` argument error causes entire PDF to silently fail (error #10) | Low | Fix existing OCR call; likely path quoting or API change |
| Financial field cross-validation | Value swaps between primer_pago/subsecuentes/financiamiento are the most common error class (errors #3-4, #6-7) | Medium | Extends or replaces existing evaluator; rule-based, not LLM |
| Export from UI | Team exports via CLI today; export button replaces that workflow | Low | `GET /polizas/export` endpoint; add format param if not present |

---

## Differentiators

Features that meaningfully improve the product beyond baseline. Not expected as day-one features but high value once table stakes are met.

| Feature | Value Proposition | Complexity | Dependency |
|---------|-------------------|------------|------------|
| Confidence-based field flagging | Highlight only uncertain fields for review; reduces review time by 60-80% in comparable HITL systems; human attention goes where it adds value | Medium | Requires field-level confidence in extraction output; Claude self-reports HIGH/MEDIUM/LOW per field group via prompt engineering |
| Correction storage + feedback loop | Corrections saved to DB become a change log for prompt improvement; closes the accuracy improvement cycle | Medium | New `field_corrections` table with field_path, original_value, corrected_value, corrected_at |
| PDF report generation per insurer | Agency produces summary documents for clients; Jinja2 + WeasyPrint HTML-to-PDF with per-insurer template | Medium | New Python deps: weasyprint, Jinja2 (Jinja2 already in Python ecosystem); one HTML template per insurer |
| Dashboard with extraction metrics | Volume by insurer, fields most frequently corrected, error rate over time; makes quality trends visible | Medium | Aggregation queries on polizas + corrections tables; chart library in frontend (Recharts recommended) |
| Field exclusion list (configurable) | `agencia_responsable`-type fields (error #8) should never appear; configurable per-insurer blocklist in Settings | Low | Extension of existing Settings system |
| Sonnet review pass for campos_adicionales | Financial subfields in campos_adicionales are where value swaps concentrate; targeted Sonnet pass only on that JSON blob | Medium | Extends existing evaluator; controlled cost: only on campos_adicionales not full extraction |
| Auto-trigger evaluator on batch sample | Run Sonnet quality evaluation on N% of batch extractions automatically, not just manually | Low | Wraps existing evaluator; config flag for sample rate |
| Expanded golden dataset (20+ fixtures) | Regression coverage across all 10 insurers; makes prompt changes safe to deploy | Medium | Needs real PDF samples from each insurer; PII redaction workflow; HITL UI enables this |

---

## Anti-Features

Features to explicitly NOT build in v2.0. Building these would waste time or introduce irreversible complexity.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| PDF annotation overlay on the source document | Heavyweight — requires commercial PDF SDK (Apryse, Syncfusion) or complex canvas work; the value is editing extracted fields, not marking up the PDF | Edit extracted fields in a form panel beside the PDF viewer; react-pdf (MIT) for read-only display |
| User authentication / role-based access | Single-user local tool for one agency office; auth adds deployment complexity with zero user benefit at current scale | Skip entirely; revisit only if multi-user or cloud deployment is planned |
| WebSocket/SSE real-time job progress stream | Poll-based `GET /jobs/{id}` is sufficient for single-user local use; SSE adds frontend complexity | Keep polling; 2-second interval in frontend is invisible to user |
| Celery/Redis job queue | Already ruled out in PROJECT.md; in-memory job_store is adequate for 200 PDFs/month on local machine | Keep ThreadPoolExecutor + in-memory store as-is |
| WYSIWYG report template editor | Building a template designer is a product in itself; per-insurer templates are manageable as HTML/CSS files | Jinja2 HTML templates edited as text files; one per insurer; CSS for styling |
| Permanent PDF storage in DB or disk | Disk management, DB bloat; re-upload is idempotent via hash cache | Store PDF path temporarily for review session only; discard after extraction completes |
| LLM fine-tuning from corrections | Claude API does not support fine-tuning; corrections cannot train model weights | Use correction history to improve system prompt examples; manual prompt iteration by developer |
| Mobile responsive layout | Agency team works on desktop; mobile polish is wasted effort at this stage | Desktop-first layout; no responsive breakpoints needed in v2.0 |
| Policy comparison / coverage gap analysis | Requires stable schema and UI first; premature for v2.0 | Deferred to v3.0 after schema stabilizes through real agency use |
| Automated golden dataset expansion from production | Already flagged out-of-scope in PROJECT.md — needs human review workflow first | Manual curation enabled by HITL UI once it ships |

---

## Feature Dependencies

```
Auto-OCR fallback (extraction pipeline fix)
  └── Zero-text page detection (threshold: <10 chars after get_text())
  └── Auto-retry through OCR path regardless of initial classification

OCR bug fix (scanned PDFs)
  └── Debug ocrmypdf.ocr() call with space/special-char filenames
  └── Likely: path quoting fix or API version change

HITL review UI (side-by-side)
  └── Temporary PDF serving for view session
      └── New FastAPI endpoint: GET /polizas/{id}/pdf (serves temp file or re-accepts upload)
  └── Inline field editing
      └── New PATCH /polizas/{id} endpoint
  └── Correction storage
      └── New field_corrections table (Alembic migration required)
      └── Field-diff logic (compare PATCH body against DB state before applying)
  └── Confidence-based field flagging (optional but synergistic)
      └── Prompt engineering change: ask Claude to self-report field confidence

PDF report generation
  └── WeasyPrint + Jinja2 (new Python deps)
  └── HTML templates per insurer (new assets in templates/)
  └── New FastAPI endpoint: GET /polizas/{id}/report.pdf

Dashboard
  └── Aggregation queries on polizas + corrections tables
  └── Chart library in frontend (Recharts, MIT license)
  └── New FastAPI endpoint: GET /stats or inline in existing routes

Expanded golden dataset
  └── HITL review UI (human must validate before fixture creation)
  └── Real PDF samples from all 10 insurers

Auto-evaluator on batch sample
  └── Existing Sonnet evaluator (already built in v1.1)
  └── New config flag: evaluator_sample_rate (0.0–1.0)
```

---

## MVP Recommendation

For v2.0 milestone, prioritize in this order:

### Phase 1 — Fix extraction pipeline (unblocks everything downstream)

1. Auto-OCR fallback for zero-text pages (error #9)
2. OCR call bug fix for scanned PDFs with spaces/special chars (error #10)
3. Financial field cross-validation rules (most common error class)
4. Field exclusion list (configurable blocklist)

Rationale: UI corrections are wasted effort if underlying extractions are systematically wrong. Fix the pipeline first so the HITL UI corrects edge cases, not systematic failures.

### Phase 2 — Core Web UI (table stakes, read-only first)

5. Upload + polizas list + detail view (read-only)
6. Extraction job status polling
7. Export from UI

Rationale: Replace CLI workflow with browser UI; unblocks daily agency use without requiring full HITL.

### Phase 3 — HITL review workflow (differentiator)

8. Inline field editing + PATCH endpoint
9. Side-by-side PDF viewer (react-pdf, MIT)
10. Correction storage (new table + Alembic migration)
11. Confidence-based field flagging (if time allows)

Rationale: Highest-value workflow improvement; doubles as quality data collection for future prompt improvement.

### Phase 4 — Reporting and quality visibility

12. PDF report generation (Jinja2 + WeasyPrint, per-insurer templates)
13. Dashboard with extraction metrics and charts
14. Auto-evaluator on batch sample
15. Expanded golden dataset (enabled by HITL UI)

### Defer from v2.0

- Policy comparison / analytics (v3.0)
- Automated golden dataset expansion from production (v3.0)
- Authentication / multi-user (only if deployment model changes)

---

## Complexity Notes

**Low** (1-3 days each): OCR bug fix, auto-OCR fallback threshold, field exclusion config, auto-evaluator sample rate, export button in UI, job polling in frontend.

**Medium** (3-7 days each): Inline field editing + PATCH endpoint, side-by-side PDF viewer integration, correction storage schema + API + UI, financial cross-validation rules, PDF report template system (WeasyPrint), dashboard aggregation + chart rendering, field-level confidence from Claude prompt engineering.

**Do not underestimate:** Side-by-side layout requires careful CSS — PDF viewer (react-pdf) on left, form panel on right. Scroll sync between PDF page and field group is optional but users will expect it after seeing the layout. Test with actual Zurich/AXA/MAPFRE PDFs early in development, not with mocks.

---

## Implementation Notes

### PDF viewer for HITL

Use `react-pdf` (MIT license, wraps Mozilla PDF.js, no cost). Renders PDF pages as canvas elements. Sufficient for read-only side-by-side display. Field editing happens in the React form panel beside it — no PDF annotation overlay needed. Install: `npm install react-pdf`.

Backend must serve the PDF file for the viewer. Options: (a) store temp file by job_id and serve it, (b) accept a re-upload from UI for the review session. Option (a) is simpler: keep job temp file alive for 1 hour (matches existing job expiry), add `GET /jobs/{id}/pdf` endpoint.

### PDF report generation

Use **WeasyPrint + Jinja2**. HTML/CSS templates are version-controllable text files; designers can edit them without Python knowledge. Pattern: render HTML from Jinja2 template with poliza context dict, then `weasyprint.HTML(string=html).write_pdf()`. One base template + per-insurer CSS override file handles 10-insurer requirement.

Add FastAPI endpoint `GET /polizas/{id}/report.pdf` that returns `StreamingResponse` with `media_type="application/pdf"`.

WeasyPrint on Windows requires GTK libraries. This is a known installation complexity (see PITFALLS.md). Alternative if GTK proves problematic: `playwright` (Chromium headless) for HTML-to-PDF — heavier dependency but no GTK requirement.

### Correction storage

New `field_corrections` table:
- `id` (integer primary key)
- `poliza_id` (foreign key -> polizas.id)
- `field_path` (string, dot-notation: `"prima_total"`, `"campos_adicionales.financiamiento"`)
- `original_value` (JSON string)
- `corrected_value` (JSON string)
- `corrected_at` (datetime)

Field-diff logic in PATCH handler: before applying update, compare each changed field against current DB value; insert a `field_corrections` row for each changed field. Apply update to poliza. Return updated poliza.

### Financial cross-validation

Rule set (start with these, add as patterns emerge from real PDFs):
- `primer_pago + (subsecuentes * recibos_subsecuentes) ≈ prima_total` within 2% relative tolerance
- If `subsecuentes == 0` and `prima_total > 0`, flag subsecuentes as possible swap
- If `financiamiento > prima_total`, flag financiamiento as likely swap with otro field

Store validation warnings in a new `validation_warnings` JSON column on `polizas` table (Alembic migration). Surface warnings in UI with yellow highlight on affected fields.

### Confidence-based field flagging

Claude tool_use structured output does not natively include per-field confidence scores. Workaround: extend the extraction schema with a `_field_confidence` dict alongside each field group; instruct Claude in the system prompt to self-report `"high"/"medium"/"low"` confidence per field. This is a prompt engineering change, not a Claude API capability.

Mark as **MEDIUM confidence** finding — needs empirical validation against actual Claude output. Claude's self-reported confidence may not correlate with actual accuracy. Run A/B test: compare self-reported confidence against ground-truth errors from the correction log.

---

## Sources

- [Human-in-the-Loop AI in Document Workflows — Parseur](https://parseur.com/blog/hitl-best-practices)
- [Human-in-the-Loop Review for Document Processing — Sensible](https://www.sensible.so/blog/human-review-document-processing)
- [react-pdf GitHub (MIT license)](https://github.com/wojtekmaj/react-pdf)
- [Best React PDF Viewer Libraries 2025](https://blog.react-pdf.dev/top-6-pdf-viewers-for-reactjs-developers-in-2025)
- [WeasyPrint + Jinja2 PDF report pattern — Practical Business Python](https://pbpython.com/pdf-reports.html)
- [Top 10 Python PDF Generator Libraries 2025 — Nutrient](https://www.nutrient.io/blog/top-10-ways-to-generate-pdfs-in-python/)
- [Confidence Scores for Document Extraction — Box Blog](https://blog.box.com/confidence-scores-box-extract-api-know-when-rely-your-extractions)
- [Validating Extractions — Sensible Docs](https://docs.sensible.so/docs/validate-extractions)
- Internal: `.planning/v2-extraction-errors.md` (real extraction errors from Zurich/AXA/MAPFRE batch test)
- Internal: `.planning/PROJECT.md` (v2.0 active requirements and constraints)
