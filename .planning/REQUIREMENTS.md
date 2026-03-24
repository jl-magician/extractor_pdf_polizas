# Requirements: Extractor PDF Polizas

**Defined:** 2026-03-20
**Core Value:** Extraer automaticamente toda la informacion posible de cualquier poliza de seguro en PDF — sin importar la aseguradora o estructura — y almacenarla de forma estructurada para consulta, reporteo e integracion con otros sistemas.

## v2.0 Requirements

Requirements for v2.0 Web UI & Extraction Quality milestone. Each maps to roadmap phases.

### Extraction Quality

- [x] **EXT-01**: System improves extraction prompts to prevent financial value swaps in breakdown tables
- [x] **EXT-02**: System validates extracted financial fields cross-referentially (primer_pago + subsecuentes ~ prima_total) and flags mismatches as warnings
- [x] **EXT-03**: System auto-reclassifies "digital" PDF pages with <10 extractable characters as scanned and applies OCR
- [x] **EXT-04**: User can configure a field exclusion list to prevent extraction of irrelevant campos_adicionales

### Web UI

- [x] **UI-01**: User can upload PDFs and view extraction results in a browser interface
- [x] **UI-02**: User can search and filter the policy list by aseguradora, date range, and status
- [x] **UI-03**: User can review extractions side-by-side with the source PDF in a split-pane view
- [x] **UI-04**: User can edit/correct extracted fields inline with changes saved to a corrections audit trail
- [x] **UI-05**: User can view a dashboard with extraction statistics and quality metrics
- [x] **UI-06**: System retains uploaded PDFs for review UI display (~1 GB/year at current volume)

### Reports

- [x] **RPT-01**: User can generate a PDF report from extracted poliza data
- [x] **RPT-02**: System supports per-insurer report templates (customizable layout per aseguradora)

### Testing & Quality

- [x] **QA-01**: Golden dataset expanded to 20+ fixtures covering all 10 insurers
- [x] **QA-02**: Sonnet evaluation auto-triggered on configurable sample percentage of batch extractions
- [x] **QA-03**: Targeted Sonnet review pass detects campos_adicionales field swaps

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
| EXT-01 | Phase 13 | Complete |
| EXT-02 | Phase 13 | Complete |
| EXT-03 | Phase 13 | Complete |
| EXT-04 | Phase 13 | Complete |
| UI-01 | Phase 14 | Complete |
| UI-02 | Phase 14 | Complete |
| UI-05 | Phase 14 | Complete |
| UI-06 | Phase 14 | Complete |
| UI-03 | Phase 15 | Complete |
| UI-04 | Phase 15 | Complete |
| RPT-01 | Phase 16 | Complete |
| RPT-02 | Phase 16 | Complete |
| QA-02 | Phase 16 | Complete |
| QA-03 | Phase 16 | Complete |
| QA-01 | Phase 17 | Complete |

**Coverage:**
- v2.0 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-20*
*Last updated: 2026-03-20 after v2.0 roadmap creation*
