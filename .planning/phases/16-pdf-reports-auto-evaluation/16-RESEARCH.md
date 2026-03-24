# Phase 16: PDF Reports & Auto-Evaluation - Research

**Researched:** 2026-03-23
**Domain:** PDF generation (fpdf2), per-insurer YAML config, auto-triggered Sonnet evaluation, campos_adicionales swap detection
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**PDF Generation Approach**
- D-01: Use WeasyPrint for PDF generation — renders Jinja2 HTML templates to PDF, reusing existing template skills. CSS-styled, professional output.
  - **OVERRIDE from STATE.md [v2.0 roadmap]:** WeasyPrint excluded — GTK/Tesseract DLL conflict on Windows 11; use fpdf2 (pure Python, pip-only). D-01 is superseded. The library is fpdf2, not WeasyPrint.
- D-02: Generate PDFs on-the-fly per request (no disk caching). Always reflects latest corrected data. Must complete under 5 seconds (SC-1).
- D-03: "Descargar Reporte" button appears on both the poliza detail page and the review page.
- D-04: Report uses corrected values from the polizas table (post-HITL corrections). No indicators for corrected vs original values.
- D-05: Paper size is Letter (8.5x11 inches) — standard for Mexican business documents.
- D-06: Filename format: `poliza_{numero_poliza}_{aseguradora}.pdf` — e.g., `poliza_12345_zurich.pdf`.

**Report Content & Layout**
- D-07: Report sections (in order): header with insurer branding, general info block, financial summary, asegurados table, coverage table, campos_adicionales key-value list.
- D-08: Asegurados appear as a full table with nombre, parentesco, fecha_nacimiento, RFC.
- D-09: Campos_adicionales shown as a simple key: value list. Always included (even if empty — show "Sin campos adicionales").
- D-10: Per-insurer differentiation via config files with brand_color, field_order, and section toggles. One base template class handles all insurers.
- D-11: Per-insurer config files stored at `policy_extractor/reports/configs/` as YAML files (e.g., `zurich.yaml`, `axa.yaml`). Version-controlled inside the package.

**Auto-Evaluation Trigger**
- D-12: Auto-evaluation triggers after any extraction (batch or single) when the total number of extractions in the recent window reaches >= 10. Default sample percentage: 20%.
- D-13: Sample percentage is configurable via settings (e.g., `EVAL_SAMPLE_PERCENT = 20`).
- D-14: Evaluation runs in the same thread as extraction, right after extraction completes. No separate background thread — adds ~3-5s per evaluated record.
- D-15: Evaluation scores surface in the web UI in two places: (a) colored score badge (green/yellow/red) on poliza list rows and detail page header, (b) aggregate stats (avg score, % evaluated) on the dashboard page.

**Campo Swap Detection**
- D-16: Campo swap detection is integrated into the existing evaluation prompt — extended criteria, not a separate Sonnet pass. One API call covers quality scoring AND swap detection.
- D-17: Swap warnings are appended to the `validation_warnings` JSON array on the Poliza row — consistent with financial cross-validation warnings from Phase 13.
- D-18: Swap detection includes suggested corrections — warning text describes the suspected swap and recommends which field the value should move to. Human reviews and applies the fix via HITL.

### Claude's Discretion
- WeasyPrint installation and CSS print stylesheet design (resolved: use fpdf2)
- Exact color scheme per insurer (can use brand-standard colors)
- Evaluation sampling algorithm (random, stratified by insurer, etc.)
- Score badge color thresholds (e.g., green >= 0.8, yellow >= 0.6, red < 0.6)
- Dashboard aggregate stats layout and positioning
- Swap detection prompt engineering (how to instruct Sonnet to identify swaps)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RPT-01 | User can generate a PDF report from extracted poliza data | fpdf2 2.8.7 installed and smoke-tested; Response(bytes(pdf.output())) pattern confirmed for FastAPI |
| RPT-02 | System supports per-insurer report templates (customizable layout per aseguradora) | YAML configs at `reports/configs/`; PyYAML 6.0.3 available; single FPDF subclass reads config at render time |
| QA-02 | Sonnet evaluation auto-triggered on configurable sample percentage of batch extractions | Hook point identified in `_run_batch_extraction()` and `_run_extraction()`; `random.sample()` for selection; EVAL_SAMPLE_PERCENT in Settings |
| QA-03 | Targeted Sonnet review pass detects campos_adicionales field swaps | Extend `EVAL_SYSTEM_PROMPT` and `build_evaluation_tool()` schema with `campos_swap_suggestions`; append to `validation_warnings` |
</phase_requirements>

---

## Summary

Phase 16 has two largely independent concerns: (1) PDF report generation and (2) auto-triggered evaluation with swap detection. Both can be planned and implemented in separate waves without interdependency.

