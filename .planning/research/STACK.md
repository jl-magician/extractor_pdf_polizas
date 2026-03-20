# Stack Research

**Domain:** Insurance PDF data extraction system — v2.0 Web UI & Extraction Quality additions
**Researched:** 2026-03-20
**Confidence:** HIGH — all versions verified against PyPI; Windows compatibility verified against WeasyPrint docs and GitHub issues

---

## Context

This file documents ONLY the new dependencies needed for v2.0. The existing v1.1 stack is complete and operational:

**Already installed (do not re-add):**
`pydantic>=2.12.5`, `sqlalchemy>=2.0.48`, `alembic>=1.13.0`, `python-dotenv>=1.0.1`, `pymupdf>=1.27.2`, `ocrmypdf>=17.3.0`, `pytesseract>=0.3.13`, `pdf2image>=1.17.0`, `loguru>=0.7`, `anthropic>=0.86.0`, `typer>=0.9.0`, `rich>=13.0.0`, `fastapi>=0.135.1`, `uvicorn[standard]>=0.42.0`, `python-multipart>=0.0.22`, `openpyxl>=3.1.5`, `aiofiles>=25.1.0`

---

## v2.0 Stack Additions (New Dependencies Only)

### Frontend — Server-Rendered Web UI

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `jinja2` | `>=3.1.6` | HTML template rendering in FastAPI | FastAPI's built-in `Jinja2Templates` uses this directly. `pip install "fastapi[standard]"` already pulls it in. The existing FastAPI app gains `app.mount("/static", ...)` and `Jinja2Templates(directory="templates")`. No SPA framework needed — server-rendered HTML is correct for a local agency tool used by one team. |
| HTMX | `2.0.4` via CDN | Partial page updates without page reloads | Loaded as `<script src="https://unpkg.com/htmx.org@2.0.4">` — zero install. HTMX turns FastAPI endpoints that return HTML fragments into interactive UI: upload progress, live table updates, inline field saves. No build step, no JS bundler, no `node_modules`. 14 KB gzipped. |
| Alpine.js | `3.x` via CDN | Client-side micro-state for the review UI | Loaded as `<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js">`. Handles local toggle states (edit mode on/off per field, confirm dialogs, field highlight on hover) that HTMX does not cover. Pairs cleanly with HTMX: HTMX owns server roundtrips, Alpine.js owns in-page state. ~16 KB gzipped. |
| Tailwind CSS | `4.x` via CDN Play | Utility-first styling, no build step | `<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4">` — browser-side JIT compiler. Appropriate for a local tool serving a single agency team; production bundle concerns do not apply. DaisyUI component classes work on top of it for pre-built buttons, modals, and tables. |

**Why HTMX + Jinja2 and not React/Vue/Svelte:** The existing FastAPI backend returns JSON. Adding a SPA requires a separate build pipeline, CORS setup, API versioning discipline, and a new mental model for a backend-focused team. HTMX lets the existing FastAPI routes return HTML fragments instead of JSON with zero architectural change. The human review UI (side-by-side PDF + edit fields) is the most interactive screen and is fully achievable with HTMX form submissions + Alpine.js field toggles.

### PDF Viewer (Browser)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| PDF.js | `5.5.207` via CDN | Render PDFs in-browser for the human review UI | Mozilla's canonical browser PDF renderer. 42K GitHub stars, ships inside Firefox. Used by loading the prebuilt viewer from `https://mozilla.github.io/pdf.js/web/viewer.html` as an `<iframe>` with `?file=` parameter, or by embedding the `pdf.js` worker directly for finer control. No install — served from CDN or copied into `static/`. Handles both text-digital and scanned (post-OCR) PDFs. |

**Integration pattern for human review:** Mount the source PDF as a static file at `/pdfs/{id}/source.pdf` and embed it in the review template:
```html
<iframe src="/static/pdfjs/web/viewer.html?file=/pdfs/{{ poliza.id }}/source.pdf"
        width="50%" height="100%"></iframe>
<div class="fields-panel" style="width:50%">
  <!-- HTMX-driven field editor on the right -->
</div>
```
Copy the PDF.js `web/` and `build/` directories into `policy_extractor/static/pdfjs/`. No npm required — download the prebuilt release zip from GitHub.

