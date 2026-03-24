# Phase 15: HITL Review Workflow - Research

**Researched:** 2026-03-23
**Domain:** HTMX inline editing, split-pane layout, SQLAlchemy corrections audit table, FastAPI PATCH endpoints
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Resizable split layout with draggable divider — PDF on left, editable fields on right. Both panes scroll independently.
- **D-02:** Separate route `/ui/polizas/{id}/review` — the existing detail page stays read-only. Detail page gets a "Revisar" button linking to review when PDF exists.
- **D-03:** Review page hides the sidebar navigation and uses full viewport width. Back button returns to detail page.
- **D-04:** Click-to-edit interaction — fields display as text, clicking a value turns it into an input. Blur/Enter saves via HTMX PATCH. No explicit save button.
- **D-05:** Nested items (asegurados, coberturas) use the same click-to-edit UX as top-level fields. Each field within each nested item is individually editable.
- **D-06:** Corrected fields show a subtle blue dot/left-border indicator to mark them as edited. Non-intrusive but visible at a glance.
- **D-07:** Polizas row reflects latest corrected values — when a correction is made, the polizas table is updated AND the change is logged in the corrections table. Other views (list, export, dashboard) automatically show corrected data without joins.
- **D-08:** Field path format uses dot-notation with database row IDs for nested items: `"prima_total"` for top-level, `"asegurados.42.nombre_descripcion"` for nested, `"campos_adicionales.numero_endoso"` for dynamic fields. Unambiguous and survives reordering.
- **D-09:** Collapsible panel at the bottom of the review page showing chronological list of all corrections for the poliza. Toggleable, always accessible without leaving the page.
- **D-10:** History also shown on the read-only detail page as a "Correcciones" section — satisfies SC-4.

### Claude's Discretion

- Alembic migration structure (migration 005) for corrections table
- HTMX endpoint design for inline PATCH operations
- Resizable divider implementation approach (CSS resize, JS library, or custom)
- Field type handling (text, numeric, date inputs based on column type)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-03 | User can review extractions side-by-side with the source PDF in a split-pane view | Split-pane layout with CSS `display:flex`, iframe-based native PDF viewer, `/ui/polizas/{id}/pdf` endpoint already exists |
| UI-04 | User can edit/correct extracted fields inline with changes saved to a corrections audit trail | HTMX `hx-patch` + `hx-trigger="blur"`, corrections ORM model with `field_path/old_value/new_value/corrected_at`, D-07 dual-write pattern |
</phase_requirements>

---

## Summary

Phase 15 adds a Human-In-The-Loop (HITL) review workflow on top of the completed Phase 14 read-only UI foundation. The central deliverable is a split-pane page (`/ui/polizas/{id}/review`) where the retained PDF renders in a native browser iframe on the left and all extracted fields are individually editable on the right, with HTMX handling auto-save on blur. Every correction is logged in a new `corrections` table (Alembic migration 005) and simultaneously written back to the source `polizas`/`asegurados`/`coberturas` rows so all existing list, export, and dashboard views reflect corrected values without any JOIN.

The tech stack is entirely within the established project patterns: FastAPI + SQLAlchemy 2.0 + Jinja2 + HTMX 2.0.8 + Tailwind CSS. No new dependencies are required. The resizable divider is achievable with a lightweight pure-CSS `resize` hack or a ~30-line vanilla-JS drag handler — no third-party library needed.

The only design subtlety is the dual-write semantics mandated by D-07: the PATCH endpoint must (1) parse `field_path`, (2) resolve the target row and column, (3) write `old_value` + `new_value` to `corrections`, and (4) apply the new value to the actual ORM row — all in a single database transaction. The dot-notation field-path scheme (D-08) unambiguously identifies top-level poliza columns, nested asegurado/cobertura columns by row ID, and `campos_adicionales` JSON keys.