For PDF generation, fpdf2 2.8.7 is confirmed installed and smoke-tested on Windows 11 Python 3.14.3. The key constraint from the v2.0 roadmap decision overrides the CONTEXT.md D-01: WeasyPrint is banned on this Windows machine; fpdf2 is the chosen library. fpdf2 does NOT support Jinja2 HTML templates — it uses a Python API directly. The per-insurer differentiation (D-10/D-11) must be implemented via YAML config files that a `PolizaReportPDF(FPDF)` subclass reads at render time. Spanish characters (accented vowels, n-tilde) require a Unicode TTF font — built-in Helvetica/Times only support latin-1; DejaVuSans (bundled with fpdf2 via fonttools) is the recommended choice.

For auto-evaluation, the hook points are already identified: `_run_batch_extraction()` in `upload.py` is the primary target for the batch trigger (D-12), while `_run_extraction()` is the single-file target. The `evaluate_policy()` function in `evaluation.py` already does everything needed for scoring; it only requires (a) a trigger decision based on sample rate, and (b) prompt extension for swap detection. The `build_evaluation_tool()` schema needs a new `campos_swap_suggestions` array property. Swap warnings are appended to `validation_warnings` (existing JSON column) per D-17.

**Primary recommendation:** Implement in two plans — Plan 01 for fpdf2 reports module + download route, Plan 02 for auto-eval hook + swap detection prompt extension + UI badges.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fpdf2 | 2.8.7 | PDF generation | Pure Python, pip-only, Windows-safe; confirmed installed and working |
| pyyaml | 6.0.3 | Parse per-insurer YAML config files | Standard Python YAML parser; already available in environment |
| python stdlib `random` | built-in | Sample selection for auto-evaluation | `random.sample()` provides random subset without extra deps |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI `Response` | (existing) | Return PDF bytes inline | `Response(content=bytes(pdf.output()), media_type="application/pdf")` |
| FastAPI `run_in_executor` | (existing) | Wrap synchronous fpdf2 in async route | STATE.md decision: "fpdf2 calls must be wrapped in run_in_executor — synchronous generator blocks FastAPI event loop if called directly in async def" |
| Jinja2 | (existing) | Score badge partials in list/detail UI | Already used; badge HTML rendered server-side as partial template |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| fpdf2 | WeasyPrint | WeasyPrint blocked on Windows 11 (GTK/Tesseract DLL conflict — locked decision) |
| fpdf2 | reportlab | reportlab requires separate license for production use; fpdf2 is MIT |
| YAML insurer configs | Python dicts in code | YAML is version-controlled, editable without touching Python source — per D-11 |
| `random.sample()` | Stratified sampling | Random is simpler; stratified-by-insurer can be added in Phase 17 if needed |

**Installation (already done — confirmed in environment):**
```bash
pip install fpdf2 pyyaml
```
Then add to `pyproject.toml` dependencies:
```toml
"fpdf2>=2.8.7",
"pyyaml>=6.0",
```

**Version verification (confirmed 2026-03-23):**
- fpdf2: 2.8.7 (installed, smoke-tested, `from fpdf import FPDF` works)
- pyyaml: 6.0.3 (installed, `import yaml` works)

---

## Architecture Patterns

### Recommended Project Structure
```
policy_extractor/
├── reports/
│   ├── __init__.py          # exports generate_poliza_report()
│   ├── renderer.py          # PolizaReportPDF(FPDF) class
│   ├── config_loader.py     # load_insurer_config(aseguradora) -> dict
│   └── configs/
│       ├── default.yaml     # fallback config for unknown insurers
│       ├── zurich.yaml
│       ├── axa.yaml
│       └── gnp.yaml         # (one per insurer as needed)
```

### Pattern 1: fpdf2 Response in FastAPI (Synchronous PDF in Async Route)

**What:** fpdf2's `FPDF.output()` is synchronous. Calling it directly inside an `async def` route blocks the event loop. Wrap in `run_in_executor`.

**When to use:** All PDF download routes.

**Example:**
```python
# Source: STATE.md [v2.0 roadmap] + https://py-pdf.github.io/fpdf2/UsageInWebAPI.html
import asyncio
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from policy_extractor.api import get_db
from policy_extractor.storage.models import Poliza
from policy_extractor.reports import generate_poliza_report

router = APIRouter()

@router.get("/ui/polizas/{poliza_id}/report")
async def poliza_report(poliza_id: int, db: Session = Depends(get_db)):
    poliza = db.get(Poliza, poliza_id)
    if poliza is None:
        raise HTTPException(status_code=404)
    loop = asyncio.get_event_loop()
    pdf_bytes = await loop.run_in_executor(None, generate_poliza_report, poliza)
    filename = f"poliza_{poliza.numero_poliza}_{poliza.aseguradora}.pdf"
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
```

### Pattern 2: PolizaReportPDF Class with Config-Driven Layout

