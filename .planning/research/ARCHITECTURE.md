# Architecture Research

**Domain:** Web UI + PDF report generation + human-in-the-loop review for insurance policy PDF extractor
**Researched:** 2026-03-20
**Confidence:** HIGH — integration points derived directly from v1.1 source (upload.py, models.py, config.py inspected); external patterns verified against official docs and 2025/2026 sources

---

## Context: v1.1 Architecture Baseline (already shipped)

```
policy_extractor/
├── config.py               # Settings — env vars, model ID, DB path
├── schemas/                # Pydantic v2 models (PolizaSchema, Asegurado, Cobertura)
├── ingestion/              # ingest_pdf() → IngestionResult; classifier + OCR + cache
├── extraction/             # extract_policy() → Claude Haiku API call; prompt + schema_builder + verification
├── storage/                # SQLAlchemy 2.0 ORM + SQLite WAL; writer.upsert_policy()
├── api/
│   ├── __init__.py         # GET/POST/PUT/DELETE /polizas (CRUD)
│   └── upload.py           # POST /polizas/upload, GET /jobs/{id}, GET /jobs
├── evaluation.py           # Sonnet quality evaluator (opt-in, --evaluate flag)
├── export.py               # Excel/CSV export
├── regression/             # field_differ, pii_redactor
└── cli.py                  # Typer: extract, batch, export, import-json, serve, create-fixture

SQLite: data/polizas.db
  Tables: polizas, asegurados, coberturas, ingestion_cache
  ORM: SQLAlchemy 2.0, Alembic migrations, WAL mode
```

Key constraint from inspection of `upload.py` line 164: **PDFs are deleted after successful extraction** (`pdf_path.unlink(missing_ok=True)`). This must change in v2.0 to support the review UI.

---

## v2.0 Target System Overview

```
Browser (React SPA — built by Vite, served as static files by FastAPI)
 ├── Upload page         POST /polizas/upload (existing endpoint, unchanged)
 ├── Dashboard           GET  /polizas         (existing)
 ├── Policy detail       GET  /polizas/{id}    (existing)
 ├── Review UI           GET  /polizas/{id}/pdf-proxy   (NEW)
 │   PDF left + form     PATCH /polizas/{id}             (NEW)
 │   right pane          GET  /polizas/{id}/corrections  (NEW)
 └── Report download     GET  /polizas/{id}/report       (NEW)
          │
          │  HTTP (same origin in prod / proxied via Vite in dev)
          ▼
FastAPI (localhost:8000)
 ├── api/upload.py          existing (modified: retain PDF instead of delete)
 ├── api/polizas.py         existing CRUD + new PATCH correction endpoint
 ├── api/reports.py         NEW — stream PDF report bytes
 ├── api/pdf_proxy.py       NEW — serve retained source PDF for review UI
 ├── api/corrections.py     NEW — GET correction history
 └── StaticFiles mount      NEW — serves frontend/dist/ at catch-all "/"
          │
          ▼
   policy_extractor package (internal modules)
    ├── ingestion/           unchanged public API
    ├── extraction/          prompt.py modified + verification.py extended
    ├── storage/             models.py + writer.py extended (Correction table)
    ├── evaluation.py        unchanged
    ├── export.py            unchanged
    └── reports/             NEW module — fpdf2-based PDF report renderer
          │
          ▼
   SQLite (data/polizas.db)
    ├── polizas              existing + new columns: source_pdf_path, validation_warnings
    ├── asegurados           existing (unchanged)
    ├── coberturas           existing (unchanged)
    ├── ingestion_cache      existing (unchanged)
    └── corrections          NEW — field correction audit log
```

---

## Component Responsibilities

### Existing Components — What Changes in v2.0

| Component | v1.1 Responsibility | v2.0 Change |
|-----------|---------------------|-------------|
| `api/upload.py` | Upload PDF, create job, background extraction, delete PDF on success | **Modified:** retain PDF to `data/pdfs/{poliza_id}.pdf`; store path in `polizas.source_pdf_path` |
| `storage/models.py` | ORM: Poliza, Asegurado, Cobertura, IngestionCache | **Extended:** add `Correction` model; add `source_pdf_path`, `validation_warnings` columns to Poliza |
| `storage/writer.py` | `upsert_policy()`, `orm_to_schema()` | **Extended:** add `save_correction()`, `apply_correction()`, `get_corrections()` |
| `extraction/verification.py` | `verify_no_hallucination()` (string overlap check) | **Extended:** add `validate_financial_fields()` — cross-check financial totals, detect value swaps |
| `extraction/prompt.py` | SYSTEM_PROMPT_V1 — Haiku extraction instructions | **Modified:** add financial table examples, field disambiguation for Zurich-style layouts |

