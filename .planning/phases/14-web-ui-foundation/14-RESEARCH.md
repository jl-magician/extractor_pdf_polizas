# Phase 14: Web UI Foundation - Research

**Researched:** 2026-03-20
**Domain:** HTMX + Jinja2 + FastAPI server-rendered UI, batch upload workflows, SQLAlchemy job persistence
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Upload supports multiple files at once — user loads all PDFs first, then submits the batch. No additional PDFs can be added while a batch is processing
- **D-02:** Both drag-and-drop and file picker supported for selecting PDFs
- **D-03:** While batch processes, show an overall progress bar (not per-file progress)
- **D-04:** When all PDFs in batch finish, show a summary table (one row per PDF: status, poliza number, aseguradora) with option to click into each detail
- **D-05:** Batch results are exportable in all supported formats (JSON, Excel, CSV) directly from the results screen
- **D-06:** If a file in the batch fails, continue processing remaining files — show failures in the summary at the end
- **D-07:** Job history persists across server restarts (stored in database, not in-memory)
- **D-08:** User can name a batch job for easy identification
- **D-09:** Job history page shows past batches with option to re-download results
- **D-10:** Default visible columns: numero_poliza, aseguradora, tipo_seguro, nombre_contratante, evaluation_score
- **D-11:** List summary bar shows: total PDFs processed, total warnings, count of low-score records needing review
- **D-12:** Collapsible filter panel (not always visible, toggleable)
- **D-13:** Free-text search across multiple fields (poliza number, contratante name, aseguradora)
- **D-14:** "Load more" pagination (not page numbers)
- **D-15:** Dashboard is the landing page (default view when user opens the app)
- **D-16:** Quick health overview: total polizas, warning count, average evaluation score
- **D-17:** Date range selector (last 7 days, last 30 days, custom range)
- **D-18:** "Records needing review" shows polizas with evaluation_score below threshold OR any validation_warnings
- **D-19:** Sidebar navigation (always visible on the left, like Linear/Notion)
- **D-20:** Five pages: Dashboard (landing), Upload (batch workflow), Poliza List, Poliza Detail, Job History
- **D-21:** Tailwind CSS via CDN — utility classes, no build step needed
- **D-22:** UI language: Spanish (matching domain terms and field names)
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

### Deferred Ideas (OUT OF SCOPE)
- Inline field editing and corrections audit trail — Phase 15
- Side-by-side PDF + extraction review view — Phase 15
- PDF report generation with per-insurer templates — Phase 16
- Auto-triggered Sonnet evaluation on batch samples — Phase 16
- WebSocket/SSE for real-time progress (polling is sufficient for single-user) — Out of Scope per REQUIREMENTS.md
- Authentication/user management — Out of Scope per REQUIREMENTS.md
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | User can upload PDFs and view extraction results in a browser interface | Batch upload endpoint redesign with `list[UploadFile]`, HTMX multipart form, polling pattern for job status |
| UI-02 | User can search and filter the policy list by aseguradora, date range, and status | Existing GET /polizas query filters extended with free-text; HTMX hx-get + hx-trigger="keyup delay:300ms" pattern |
| UI-05 | User can view a dashboard with extraction statistics and quality metrics | SQLAlchemy aggregate queries (COUNT, AVG, JSON_LENGTH) on existing polizas table; Jinja2 card template |
| UI-06 | System retains uploaded PDFs for review UI display (~1 GB/year at current volume) | Convert upload.py line 164 `pdf_path.unlink()` to copy/move to `data/pdfs/{poliza_id}.pdf`; FileResponse for PDF viewer |
</phase_requirements>

---

## Summary

Phase 14 adds a browser-based interface on top of the existing FastAPI backend using HTMX 2.0.8 + Jinja2 3.1.6 + Tailwind CSS v4 (CDN). No Node.js build step is required — Tailwind is loaded via `<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4">` and HTMX via `<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js">`. The approach is to add HTML-returning routes alongside the existing JSON routes in the FastAPI app, mount Jinja2Templates and StaticFiles at startup, and use HTMX attributes to create dynamic interactions without any client-side JavaScript framework.

The biggest structural change is migrating from the current in-memory `_job_store` dict in `upload.py` to a persistent `batch_jobs` SQLite table (D-07). The current upload route accepts one file; it must be redesigned for `list[UploadFile]` (D-01). HTMX polling with `hx-trigger="every 2s"` drives the progress bar (D-03) and replaces the batch result panel when the server returns `HX-Trigger: done` in the response headers. PDF retention is a one-line change on line 164 of `upload.py` — change `pdf_path.unlink(missing_ok=True)` to a copy into `data/pdfs/{poliza_id}.pdf` (D-25/UI-06).