**What:** A single `FPDF` subclass reads a per-insurer YAML config to determine brand_color, field_order, section toggles. One class handles all insurers.

**When to use:** All PDF report generation.

**Example:**
```python
# Source: https://py-pdf.github.io/fpdf2/Tutorial.html + verified fpdf2 2.8.7 API
from fpdf import FPDF
from fpdf.fonts import FontFace
from policy_extractor.reports.config_loader import load_insurer_config

class PolizaReportPDF(FPDF):
    def __init__(self, poliza, config: dict):
        super().__init__(orientation="P", unit="mm", format="Letter")
        self.poliza = poliza
        self.config = config
        # Must add Unicode font for Spanish characters (á, é, ñ etc.)
        # DejaVuSans is bundled with fpdf2 via fonttools
        self.add_font("dejavu", style="", fname="DejaVuSans.ttf")
        self.add_font("dejavu", style="B", fname="DejaVuSans-Bold.ttf")

    def header(self):
        brand_color = self.config.get("brand_color", (0, 82, 160))  # default blue
        self.set_fill_color(*brand_color)
        self.rect(0, 0, 216, 20, style="F")  # Letter = 215.9mm wide
        self.set_font("dejavu", "B", 14)
        self.set_text_color(255, 255, 255)
        self.set_y(5)
        self.cell(0, 10, self.poliza.aseguradora.upper(), align="L")

    def render(self) -> bytearray:
        self.add_page()
        self._render_general_info()
        self._render_financial_summary()
        self._render_asegurados_table()
        self._render_coberturas_table()
        self._render_campos_adicionales()
        return self.output()
```

### Pattern 3: fpdf2 Table API for Asegurados and Coberturas

**What:** Use `pdf.table()` context manager for structured tables (asegurados, coberturas).

**When to use:** Asegurados table (D-08) and Coberturas table (D-07).

**Example:**
```python
# Source: https://py-pdf.github.io/fpdf2/Tables.html (verified fpdf2 2.8.7)
from fpdf.fonts import FontFace

def _render_asegurados_table(self):
    self.set_font("dejavu", "B", 10)
    self.cell(0, 8, "Asegurados", new_x="LMARGIN", new_y="NEXT")

    header_style = FontFace(emphasis="B", fill_color=(220, 220, 220))
    with self.table(
        headings_style=header_style,
        col_widths=(60, 30, 30, 40),
        line_height=6,
        borders_layout="MINIMAL",
    ) as table:
        # Header row
        row = table.row()
        for h in ("Nombre", "Parentesco", "Fecha Nac.", "RFC"):
            row.cell(h)
        # Data rows
        for aseg in self.poliza.asegurados:
            row = table.row()
            row.cell(aseg.nombre_descripcion or "-")
            row.cell(aseg.parentesco or "-")
            row.cell(str(aseg.fecha_nacimiento) if aseg.fecha_nacimiento else "-")
            row.cell(aseg.rfc or "-")
```

### Pattern 4: Auto-Evaluation Hook in Batch Worker

**What:** After `_run_batch_extraction()` finishes, check if total extracted >= 10. Sample 20% (configurable) and call `evaluate_policy()` for each sampled poliza.

**When to use:** End of `_run_batch_extraction()` in `upload.py` (D-12, D-14).

**Example:**
```python
# Source: existing evaluation.py patterns + random.sample stdlib
import random
from policy_extractor.config import settings

def _auto_evaluate_batch(session, summaries: list[dict], model: str | None) -> None:
    """Evaluate a random sample of successfully extracted polizas from a batch."""
    successful = [s for s in summaries if s["status"] == "complete" and s["poliza_id"]]
    total = len(successful)
    if total < 10:
        return  # D-12: only trigger when >= 10 in batch
    sample_count = max(1, round(total * settings.EVAL_SAMPLE_PERCENT / 100))
    sampled = random.sample(successful, min(sample_count, total))

    from policy_extractor.evaluation import evaluate_policy
    from policy_extractor.storage.writer import update_evaluation_columns
    from policy_extractor.storage.models import Poliza
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    for entry in sampled:
        poliza = session.execute(
            select(Poliza)
            .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
            .where(Poliza.id == entry["poliza_id"])
        ).scalar_one_or_none()
        if poliza is None:
            continue
        # Reconstruct IngestionResult from cache if available — or pass cached ingestion_result
        # (implementation detail: evaluate_policy needs assembled_text; use ingestion cache)
        eval_result = evaluate_policy(ingestion_result, policy_schema, model=model or EVAL_MODEL_ID)
        if eval_result:
            update_evaluation_columns(session, poliza.numero_poliza, poliza.aseguradora, ...)
```