### PDF Report Generation

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `fpdf2` | `>=2.8.3` | Generate PDF reports from extracted poliza data | Pure Python, no system dependencies. Supports Jinja2 templating (`FPDF.write_html()` + Jinja-rendered HTML), tables, custom fonts, headers/footers. Works on Windows 11 without any GTK/cairo/Pango installation. v2.8.7 current (Feb 2026), Python 3.10+. |

**Why fpdf2 and not WeasyPrint:** WeasyPrint 68.1 requires MSYS2 + `pacman -S mingw-w64-x86_64-pango` on Windows, manual `WEASYPRINT_DLL_DIRECTORIES` env var configuration, and is flagged as malware by some Windows antivirus products (documented in their own release notes). For a local Windows 11 deployment, that installation friction is unacceptable. fpdf2 is `pip install fpdf2` with no system prerequisites.

**Why not ReportLab:** ReportLab's open-source version requires learning a low-level drawing API (canvas, frames, flowables). For per-insurer report templates, fpdf2's Jinja2 integration is faster to develop and the templates are HTML-like strings rather than Python drawing calls.

**Report template pattern:**
```python
from fpdf import FPDF, HTMLMixin

class PolizaReport(FPDF, HTMLMixin):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Resumen de Póliza", align="C")

def generate_report(poliza: Poliza, template_html: str) -> bytes:
    pdf = PolizaReport()
    pdf.add_page()
    pdf.write_html(template_html)   # Jinja2-rendered HTML string
    return pdf.output()
```

Per-insurer templates live in `policy_extractor/reports/templates/{aseguradora}.html`. The FastAPI endpoint streams the result:
```python
from fastapi.responses import StreamingResponse
import io

@app.get("/polizas/{id}/report")
async def download_report(id: int):
    poliza = get_poliza(id)
    pdf_bytes = generate_report(poliza, load_template(poliza.aseguradora))
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=poliza_{id}.pdf"}
    )
```

### Extraction Quality — No New Libraries Needed

All extraction quality improvements use existing stack:

| Feature | Approach | Library |
|---------|---------|---------|
| Cross-field financial validation | `@model_validator(mode='after')` in existing `PolicyExtraction` Pydantic model | `pydantic` (already installed) |
| Auto-OCR fallback for zero-text pages | Add `char_count < 10` check before returning text; re-route through existing `ocrmypdf` pipeline | `pymupdf` + `ocrmypdf` (already installed) |
| Field exclusion list | Config key in `config.json` → `Settings` model; post-extraction filter strips excluded fields | `pydantic` + `python-dotenv` (already installed) |
| Sonnet review pass for `campos_adicionales` | Second Claude call with `claude-sonnet` + existing `tool_use` pattern | `anthropic` (already installed) |
| Prompt improvements | Edit `policy_extractor/extraction/prompts.py` | No library change |
| Correction storage (human review) | New `corrections` table in SQLite via Alembic migration | `sqlalchemy` + `alembic` (already installed) |

**Cross-field validator implementation:**
```python
from pydantic import model_validator
from decimal import Decimal

class PolicyExtraction(BaseModel):
    prima_total: Decimal | None = None
    primer_pago: Decimal | None = None
    subsecuentes: Decimal | None = None
    financiamiento: Decimal | None = None
    otros_servicios_contratados: Decimal | None = None

    @model_validator(mode='after')
    def check_financial_consistency(self) -> 'PolicyExtraction':
        if all(v is not None for v in [self.prima_total, self.primer_pago]):
            if self.primer_pago > self.prima_total * Decimal('1.1'):
                # Flag as suspicious — primer_pago exceeds prima_total by >10%
                # Do NOT raise — log warning and continue (extraction still valid)
                import warnings
                warnings.warn(
                    f"primer_pago ({self.primer_pago}) > prima_total ({self.prima_total})"
                )
        return self
```

---

## Complete v2.0 pyproject.toml Additions

```toml
[project]
dependencies = [
    # === Existing v1.1 (do not change) ===
    "pydantic>=2.12.5",
    "sqlalchemy>=2.0.48",
    "alembic>=1.13.0",
    "python-dotenv>=1.0.1",
    "pymupdf>=1.27.2",
    "ocrmypdf>=17.3.0",
    "pytesseract>=0.3.13",
    "pdf2image>=1.17.0",
    "loguru>=0.7",
    "anthropic>=0.86.0",
    "typer>=0.9.0",
    "rich>=13.0.0",
    "fastapi>=0.135.1",
    "uvicorn[standard]>=0.42.0",
    "python-multipart>=0.0.22",
    "openpyxl>=3.1.5",
    "aiofiles>=25.1.0",
    # === New for v2.0 ===
    "jinja2>=3.1.6",
    "fpdf2>=2.8.3",
]
```