**Primary recommendation:** Implement the review page as a single new file `review_views.py` registered in `__init__.py`, one new template `poliza_review.html` using a full-viewport layout variant (no sidebar), one `Correction` ORM model added to `models.py`, Alembic migration 005, and two thin partial templates for the editable field row and the history panel.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.135.1 (installed) | PATCH + GET routes for review page | Already in project |
| SQLAlchemy | 2.0.48 (installed) | ORM for Correction model + dual-write | Already in project; `select()` + `mapped_column()` pattern established |
| Alembic | 1.18.4 (installed) | Migration 005 for corrections table | Already in project; `render_as_batch=True` required for SQLite |
| Jinja2 | 3.1.6 (installed) | `poliza_review.html` + partials | Already in project; shared `templates` instance in `api/ui/__init__.py` |
| HTMX | 2.0.8 (CDN) | `hx-patch` + `hx-trigger="blur"` for auto-save; `hx-swap="outerHTML"` to replace field row | Already in project via CDN in `base.html` |
| Tailwind CSS Browser | @4 (CDN) | Utility classes for split-pane, editable indicators | Already in project via CDN in `base.html` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest + TestClient | 8.4.2 / fastapi | Unit + integration tests for review routes | All new routes need GET/PATCH test coverage |
| StaticPool | sqlalchemy.pool | In-memory SQLite that shares state across connections in tests | Required pattern for all UI test modules (established in Phase 14) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Vanilla-JS 30-line drag divider | Split.js library | Split.js is 3 KB but adds a JS dependency; vanilla drag is sufficient given simple two-pane layout |
| CSS `resize: horizontal` on left pane | Full JS drag handler | CSS resize is zero-JS but has non-standard UX on touch; JS drag gives consistent behavior across browsers |
| HTMX `hx-trigger="blur"` | `hx-trigger="change"` | `blur` fires on every focus-out including Enter; `change` only fires when value differs — `blur` is safer for always-save-on-leave semantics |

**Installation:** No new packages required. All libraries already installed.

---

## Architecture Patterns

### Recommended Project Structure

```
policy_extractor/
├── api/
│   └── ui/
│       ├── __init__.py              # existing — add review_router registration
│       ├── poliza_views.py          # existing — add "Revisar" button context + corrections section
│       └── review_views.py          # NEW — GET review page + PATCH field endpoint
├── storage/
│   └── models.py                    # existing — add Correction ORM class
└── templates/
    ├── base.html                    # existing — unchanged
    ├── poliza_detail.html           # existing — add "Revisar" button + "Correcciones" section
    ├── poliza_review.html           # NEW — full-viewport, no sidebar
    └── partials/
        ├── field_row.html           # NEW — single editable field row (display + input modes)
        └── correction_history.html  # NEW — chronological corrections list panel

alembic/versions/
└── 005_corrections.py              # NEW — creates corrections table
```

### Pattern 1: Full-viewport Layout Without Sidebar

The review page must use the full viewport width (D-03). The existing `base.html` always renders the sidebar, so `poliza_review.html` is a standalone HTML file that does NOT extend `base.html`. It manually includes the CDN tags and a minimal `<body>` structure with its own layout.

```html
<!-- poliza_review.html — does NOT extend base.html -->
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Revisar — {{ poliza.numero_poliza }}</title>
  <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
  <script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"></script>
</head>
<body class="h-screen flex flex-col bg-gray-50">
  <!-- top bar: back button + poliza number -->
  <header class="flex items-center gap-4 px-4 py-2 bg-white border-b border-gray-200 flex-shrink-0">
    <a href="/ui/polizas/{{ poliza.id }}" class="text-blue-600 hover:underline text-sm">&larr; Volver</a>
    <h1 class="text-sm font-semibold text-gray-900">Poliza {{ poliza.numero_poliza }}</h1>
  </header>
  <!-- split pane -->
  <div class="flex flex-1 overflow-hidden" id="split-container">
    <div id="pdf-pane" class="w-1/2 min-w-[300px] overflow-auto border-r border-gray-200">
      <iframe src="/ui/polizas/{{ poliza.id }}/pdf"
              class="w-full h-full border-0" title="PDF"></iframe>
    </div>
    <div id="divider" class="w-1 bg-gray-300 cursor-col-resize flex-shrink-0"></div>
    <div id="fields-pane" class="flex-1 overflow-y-auto p-4">
      <!-- editable field groups -->
    </div>
  </div>
</body>
</html>
```

### Pattern 2: Resizable Divider (Vanilla JS, No Library)

The drag divider requires ~30 lines of JavaScript inline in `poliza_review.html`. This avoids any third-party library.