**Key constraint:** `evaluate_policy()` requires an `IngestionResult` (assembled text) and `PolicyExtraction` (Pydantic schema). The batch worker currently only has `poliza_id` in summaries. Implementation must either (a) pass ingestion_result/policy through the pipeline, or (b) reconstruct from `ingestion_cache` DB table. Option (a) is simpler: pass them through `_run_single_file_extraction()` return value when evaluation is enabled.

### Pattern 5: Extended Evaluation Tool Schema for Swap Detection

**What:** Extend `build_evaluation_tool()` with a `campos_swap_suggestions` array property and extend `EVAL_SYSTEM_PROMPT` with swap detection criteria (D-16).

**When to use:** Replace existing `build_evaluation_tool()` and `EVAL_SYSTEM_PROMPT` in `evaluation.py`.

**Example:**
```python
# Source: evaluation.py existing patterns — extend, not replace
"campos_swap_suggestions": {
    "type": "array",
    "description": (
        "List of suspected campo swap errors in campos_adicionales. "
        "A swap is when a value clearly belongs to a different key than the one it is stored under. "
        "For each swap: identify the source_key (where value is now), the target_key (where it should be), "
        "and the suspicious_value."
    ),
    "items": {
        "type": "object",
        "properties": {
            "source_key": {"type": "string"},
            "target_key": {"type": "string"},
            "suspicious_value": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["source_key", "target_key", "suspicious_value", "reason"],
    },
},
```

Swap warnings are appended to `validation_warnings` (existing JSON array column) as strings like:
`"SWAP: campos_adicionales.{source_key} = '{value}' parece pertenecer a '{target_key}'. Sugerencia: mover a {target_key}."`

### YAML Insurer Config Format

**What:** Minimal YAML schema for per-insurer configuration.

**Example (`zurich.yaml`):**
```yaml
brand_color: [0, 82, 160]      # RGB tuple — Zurich blue
display_name: "Zurich Seguros"
field_order:                    # optional: reorder general info fields
  - numero_poliza
  - nombre_contratante
  - tipo_seguro
  - fecha_emision
sections:
  asegurados: true
  coberturas: true
  campos_adicionales: true
```

**`default.yaml`** fallback used for unrecognized insurers (all sections enabled, neutral color).

### Anti-Patterns to Avoid
- **Calling `pdf.output()` directly in `async def` without executor:** Blocks the event loop — always use `run_in_executor` per STATE.md [v2.0 roadmap].
- **Using built-in Helvetica/Times for Spanish text:** These fonts only support latin-1; Spanish characters (ñ, á, é) will fail silently or raise. Always add a Unicode TTF font.
- **Reusing a single FPDF instance across requests:** FPDF is stateful and not thread-safe. Always create a new instance per request.
- **Storing PDF bytes to disk:** D-02 requires on-the-fly generation; no caching to disk.
- **Making swap detection a separate Sonnet API call:** D-16 requires a single call — extend the existing evaluation tool schema only.
- **Triggering evaluation for batches < 10:** D-12 specifies >= 10 threshold; evaluation on tiny batches wastes API credits.
- **Overwriting `validation_warnings` on evaluation:** Append swap warnings to the existing array — do not replace financial cross-validation warnings already present from Phase 13.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF table layout | Custom cell-drawing loop with column math | `fpdf2 table()` context manager | Handles borders, padding, overflow, page breaks automatically |
| Unicode font loading | Custom TTF parser | `pdf.add_font(fname="DejaVuSans.ttf")` | fpdf2 handles embedding and subsetting |
| Random sample selection | Custom shuffle+slice | `random.sample(population, k)` | Thread-safe, documented, handles edge cases |
| YAML parsing | Custom config parser | `yaml.safe_load()` | Standard; `safe_load` prevents code execution from config files |
| PDF bytes → HTTP response | Temp file write + FileResponse + cleanup | `Response(content=bytes(pdf.output()), media_type="application/pdf")` | No disk I/O, no cleanup task needed |

**Key insight:** fpdf2's table API handles the most complex layout concern (asegurados, coberturas tables). All other report sections are simple `cell()` / `multi_cell()` calls.

---

## Common Pitfalls

### Pitfall 1: Spanish Characters Silently Drop with Built-in Fonts
**What goes wrong:** `pdf.set_font("Helvetica")` then `pdf.cell(text="José Rodríguez")` — accented characters render as boxes or are omitted silently.
**Why it happens:** fpdf2 built-in fonts only support latin-1 (ISO 8859-1). Spanish diacriticals like á, é, í, ó, ú, ñ are outside that range.
**How to avoid:** Always use a Unicode TTF font via `pdf.add_font(fname="DejaVuSans.ttf")` before any text rendering. DejaVuSans is bundled with fonttools (already a dep of fpdf2).
**Warning signs:** Characters in PDF appear as blank or question marks.