The existing export functions (`export_xlsx`, `export_csv` in `export.py`) and JSON serialization (`orm_to_schema`) are reused directly for download endpoints — no new export logic is needed.

**Primary recommendation:** Implement in five waves: (1) infrastructure — jinja2 install, static mount, base template, sidebar layout; (2) database — BatchJob ORM model + migration + migration from in-memory store; (3) upload UI — multipart batch form, HTMX polling, summary table; (4) poliza list + detail pages + export downloads; (5) dashboard + job history pages.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Jinja2 | 3.1.6 (latest) | Server-side HTML templating | Native FastAPI/Starlette integration; already a transitive dep via FastAPI |
| HTMX | 2.0.8 (CDN) | Hypermedia-driven AJAX without JS framework | Matches architecture decision D-23; no build step; server controls all state |
| Tailwind CSS | v4 (CDN) | Utility-first styling without build step | Decision D-21; v4 via `@tailwindcss/browser@4` CDN tag replaces the old v3 CDN |
| FastAPI StaticFiles | (bundled in starlette) | Serve CSS/JS/icon static assets | Required to mount `/static` directory for any project-authored assets |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-multipart | 0.0.9 (already in pyproject.toml) | Parse multipart/form-data from UploadFile | Already installed; required for any file upload form |
| openpyxl | 3.1.5 (already installed) | Excel export from batch results and detail page | Already installed via export.py; no new dep needed |

### CDN URLs (confirmed versions)
```html
<!-- HTMX 2.0.8 -->
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"></script>

<!-- Tailwind CSS v4 browser CDN (no build step) -->
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
```

### What to Add to pyproject.toml
Only Jinja2 is missing from the declared dependencies. `python-multipart` is already listed. `fpdf2` is NOT needed for Phase 14 (it is Phase 16).

```bash
# Verify jinja2 is already present as transitive dep before adding:
pip show jinja2  # should show 3.1.6 — add explicitly to pyproject.toml anyway
```

**Installation (add to pyproject.toml `dependencies`):**
```
"jinja2>=3.1.6",
```

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Tailwind v4 CDN | Tailwind v3 CDN (`https://cdn.tailwindcss.com`) | v3 CDN is "development only" per official docs; v4 via `@tailwindcss/browser` is the current recommended CDN approach |
| HTMX polling | SSE / WebSocket | Explicitly out of scope per REQUIREMENTS.md; polling is sufficient for single-user |
| Server-side free-text search (DB LIKE query) | Client-side JS filter | Server query is consistent with HTMX architecture; no JS needed; prefer for correctness |

---

## Architecture Patterns

### Recommended Project Structure
```
policy_extractor/
├── api/
│   ├── __init__.py          # Add: Jinja2Templates mount, StaticFiles mount, HTML routes
│   ├── upload.py            # Modify: list[UploadFile], DB-backed batch jobs, PDF retention
│   └── ui/                  # New: HTML-returning route modules (one per page group)
│       ├── __init__.py
│       ├── dashboard.py     # GET / → dashboard.html
│       ├── polizas.py       # GET /ui/polizas, GET /ui/polizas/{id}
│       └── jobs.py          # GET /ui/jobs, GET /ui/jobs/{batch_id}
├── storage/
│   └── models.py            # Add: BatchJob ORM model
├── templates/               # New: Jinja2 templates
│   ├── base.html            # Sidebar layout, CDN script tags
│   ├── dashboard.html
│   ├── upload.html
│   ├── poliza_list.html
│   ├── poliza_detail.html
│   ├── job_history.html
│   └── partials/            # HTMX partial responses (no <html>/<body> wrapper)
│       ├── batch_progress.html
│       ├── batch_summary.html
│       ├── poliza_rows.html
│       └── dashboard_stats.html
└── static/                  # New: project-authored assets (optional — CDN handles Tailwind/HTMX)
    └── app.css              # Custom overrides only (drag-drop highlight, sidebar widths)
```

### Pattern 1: Mounting Templates and Static Files in FastAPI

Add to `api/__init__.py` alongside existing JSON routes:

```python
# Source: https://fastapi.tiangolo.com/advanced/templates/
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: DbDep):
    # ... query dashboard stats ...
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"stats": stats},
    )
```

**Key requirement:** Every HTML route MUST declare `request: Request` as a parameter and pass `request=request` to `TemplateResponse`. The `request` object is required for `url_for()` to work inside templates.

### Pattern 2: HTMX Polling for Batch Job Progress

The HTMX progress bar polling pattern — server signals done via response header:

```html
<!-- In upload.html — polling div, replaced by batch_summary.html when done -->
<div id="batch-status"
     hx-get="/ui/batch/{batch_id}/status"
     hx-trigger="every 2s"
     hx-swap="outerHTML">
  <!-- batch_progress.html partial rendered here -->
  <progress value="{{ completed }}" max="{{ total }}"></progress>
  <p>{{ completed }} / {{ total }} procesados</p>
</div>
```

Server endpoint for polling — returns partial HTML:

```python
# Source: https://htmx.org/examples/progress-bar/
from fastapi.responses import HTMLResponse
from fastapi import Response

@router.get("/ui/batch/{batch_id}/status")
def batch_status(batch_id: str, request: Request, db: DbDep, response: Response):
    batch = db.get(BatchJob, batch_id)
    if batch.status in ("complete", "failed"):
        # Signal HTMX to stop polling and trigger final UI swap
        response.headers["HX-Trigger"] = "batchDone"
        return templates.TemplateResponse(
            request=request,
            name="partials/batch_summary.html",
            context={"batch": batch},
        )
    return templates.TemplateResponse(
        request=request,
        name="partials/batch_progress.html",
        context={"batch": batch},
    )
```

When `HX-Trigger: batchDone` is returned, a second element on the page listens:
```html
<div hx-get="/ui/batch/{batch_id}/results"
     hx-trigger="batchDone from:body"
     hx-swap="innerHTML"
     id="results-panel">
</div>
```

### Pattern 3: Multiple File Upload with HTMX

```html
<!-- Source: https://htmx.org/examples/file-upload/ -->
<form id="upload-form"
      hx-post="/polizas/upload/batch"
      hx-encoding="multipart/form-data"
      hx-target="#batch-status"
      hx-swap="outerHTML">
  <input type="text" name="batch_name" placeholder="Nombre del lote (ej: Zurich Marzo 2026)">
  <input type="file" name="files" multiple accept=".pdf">
  <button type="submit">Procesar</button>
</form>
```

FastAPI batch upload endpoint:

```python
# Source: https://fastapi.tiangolo.com/tutorial/request-files/
@router.post("/polizas/upload/batch", status_code=202)
async def upload_batch(
    files: list[UploadFile] = File(...),
    batch_name: str = Form(""),
    db: Session = Depends(get_db),
):
    # Create BatchJob row, spawn threads per file, return batch_progress partial
```

### Pattern 4: BatchJob ORM Model (new model in models.py)

```python
class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    batch_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|processing|complete|failed
    total_files: Mapped[int] = mapped_column(default=0)
    completed_files: Mapped[int] = mapped_column(default=0)
    failed_files: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    results_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of per-file results
```

Alembic migration for `batch_jobs` follows the established pattern (migration `004_batch_jobs.py`, `render_as_batch=True`, inspector guard for idempotency on fresh DBs).

### Pattern 5: File Download Endpoint

```python
# Source: https://fastapi.tiangolo.com/advanced/custom-response/
from fastapi.responses import FileResponse
import tempfile, os

@router.get("/polizas/{poliza_id}/export/xlsx")
def download_xlsx(poliza_id: int, db: DbDep):
    poliza = _load_poliza_with_relations(poliza_id, db)  # 404 if not found
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    export_xlsx([poliza], Path(tmp.name))
    return FileResponse(
        path=tmp.name,
        filename=f"poliza_{poliza.numero_poliza}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    # Note: FileResponse streams the file; temp file cleanup needs BackgroundTask
```

Use `BackgroundTasks` to delete the temp file after streaming:

```python
from fastapi import BackgroundTasks

@router.get("/polizas/{poliza_id}/export/xlsx")
def download_xlsx(poliza_id: int, db: DbDep, background_tasks: BackgroundTasks):
    # ... generate tmp file ...
    background_tasks.add_task(os.unlink, tmp.name)
    return FileResponse(path=tmp.name, filename="...", media_type="...")
```

### Pattern 6: PDF Retention (UI-06 fix)

