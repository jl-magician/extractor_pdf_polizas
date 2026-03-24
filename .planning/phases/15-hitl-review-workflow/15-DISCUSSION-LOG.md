# Phase 15: HITL Review Workflow - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-23
**Phase:** 15-hitl-review-workflow
**Areas discussed:** Split-pane layout, Inline editing UX, Corrections audit trail, Correction history view

---

## Split-Pane Layout

### Q1: How should the PDF and fields be arranged?

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed 50/50 split | PDF left, fields right, each 50% width. Simple, no drag handles. | |
| Resizable split | Same left/right but with draggable divider for flexible sizing. | ✓ |
| Tabbed (no split) | PDF and fields in separate tabs. Violates SC-1 (no tab-switching). | |

**User's choice:** Resizable split
**Notes:** None

### Q2: Should the review page replace the detail page or be a separate route?

| Option | Description | Selected |
|--------|-------------|----------|
| Separate /review route | New route, detail stays read-only, link from detail to review. | ✓ |
| Replace detail page | Transform detail into split-pane review. Loses read-only view. | |
| You decide | Claude picks. | |

**User's choice:** Separate /review route
**Notes:** None

### Q3: Sidebar visibility in review page?

| Option | Description | Selected |
|--------|-------------|----------|
| Hide sidebar | Full viewport width for maximum split-pane space. | ✓ |
| Keep sidebar | Consistent navigation but less horizontal space. | |

**User's choice:** Hide sidebar
**Notes:** None

---

## Inline Editing UX

### Q1: How should users edit field values?

| Option | Description | Selected |
|--------|-------------|----------|
| Click-to-edit | Fields display as text, click to turn into input. Blur/Enter saves via HTMX PATCH. | ✓ |
| Always-editable form | All fields render as inputs immediately. More traditional but noisier. | |
| Edit toggle button | Single button switches whole pane between read/edit modes. | |

**User's choice:** Click-to-edit
**Notes:** None

### Q2: How should nested items (asegurados, coberturas) be editable?

| Option | Description | Selected |
|--------|-------------|----------|
| Same click-to-edit | Each field individually click-to-edit, same UX as top-level. | ✓ |
| Expandable cards | Collapsible cards, click to expand and edit. | |
| You decide | Claude picks. | |

**User's choice:** Same click-to-edit
**Notes:** None

### Q3: Visual feedback for corrected fields?

| Option | Description | Selected |
|--------|-------------|----------|
| Subtle indicator | Blue dot or left-border highlight on corrected fields. | ✓ |
| No indicator | Fields look the same. Must check history. | |
| Strikethrough old value | Old value crossed out next to new value. Clutters view. | |

**User's choice:** Subtle indicator (blue dot)
**Notes:** None

---

## Corrections Audit Trail

### Q1: Should polizas row stay untouched or reflect latest corrections?

| Option | Description | Selected |
|--------|-------------|----------|
| Polizas reflects latest | Update polizas row AND log change in corrections table. | ✓ |
| Polizas untouched | Never change original. Every query must join corrections. | |
| You decide | Claude picks. | |

**User's choice:** Polizas reflects latest
**Notes:** None

### Q2: field_path format for nested items?

| Option | Description | Selected |
|--------|-------------|----------|
| Dot-notation with IDs | Use DB row ID: "asegurados.42.nombre_descripcion". Unambiguous. | ✓ |
| Dot-notation with index | Array index: "asegurados[0].nombre_descripcion". Breaks on reorder. | |
| You decide | Claude picks. | |

**User's choice:** Dot-notation with IDs
**Notes:** None

---

## Correction History View

### Q1: How should correction history be displayed?

| Option | Description | Selected |
|--------|-------------|----------|
| Collapsible panel in review page | Toggleable panel at bottom showing chronological list. | ✓ |
| Separate history page | Dedicated /history route. Clean but requires navigation. | |
| Per-field tooltip | Hover/click dot to see field's history inline. One at a time. | |

**User's choice:** Collapsible panel in review page
**Notes:** None

### Q2: Should history be accessible from the detail page too?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, show on detail page too | Add "Correcciones" section to poliza_detail.html. Satisfies SC-4. | ✓ |
| Only in review page | History only visible in /review. | |
| You decide | Claude picks. | |

**User's choice:** Yes, show on detail page too
**Notes:** None

---

## Claude's Discretion

- Alembic migration structure for corrections table
- HTMX endpoint design for inline PATCH operations
- Resizable divider implementation approach
- Field type handling (text, numeric, date inputs)

## Deferred Ideas

None — discussion stayed within phase scope