```javascript
// Source: established vanilla-JS drag-resize pattern
const divider = document.getElementById('divider');
const leftPane = document.getElementById('pdf-pane');
const container = document.getElementById('split-container');
let dragging = false;

divider.addEventListener('mousedown', () => { dragging = true; });
document.addEventListener('mousemove', (e) => {
  if (!dragging) return;
  const rect = container.getBoundingClientRect();
  const newLeft = Math.max(200, Math.min(e.clientX - rect.left, rect.width - 200));
  leftPane.style.width = newLeft + 'px';
});
document.addEventListener('mouseup', () => { dragging = false; });
```

### Pattern 3: Click-to-Edit Field Row with HTMX PATCH

Each editable field is rendered as a small partial that toggles between display mode and input mode via JavaScript `onclick`, then saves via HTMX PATCH on blur.

```html
<!-- partials/field_row.html -->
<!-- field_path: e.g. "prima_total" or "asegurados.42.nombre_descripcion" -->
<div id="field-{{ field_path | replace('.', '-') }}"
     class="flex items-center gap-2 py-1
            {% if is_corrected %}border-l-2 border-blue-400 pl-2{% endif %}">
  <span class="text-xs font-semibold uppercase tracking-wide text-gray-500 w-40 flex-shrink-0">
    {{ label }}
  </span>
  <!-- Display value (click to edit) -->
  <span class="field-display text-sm text-gray-900 cursor-pointer hover:bg-blue-50 rounded px-1"
        onclick="this.closest('div').querySelector('.field-display').classList.add('hidden');
                 this.closest('div').querySelector('.field-input').classList.remove('hidden');
                 this.closest('div').querySelector('input').focus();">
    {{ value or '-' }}
  </span>
  <!-- Input (hidden until clicked) -->
  <input
    class="field-input hidden text-sm border border-blue-400 rounded px-2 py-0.5 focus:outline-none w-full"
    type="{{ input_type }}"
    name="value"
    value="{{ value or '' }}"
    hx-patch="/ui/polizas/{{ poliza_id }}/review/field"
    hx-trigger="blur, keydown[key=='Enter']"
    hx-vals='{"field_path": "{{ field_path }}"}'
    hx-target="#field-{{ field_path | replace('.', '-') }}"
    hx-swap="outerHTML"
  >
</div>
```

**Key HTMX details:**
- `hx-patch` sends a PATCH to `/ui/polizas/{id}/review/field`
- `hx-trigger="blur, keydown[key=='Enter']"` — saves on focus-out OR Enter key
- `hx-vals` injects `field_path` as a hidden form field alongside the input's `name="value"`
- `hx-target` + `hx-swap="outerHTML"` — the server returns a fresh `field_row.html` partial with `is_corrected=True` and the updated value; this replaces the entire `<div>` atomically

### Pattern 4: PATCH Endpoint — Dual-Write Logic

The backend PATCH endpoint receives `field_path` + `value`, resolves the target ORM object/column, writes to `corrections`, and writes to the live ORM row — all in one transaction.

```python
# review_views.py
@review_router.patch("/ui/polizas/{poliza_id}/review/field", response_class=HTMLResponse)
def patch_field(
    poliza_id: int,
    request: Request,
    field_path: str = Form(...),
    value: str = Form(...),
    db: Session = Depends(get_db),
):
    poliza = db.get(Poliza, poliza_id)
    if poliza is None:
        raise HTTPException(status_code=404)

    # Resolve old_value and apply new_value to ORM row
    old_value, new_value = _apply_field_update(db, poliza, field_path, value)

    # Log correction (always, even if value unchanged — idempotent)
    if old_value != new_value:
        correction = Correction(
            poliza_id=poliza_id,
            field_path=field_path,
            old_value=str(old_value) if old_value is not None else None,
            new_value=new_value,
            corrected_at=datetime.utcnow(),
        )
        db.add(correction)
        db.commit()

    is_corrected = db.scalar(
        select(func.count(Correction.id))
        .where(Correction.poliza_id == poliza_id, Correction.field_path == field_path)
    ) > 0

    # Return fresh field_row partial
    return templates.TemplateResponse(
        request=request, name="partials/field_row.html",
        context={
            "poliza_id": poliza_id,
            "field_path": field_path,
            "label": _field_label(field_path),
            "value": new_value,
            "input_type": _input_type(field_path),
            "is_corrected": is_corrected,
        }
    )
```