Change in `upload.py` line 164 (and the cache-hit branch on line 134):

```python
# BEFORE (delete after extraction):
pdf_path.unlink(missing_ok=True)

# AFTER (retain at data/pdfs/{poliza_id}.pdf):
import shutil
PDFS_RETENTION_DIR = Path("data/pdfs")
PDFS_RETENTION_DIR.mkdir(parents=True, exist_ok=True)
dest = PDFS_RETENTION_DIR / f"{poliza_orm_id}.pdf"
shutil.copy2(str(pdf_path), str(dest))
pdf_path.unlink(missing_ok=True)  # remove from uploads/, keep copy in data/pdfs/
```

The `poliza_orm_id` must be retrieved from the upserted Poliza row after `upsert_policy()`.

### Pattern 7: "Load More" Pagination

HTMX append-style load more using `hx-swap="beforeend"` on the table body:

```html
<button hx-get="/ui/polizas?skip={{ next_skip }}&limit=50{{ filter_params }}"
        hx-target="#poliza-rows"
        hx-swap="beforeend">
  Cargar más
</button>
```

Server returns only `<tr>` rows (no `<table>` wrapper) when the request has `HX-Request: true` header.

### Pattern 8: Free-Text Search via HTMX

Server-side LIKE query triggered on keyup with debounce:

```html
<input type="text"
       name="q"
       hx-get="/ui/polizas/search"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#poliza-rows"
       hx-swap="innerHTML">
```

Backend adds `WHERE (numero_poliza LIKE :q OR nombre_contratante LIKE :q OR aseguradora LIKE :q)`.

### Anti-Patterns to Avoid
- **Returning full HTML page from HTMX partial endpoints:** Partial endpoints must return only the target fragment (no `<html>`, `<body>`, `<head>` tags). Full-page templates are only for direct browser navigation.
- **Importing Jinja2Templates at module level in routers:** Instantiate once in `api/__init__.py` and pass to routers as a dependency or via shared module — do NOT create a second `Jinja2Templates` instance in each router file.
- **Synchronous blocking in async routes:** `export_xlsx` uses openpyxl synchronous I/O. For async route handlers, wrap with `run_in_executor` or use a sync route (FastAPI runs sync routes in a thread pool automatically). Prefer `def` (sync) for export endpoints.
- **Polling against the in-memory job store after migration:** Once BatchJob is in the DB, the old `_get_job()` dict function must NOT be used for UI polling — it won't survive server restart.
- **Tailwind v4 CDN `@apply` directives in a plain `<style>` tag:** Tailwind v4 browser CDN requires `<style type="text/tailwindcss">` for `@apply` support — a plain `<style>` tag won't process Tailwind directives.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Template rendering | String concatenation / f-string HTML | Jinja2Templates | XSS escaping, template inheritance, `url_for()` |
| File download Content-Disposition | Manual response headers | FastAPI FileResponse with `filename=` param | Sets correct MIME type, Content-Length, ETag automatically |
| Polling lifecycle control | JS `setInterval` + custom stop logic | HTMX `hx-trigger="every Ns"` + `HX-Trigger` response header | Server controls polling stop; no client JS needed |
| Upload progress on batch | Custom XHR progress events | HTMX `htmx:xhr:progress` event listener (one-liner JS) | 3 lines of JS vs custom XMLHttpRequest wrapper |
| SQLite column guard on migration | Custom schema diffing | Inspector guard pattern (already established in this codebase) | Prevents "duplicate column" on fresh DBs that used `create_all` |
| Dashboard aggregate stats | Python loops over all ORM objects | SQLAlchemy `func.count()`, `func.avg()`, scalar subqueries | Executes in DB, O(1) query vs O(N) Python |

**Key insight:** HTMX + Jinja2 eliminates the need for a REST API contract between backend and frontend — the server IS the frontend. Resist the temptation to create `application/json` endpoints "for the UI" — have HTML endpoints return HTML fragments directly.

---

## Common Pitfalls

### Pitfall 1: Request Object Not Passed to TemplateResponse
**What goes wrong:** `AttributeError: 'NoneType' object has no attribute 'url_for'` or `url_for()` fails in template
**Why it happens:** `TemplateResponse` requires `request=request` kwarg (FastAPI/Starlette >= 0.93); older examples used positional args that are now deprecated
**How to avoid:** Always `return templates.TemplateResponse(request=request, name="...", context={...})`
**Warning signs:** `url_for('static', path='...')` returns empty string in rendered template

