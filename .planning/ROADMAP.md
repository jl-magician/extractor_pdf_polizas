# Roadmap: Extractor PDF Polizas

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-03-18)
- ✅ **v1.1 API & Quality** — Phases 6-12 (shipped 2026-03-19)
- 🔄 **v2.0 Web UI & Extraction Quality** — Phases 13-17 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-5) — SHIPPED 2026-03-18</summary>

- [x] Phase 1: Foundation (2/2 plans) — completed 2026-03-18
- [x] Phase 2: Ingestion (2/2 plans) — completed 2026-03-18
- [x] Phase 3: Extraction (2/2 plans) — completed 2026-03-18
- [x] Phase 4: CLI & Batch (2/2 plans) — completed 2026-03-18
- [x] Phase 5: Storage & API (2/2 plans) — completed 2026-03-18

</details>

<details>
<summary>✅ v1.1 API & Quality (Phases 6-12) — SHIPPED 2026-03-19</summary>

- [x] Phase 6: Migrations (2/2 plans) — completed 2026-03-19
- [x] Phase 7: Export (2/2 plans) — completed 2026-03-19
- [x] Phase 8: PDF Upload API (2/2 plans) — completed 2026-03-19
- [x] Phase 9: Async Batch (2/2 plans) — completed 2026-03-19
- [x] Phase 10: Quality Evaluator (2/2 plans) — completed 2026-03-19
- [x] Phase 11: Regression Suite (2/2 plans) — completed 2026-03-19
- [x] Phase 12: Milestone Polish (2/2 plans) — completed 2026-03-19

</details>

### v2.0 Web UI & Extraction Quality (Phases 13-17)

- [x] **Phase 13: Extraction Pipeline Fixes** - Fix auto-OCR fallback, financial cross-validation, and field exclusion (completed 2026-03-20)
- [ ] **Phase 14: Web UI Foundation** - Read-only browser interface: upload, list, detail, dashboard, PDF retention
- [ ] **Phase 15: HITL Review Workflow** - Side-by-side PDF editor with corrections audit trail
- [ ] **Phase 16: PDF Reports & Auto-Evaluation** - Per-insurer PDF reports and auto-triggered Sonnet evaluation
- [ ] **Phase 17: Golden Dataset Expansion** - 20+ fixtures covering all 10 insurers

## Phase Details

### Phase 13: Extraction Pipeline Fixes
**Goal**: Systematic extraction errors are eliminated before any UI is built on top of them
**Depends on**: Phase 12 (v1.1 complete)
**Requirements**: EXT-01, EXT-02, EXT-03, EXT-04
**Success Criteria** (what must be TRUE):
  1. A digital PDF whose pages contain fewer than 10 extractable characters is automatically reclassified as scanned and OCR is applied — the user never receives an all-null extraction due to vector-path text
  2. After extracting any poliza, the system checks whether primer_pago + subsecuentes approximates prima_total and writes a human-readable warning to validation_warnings when the invariant is violated
  3. A configurable exclusion list prevents specified field names from ever appearing in campos_adicionales output — the excluded fields are silently dropped before the record is saved
  4. The extraction prompt for financial breakdown tables produces correct column-to-field mapping on a known-bad Zurich/AXA fixture where values were previously swapped
**Plans:** 3/3 plans complete
Plans:
- [x] 13-01-PLAN.md — Auto-OCR fallback for zero-text digital pages (EXT-03)
- [x] 13-02-PLAN.md — Validation infrastructure: migration, validator registry, financial and date checks (EXT-02)
- [x] 13-03-PLAN.md — Prompt v2.0.0 with Zurich overlay, field exclusion, and pipeline wiring (EXT-01, EXT-04)

### Phase 14: Web UI Foundation
**Goal**: The agency team can upload PDFs, monitor job progress, browse polizas, and export data from a browser without using the CLI
**Depends on**: Phase 13
**Requirements**: UI-01, UI-02, UI-05, UI-06
**Success Criteria** (what must be TRUE):
  1. User can drag-and-drop (or file-pick) a PDF in the browser, submit it, and watch an inline status indicator update to "complete" when extraction finishes — without refreshing the page
  2. User can browse a paginated poliza list filtered by aseguradora, date range, and status, and open any record to see all extracted fields on a detail page
  3. User can view a dashboard page showing total polizas processed, breakdown by aseguradora, and the count of records with validation warnings
  4. User can download a poliza's data as Excel or JSON directly from the detail page without opening a terminal
  5. Uploaded PDFs are retained on disk at data/pdfs/{poliza_id}.pdf and remain accessible after the extraction job expires from memory