### Pitfall 2: Blocking the FastAPI Event Loop
**What goes wrong:** `pdf_bytes = pdf.output()` called directly inside `async def` route — all other requests stall during PDF generation.
**Why it happens:** fpdf2 is synchronous. FastAPI's async routes share a single event loop thread.
**How to avoid:** Wrap in `await loop.run_in_executor(None, generate_fn, args)`. This is a locked decision from STATE.md [v2.0 roadmap].
**Warning signs:** Response times of other endpoints spike when a PDF is being generated.

### Pitfall 3: Auto-Evaluation Missing IngestionResult
**What goes wrong:** `evaluate_policy()` called at batch completion, but `ingestion_result` (assembled PDF text) is no longer available — it was only held in memory during extraction.
**Why it happens:** `_run_batch_extraction()` currently only stores poliza_id/numero_poliza/aseguradora in summaries. `evaluate_policy()` signature requires `IngestionResult`.
**How to avoid:** Extend `_run_single_file_extraction()` to return `(status, result_dict, ingestion_result, policy_schema)` when evaluation mode is on, so callers can pass them to `evaluate_policy()` immediately. Do NOT attempt to reconstruct from ingestion_cache — cache stores page text but not the full IngestionResult shape.
**Warning signs:** `evaluate_policy` called with None or placeholder — returns None silently.

### Pitfall 4: Overwriting Existing validation_warnings
**What goes wrong:** `session.execute(update(Poliza).values(validation_warnings=[new_warning]))` — overwrites financial cross-validation warnings from Phase 13.
**Why it happens:** JSON column update replaces the entire value.
**How to avoid:** Read existing list first, append swap warnings, then write back:
```python
existing = poliza.validation_warnings or []
poliza.validation_warnings = existing + new_swap_warnings
session.commit()
```
**Warning signs:** Phase 13 financial warnings disappear after evaluation runs.

### Pitfall 5: YAML Config File Not Found for Unknown Insurer
**What goes wrong:** `open(f"configs/{aseguradora.lower()}.yaml")` raises FileNotFoundError for an insurer not yet configured (e.g. "HDI Seguros").
**Why it happens:** Only 2-3 insurer YAMLs exist at phase delivery; 10 insurers in production.
**How to avoid:** `config_loader.py` must fall back to `default.yaml` when insurer-specific config is missing. Never raise on missing insurer config.
**Warning signs:** PDF download fails with 500 for uncommon insurers.

### Pitfall 6: fpdf2 FPDF Instance Not Thread-Safe
**What goes wrong:** Sharing a module-level FPDF instance across concurrent requests corrupts PDF output.
**Why it happens:** FPDF maintains internal state (current page, fonts, coordinates).
**How to avoid:** Create a new `PolizaReportPDF(poliza, config)` instance per request inside the `run_in_executor` callable.

### Pitfall 7: Evaluation Score Badge Missing for Unevaluated Polizas
**What goes wrong:** Jinja2 template crashes on `poliza.evaluation_score` being None when rendering badge.
**Why it happens:** Only 20% of polizas are evaluated; most rows have `evaluation_score = NULL`.
**How to avoid:** Template must always guard: `{% if poliza.evaluation_score is not none %}`.
**Warning signs:** 500 errors on poliza list page after auto-evaluation added.

---

## Code Examples

### Generate PDF and Return from FastAPI Route
```python
# Source: https://py-pdf.github.io/fpdf2/UsageInWebAPI.html + STATE.md [v2.0 roadmap]
import asyncio
from fastapi.responses import Response

@poliza_ui_router.get("/ui/polizas/{poliza_id}/report")
async def poliza_report(poliza_id: int, db: Session = Depends(get_db)):
    poliza = db.execute(
        select(Poliza)
        .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
        .where(Poliza.id == poliza_id)
    ).scalar_one_or_none()
    if poliza is None:
        raise HTTPException(status_code=404)

    def _generate():
        from policy_extractor.reports import generate_poliza_report
        return generate_poliza_report(poliza)

    loop = asyncio.get_event_loop()
    pdf_bytes = await loop.run_in_executor(None, _generate)

    aseg_slug = (poliza.aseguradora or "sin_aseguradora").lower().replace(" ", "_")
    filename = f"poliza_{poliza.numero_poliza}_{aseg_slug}.pdf"
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
```

### Load Insurer Config with Fallback
```python
# Source: pyyaml 6.0.3 docs + project pattern
import yaml
from pathlib import Path
from functools import lru_cache

_CONFIGS_DIR = Path(__file__).parent / "configs"

@lru_cache(maxsize=16)
def load_insurer_config(aseguradora: str) -> dict:
    """Load insurer YAML config, falling back to default.yaml if not found."""
    slug = aseguradora.lower().replace(" ", "_")
    candidate = _CONFIGS_DIR / f"{slug}.yaml"
    config_path = candidate if candidate.exists() else _CONFIGS_DIR / "default.yaml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)
```