### Pitfall 2: HTMX Partial Returns Full Page (Double Layout)
**What goes wrong:** Sidebar appears twice; the page looks broken after first HTMX swap
**Why it happens:** HTMX partial endpoint returned `base.html` (with full sidebar) instead of a bare fragment template
**How to avoid:** Create separate partial templates in `templates/partials/` that contain ONLY the fragment. Full-page routes use `{% extends "base.html" %}`. Never call a full-page template from an HTMX partial route.
**Warning signs:** Any HTML response from a polled endpoint that contains `<html>` or `{% block content %}`

### Pitfall 3: BatchJob.results_json Grows Unboundedly for Large Batches
**What goes wrong:** Memory spike when loading batch history for batches with 100+ PDFs
**Why it happens:** Full PolicyExtraction JSON per file stored as TEXT in `results_json` — 100 polizas × ~10 KB = 1 MB per batch row
**How to avoid:** Store only summary per file (status, poliza_id, numero_poliza, aseguradora, error) in `results_json` — full extraction is in the polizas table
**Warning signs:** `/ui/jobs/{batch_id}` is slow to load for large batches

### Pitfall 4: PDF Retention Path Uses job_id Instead of poliza_id
**What goes wrong:** `data/pdfs/{job_id}.pdf` exists but no route can serve it by poliza_id — the Phase 15 PDF viewer breaks
**Why it happens:** `_run_extraction` has the job_id readily available but must query the DB for the poliza.id after upsert
**How to avoid:** After `upsert_policy(session, policy)`, query `Poliza.id` and use it as the filename: `data/pdfs/{poliza.id}.pdf`
**Warning signs:** Poliza detail page shows PDF iframe 404 error

### Pitfall 5: Thread-Safety on BatchJob Counter Updates
**What goes wrong:** `completed_files` count is incorrect when multiple PDF extraction threads update simultaneously
**Why it happens:** SQLite WAL mode + multiple threads each doing `batch.completed_files += 1` have read-modify-write races
**How to avoid:** Use SQLAlchemy atomic update: `db.execute(update(BatchJob).where(BatchJob.id == batch_id).values(completed_files=BatchJob.completed_files + 1))` — never read-modify-write from multiple threads
**Warning signs:** batch progress bar stalls at N-1 or N-2; completed_files < actual completed count

### Pitfall 6: Static Directory Does Not Exist at Startup
**What goes wrong:** `RuntimeError: directory 'static' does not exist` when FastAPI starts
**Why it happens:** `StaticFiles(directory="static")` raises if the directory is missing at mount time
**How to avoid:** Create `static/` directory (even empty) and commit a `.gitkeep`. Or create it programmatically in `on_startup` before mounting.
**Warning signs:** Server starts successfully in dev but fails on fresh clone

### Pitfall 7: Tailwind v4 CDN Incompatibility with v3 Class Names
**What goes wrong:** Certain Tailwind v3 utility classes don't work with v4 CDN
**Why it happens:** Tailwind v4 introduced breaking changes to some utility names and the CDN is the full v4 build
**How to avoid:** Use the official v4 class documentation. The most common differences: `divide-*`, `ring-*`, `shadow-*` utilities have subtle changes. Stick to basic layout utilities (`flex`, `grid`, `p-*`, `m-*`, `text-*`, `bg-*`) which are stable across versions.
**Warning signs:** Styling looks correct in isolation but breaks in specific utility combinations

---

## Code Examples

Verified patterns from official sources:

### Dashboard Aggregate Query (SQLAlchemy)
```python
# Source: SQLAlchemy 2.0 ORM Query Guide
from sqlalchemy import func, select, case

def get_dashboard_stats(db: Session, since: date | None = None) -> dict:
    stmt = select(
        func.count(Poliza.id).label("total"),
        func.avg(Poliza.evaluation_score).label("avg_score"),
    )
    if since:
        stmt = stmt.where(Poliza.extracted_at >= since)
    row = db.execute(stmt).one()

    # Count polizas with any validation_warnings (non-null, non-empty)
    warnings_stmt = select(func.count(Poliza.id)).where(
        Poliza.validation_warnings.is_not(None)
    )
    if since:
        warnings_stmt = warnings_stmt.where(Poliza.extracted_at >= since)
    total_warnings = db.scalar(warnings_stmt)

    return {
        "total": row.total or 0,
        "avg_score": round(row.avg_score or 0, 2),
        "total_warnings": total_warnings or 0,
    }
```

