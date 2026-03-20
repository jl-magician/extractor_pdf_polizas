# Requirements: Extractor PDF Polizas

**Defined:** 2026-03-20
**Core Value:** Extraer automaticamente toda la informacion posible de cualquier poliza de seguro en PDF — sin importar la aseguradora o estructura — y almacenarla de forma estructurada para consulta, reporteo e integracion con otros sistemas.

## v2.0 Requirements

Requirements for v2.0 Web UI & Extraction Quality milestone. Each maps to roadmap phases.

### Extraction Quality

- [ ] **EXT-01**: System improves extraction prompts to prevent financial value swaps in breakdown tables
- [ ] **EXT-02**: System validates extracted financial fields cross-referentially (primer_pago + subsecuentes ~ prima_total) and flags mismatches as warnings
- [ ] **EXT-03**: System auto-reclassifies "digital" PDF pages with <10 extractable characters as scanned and applies OCR
- [ ] **EXT-04**: User can configure a field exclusion list to prevent extraction of irrelevant campos_adicionales

### Web UI

- [ ] **UI-01**: User can upload PDFs and view extraction results in a browser interface
- [ ] **UI-02**: User can search and filter the policy list by aseguradora, date range, and status
- [ ] **UI-03**: User can review extractions side-by-side with the source PDF in a split-pane view
- [ ] **UI-04**: User can edit/correct extracted fields inline with changes saved to a corrections audit trail
- [ ] **UI-05**: User can view a dashboard with extraction statistics and quality metrics
- [ ] **UI-06**: System retains uploaded PDFs for review UI display (~1 GB/year at current volume)

### Reports

- [ ] **RPT-01**: User can generate a PDF report from extracted poliza data
- [ ] **RPT-02**: System supports per-insurer report templates (customizable layout per aseguradora)

### Testing & Quality

- [ ] **QA-01**: Golden dataset expanded to 20+ fixtures covering all 10 insurers
- [ ] **QA-02**: Sonnet evaluation auto-triggered on configurable sample percentage of batch extractions
- [ ] **QA-03**: Targeted Sonnet review pass detects campos_adicionales field swaps

## Future Requirements

Deferred beyond v2.0. Tracked but not in current roadmap.

### Scale & Distribution

- **SCALE-01**: Celery/Redis distributed job queue for >10,000 PDFs/month
- **SCALE-02**: Automated golden dataset expansion from production data (needs human review workflow first)

### Analytics

- **ANLY-01**: Policy comparison and coverage gap analysis across insurers

### Mobile

- **MOBI-01**: Mobile application for field agents

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Mobile application | Desktop/browser sufficient for office use; defer indefinitely |
| Direct insurer system integration | Out of scope — no API access to insurer systems |
| Celery/Redis job queue | Not needed at <10K PDFs/month single-user scale |
| OAuth/authentication | Single-user local tool; no multi-tenant needs |
| Real-time SSE/WebSocket streams | Polling sufficient for single-user; complexity not justified |
| PDF annotation overlay | Read-only PDF viewer sufficient; annotation adds significant complexity |
| WYSIWYG report template editor | Per-insurer templates managed as code; visual editor is over-engineering |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| EXT-01 | — | Pending |
| EXT-02 | — | Pending |
| EXT-03 | — | Pending |
| EXT-04 | — | Pending |
| UI-01 | — | Pending |
| UI-02 | — | Pending |
| UI-03 | — | Pending |
| UI-04 | — | Pending |
| UI-05 | — | Pending |
| UI-06 | — | Pending |
| RPT-01 | — | Pending |
| RPT-02 | — | Pending |
| QA-01 | — | Pending |
| QA-02 | — | Pending |
| QA-03 | — | Pending |

**Coverage:**
- v2.0 requirements: 15 total
- Mapped to phases: 0
- Unmapped: 15 ⚠️

---
*Requirements defined: 2026-03-20*
*Last updated: 2026-03-20 after initial definition*
