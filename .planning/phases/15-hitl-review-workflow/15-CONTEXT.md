# Phase 15: HITL Review Workflow - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Reviewers can correct extracted fields in the browser with the source PDF visible alongside, and every change is stored in a non-destructive audit trail. This phase delivers:
- A split-pane review page (PDF viewer + editable fields)
- Inline click-to-edit for all field types (top-level, nested, campos_adicionales)
- A corrections table with full audit trail
- Correction history visible in both review and detail pages

</domain>

<decisions>
## Implementation Decisions

### Split-Pane Layout
- **D-01:** Resizable split layout with draggable divider — PDF on left, editable fields on right. Both panes scroll independently.
- **D-02:** Separate route `/ui/polizas/{id}/review` — the existing detail page stays read-only. Detail page gets a "Revisar" button linking to review when PDF exists.
- **D-03:** Review page hides the sidebar navigation and uses full viewport width. Back button returns to detail page.

### Inline Editing UX
- **D-04:** Click-to-edit interaction — fields display as text, clicking a value turns it into an input. Blur/Enter saves via HTMX PATCH. No explicit save button.
- **D-05:** Nested items (asegurados, coberturas) use the same click-to-edit UX as top-level fields. Each field within each nested item is individually editable.
- **D-06:** Corrected fields show a subtle blue dot/left-border indicator to mark them as edited. Non-intrusive but visible at a glance.

### Corrections Audit Trail
- **D-07:** Polizas row reflects latest corrected values — when a correction is made, the polizas table is updated AND the change is logged in the corrections table. Other views (list, export, dashboard) automatically show corrected data without joins.
- **D-08:** Field path format uses dot-notation with database row IDs for nested items: `"prima_total"` for top-level, `"asegurados.42.nombre_descripcion"` for nested, `"campos_adicionales.numero_endoso"` for dynamic fields. Unambiguous and survives reordering.

### Correction History View
- **D-09:** Collapsible panel at the bottom of the review page showing chronological list of all corrections for the poliza. Toggleable, always accessible without leaving the page.
- **D-10:** History also shown on the read-only detail page as a "Correcciones" section — satisfies SC-4 (view full correction history for any poliza).

### Claude's Discretion
- Alembic migration structure (migration 005) for corrections table
- HTMX endpoint design for inline PATCH operations
- Resizable divider implementation approach (CSS resize, JS library, or custom)
- Field type handling (text, numeric, date inputs based on column type)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing UI Templates
- `policy_extractor/templates/poliza_detail.html` — Current read-only detail view; field groups to replicate in review pane
- `policy_extractor/templates/base.html` — Base layout with sidebar; review page needs a variant without sidebar

### Backend Routes
- `policy_extractor/api/ui/poliza_views.py` — Existing detail + PDF endpoints; review route builds on these
- `policy_extractor/api/ui/__init__.py` — Router registration pattern

### Data Models
- `policy_extractor/storage/models.py` — Poliza, Asegurado, Cobertura ORM models; corrections table will reference Poliza
- `alembic/versions/004_batch_jobs.py` — Latest migration; next is 005

### Requirements
- `.planning/REQUIREMENTS.md` §UI-03 — Side-by-side PDF + extraction split-pane view
- `.planning/REQUIREMENTS.md` §UI-04 — Inline edit with corrections audit trail

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `poliza_detail.html` field group structure (General, Vigencia, Financiero, Personas, Asegurados, Coberturas, Campos Adicionales) — reuse as editable field layout in review pane
- `poliza_views.py:poliza_pdf` endpoint — serves retained PDFs for iframe display, already working
- `poliza_views.py:poliza_detail` — already computes `has_pdf` flag, can add "Revisar" link conditionally
- HTMX + Tailwind CSS pattern established across all UI pages

### Established Patterns
- Jinja2 templates extending `base.html` with `{% block content %}`
- HTMX for partial page updates (e.g., poliza list search/load-more)
- FastAPI `APIRouter` per feature area registered in `__init__.py`
- SQLAlchemy 2.0 with `select()` + `selectinload()` for eager loading
- Alembic migrations with `render_as_batch=True` for SQLite

### Integration Points
- New `review_views.py` router registered alongside existing UI routers
- New `poliza_review.html` template (full-width variant of base layout)
- New `corrections` table via Alembic migration 005
- "Revisar" button added to `poliza_detail.html` header
- "Correcciones" section added to `poliza_detail.html` bottom

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

*Phase: 15-hitl-review-workflow*
*Context gathered: 2026-03-23*