### Jinja2 Base Template with Sidebar
```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Extractor de Pólizas{% endblock %}</title>
  <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
  <script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"></script>
</head>
<body class="flex h-screen bg-gray-50">
  <!-- Sidebar -->
  <nav class="w-56 bg-white border-r border-gray-200 flex flex-col p-4 gap-2 shrink-0">
    <a href="{{ url_for('dashboard') }}" class="...">Panel Principal</a>
    <a href="{{ url_for('upload_page') }}" class="...">Cargar PDFs</a>
    <a href="{{ url_for('poliza_list') }}" class="...">Pólizas</a>
    <a href="{{ url_for('job_history') }}" class="...">Historial</a>
  </nav>
  <!-- Main content -->
  <main class="flex-1 overflow-auto p-6">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

### HTMX Polling Stop via HX-Trigger Header
```python
# Source: https://htmx.org/examples/progress-bar/
from fastapi import Response

@router.get("/ui/batch/{batch_id}/status")
def batch_status(batch_id: str, request: Request, db: DbDep, response: Response):
    batch = db.get(BatchJob, batch_id)
    if batch is None:
        raise HTTPException(status_code=404)
    if batch.status in ("complete", "failed"):
        response.headers["HX-Trigger"] = "batchDone"
    pct = int(batch.completed_files / max(batch.total_files, 1) * 100)
    return templates.TemplateResponse(
        request=request,
        name="partials/batch_progress.html",
        context={"batch": batch, "pct": pct},
    )
```

### Alembic Migration for batch_jobs (pattern 004)
```python
# alembic/versions/004_batch_jobs.py
def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "batch_jobs" not in inspector.get_table_names():
        op.create_table(
            "batch_jobs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("batch_name", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_files", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_files", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("results_json", sa.Text(), nullable=True),
        )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tailwind CDN v3 `https://cdn.tailwindcss.com` | Tailwind v4 CDN `@tailwindcss/browser@4` | Tailwind v4.0 released 2025 | v4 CDN requires `<script>` not `<link>`; some utility names changed |
| HTMX 1.x | HTMX 2.0.8 | HTMX 2.0.0 released June 2024 | Breaking change: `hx-on` attribute syntax changed; `htmx:xhr:progress` event unchanged |
| FastAPI TemplateResponse positional args | `TemplateResponse(request=request, name=..., context=...)` kwargs | FastAPI 0.100+ | Old positional `name, context, request` order deprecated — always use keyword args |

**Deprecated/outdated:**
- `@app.on_event("startup")`: FastAPI now recommends `lifespan` context manager (but `on_event` still works in 0.135.1 — no need to change in Phase 14)
- HTMX 1.x `hx-on` syntax: In HTMX 2.x the `hx-on:` attribute syntax changed. Since we use CDN at 2.0.8, use only 2.x documented syntax.

---

## Open Questions

1. **Batch name auto-generation vs required user input**
   - What we know: D-08 says user can name the batch; Claude's Discretion says auto-generated default name is acceptable
   - What's unclear: Whether a blank name should be allowed or auto-filled with "Lote {date}"
   - Recommendation: Auto-generate default `"Lote {YYYY-MM-DD HH:MM}"` — user can overwrite before submitting. Never block submission on name.

2. **Evaluation score threshold for "needs review"**
   - What we know: D-18 uses evaluation_score below threshold OR any validation_warnings
   - What's unclear: Exact threshold value
   - Recommendation: Default threshold = 0.7 (below 70% = needs review). Store in `settings.py` as `REVIEW_SCORE_THRESHOLD: float = 0.7` so it can be env-var overridden.

3. **HTMX polling interval**
   - What we know: HTMX docs show 600ms for demos; Claude's Discretion
   - What's unclear: What polling interval balances UI responsiveness vs DB query load
   - Recommendation: 2 seconds (`hx-trigger="every 2s"`). Extraction takes 10-60 seconds per PDF; 2s gives good UX without hammering SQLite. Can be tuned.

4. **"Load more" batch size**
   - What we know: Existing API defaults to limit=50
   - Recommendation: Use 25 per "load more" click (initial load 25, each click adds 25). Keeps initial page fast.