### Pattern 5: Field Path Resolution (_apply_field_update)

The `field_path` dot-notation (D-08) maps to three distinct resolution cases:

```python
def _apply_field_update(db, poliza, field_path: str, raw_value: str):
    parts = field_path.split(".")

    if len(parts) == 1:
        # Top-level poliza column: e.g. "prima_total", "nombre_contratante"
        col = parts[0]
        old_value = getattr(poliza, col, None)
        typed_value = _coerce_value(col, raw_value)
        setattr(poliza, col, typed_value)
        return old_value, raw_value

    elif parts[0] == "campos_adicionales" and len(parts) == 2:
        # Dynamic JSON key on poliza: "campos_adicionales.numero_endoso"
        key = parts[1]
        current = dict(poliza.campos_adicionales or {})
        old_value = current.get(key)
        current[key] = raw_value
        poliza.campos_adicionales = current  # triggers JSON dirty-tracking
        return old_value, raw_value

    elif parts[0] in ("asegurados", "coberturas") and len(parts) == 3:
        # Nested row field: "asegurados.42.nombre_descripcion"
        table, row_id_str, col = parts
        row_id = int(row_id_str)
        if table == "asegurados":
            obj = db.get(Asegurado, row_id)
        else:
            obj = db.get(Cobertura, row_id)
        if obj is None or obj.poliza_id != poliza.id:
            raise HTTPException(status_code=404)
        old_value = getattr(obj, col, None)
        typed_value = _coerce_value(col, raw_value)
        setattr(obj, col, typed_value)
        return old_value, raw_value

    raise HTTPException(status_code=400, detail=f"Unknown field_path: {field_path}")
```

### Pattern 6: Alembic Migration 005 — Corrections Table

```python
# alembic/versions/005_corrections.py
revision = "b5e7d21f0a3c"
down_revision = "a3f8c91d0e2b"  # 004_batch_jobs

def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "corrections" not in inspector.get_table_names():
        op.create_table(
            "corrections",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("poliza_id", sa.Integer(),
                      sa.ForeignKey("polizas.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("field_path", sa.String(), nullable=False),
            sa.Column("old_value", sa.Text(), nullable=True),
            sa.Column("new_value", sa.Text(), nullable=True),
            sa.Column("corrected_at", sa.DateTime(), nullable=False),
        )

def downgrade():
    op.drop_table("corrections")
```

**Index note:** An index on `(poliza_id, corrected_at)` supports the history query. A single `poliza_id` index (created by `index=True`) is sufficient for this phase's query pattern; a composite index can be added later if needed.

### Pattern 7: Correction ORM Model

Add to `policy_extractor/storage/models.py`:

```python
class Correction(Base):
    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id", ondelete="CASCADE"), index=True)
    field_path: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    poliza: Mapped["Poliza"] = relationship("Poliza", back_populates="corrections")
```

Add back-reference to `Poliza`:
```python
corrections: Mapped[list["Correction"]] = relationship(
    "Correction", back_populates="poliza", cascade="all, delete-orphan",
    order_by="Correction.corrected_at"
)
```

### Pattern 8: "Revisar" Button in poliza_detail.html

Conditionally added to the detail page header when `has_pdf` is `True` (context already computed by `poliza_detail` view):

```html
{% if has_pdf %}
<a href="/ui/polizas/{{ poliza.id }}/review"
   class="inline-flex items-center justify-center min-h-[44px] px-4 py-2
          bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold
          rounded-md transition-colors">
  Revisar
</a>
{% endif %}
```

### Pattern 9: "Correcciones" Section in poliza_detail.html

Added at the bottom of the detail page:

```html
{% if corrections %}
<div class="bg-white rounded-lg border border-gray-200 p-6">
  <h2 class="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-4">
    Correcciones ({{ corrections|length }})
  </h2>
  <ul class="space-y-2">
    {% for c in corrections %}
    <li class="text-sm text-gray-700">
      <span class="font-mono text-xs text-gray-500">{{ c.field_path }}</span>
      &nbsp;
      <span class="text-red-500 line-through">{{ c.old_value or '-' }}</span>
      &rarr;
      <span class="text-green-700 font-semibold">{{ c.new_value or '-' }}</span>
      <span class="text-gray-400 text-xs ml-2">{{ c.corrected_at.strftime('%Y-%m-%d %H:%M') }}</span>
    </li>
    {% endfor %}
  </ul>
</div>
{% endif %}
```

### Anti-Patterns to Avoid

- **Modifying polizas WITHOUT logging to corrections:** D-07 requires both operations in the same transaction. Never update the ORM row without first capturing `old_value`.
- **Using a JavaScript SPA framework (React/Vue) for click-to-edit:** The project is server-rendered HTMX. Any dynamic widget must be achievable with `hx-swap="outerHTML"` + small inline JS. Confirmed by existing patterns in `poliza_rows.html` (`hx-on::after-request`).
- **Overwriting campos_adicionales dict by reference:** `poliza.campos_adicionales = current_dict` (full replacement) is required. Mutating the dict in-place does not mark the JSON column dirty in SQLAlchemy 2.0.
- **Using `hx-swap="innerHTML"` for field rows:** This would leave the wrapping `<div id="field-...">` intact but replace children, making it impossible to update the `border-l-2` indicator class on the container. Use `hx-swap="outerHTML"` to replace the entire `<div>`.
- **Storing Decimal as string without coercion:** When writing back `prima_total` or numeric cobertura fields, `raw_value` (a string from the form) must be coerced to `Decimal` before writing to the `Numeric(15,2)` column, otherwise SQLAlchemy will raise a type error.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF rendering in browser | Custom renderer / PDF.js | Native `<iframe src="...pdf">` | Already working via `poliza_pdf` FileResponse endpoint; PDF.js has canvas memory crash on large scanned PDFs (documented in STATE.md) |
| Split pane resize | Third-party Split.js | 30-line vanilla JS drag handler | No JS dependency needed; Split.js adds weight for a trivial use case |
| Corrections API | Custom REST payload parsing | FastAPI `Form(...)` parameters | HTMX naturally sends `application/x-www-form-urlencoded`; `Form(...)` is zero-overhead parsing |
| Date coercion | Custom string-to-date | `date.fromisoformat(raw_value)` | Standard library; handles YYYY-MM-DD from `<input type="date">` |
| Decimal coercion | Custom money parser | `Decimal(raw_value)` with `try/except` | Standard library; raises `InvalidOperation` on bad input which maps naturally to HTTP 422 |
| In-memory test DB | Custom fixture setup | `StaticPool` + `create_all` pattern (established in Phase 14) | Phase 14 established the exact pattern; copy from `test_ui_pages.py` |

---

## Common Pitfalls

### Pitfall 1: JSON Column Dirty-Tracking

**What goes wrong:** `poliza.campos_adicionales["key"] = value` does not mark the column dirty. SQLAlchemy does not detect in-place mutation of JSON columns by default.

**Why it happens:** SQLAlchemy's change detection tracks object identity, not deep content. Mutating the existing dict object produces no `UPDATE` statement.

**How to avoid:** Always assign a NEW dict: `poliza.campos_adicionales = {**poliza.campos_adicionales, "key": value}` or `current = dict(poliza.campos_adicionales); current[key] = value; poliza.campos_adicionales = current`.

**Warning signs:** Correction is logged but the detail page still shows the old value after save.

### Pitfall 2: HTMX OOB Swap vs. outerHTML on Field Rows

**What goes wrong:** Using `hx-swap="innerHTML"` on the containing `<div id="field-...">` causes the `id` attribute and indicator classes (border-l-2) to be lost after first correction, breaking subsequent corrections on the same field.

**Why it happens:** `innerHTML` replaces the children but keeps the original element. If the server sends back a full `<div id="...">` with updated classes, HTMX discards the outer element from the response and only inserts its children.

**How to avoid:** Always use `hx-swap="outerHTML"` so the entire `<div id="field-...">` is replaced by the server response.

**Warning signs:** Blue indicator does not appear after the first correction on a field.

### Pitfall 3: `corrected_at` Timestamp is Naive (No Timezone)