**Plans:** 4/5 plans executed
Plans:
- [x] 14-01-PLAN.md — Infrastructure: jinja2 dep, BatchJob model, migration, base template, sidebar layout (UI-06)
- [x] 14-02-PLAN.md — Upload batch workflow with HTMX polling, progress bar, summary, PDF retention (UI-01, UI-06)
- [x] 14-03-PLAN.md — Poliza list with search/filter/pagination and detail page with exports (UI-02)
- [x] 14-04-PLAN.md — Dashboard with stat cards, date range filter, needs-review table, job history (UI-05)
- [ ] 14-05-PLAN.md — Integration tests and visual verification checkpoint (UI-01, UI-02, UI-05, UI-06)

### Phase 15: HITL Review Workflow
**Goal**: Reviewers can correct extracted fields in the browser with the source PDF visible alongside, and every change is stored in a non-destructive audit trail
**Depends on**: Phase 14 (PDF retention from UI-06 required; read-only UI validated first)
**Requirements**: UI-03, UI-04
**Success Criteria** (what must be TRUE):
  1. User can open a poliza review page that shows the source PDF in the left pane (browser native viewer, no external app) and extracted fields in the right pane simultaneously without tab-switching
  2. User can click any field value, edit it inline, and the change is saved automatically when the user leaves the field — no explicit save button required
  3. Every correction is stored in a separate corrections table with field_path, old_value, new_value, and corrected_at — the original LLM-extracted value in the polizas table is never overwritten
  4. User can view the full correction history for any poliza as a chronological list showing what was changed, from what, to what, and when
**Plans**: TBD

### Phase 16: PDF Reports & Auto-Evaluation
**Goal**: Users can download a formatted PDF summary for any poliza, and Sonnet quality evaluation runs automatically on a sample of each batch
**Depends on**: Phase 15 (corrections table exists for quality metrics; Phase 14 minimum for UI integration)
**Requirements**: RPT-01, RPT-02, QA-02, QA-03
**Success Criteria** (what must be TRUE):
  1. User can click "Download Report" on any poliza detail page and receive a formatted PDF containing the key extracted fields, coverage summary, and insurer branding — generated in under 5 seconds
  2. The report layout differs visibly per aseguradora (e.g. Zurich uses a different field order and header than AXA) — templates are independently configurable without changing shared code
  3. When a batch extraction completes with 10 or more polizas, Sonnet evaluation is automatically triggered on a configurable percentage (default 10%) of the records in the batch — the user sees evaluation scores in the poliza list without running a separate command
  4. A dedicated Sonnet review pass detects campos_adicionales field swaps (where a value belongs to a different field key) and adds a warning to validation_warnings on the affected record
**Plans**: TBD

### Phase 17: Golden Dataset Expansion
**Goal**: The regression suite covers all 10 insurers with 20+ fixtures, giving systematic confidence that extraction quality does not regress across insurer formats
**Depends on**: Phase 15 (HITL review UI makes fixture creation safe and fast; reviewed polizas are trusted ground truth)
**Requirements**: QA-01
**Success Criteria** (what must be TRUE):
  1. The golden dataset contains at least 20 PII-redacted fixtures, with at least one fixture per each of the 10 insurers the agency works with
  2. Running `pytest -m regression` passes all fixtures without any skipped tests due to missing fixture files
  3. Any new extraction prompt change that causes a field regression on an existing fixture is caught by the test suite before merging
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 13 → 14 → 15 → 16 → 17

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 2/2 | Complete | 2026-03-18 |
| 2. Ingestion | v1.0 | 2/2 | Complete | 2026-03-18 |
| 3. Extraction | v1.0 | 2/2 | Complete | 2026-03-18 |
| 4. CLI & Batch | v1.0 | 2/2 | Complete | 2026-03-18 |
| 5. Storage & API | v1.0 | 2/2 | Complete | 2026-03-18 |
| 6. Migrations | v1.1 | 2/2 | Complete | 2026-03-19 |
| 7. Export | v1.1 | 2/2 | Complete | 2026-03-19 |
| 8. PDF Upload API | v1.1 | 2/2 | Complete | 2026-03-19 |
| 9. Async Batch | v1.1 | 2/2 | Complete | 2026-03-19 |
| 10. Quality Evaluator | v1.1 | 2/2 | Complete | 2026-03-19 |
| 11. Regression Suite | v1.1 | 2/2 | Complete | 2026-03-19 |
| 12. Milestone Polish | v1.1 | 2/2 | Complete | 2026-03-19 |
| 13. Extraction Pipeline Fixes | v2.0 | 3/3 | Complete    | 2026-03-20 |
| 14. Web UI Foundation | v2.0 | 4/5 | In Progress|  |
| 15. HITL Review Workflow | v2.0 | 0/? | Not started | - |
| 16. PDF Reports & Auto-Evaluation | v2.0 | 0/? | Not started | - |
| 17. Golden Dataset Expansion | v2.0 | 0/? | Not started | - |