5. **Free-text search: client-side vs server query**
   - What we know: Claude's Discretion; small dataset (< 10,000 polizas expected)
   - Recommendation: Server-side LIKE query triggered by HTMX keyup with 300ms debounce. More consistent with HTMX architecture than loading all rows client-side. SQLite LIKE on indexed columns is fast enough.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already configured in pyproject.toml) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_ui.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | POST /polizas/upload/batch returns 202 with batch_id | unit (TestClient) | `pytest tests/test_ui_upload.py -x` | Wave 0 |
| UI-01 | GET /ui/batch/{id}/status returns HTML with progress | unit (TestClient) | `pytest tests/test_ui_upload.py::test_batch_status_html -x` | Wave 0 |
| UI-01 | Dashboard page returns 200 HTML with sidebar | unit (TestClient) | `pytest tests/test_ui_pages.py::test_dashboard_200 -x` | Wave 0 |
| UI-02 | GET /ui/polizas?q=text returns filtered HTML rows | unit (TestClient) | `pytest tests/test_ui_pages.py::test_poliza_search -x` | Wave 0 |
| UI-05 | GET / returns dashboard with stat cards | unit (TestClient) | `pytest tests/test_ui_pages.py::test_dashboard_stats -x` | Wave 0 |
| UI-06 | After extraction, data/pdfs/{id}.pdf exists on disk | unit | `pytest tests/test_ui_upload.py::test_pdf_retained -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_ui_upload.py tests/test_ui_pages.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ui_upload.py` — covers UI-01, UI-06 upload batch endpoint and PDF retention
- [ ] `tests/test_ui_pages.py` — covers UI-01, UI-02, UI-05 HTML page rendering
- [ ] `tests/conftest.py` — confirm in-memory DB override pattern is already present (it is, in `test_upload.py` — copy pattern)
- [ ] `templates/` directory — must exist before any TemplateResponse routes are tested
- [ ] `static/` directory — must exist (even empty) before StaticFiles mount

*(Existing `tests/test_upload.py` covers the old single-file upload API; new `test_ui_upload.py` covers the batch UI endpoint. Both can coexist.)*

---

## Sources

### Primary (HIGH confidence)
- FastAPI official docs (https://fastapi.tiangolo.com/advanced/templates/) — Jinja2Templates setup, TemplateResponse kwargs pattern
- HTMX official docs (https://htmx.org/examples/progress-bar/) — polling with `hx-trigger="every Ns"`, `HX-Trigger` header stop signal
- HTMX official docs (https://htmx.org/examples/file-upload/) — multipart/form-data, `hx-encoding`, `htmx:xhr:progress`
- HTMX official docs (https://htmx.org/attributes/hx-trigger/) — `every` polling syntax, `load` trigger
- FastAPI official docs (https://fastapi.tiangolo.com/tutorial/request-files/) — `list[UploadFile]` multiple file pattern
- FastAPI official docs (https://fastapi.tiangolo.com/advanced/custom-response/) — FileResponse with `filename=` for downloads
- Tailwind CSS official docs (https://tailwindcss.com/docs/installation/play-cdn) — v4 CDN `@tailwindcss/browser@4` script tag
- jsDelivr CDN (https://cdn.jsdelivr.net/npm/htmx.org/package.json) — confirmed HTMX latest version 2.0.8
- Project codebase: `policy_extractor/api/__init__.py`, `upload.py`, `storage/models.py`, `export.py`, `storage/database.py` — all read and verified

### Secondary (MEDIUM confidence)
- WebSearch: FastAPI + HTMX patterns 2025 — confirms CDN + server-rendered approach is current standard
- WebSearch: Tailwind v4 breaking changes — v3 vs v4 CDN tag differences confirmed

### Tertiary (LOW confidence)
- Thread-safety recommendation for SQLite atomic counter updates — based on SQLAlchemy 2.0 UPDATE patterns; specific to WAL mode behavior under concurrent threads (project-specific concern, not directly verified against SQLite WAL docs)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all library versions verified against CDN and pip registry
- Architecture: HIGH — all patterns verified against official FastAPI and HTMX documentation
- Pitfalls: HIGH for structural pitfalls (template partial vs full-page, thread safety for counters); MEDIUM for Tailwind v4 class compatibility (not exhaustively tested)
- Dashboard aggregate queries: HIGH — standard SQLAlchemy func.count/avg patterns
- Validation architecture: HIGH — test framework already in place, gaps clearly identified

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (30 days — HTMX and FastAPI are stable; Tailwind v4 CDN is newly released, check for minor updates)