**What goes wrong:** `datetime.utcnow()` produces a timezone-naive datetime. This is consistent with existing usage in the project (e.g., `BatchJob.created_at`, `Poliza.extracted_at`).

**Why it happens:** SQLite stores datetimes as strings without timezone info. SQLAlchemy 2.0 uses naive datetimes for SQLite by default.

**How to avoid:** Use `datetime.utcnow()` consistently (matches all other models in `models.py`). Do not mix `datetime.now(timezone.utc)` (aware) and `datetime.utcnow()` (naive) in the same codebase.

**Warning signs:** TypeError in Jinja2 when formatting `corrected_at` with `.strftime()` if `None` leaks through.

### Pitfall 4: field_path with Float/Decimal Input Types

**What goes wrong:** `<input type="number">` for monetary fields sends values like `"12345.67"`. Writing this string directly to a `Numeric(15,2)` column raises `sqlalchemy.exc.StatementError`.

**Why it happens:** FastAPI `Form(...)` always delivers strings; SQLAlchemy does not auto-coerce string to Decimal for `Numeric` columns.

**How to avoid:** The `_coerce_value(col, raw_value)` helper must know which columns are `Numeric` and apply `Decimal(raw_value)`. Maintain a small dict: `_NUMERIC_COLS = {"prima_total", "suma_asegurada", "deducible"}` and `_DATE_COLS = {"fecha_emision", "inicio_vigencia", "fin_vigencia", "fecha_nacimiento"}`.

**Warning signs:** 500 error when saving a monetary field for the first time.

### Pitfall 5: Corrections Table Not Created in Test DB

**What goes wrong:** `Base.metadata.create_all(engine)` in test files creates all tables defined in `models.py` at import time. If `Correction` is added to `models.py` but test file was imported before the model was added (cached `.pyc`), the table won't exist.

**Why it happens:** Python bytecode cache (`.pyc`); or test file was written before `Correction` was added to `models.py`.

**How to avoid:** The `clean_polizas_table` / `clean_tables` fixture pattern from Phase 14 runs `Base.metadata.create_all(engine)` at module level — as long as `models.py` is imported after `Correction` is defined, the table is created. Ensure `Correction` import is in `models.py`, not a separate file.

**Warning signs:** `OperationalError: no such table: corrections` in tests.

### Pitfall 6: hx-vals JSON String Must Use Single-Outer / Double-Inner Quotes

**What goes wrong:** `hx-vals='{"field_path": "asegurados.42.nombre"}'` fails if `field_path` contains a double quote (unlikely but field keys should be ASCII dot-paths) or if the HTML attribute uses double quotes.

**Why it happens:** Jinja2 renders variable values into attribute strings; if the field_path contains a double quote or if the surrounding attribute delimiter is double-quoted, the JSON breaks.

**How to avoid:** Always use `hx-vals='{"field_path": "{{ field_path }}"}'` with single-outer quotes in the HTML attribute. field_path values per D-08 are lowercase alphanumeric + dots + underscores — safe for this pattern.

**Warning signs:** Browser console shows HTMX parsing error on attribute; field_path arrives as `undefined` in the PATCH request.

---

## Code Examples

### Verified Pattern: HTMX blur auto-save (project codebase)

Existing `poliza_list.html` uses `hx-trigger="keyup changed delay:300ms"` for search. The `blur` trigger for inline editing is a parallel pattern — both follow the same `hx-target` + `hx-swap` convention:

```html
<!-- Existing pattern (poliza_list.html) -->
<input hx-get="/ui/polizas"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#poliza-rows"
       hx-swap="innerHTML">

<!-- New pattern for blur auto-save (review page) -->
<input hx-patch="/ui/polizas/{{ poliza_id }}/review/field"
       hx-trigger="blur, keydown[key=='Enter']"
       hx-vals='{"field_path": "{{ field_path }}"}'
       hx-target="#field-{{ field_path | replace('.', '-') }}"
       hx-swap="outerHTML">
```

### Verified Pattern: HTMX partial response returns HTML fragment (project codebase)

The `poliza_list` view returns `partials/poliza_rows.html` when `HX-Request` header is set. The review PATCH endpoint follows the same pattern — it returns `partials/field_row.html` unconditionally (not conditional on HX-Request, since the endpoint is PATCH-only and always called by HTMX).