**Browser assets (no pip install):**
- HTMX 2.0.4 — load from CDN in base template
- Alpine.js 3.x — load from CDN in base template
- Tailwind CSS 4.x Play CDN — load from CDN in base template
- PDF.js 5.5.207 — download prebuilt zip from GitHub, copy into `policy_extractor/static/pdfjs/`

```bash
pip install "jinja2>=3.1.6" "fpdf2>=2.8.3"
```

---

## What NOT to Add for v2.0

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `weasyprint` | Requires MSYS2 + Pango DLL installation on Windows; flagged as malware by some AV; `WEASYPRINT_DLL_DIRECTORIES` env var required. Unacceptable friction for a local Windows 11 deployment. | `fpdf2` — pure Python, `pip install fpdf2`, zero system dependencies |
| React / Vue / Svelte | Requires Node.js, npm, build pipeline, bundler configuration, separate dev server, CORS headers on FastAPI. The UI is a single-user local tool, not a SaaS product. | HTMX + Jinja2 — backend-rendered HTML fragments, zero JS build infrastructure |
| `streamlit` | Spins up a separate process with its own server, owns the entire page layout, and has a non-standard execution model (reruns whole script on each widget change). Does not integrate with the existing FastAPI/SQLAlchemy stack. | HTMX + Jinja2 templates mounted directly on the FastAPI app |
| `flask` + `flask-wtf` | Would require running a second WSGI server alongside FastAPI. Flask has no benefit over FastAPI's Jinja2 support. | Existing FastAPI + `Jinja2Templates` |
| `reportlab` | Low-level drawing API (canvas, frames, flowables) is significantly more verbose than fpdf2 for document-style reports. Open source version lacks HTML conversion. | `fpdf2` with `write_html()` for template-driven reports |
| `xhtml2pdf` | Wraps ReportLab with HTML-to-PDF conversion but CSS support is limited to CSS 2.1 (no flexbox, no grid), and it has fewer active maintainers than fpdf2. | `fpdf2` |
| `playwright` / `selenium` + headless Chrome | Correct for pixel-perfect HTML→PDF on Windows, but adds a 200MB+ browser download, subprocess management, and a background Chrome process. Overkill for insurance reports. | `fpdf2` |
| `celery` + `redis` | Already ruled out in v1.1. Still not needed at 200 polizas/month. | `BackgroundTasks` + `ThreadPoolExecutor` (existing) |
| Full SPA state management (Redux, Pinia, Zustand) | The review UI has trivial state: one poliza at a time, toggle edit per field, save. Alpine.js `x-data` handles this in 20 lines. | Alpine.js micro-state |

---

## Architecture Integration

### New File Layout

```
policy_extractor/
├── api/
│   ├── __init__.py       # Mount static, add Jinja2Templates
│   ├── upload.py         # Existing upload endpoints
│   ├── web.py            # New: HTML-returning routes for the UI
│   └── reports.py        # New: PDF report generation endpoints
├── static/
│   ├── css/              # (empty — Tailwind via CDN)
│   ├── js/               # (empty — HTMX/Alpine via CDN)
│   └── pdfjs/            # Copied from PDF.js prebuilt release
│       ├── web/
│       └── build/
├── templates/
│   ├── base.html         # CDN scripts, nav, layout
│   ├── dashboard.html    # Statistics overview
│   ├── upload.html       # PDF upload form
│   ├── polizas/
│   │   ├── list.html     # Paginated poliza table
│   │   ├── detail.html   # Full extraction view + edit
│   │   └── review.html   # Side-by-side: PDF.js + field editor
│   └── partials/
│       ├── field_row.html         # HTMX-swappable field row
│       └── upload_progress.html   # Job status fragment
├── reports/
│   ├── generator.py      # fpdf2 report generation logic
│   └── templates/        # Per-insurer Jinja2 HTML templates
│       ├── zurich_auto.html
│       ├── axa_auto.html
│       └── default.html
└── validation/
    └── financial.py      # Cross-field Pydantic validators (no new library)
```

### FastAPI Route Pattern

New routes return `HTMLResponse` (full page) or HTML fragments (HTMX partial):