### Add Unicode Font in fpdf2
```python
# Source: https://py-pdf.github.io/fpdf2/Unicode.html (verified fpdf2 2.8.7)
# DejaVuSans ships with fonttools which is already a dep of fpdf2
import importlib.resources

def _add_unicode_fonts(pdf):
    """Add DejaVuSans Unicode fonts for Spanish character support."""
    # fpdf2 bundles DejaVuSans via its own font path; locate via pkg_resources
    # OR ship font files in policy_extractor/reports/fonts/
    pdf.add_font("dejavu", style="", fname="/path/to/DejaVuSans.ttf")
    pdf.add_font("dejavu", style="B", fname="/path/to/DejaVuSans-Bold.ttf")
    pdf.set_font("dejavu", size=10)
```

**IMPORTANT font resolution:** fpdf2 2.8.7 does not bundle DejaVuSans directly — it only lists it as an example. The project must either ship DejaVuSans TTF files inside `policy_extractor/reports/fonts/` or use `importlib.resources` to locate them. DejaVuSans is available for free (SIL license). Recommended: download `DejaVuSans.ttf` and `DejaVuSans-Bold.ttf` and commit to `policy_extractor/reports/fonts/`.

**Alternative (simpler):** fpdf2 ships with `fpdf.fonts.FPDF_FONT_DIR` which contains a few fonts. Check which are available:
```python
from pathlib import Path
from fpdf import FPDF
print(list((Path(FPDF.__module__).parent / "fonts").glob("*.ttf")))
```

### Extend Evaluation Tool for Swap Detection
```python
# Source: existing evaluation.py build_evaluation_tool() pattern
# Add to input_schema properties in build_evaluation_tool():
"campos_swap_suggestions": {
    "type": "array",
    "description": (
        "Posibles errores de intercambio de campos en campos_adicionales. "
        "Un intercambio ocurre cuando el valor de una clave claramente pertenece "
        "a otra clave diferente. Lista vacia si no hay sospechas de intercambio."
    ),
    "items": {
        "type": "object",
        "properties": {
            "source_key": {"type": "string", "description": "Clave donde esta el valor ahora"},
            "target_key": {"type": "string", "description": "Clave donde deberia estar el valor"},
            "suspicious_value": {"type": "string", "description": "El valor sospechoso"},
            "reason": {"type": "string", "description": "Por que parece un intercambio"},
        },
        "required": ["source_key", "target_key", "suspicious_value", "reason"],
    },
},
```

Add to `EVAL_SYSTEM_PROMPT` (swap detection section appended):
```
## Deteccion de intercambios en campos_adicionales

6. **campos_swap_suggestions**: Lista de posibles intercambios de valores entre claves de campos_adicionales.
   - Un "intercambio" ocurre cuando el valor de una clave parece pertenecer semanticamente a otra clave.
   - Ejemplo: campos_adicionales = {"numero_serie": "ABC123", "marca": "12345-ABC"} — el valor numerico en "numero_serie" y el alfanumerico en "marca" estan probablemente intercambiados.
   - Compara el tipo de dato esperado para cada clave (nombres → strings, importes → numeros, fechas → formato fecha) contra el valor real.
   - Solo incluye swaps con alta certeza. Lista vacia si no hay sospechas claras.
```