```python
# Established pattern (poliza_views.py)
if request.headers.get("HX-Request"):
    return templates.TemplateResponse(request=request, name="partials/poliza_rows.html", context={...})

# New pattern (review_views.py) — PATCH endpoint always returns partial
return templates.TemplateResponse(request=request, name="partials/field_row.html", context={...})
```

### Verified Pattern: SQLAlchemy ORM update with Alembic migration (project codebase)

Migration 004 inspector-guard pattern is the established template for migration 005:

```python
# 004_batch_jobs.py (existing)
if "batch_jobs" not in inspector.get_table_names():
    op.create_table("batch_jobs", ...)

# 005_corrections.py (new — same pattern)
if "corrections" not in inspector.get_table_names():
    op.create_table("corrections", ...)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Overwrite polizas on correction | Dual-write: update polizas + log to corrections | D-07 (this phase) | Other views automatically show corrected data without JOIN overhead |
| Global poliza JSON stored as flat keys | Dot-notation field_path for nested rows: `asegurados.{row_id}.{col}` | D-08 (this phase) | Corrections are unambiguous and survive list reordering |
| No correction visibility | Blue left-border indicator on corrected fields | D-06 (this phase) | Reviewer can see which fields were human-edited at a glance |

**Deprecated/outdated for this phase:**

- The "corrections never overwrite polizas" note in STATE.md (line 103) was the original roadmap note. Decision D-07 supersedes it — the polizas row IS updated. The corrections table remains the audit log.

---

## Open Questions

1. **Decimal → display formatting in review pane**
   - What we know: Detail page shows `{{ poliza.prima_total or '-' }}` without formatting (renders as Python `Decimal('12345.67')` string).
   - What's unclear: Should the review pane show formatted values (e.g., `$ 12,345.67`) or raw Decimal strings? The `<input type="number">` needs the raw numeric string as its `value` attribute.
   - Recommendation: Use the same unformatted display as the existing detail page. Add formatting as a separate improvement; it's out of phase scope.

2. **Empty-string vs. NULL when clearing a field**
   - What we know: A reviewer may blank a field (submit empty string). `_coerce_value` for `Numeric` columns will raise `InvalidOperation` on empty string.
   - What's unclear: Should empty string be interpreted as NULL (clear the field) or rejected as invalid?
   - Recommendation: Treat empty string as NULL for optional columns (most poliza columns are nullable). For `numero_poliza` and `aseguradora` (non-nullable), reject with HTTP 422.

3. **campos_adicionales nested correction display label**
   - What we know: `campos_adicionales` keys are dynamic strings from LLM extraction (e.g., `"numero_endoso"`, `"deducible_rc"`). Field path is `"campos_adicionales.numero_endoso"`.
   - What's unclear: What human-readable label to show for these fields in the correction history on the detail page?
   - Recommendation: Display the key as-is (e.g., `"numero_endoso"`) with a `campos_adicionales.` prefix visible in the history line. No mapping table needed.

---

## Environment Availability

Step 2.6: SKIPPED (no new external dependencies — phase uses only installed packages; native browser PDF viewer requires no server-side tooling).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_ui_review.py -x -q` |
| Full suite command | `python -m pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-03 | GET `/ui/polizas/{id}/review` returns 200 with HTML | integration | `python -m pytest tests/test_ui_review.py::test_review_page_returns_200 -x` | Wave 0 |
| UI-03 | Review page contains `<iframe` pointing to PDF endpoint | integration | `python -m pytest tests/test_ui_review.py::test_review_page_has_pdf_iframe -x` | Wave 0 |
| UI-03 | Review page returns 404 when poliza has no PDF | integration | `python -m pytest tests/test_ui_review.py::test_review_page_404_without_pdf -x` | Wave 0 |
| UI-04 | PATCH `/ui/polizas/{id}/review/field` with valid field_path returns 200 + HTML partial | integration | `python -m pytest tests/test_ui_review.py::test_patch_field_returns_partial -x` | Wave 0 |
| UI-04 | PATCH updates polizas row (dual-write) | integration | `python -m pytest tests/test_ui_review.py::test_patch_updates_poliza_row -x` | Wave 0 |
| UI-04 | PATCH logs correction to corrections table | integration | `python -m pytest tests/test_ui_review.py::test_patch_logs_correction -x` | Wave 0 |
| UI-04 | PATCH for nested field (asegurados.{id}.col) updates asegurado row | integration | `python -m pytest tests/test_ui_review.py::test_patch_nested_field -x` | Wave 0 |
| UI-04 | GET detail page shows "Correcciones" section after at least one correction | integration | `python -m pytest tests/test_ui_review.py::test_detail_shows_corrections_section -x` | Wave 0 |
| UI-04 | Detail page has "Revisar" button when PDF exists | integration | `python -m pytest tests/test_ui_review.py::test_detail_has_revisar_button_with_pdf -x` | Wave 0 |
| UI-04 | PATCH for campos_adicionales field updates JSON dict | integration | `python -m pytest tests/test_ui_review.py::test_patch_campos_adicionales -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_ui_review.py -x -q`
- **Per wave merge:** `python -m pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_ui_review.py` — covers all UI-03 and UI-04 test cases listed above; uses StaticPool + dependency_overrides pattern from `test_ui_pages.py`; must create `Correction` rows directly via `TestingSessionLocal` for history tests

*(No additional framework install needed — pytest 8.4.2 already installed)*

---

## Project Constraints (from CLAUDE.md)

CLAUDE.md does not exist at the project root. No project-specific directives to enforce beyond those documented in STATE.md and CONTEXT.md.

Key conventions extracted from STATE.md and codebase that apply to this phase:

- Use `render_as_batch=True` in all Alembic migrations (SQLite ALTER TABLE requirement)
- Use `StaticPool` + `Base.metadata.create_all(engine)` at module level in all UI test files
- Use `app.dependency_overrides[get_db]` + autouse fixture for test DB override; save/restore previous override
- Lazy-import `openpyxl`/`fpdf2` inside function bodies (established pattern — not applicable here but generalizes to: avoid module-level imports of heavy deps)
- All monetary columns use `Numeric(15,2)` not `Float`
- Spanish domain terms in field names and UI copy
- HTMX 2.0.8 from CDN (`cdn.jsdelivr.net/npm/htmx.org@2.0.8`)
- Tailwind CSS Browser @4 from CDN (`cdn.jsdelivr.net/npm/@tailwindcss/browser@4`)
- Corrections table must exist in `models.py` so `Base.metadata.create_all()` in tests creates it automatically

---

## Sources

### Primary (HIGH confidence)

- Codebase direct read: `policy_extractor/api/ui/poliza_views.py` — existing detail + PDF routes; basis for review route
- Codebase direct read: `policy_extractor/storage/models.py` — ORM models for Poliza, Asegurado, Cobertura; correction model schema derived from these
- Codebase direct read: `alembic/versions/004_batch_jobs.py` — migration pattern for 005
- Codebase direct read: `policy_extractor/templates/poliza_list.html` + `partials/poliza_rows.html` — HTMX patterns in use
- Codebase direct read: `tests/test_ui_pages.py` + `tests/test_ui_integration.py` — StaticPool + override pattern
- Codebase direct read: `policy_extractor/api/__init__.py` — router registration pattern
- `pyproject.toml` — installed package versions confirmed

### Secondary (MEDIUM confidence)

- HTMX documentation reference: `hx-trigger="blur"` and `hx-vals` attributes are standard HTMX 2.x features consistent with 2.0.8 CDN already in use
- SQLAlchemy JSON column dirty-tracking behavior: well-documented limitation; requires dict reassignment — confirmed by project decision in STATE.md Phase 13-02

### Tertiary (LOW confidence)

- None — all claims are directly verifiable from the installed codebase or well-established SQLAlchemy/HTMX behavior.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all libraries are already installed and in use; no new dependencies
- Architecture: HIGH — patterns derived directly from existing project code
- Pitfalls: HIGH — JSON dirty-tracking and HTMX swap pitfalls are well-documented in the project's own STATE.md and HTMX docs
- Test architecture: HIGH — follows identical pattern to Phase 14 UI tests

**Research date:** 2026-03-23
**Valid until:** 2026-06-23 (stable libraries; no fast-moving dependencies)