### New Components — v2.0 Additions

| Component | Responsibility | Location |
|-----------|---------------|----------|
| `api/polizas.py` (new PATCH) | Accept field correction, write to DB, record in corrections table | `policy_extractor/api/polizas.py` |
| `api/reports.py` | Load poliza from DB, call renderer, stream PDF bytes | `policy_extractor/api/reports.py` |
| `api/pdf_proxy.py` | Read retained PDF from disk, stream bytes to browser | `policy_extractor/api/pdf_proxy.py` |
| `api/corrections.py` | Return correction history for a poliza | `policy_extractor/api/corrections.py` |
| `reports/renderer.py` | fpdf2-based report generator with per-insurer templates | `policy_extractor/reports/renderer.py` |
| `frontend/` | React SPA: upload, dashboard, review, report download | `frontend/` (new top-level directory) |
| Alembic migration | Add corrections table + poliza columns | `alembic/versions/` |

---

## Recommended Project Structure

```
extractor_pdf_polizas/
├── policy_extractor/
│   ├── api/
│   │   ├── upload.py           # existing — modified to retain PDF
│   │   ├── polizas.py          # existing — add PATCH correction endpoint
│   │   ├── reports.py          # NEW — GET /polizas/{id}/report
│   │   ├── pdf_proxy.py        # NEW — GET /polizas/{id}/pdf-proxy
│   │   └── corrections.py      # NEW — GET /polizas/{id}/corrections
│   ├── reports/
│   │   ├── __init__.py
│   │   └── renderer.py         # NEW — fpdf2 PDF generation, per-insurer templates
│   ├── storage/
│   │   ├── models.py           # add Correction model + poliza columns
│   │   └── writer.py           # add save_correction(), apply_correction()
│   └── extraction/
│       ├── prompt.py           # improved financial table instructions
│       └── verification.py     # extended: validate_financial_fields()
├── frontend/                   # NEW — React SPA
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts       # typed fetch wrappers for all FastAPI endpoints
│   │   ├── components/
│   │   │   ├── UploadZone.tsx      # drag-drop + job poll
│   │   │   ├── PolicyList.tsx      # filterable table
│   │   │   ├── PolicyDetail.tsx    # detail view + report download button
│   │   │   ├── ReviewPanel.tsx     # side-by-side PDF + editable fields
│   │   │   └── Dashboard.tsx       # stats: volume, avg score, error rate
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts          # proxy /api → localhost:8000 in dev
├── data/
│   └── pdfs/                   # NEW — retained source PDFs keyed by poliza_id
└── alembic/
    └── versions/
        └── 003_v2_schema.py    # corrections table + poliza columns
```

### Structure Rationale

- **`policy_extractor/reports/`:** Report generation is Python-side — fpdf2 runs server-side, no client rendering needed. Placing it inside the package keeps it importable by both FastAPI routes and CLI (`poliza-extractor export-report` command if added later).
- **`frontend/`:** Sibling to `policy_extractor/` at repo root. Built with Vite into `frontend/dist/`, mounted by FastAPI as StaticFiles. One uvicorn process serves everything — no nginx, no separate Node server in production.
- **`data/pdfs/`:** Retained PDFs stored here, keyed by `{poliza_id}.pdf`. Separate from `uploads/` (temp) to make retention intent explicit. This directory is gitignored.
- **`api/pdf_proxy.py`:** Separate router from `upload.py` for clear separation of concerns. Upload is about async job management; pdf_proxy is about serving stored assets.

---

## Architectural Patterns

### Pattern 1: FastAPI Serves the React SPA (Single Process)

**What:** After `npm run build`, Vite outputs `frontend/dist/`. FastAPI mounts this directory with `StaticFiles(html=True)` at the catch-all route. All `/api/` (or prefixed) routes are registered first — API routes win over static files.

**When to use:** Single-process local deployment, single user, Windows 11. No nginx, no Docker, no separate server.

**Trade-offs:** Simple to operate. Python is slower than nginx for static files but irrelevant at <10 concurrent users. The `html=True` parameter makes StaticFiles serve `index.html` for unknown paths (required for React Router client-side routing).

**Example:**
```python
# policy_extractor/main.py — app factory, after all router includes
from fastapi.staticfiles import StaticFiles
from pathlib import Path

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    # IMPORTANT: mount AFTER all API routers so /api/* routes take priority
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="spa")
```