### Score Badge Template Pattern (Jinja2)
```html
<!-- In poliza_list.html row and poliza_detail.html header -->
{% if poliza.evaluation_score is not none %}
  {% if poliza.evaluation_score >= 0.8 %}
    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-800">
      {{ "%.2f"|format(poliza.evaluation_score) }}
    </span>
  {% elif poliza.evaluation_score >= 0.6 %}
    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-yellow-100 text-yellow-800">
      {{ "%.2f"|format(poliza.evaluation_score) }}
    </span>
  {% else %}
    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800">
      {{ "%.2f"|format(poliza.evaluation_score) }}
    </span>
  {% endif %}
{% else %}
  <span class="text-xs text-gray-400">—</span>
{% endif %}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| WeasyPrint (HTML→PDF) | fpdf2 (Python API) | v2.0 roadmap decision | No GTK dependency; works on Windows 11; no Jinja2 templates for PDF — use Python API instead |
| Manual table drawing in FPDF | `fpdf2 table()` context manager | fpdf2 2.5+ | Dramatically simpler — no manual column math or cell positioning |
| Separate evaluation CLI flag only | Auto-trigger from batch completion | Phase 16 | Evaluation becomes ambient quality signal, not manual step |

**Deprecated/outdated:**
- WeasyPrint: Blocked on Windows 11 (GTK DLL conflict with Tesseract) — do not use regardless of D-01 in CONTEXT.md. STATE.md overrides.
- `FPDF.ln()` + manual `cell()` grid for tables: Superseded by `table()` context manager in fpdf2 2.5+.

---

## Open Questions

1. **DejaVuSans TTF font source**
   - What we know: fpdf2 does not bundle DejaVuSans itself; the Unicode docs show it as an example requiring separate download.
   - What's unclear: Whether to ship TTF files inside the package, use a system font path, or find another bundled Unicode font.
   - Recommendation: Run `list((Path(FPDF.__module__).parent / "fonts").glob("*.ttf"))` at Wave 0 to discover what fpdf2 actually ships. If DejaVuSans is not present, download and commit `DejaVuSans.ttf` + `DejaVuSans-Bold.ttf` to `policy_extractor/reports/fonts/` (SIL Open Font License — free for commercial use).

2. **IngestionResult availability at auto-evaluation time**
   - What we know: `evaluate_policy()` requires an `IngestionResult`. `_run_batch_extraction()` currently disposes it after each file.
   - What's unclear: Whether to pass it through summaries list (memory overhead for large batches) or accept that evaluation only works immediately after extraction (same thread, same call chain).
   - Recommendation: Pass `(ingestion_result, policy_schema)` directly from `_run_single_file_extraction()` to the evaluation call in the same iteration — no storage needed. Evaluate inline, not retrospectively.

3. **Evaluation window definition for "recent" (D-12)**
   - What we know: D-12 says "when the total number of extractions in the recent window reaches >= 10". The window is not explicitly defined — it refers to the current batch.
   - What's unclear: Does "recent window" mean the current batch only, or a time window (last N minutes)?
   - Recommendation: Interpret as "current batch" — trigger evaluation when `len(successful_in_batch) >= 10`. This is the simplest correct interpretation and consistent with "When a batch extraction completes with 10 or more polizas" from success criterion SC-3.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| fpdf2 | RPT-01, RPT-02 | Yes | 2.8.7 | — (confirmed installed, smoke-tested) |
| pyyaml | RPT-02 | Yes | 6.0.3 | — (confirmed installed) |
| Python `random` | QA-02 | Yes | stdlib | — |
| DejaVuSans.ttf font | RPT-01 (Unicode) | Unknown | — | Download from dejavu-fonts.org (SIL OFL); commit to `reports/fonts/` |
| Anthropic SDK | QA-02, QA-03 | Yes | 0.86.0 | — (existing dep) |

**Missing dependencies with no fallback:**
- DejaVuSans.ttf: Must be resolved in Wave 0 to unblock all PDF rendering. Either found bundled with fpdf2 installation or must be downloaded.

**Missing dependencies with fallback:**
- None.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (from pyproject.toml dev deps) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `addopts = "-m 'not regression'"` |
| Quick run command | `python -m pytest tests/test_reports.py tests/test_evaluation.py -q` |
| Full suite command | `python -m pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RPT-01 | `generate_poliza_report(poliza)` returns bytearray starting with `%PDF` | unit | `python -m pytest tests/test_reports.py::test_generate_poliza_report_returns_pdf_bytes -x` | Wave 0 |
| RPT-01 | Report filename format matches `poliza_{numero}_{aseg}.pdf` | unit | `python -m pytest tests/test_reports.py::test_report_filename_format -x` | Wave 0 |
| RPT-01 | PDF download route returns 200 with content-type `application/pdf` | integration | `python -m pytest tests/test_ui_report.py::test_report_download_route -x` | Wave 0 |
| RPT-01 | PDF download route returns 404 for unknown poliza_id | integration | `python -m pytest tests/test_ui_report.py::test_report_download_404 -x` | Wave 0 |
| RPT-02 | Config loader returns default config when insurer YAML not found | unit | `python -m pytest tests/test_reports.py::test_config_loader_fallback_to_default -x` | Wave 0 |
| RPT-02 | Config loader returns insurer-specific config when YAML exists | unit | `python -m pytest tests/test_reports.py::test_config_loader_zurich -x` | Wave 0 |
| RPT-02 | Two polizas with different insurers produce PDFs with different content (header text) | unit | `python -m pytest tests/test_reports.py::test_per_insurer_differentiation -x` | Wave 0 |
| QA-02 | Auto-eval not triggered when batch has fewer than 10 polizas | unit | `python -m pytest tests/test_auto_eval.py::test_auto_eval_skipped_under_threshold -x` | Wave 0 |
| QA-02 | Auto-eval triggers on batch of 10 and calls evaluate_policy on sampled subset | unit | `python -m pytest tests/test_auto_eval.py::test_auto_eval_triggers_at_threshold -x` | Wave 0 |
| QA-02 | Sample count respects EVAL_SAMPLE_PERCENT setting (20% of 10 = 2) | unit | `python -m pytest tests/test_auto_eval.py::test_auto_eval_sample_count -x` | Wave 0 |
| QA-02 | evaluation_score appears on poliza list rows after auto-eval | integration | `python -m pytest tests/test_ui_report.py::test_eval_badge_present_after_eval -x` | Wave 0 |
| QA-03 | Extended evaluation tool schema includes `campos_swap_suggestions` property | unit | `python -m pytest tests/test_evaluation.py::TestBuildEvaluationTool::test_schema_has_swap_suggestions` | Extend existing |
| QA-03 | Swap suggestions from evaluation are appended (not overwriting) to `validation_warnings` | unit | `python -m pytest tests/test_auto_eval.py::test_swap_warnings_appended_to_existing -x` | Wave 0 |
| QA-03 | Swap warnings follow prescribed text format | unit | `python -m pytest tests/test_auto_eval.py::test_swap_warning_format -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_reports.py tests/test_auto_eval.py tests/test_evaluation.py -q`
- **Per wave merge:** `python -m pytest -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_reports.py` — covers RPT-01, RPT-02 (new file)
- [ ] `tests/test_ui_report.py` — covers RPT-01 route integration, QA-02 badge display (new file)
- [ ] `tests/test_auto_eval.py` — covers QA-02 trigger logic, QA-03 swap warning append (new file)
- [ ] `policy_extractor/reports/__init__.py` — must exist before any import in tests
- [ ] `policy_extractor/reports/configs/default.yaml` — must exist for fallback config loader test
- [ ] DejaVuSans TTF font resolution — verify `fpdf2` bundled fonts or download — blocks `test_generate_poliza_report_returns_pdf_bytes`