```python
# policy_extractor/api/web.py
from fastapi import Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

templates = Jinja2Templates(directory="policy_extractor/templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    stats = get_extraction_stats()
    return templates.TemplateResponse("dashboard.html", {"request": request, "stats": stats})

@app.get("/polizas/{id}/review", response_class=HTMLResponse)
async def review_poliza(request: Request, id: int):
    poliza = get_poliza(id)
    return templates.TemplateResponse("polizas/review.html", {"request": request, "poliza": poliza})

@app.put("/polizas/{id}/fields/{field_name}", response_class=HTMLResponse)
async def update_field(request: Request, id: int, field_name: str, value: str = Form(...)):
    """HTMX endpoint — returns updated field row HTML fragment after saving."""
    update_poliza_field(id, field_name, value)
    store_correction(id, field_name, value)
    poliza = get_poliza(id)
    return templates.TemplateResponse(
        "partials/field_row.html",
        {"request": request, "field": field_name, "value": value, "poliza": poliza}
    )
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `fpdf2` | `WeasyPrint` | If deploying on Linux/macOS only — WeasyPrint produces better CSS rendering. On Windows, avoid unless willing to maintain MSYS2 toolchain. |
| HTMX + Jinja2 | React + separate FastAPI JSON API | If building a multi-tenant SaaS with complex client-side state (real-time collaboration, offline support, mobile app sharing the API). Not applicable here. |
| PDF.js (self-hosted static files) | `pdf-lib` JS library | `pdf-lib` is for creating/modifying PDFs in JS, not displaying them. Wrong category. |
| Alpine.js 3.x | htmx extensions only | If all interactivity is server-round-trip-based and no local toggle state is needed. Alpine.js can be dropped if the review UI simplifies enough. |
| Tailwind CDN Play | PostCSS build pipeline | When deploying to production at scale with many users and bundle size matters. Not applicable for a local single-agency tool. |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `jinja2>=3.1.6` | `fastapi>=0.135.1` | FastAPI uses Jinja2 internally for `Jinja2Templates`. Version pinned to >=3.1.6 (Mar 2025 release). |
| `fpdf2>=2.8.3` | Python 3.11+ | fpdf2 requires Python >=3.10; compatible with project's Python 3.11+ baseline. |
| PDF.js 5.5.207 | Chromium 118+, Firefox 115+, modern Edge | Modern browsers only. Local deployment — browser version is controlled by the agency team. |
| HTMX 2.0.4 | Any modern browser | No Python version dependency — CDN-loaded JS. |
| Alpine.js 3.x | Any modern browser | No Python version dependency — CDN-loaded JS. |

---

## Sources

- [PyPI: fpdf2](https://pypi.org/project/fpdf2/) — v2.8.7 verified Feb 28, 2026 (HIGH confidence)
- [fpdf2 documentation](https://py-pdf.github.io/fpdf2/index.html) — Jinja2 template support, `write_html()`, FastAPI integration confirmed
- [PyPI: Jinja2](https://pypi.org/project/Jinja2/) — v3.1.6 verified Mar 2025 (HIGH confidence)
- [PyPI: aiofiles](https://pypi.org/project/aiofiles/) — v25.1.0 verified Oct 2025 (HIGH confidence)
- [WeasyPrint first steps docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) — Windows requires MSYS2 + Pango; antivirus false positive warning documented (HIGH confidence)
- [WeasyPrint GitHub issue #2105](https://github.com/Kozea/WeasyPrint/issues/2105) — Windows MSYS2 guidance, ongoing DLL path issues
- [PDF.js GitHub releases](https://github.com/mozilla/pdf.js/releases) — v5.5.207 latest stable (Mar 2025) (HIGH confidence)
- [HTMX docs](https://htmx.org/docs/) — v2.0.4 CDN pattern verified (HIGH confidence)
- [FastAPI templating docs](https://fastapi.tiangolo.com/advanced/templates/) — `Jinja2Templates` + `StaticFiles` mount pattern confirmed (HIGH confidence)
- [Pydantic validators docs](https://docs.pydantic.dev/latest/concepts/validators/) — `@model_validator(mode='after')` cross-field pattern confirmed (HIGH confidence)
- [TestDriven.io: FastAPI + HTMX](https://testdriven.io/blog/fastapi-htmx/) — HTMX + FastAPI HTML fragment pattern (MEDIUM confidence)

---

*Stack research for: extractor_pdf_polizas v2.0 (Web UI, PDF reports, extraction quality, human review)*
*Researched: 2026-03-20*