**Dev workflow (no build needed):** Vite dev server runs at `localhost:5173`, proxies `/api` to FastAPI at port 8000. CORS must be enabled on FastAPI in dev mode only.

```typescript
// frontend/vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      "/api": "http://localhost:8000"
    }
  }
})
```

---

### Pattern 2: PATCH Correction + Corrections Audit Table

**What:** `PATCH /polizas/{id}` accepts a partial correction payload (field path + new value). The handler writes the corrected value into the appropriate column (or into `campos_adicionales` for dynamic fields) and appends a row to the `corrections` table. The correction is atomic with the poliza update (same SQLAlchemy session, same transaction).

**When to use:** Human-in-the-loop field corrections. Any time a user overrides an extracted value via the review UI.

**Trade-offs:** Simple; no event sourcing overhead. Corrections survive re-extractions only if re-extraction is blocked when `has_corrections = true` (or user explicitly confirms overwrite). Does not automatically re-apply corrections if the poliza is re-extracted — the UI should warn.

**Correction table schema:**
```python
class Correction(Base):
    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id"), index=True)
    # e.g. "prima_total", "campos_adicionales.financiamiento", "asegurados[0].nombre_descripcion"
    field_path: Mapped[str] = mapped_column(String)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON-serialised
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON-serialised
    corrected_by: Mapped[str] = mapped_column(String, default="user")
    corrected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    poliza: Mapped["Poliza"] = relationship("Poliza")
```

**New poliza column:**
```python
# Added to Poliza model via Alembic migration 003
has_corrections: Mapped[bool] = mapped_column(Boolean, default=False)
source_pdf_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
validation_warnings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
```

---

### Pattern 3: fpdf2 for PDF Report Generation (Windows-safe)

**What:** `fpdf2` generates PDF reports from poliza data programmatically. The `reports/renderer.py` module selects a template function by `poliza.aseguradora` and renders header, contratante block, asegurados table, coberturas table, and financial summary. `GET /polizas/{id}/report` streams the bytes.