---

## Project Constraints (from CLAUDE.md)

CLAUDE.md does not exist in the working directory. No project-specific overrides.

However, the following constraints are drawn from STATE.md accumulated decisions that function as CLAUDE.md equivalents:

- **fpdf2, not WeasyPrint:** `[v2.0 roadmap]: WeasyPrint excluded — GTK/Tesseract DLL conflict on Windows 11; use fpdf2 (pure Python, pip-only)`
- **run_in_executor for fpdf2:** `[v2.0 roadmap]: fpdf2 calls must be wrapped in run_in_executor — synchronous generator blocks FastAPI event loop if called directly in async def`
- **Corrections stored separately:** `[v2.0 roadmap]: Corrections stored in separate corrections table (never overwrite polizas LLM values)` — report uses polizas table values directly (D-04)
- **render_as_batch=True for Alembic:** Required for SQLite ALTER TABLE — any new migration must include this
- **Lazy imports in opt-in branches:** `[Phase 10]: evaluate_policy lazy-imported inside if evaluate: branch` — maintain this pattern in auto-eval hook
- **validation_warnings written as None (not []) when empty:** `[Phase 13-03]: validation_warnings written as None (not []) when empty` — when appending swap warnings, only write if list is non-empty
- **Alembic inspector guard for new tables:** `[Phase 14]: Migration 004 uses inspector guard for batch_jobs table` — any new migration must guard against fresh DBs

---

## Sources

### Primary (HIGH confidence)
- fpdf2 official docs `https://py-pdf.github.io/fpdf2/Tables.html` — table() API, FontFace styling, col_widths
- fpdf2 official docs `https://py-pdf.github.io/fpdf2/Unicode.html` — Unicode font requirements, DejaVuSans example
- fpdf2 official docs `https://py-pdf.github.io/fpdf2/Tutorial.html` — page setup, Letter format, headers/footers
- fpdf2 official docs `https://py-pdf.github.io/fpdf2/UsageInWebAPI.html` — FastAPI Response pattern, `bytes(pdf.output())`
- Direct smoke test: `python -c "from fpdf import FPDF; pdf = FPDF(); pdf.add_page(); pdf.output('test.pdf')"` — PASSED on Python 3.14.3 Windows 11
- `policy_extractor/evaluation.py` — full evaluation pipeline reviewed; extension points identified
- `policy_extractor/api/upload.py` — hook insertion points in `_run_batch_extraction()` and `_run_extraction()` confirmed
- `policy_extractor/storage/models.py` — `validation_warnings` column type (JSON), `evaluation_score` column confirmed
- `policy_extractor/.planning/STATE.md` — v2.0 roadmap decisions, fpdf2 mandate, run_in_executor mandate

### Secondary (MEDIUM confidence)
- WebSearch: fpdf2 FastAPI BytesIO run_in_executor — consistent with official UsageInWebAPI.html pattern

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — fpdf2 confirmed installed and smoke-tested; pyyaml confirmed; all existing deps verified
- Architecture: HIGH — hook points confirmed in existing code; fpdf2 API verified from official docs
- Pitfalls: HIGH — Unicode font requirement verified from official docs; run_in_executor is a locked decision; append-not-overwrite validated from existing patterns

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (fpdf2 is stable; anthropic SDK changes faster but evaluation API patterns are unchanged)
