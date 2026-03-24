---
phase: 15-hitl-review-workflow
plan: "02"
subsystem: hitl-review-ui
tags: [hitl, corrections, jinja2, htmx, tailwind, split-pane, inline-editing]
dependency_graph:
  requires:
    - phase: 15-01
      provides: corrections-orm, review-routes, dual-write-patch, stub-templates
  provides:
    - full split-pane review page (poliza_review.html)
    - click-to-edit field row partial (partials/field_row.html)
    - collapsible correction history partial (partials/correction_history.html)
    - Revisar button and Correcciones section on detail page
  affects: [policy_extractor/api/ui/poliza_views.py, poliza_detail.html]
tech_stack:
  added: []
  patterns:
    - Standalone HTML page (no base.html extension) for full-viewport review layout
    - HTMX outerHTML swap for inline field editing partial replacement
    - hx-trigger correctionSaved from:body for cross-element HTMX event propagation
    - Native details/summary element for zero-JS collapsible panel
    - JS mousedown/mousemove/mouseup drag pattern with Math.max/min clamp for resizable panes
key_files:
  created: []
  modified:
    - policy_extractor/templates/poliza_review.html
    - policy_extractor/templates/partials/field_row.html
    - policy_extractor/templates/partials/correction_history.html
    - policy_extractor/templates/poliza_detail.html
    - policy_extractor/api/ui/poliza_views.py
key_decisions:
  - "poliza_review.html is standalone (no extends base.html) — full viewport without sidebar per D-03"
  - "field_row uses style=display:none for input hiding to avoid classList toggle JS dependency"
  - "hx-vals uses single-outer/double-inner quoting to avoid Jinja2 parsing conflicts"
  - "selectinload(Poliza.corrections) added to poliza_detail query — corrections loaded eagerly for detail page"
patterns_established:
  - "Standalone review page pattern: full-viewport Jinja2 template with embedded CDN scripts"
  - "HTMX event propagation: hx-trigger='correctionSaved from:body' refreshes history partial after PATCH"
requirements_completed: [UI-03, UI-04]
metrics:
  duration_seconds: 147
  completed_date: "2026-03-24"
  tasks_completed: 2
  files_created: 0
  files_modified: 5
---

# Phase 15 Plan 02: HITL Review Templates Summary

**Full split-pane review page with PDF iframe, click-to-edit HTMX fields, correction history panel, and Revisar button + Correcciones section on the detail page.**

## Performance

- **Duration:** ~2.5 min
- **Started:** 2026-03-24T02:01:54Z
- **Completed:** 2026-03-24T02:04:21Z
- **Tasks:** 2 completed (Task 3 is human-verify checkpoint)
- **Files modified:** 5

## Accomplishments

- Replaced stub templates from Plan 01 with full production implementations
- Split-pane layout with PDF iframe (left) and editable fields (right), draggable divider with 200px clamp
- Click-to-edit field rows with HTMX PATCH auto-save on blur/Enter, corrected blue left-border indicator
- Collapsible correction history panel using native HTML details/summary (zero JS)
- Detail page updated: Revisar button (conditional on has_pdf), Correcciones section with audit trail
- All 15 review tests pass plus 2 previously-xfail tests now pass (17 total passing)

## Task Commits

1. **Task 1: Review page template + field row partial + correction history partial** - `0c753ee` (feat)
2. **Task 2: Modify detail page -- Revisar button + Correcciones section + backend context** - `c154699` (feat)

**Plan metadata:** (to be added after SUMMARY commit)

## Files Created/Modified

- `policy_extractor/templates/poliza_review.html` - Full split-pane review page: standalone HTML, PDF iframe, field groups with included partials, correction history wrapper, draggable divider JS
- `policy_extractor/templates/partials/field_row.html` - Click-to-edit field row: display span + hidden input, HTMX PATCH on blur/Enter, corrected indicator border
- `policy_extractor/templates/partials/correction_history.html` - Collapsible details/summary panel: chronological corrections descending, empty state
- `policy_extractor/templates/poliza_detail.html` - Added Revisar button (conditional on has_pdf) and Correcciones section at bottom
- `policy_extractor/api/ui/poliza_views.py` - Added Correction import, selectinload(Poliza.corrections), corrections context key

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None — all stub templates from Plan 01 have been replaced with full implementations.

## Self-Check: PASSED

Files confirmed present:
- policy_extractor/templates/poliza_review.html: FOUND
- policy_extractor/templates/partials/field_row.html: FOUND
- policy_extractor/templates/partials/correction_history.html: FOUND
- policy_extractor/templates/poliza_detail.html: FOUND
- policy_extractor/api/ui/poliza_views.py: FOUND

Commits confirmed:
- 0c753ee feat(15-02): full review page, field_row, and correction_history templates
- c154699 feat(15-02): add Revisar button and Correcciones section to detail page