**When to use:** Generating structured PDF output from structured relational data. Always on Windows (this app's target platform).

**Why fpdf2 over WeasyPrint:** WeasyPrint on Windows 11 with Python 3.11 has documented installation failures (GitHub issue #2480 — GTK DLL resolution errors). The project already follows the "lightweight, no native deps" philosophy (openpyxl instead of pandas for Excel). fpdf2 is pure Python with only Pillow + fontTools as dependencies — both already present or trivial to add on Windows. WeasyPrint would require MSYS2 + GTK and `WEASYPRINT_DLL_DIRECTORIES` env var management.

**Example — renderer skeleton:**
```python
# policy_extractor/reports/renderer.py
from fpdf import FPDF
from policy_extractor.schemas.poliza import PolizaSchema

_INSURER_TEMPLATES = {}  # populated by register_template decorator

def generate_report(poliza: PolizaSchema) -> bytes:
    template_fn = _INSURER_TEMPLATES.get(poliza.aseguradora, _default_template)
    pdf = template_fn(poliza)
    return bytes(pdf.output())

def _default_template(poliza: PolizaSchema) -> FPDF:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Poliza {poliza.numero_poliza} — {poliza.aseguradora}", new_x="LMARGIN", new_y="NEXT")
    # ... coberturas table, financial summary
    return pdf
```

**API endpoint:**
```python
# policy_extractor/api/reports.py
from fastapi.responses import StreamingResponse
import io

@router.get("/polizas/{poliza_id}/report")
def get_report(poliza_id: int, db: Session = Depends(get_db)):
    poliza = _load_poliza(db, poliza_id)  # raises 404 if not found
    pdf_bytes = generate_report(orm_to_schema(poliza))
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=poliza_{poliza_id}.pdf"}
    )
```

---

### Pattern 4: react-pdf for Side-by-Side PDF Viewer

**What:** The review UI (`ReviewPanel.tsx`) renders the original PDF in the left pane using `react-pdf` (Mozilla PDF.js wrapper, ~950K weekly npm downloads, actively maintained 2025). The right pane shows an editable form for all extracted fields. Corrections submit via PATCH to the backend.

**When to use:** Human-in-the-loop review where the reviewer must see the source document alongside the extracted data.

**Why react-pdf:** Lightweight, pure-JS, no annotation overhead, full UI control. The use case is read-only PDF display — no form fill, no signatures needed. The library works with a CDN-loaded web worker (PDF.js) which keeps the main thread free during rendering.

**PDF serving — critical dependency:** The original PDF must be retained (see Anti-Pattern 1 below). `GET /polizas/{id}/pdf-proxy` streams the file from `data/pdfs/{poliza_id}.pdf`. The React component loads it via a blob URL or a direct `<Document url>` prop.

**Side-by-side layout:**
```tsx
// frontend/src/components/ReviewPanel.tsx (skeleton)
import { Document, Page } from "react-pdf";

export function ReviewPanel({ polizaId }: { polizaId: number }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", height: "100vh" }}>
      <div style={{ overflow: "auto" }}>
        <Document file={`/api/polizas/${polizaId}/pdf-proxy`}>
          <Page pageNumber={1} />
        </Document>
      </div>
      <div style={{ overflow: "auto" }}>
        <ExtractionForm polizaId={polizaId} />
      </div>
    </div>
  )
}
```

---

### Pattern 5: Post-Extraction Financial Validation

**What:** After `extract_policy()` returns, call `validate_financial_fields(poliza)` to cross-check numeric consistency and detect known swap patterns. Returns a list of `ValidationWarning` objects stored in `polizas.validation_warnings` (JSON column). The review UI shows an orange badge for policies with warnings.

**Validation rules based on real errors from v2-extraction-errors.md:**
1. `primer_pago + (subsecuentes * pagos_restantes) ≈ prima_total` within 5% tolerance
2. If `financiamiento == 0.0` and `otros_servicios_contratados > 0` (or vice versa), flag as probable value swap
3. If `subsecuentes == primer_pago` and `subsecuentes > 0`, flag as probable copy error (error #5 in extraction errors)
4. If `folio` is numeric-only and `clave` is empty, flag as probable field swap (errors #6-#7)

**Integration point:** Called inside `_run_extraction()` in `upload.py` after `extract_policy()`, before `upsert_policy()`. Adds `validation_warnings` to the result dict stored in the job.

---

## Data Flow

### Upload + Extraction Flow (modified in v2.0)

```
User uploads PDF in browser
    |
    v
POST /polizas/upload (multipart)
    |
    v
api/upload.py: validate → create job → save to uploads/{job_id}.pdf
    |
    v
ThreadPoolExecutor: _run_extraction() background thread
    |
    +-- ingestion.ingest_pdf() → classify pages, OCR if needed
    |
    +-- extraction.extract_policy() → PolizaSchema (Claude Haiku)
    |
    +-- extraction.verification.validate_financial_fields() → warnings  [NEW]
    |
    +-- storage.writer.upsert_policy() → poliza_id returned
    |
    +-- Move PDF: uploads/{job_id}.pdf → data/pdfs/{poliza_id}.pdf     [NEW]
    |   Update polizas.source_pdf_path = "data/pdfs/{poliza_id}.pdf"   [NEW]
    |
    +-- Store validation_warnings in polizas.validation_warnings        [NEW]
    |
    v
job status → complete | failed
Browser polls GET /jobs/{job_id} → redirect to /polizas/{poliza_id}
```

### Correction Flow (NEW)

```
Review UI: reviewer sees PDF (left pane) + extracted fields (right pane)
    |
    v
Reviewer edits "financiamiento" field from 808.2 to 0.0
Clicks "Save"
    |
    v
PATCH /polizas/{id}
  { "field_path": "campos_adicionales.financiamiento", "new_value": 0.0, "note": "value swap" }
    |
    v
api/polizas.py: load poliza, read current value of field_path
    |
    v
storage.writer.apply_correction():
    - UPDATE polizas SET campos_adicionales = {...patched}, has_corrections = true
    - INSERT INTO corrections (poliza_id, field_path, old_value, new_value, note, corrected_at)
    (single SQLAlchemy session → atomic transaction)
    |
    v
Return 200 + updated poliza JSON
UI reflects corrected value; PDF panel unchanged
```

### Report Generation Flow (NEW)

```
User clicks "Download report" on policy detail page
    |
    v
GET /polizas/{id}/report
    |
    v
api/reports.py:
    - Load poliza from DB with selectinload(asegurados, coberturas)
    - Call reports.renderer.generate_report(orm_to_schema(poliza))
    - renderer selects template by poliza.aseguradora
    - fpdf2 builds PDF in memory → bytes
    |
    v
StreamingResponse(bytes, media_type="application/pdf",
                  Content-Disposition: attachment; filename=poliza_{id}.pdf)
```

### Auto-OCR Fallback Flow (NEW — inside ingestion)

```
ingest_pdf() classifies pages
    |
    v
For each "digital" page:
    - Extract text with PyMuPDF get_text()
    - If len(text.strip()) < 10 chars:
        reclassify page as "scanned"
        run OCR on this page
    |
    v
If full extraction returns all-null core fields or all <UNKNOWN>:
    retry entire PDF through OCR pipeline regardless of classification
```

---

## Integration Points

### Existing API — No Breaking Changes

All v1.1 endpoints retain their signatures. v2.0 adds endpoints only.

| Endpoint | v1.1 Status | v2.0 Change |
|----------|-------------|-------------|
| `POST /polizas/upload` | Existing | Side effect change only: PDF retained instead of deleted |
| `GET /jobs/{job_id}` | Existing | No change |
| `GET /jobs` | Existing | No change |
| `GET /polizas` | Existing | No change |
| `GET /polizas/{id}` | Existing | No change |
| `PATCH /polizas/{id}` | Does not exist | NEW — correction endpoint |
| `GET /polizas/{id}/report` | Does not exist | NEW — PDF report download |
| `GET /polizas/{id}/pdf-proxy` | Does not exist | NEW — stream retained source PDF |
| `GET /polizas/{id}/corrections` | Does not exist | NEW — correction history |
| `GET /` (catch-all) | Does not exist | NEW — SPA static files |

### Internal Module Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `api/` → `storage/` | Direct import (sync SQLAlchemy session via Depends) | No change from v1.1 |
| `api/reports.py` → `reports/renderer.py` | Direct function call, returns bytes | New boundary |
| `extraction/` → `extraction/verification.py` | Direct call post-extraction | Verification is post-processing, not inline in the API call |
| `api/upload.py` → `storage/writer.py` | Calls `upsert_policy()` then new `update_source_pdf_path()` | Minor extension |
| `frontend/` → `api/` | HTTP fetch (same origin in prod, proxied in dev) | CORS disabled in prod; enabled in dev only |
| `storage/writer.py` → `Correction` model | Same session, same transaction as poliza update | Atomicity guaranteed |

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Claude API (Anthropic) | Existing — `extraction/client.py` | No change |
| react-pdf (PDF.js) | npm package, loads PDF.js web worker | No backend dependency; web worker runs in browser |
| fpdf2 | Python package — add to `pyproject.toml` | No native deps; pure Python on Windows |

---

## Build Order Recommendation

Dependencies flow strictly from left to right. Each phase is a prerequisite for subsequent phases.

### Phase 1 — Backend Corrections Infrastructure

**Why first:** The `corrections` table and PATCH endpoint are the data contract for the review UI. Building them before the UI ensures the UI is built against the real API, not a mock.

**Scope:**
- Add `Correction` ORM model to `storage/models.py`
- Add `has_corrections`, `source_pdf_path`, `validation_warnings` columns to `Poliza`
- Alembic migration 003
- `save_correction()`, `apply_correction()`, `get_corrections()` in `storage/writer.py`
- `PATCH /polizas/{id}` endpoint
- `GET /polizas/{id}/corrections` endpoint
- Modify `upload.py` to retain PDF to `data/pdfs/{poliza_id}.pdf` + update `source_pdf_path`
- `GET /polizas/{id}/pdf-proxy` endpoint (stream from `source_pdf_path`)

**Validates:** Correction storage, PDF retention, new DB schema. All testable without a browser.

### Phase 2 — Extraction Quality Improvements

**Why second:** Prompt fixes and validation are independent of UI. Shipping them before the UI means users see better default extractions in the review UI from day one. The financial validation also produces `validation_warnings` data that Phase 4 (review UI) will display.

**Scope:**
- `extraction/prompt.py`: add financial table disambiguation examples (Zurich-style layouts), field swap guards
- `extraction/verification.py`: add `validate_financial_fields()` — cross-check financial totals, detect swap patterns
- Auto-OCR fallback in `ingestion/classifier.py` — <10 char threshold for "digital" pages
- Fix `ocrmypdf.ocr()` argument bug for scanned PDFs with spaces/special chars in filename
- Field exclusion list configurable via `Settings`
- Wire `validate_financial_fields()` into `_run_extraction()` in `upload.py`

**Validates:** Extraction accuracy improvements via existing regression suite + real PDF testing.

### Phase 3 — React SPA Shell + Upload + Policy List

**Why third:** Foundation of the UI. Upload and list views are simpler than the review UI (no PDF viewer, no complex form state) and validate the Vite + FastAPI serving pattern early.

**Scope:**
- Scaffold `frontend/` with Vite + React + TypeScript + Tailwind CSS
- `api/client.ts` — typed fetch wrappers for all existing endpoints
- Upload page: drag-drop zone, job polling (GET /jobs/{id}), success redirect
- Policy list page: table with filters (aseguradora, tipo_seguro, fecha range), sort
- Policy detail page: read-only field display + "Download report" placeholder + "Review" button
- FastAPI StaticFiles mount for SPA
- CORS middleware (dev mode only via Settings flag)

**Validates:** SPA serving pattern, end-to-end upload flow in the browser.

### Phase 4 — Human-in-the-Loop Review UI

**Why fourth:** Depends on Phase 1 (corrections backend + PDF proxy) and Phase 3 (SPA shell). Most complex UI component — split-pane with PDF viewer and live-editable form.

**Scope:**
- `ReviewPanel.tsx`: react-pdf left pane + `ExtractionForm.tsx` right pane
- PATCH-on-save for each corrected field (debounced or on explicit "Save" button)
- Field warning badges from `validation_warnings` (orange badge on flagged fields)
- Correction history panel below the form
- "Mark as reviewed" action (sets `has_corrections = true` even with no edits)
- react-pdf worker config (vite static copy of pdfjs worker file)

**Validates:** The human-in-the-loop workflow end-to-end with a real PDF.

### Phase 5 — PDF Report Generation

**Why fifth:** Independent of review UI. Can be parallelized with Phase 4 for a single developer but depends on Phase 3 (download button placeholder already placed). Simple API addition.

**Scope:**
- Add `fpdf2` to `pyproject.toml`
- `reports/renderer.py`: base template + Zurich template + AXA template (two most common from batch test data)
- `GET /polizas/{id}/report` endpoint with StreamingResponse
- Wire download button in policy detail page (Phase 3 placeholder)

**Validates:** PDF generation on Windows, per-insurer template differentiation.

### Phase 6 — Dashboard + Expanded Golden Dataset

**Why last:** Non-blocking. Requires data from real usage (Phases 3-4) to show meaningful stats. Golden dataset expansion benefits from the correction workflow (Phase 4) as a source of ground truth.

**Scope:**
- Dashboard: upload volume over time, avg `evaluation_score`, error rate by aseguradora, correction rate
- Auto-trigger Sonnet evaluator on batch samples (configurable `EVALUATION_SAMPLE_RATE` in Settings)
- Expand golden dataset to 20+ fixtures covering all 10 insurers
- Use Phase 4 corrections as source of expected values for new fixtures

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Current: 200 PDFs/month, 1 user, local | This architecture is correct. SQLite WAL + in-memory job store + monolith is fine. |
| 2000 PDFs/month, 5 users | Same architecture. Tune SQLite WAL checkpoint. Replace in-memory job_store with DB table (jobs not lost on restart). |
| 20k+ PDFs/month, multi-user | Beyond scope per PROJECT.md. Would need: PostgreSQL, async SQLAlchemy, persistent job queue (Redis/Celery or DB-backed). |

### Scaling Priorities

1. **First bottleneck at current scale:** Claude API rate limits (already handled by retry backoff). Not SQLite, not Python.
2. **Second bottleneck if user count grows:** In-memory job_store is lost on restart and not visible across processes. Persist jobs to a `jobs` DB table before needing a full task queue.

---

## Anti-Patterns

### Anti-Pattern 1: Deleting the Source PDF After Extraction (Existing Behavior)

**What the current code does:** `upload.py` line 164 calls `pdf_path.unlink(missing_ok=True)` on extraction success to save disk space.
**Why it's wrong for v2.0:** The review UI requires the original PDF to show side-by-side with the extracted data. Without the PDF, the reviewer cannot verify what Claude actually read — defeating the purpose of human-in-the-loop review.
**Do this instead:** Move (not copy) the PDF from `uploads/{job_id}.pdf` to `data/pdfs/{poliza_id}.pdf` after `upsert_policy()` returns the poliza ID. Store the path in `polizas.source_pdf_path`. Add a CLI command (`poliza-extractor prune-pdfs --older-than 90d`) for optional disk cleanup.

### Anti-Pattern 2: Applying Corrections by Re-Extracting

**What people do:** When a user submits a correction, re-run the Claude extraction with the corrected values injected as context to "confirm" the fix.
**Why it's wrong:** Re-extraction costs API money (~$0.02/PDF on Haiku), takes 5-30 seconds, and may overwrite different correctly-extracted fields. Corrections are point fixes on specific fields — they must be applied surgically as targeted DB updates.
**Do this instead:** PATCH the specific field in SQLite directly, record the correction in the audit table, and mark `polizas.has_corrections = true`. A visual indicator in the UI shows the poliza has been manually reviewed.

### Anti-Pattern 3: WeasyPrint for PDF Reports on Windows

**What people do:** Choose WeasyPrint for its HTML/CSS-based layout which produces visually richer PDFs.
**Why it's wrong:** WeasyPrint on Windows 11 with Python 3.11 has known GTK DLL resolution failures (GitHub issue #2480). The team would need MSYS2 + GTK + `WEASYPRINT_DLL_DIRECTORIES` env var management — a maintenance burden on a Windows-only workstation.
**Do this instead:** Use `fpdf2` — pure Python, Pillow + fontTools dependencies only, zero native DLL concerns. The project already follows this pattern (openpyxl over pandas for Excel export). Accept slightly less CSS flexibility; a well-structured fpdf2 template is sufficient for policy reports.

### Anti-Pattern 4: Feeding Corrections Back Into Extraction Prompts

**What people do:** Collect user corrections and inject them as few-shot examples into future Claude prompts to "teach" the model.
**Why it's wrong:** At 200 PDFs/month across 10 insurers, correction volume is too thin per insurer type for few-shot examples to be statistically meaningful. Stale corrections in prompts risk anchoring the model to old errors. Prompt context window costs increase linearly.
**Do this instead:** Use the corrections table to identify systematic error patterns (e.g., "financiamiento/otros_servicios swap appears in 30% of Zurich auto PDFs"). Then update `extraction/prompt.py` with explicit field disambiguation rules as a deliberate, version-tracked engineering change (`EXTRACTION_PROMPT_VERSION` bump).

### Anti-Pattern 5: Global SQLAlchemy Session in Background Workers

**What the current code does correctly:** Each `_run_extraction()` call creates its own `SessionLocal()` session.
**What to avoid in new code:** Do not pass a session from the FastAPI request scope into background threads (ThreadPoolExecutor). Sessions are not thread-safe.
**Do this instead:** Any new background work (e.g., auto-evaluation batch) must call `SessionLocal()` independently inside the worker function, and close it in a `finally` block.

### Anti-Pattern 6: Per-Insurer Pydantic Schemas

**What people do:** Create separate `PolizaZurich`, `PolizaAXA`, `PolizaMAPFRE` Pydantic models to capture insurer-specific fields.
**Why it's wrong:** 50-70 distinct PDF structures makes this unmanageable. Schema explosion multiplies test surface and prompt complexity.
**Do this instead:** Keep the single `PolizaSchema`. Use `campos_adicionales: dict` for insurer-specific overflow fields. Per-insurer differentiation belongs in report templates (Phase 5), not in the data model.

---

## Modified vs New: Explicit Inventory

### Files MODIFIED in v2.0

| File | What Changes |
|------|-------------|
| `policy_extractor/api/upload.py` | Retain PDF to `data/pdfs/{poliza_id}.pdf`; call `update_source_pdf_path()`; store validation_warnings |
| `policy_extractor/storage/models.py` | Add `Correction` model; add `has_corrections`, `source_pdf_path`, `validation_warnings` to `Poliza` |
| `policy_extractor/storage/writer.py` | Add `save_correction()`, `apply_correction()`, `get_corrections()`, `update_source_pdf_path()` |
| `policy_extractor/extraction/prompt.py` | Add financial table disambiguation examples; bump `EXTRACTION_PROMPT_VERSION` to v1.1.0 |
| `policy_extractor/extraction/verification.py` | Add `validate_financial_fields()` returning `list[ValidationWarning]` |
| `policy_extractor/ingestion/classifier.py` | Add <10 char auto-OCR fallback for "digital" pages |
| `policy_extractor/ingestion/ocr_runner.py` | Fix `ocrmypdf.ocr()` argument bug for filenames with spaces/special chars |
| `policy_extractor/config.py` | Add `EVALUATION_SAMPLE_RATE`, `FIELD_EXCLUSION_LIST`, `RETAIN_SOURCE_PDFS` settings |
| `pyproject.toml` | Add `fpdf2` dependency |

### Files CREATED in v2.0

| File | Purpose |
|------|---------|
| `policy_extractor/api/polizas.py` | PATCH correction endpoint (may be split from `api/__init__.py`) |
| `policy_extractor/api/reports.py` | GET /polizas/{id}/report — stream PDF report bytes |
| `policy_extractor/api/pdf_proxy.py` | GET /polizas/{id}/pdf-proxy — stream retained source PDF |
| `policy_extractor/api/corrections.py` | GET /polizas/{id}/corrections — correction history |
| `policy_extractor/reports/__init__.py` | Package init |
| `policy_extractor/reports/renderer.py` | fpdf2 PDF generator with per-insurer template dispatch |
| `frontend/` | React SPA (Vite + TypeScript + Tailwind) |
| `alembic/versions/003_v2_schema.py` | Migrations: corrections table + poliza columns |
| `data/pdfs/` | Directory for retained source PDFs (gitignored) |

### Files UNCHANGED in v2.0

`ingestion/cache.py`, `extraction/client.py`, `extraction/schema_builder.py`, `storage/database.py`, `storage/exporter.py`, `evaluation.py`, `export.py`, `regression/`, `cli.py` (minor additions possible for new CLI commands), `schemas/` (all Pydantic models), `alembic/env.py`, `alembic.ini`.

---

## Sources

- FastAPI StaticFiles official docs: [https://fastapi.tiangolo.com/tutorial/static-files/](https://fastapi.tiangolo.com/tutorial/static-files/) — `html=True` for SPA fallback (HIGH confidence)
- React SPA served by FastAPI pattern: [https://davidmuraya.com/blog/serving-a-react-frontend-application-with-fastapi/](https://davidmuraya.com/blog/serving-a-react-frontend-application-with-fastapi/) (MEDIUM confidence)
- react-pdf (Mozilla PDF.js wrapper): [https://github.com/wojtekmaj/react-pdf](https://github.com/wojtekmaj/react-pdf) — ~950K weekly npm downloads, actively maintained 2025-2026 (HIGH confidence)
- Top React PDF viewer libraries 2025: [https://dev.to/ansonch/top-6-pdf-viewers-for-reactjs-developers-in-2025-37kh](https://dev.to/ansonch/top-6-pdf-viewers-for-reactjs-developers-in-2025-37kh) (MEDIUM confidence)
- fpdf2 pure-Python PDF generation: [https://py-pdf.github.io/fpdf2/](https://py-pdf.github.io/fpdf2/) — no native dependencies (HIGH confidence)
- WeasyPrint Windows 11 + Python 3.11 failure: [https://github.com/Kozea/WeasyPrint/issues/2480](https://github.com/Kozea/WeasyPrint/issues/2480) (HIGH confidence — official GitHub issue)
- WeasyPrint + Jinja2 pattern (reference): [https://joshkaramuth.com/blog/generate-good-looking-pdfs-weasyprint-jinja2/](https://joshkaramuth.com/blog/generate-good-looking-pdfs-weasyprint-jinja2/) (MEDIUM confidence — relevant for if WeasyPrint platform issues are resolved)
- Vite proxy + FastAPI integration 2025: [https://www.joshfinnie.com/blog/fastapi-and-react-in-2025/](https://www.joshfinnie.com/blog/fastapi-and-react-in-2025/) (MEDIUM confidence)
- FastAPI + Vite full-stack modern setup: [https://dev.to/stamigos/modern-full-stack-setup-fastapi-reactjs-vite-mui-with-typescript-2mef](https://dev.to/stamigos/modern-full-stack-setup-fastapi-reactjs-vite-mui-with-typescript-2mef) (MEDIUM confidence)
- SQLAlchemy audit log via session events: [https://medium.com/@singh.surbhicse/creating-audit-table-to-log-insert-update-and-delete-changes-in-flask-sqlalchemy-f2ca53f7b02f](https://medium.com/@singh.surbhicse/creating-audit-table-to-log-insert-update-and-delete-changes-in-flask-sqlalchemy-f2ca53f7b02f) (MEDIUM confidence — Flask but same pattern applies to FastAPI/SQLAlchemy)
- Existing v1.1 source code (direct inspection): `api/upload.py`, `storage/models.py`, `config.py`, `pyproject.toml` (HIGH confidence — primary source)
- v2-extraction-errors.md (direct inspection): Real error patterns from Zurich auto policy PDF batch testing (HIGH confidence — primary source)

---

*Architecture research for: extractor_pdf_polizas v2.0 — Web UI, PDF Reports, Human-in-the-Loop Review, Extraction Quality*
*Researched: 2026-03-20*
