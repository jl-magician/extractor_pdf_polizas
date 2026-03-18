# Requirements: Extractor PDF Pólizas

**Defined:** 2026-03-18
**Core Value:** Extraer automáticamente toda la información posible de cualquier póliza de seguro en PDF y almacenarla de forma estructurada.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Ingestion

- [x] **ING-01**: System detects whether a PDF contains selectable text or is a scanned image
- [x] **ING-02**: System extracts text from scanned PDFs using OCR with Spanish and English support
- [x] **ING-03**: User can process a single PDF file via CLI
- [x] **ING-04**: User can process a directory of PDFs in batch via CLI
- [x] **ING-05**: System caches OCR results to avoid reprocessing the same PDF

### Extraction

- [x] **EXT-01**: System extracts all available fields from a policy PDF using Claude API (contratante, asegurado(s), costo, coberturas, sumas aseguradas, compañía, vigencia, agente, forma de pago, deducibles, and any additional fields)
- [x] **EXT-02**: Extraction output is structured JSON validated against Pydantic schemas
- [x] **EXT-03**: System automatically classifies the insurer and insurance type from the PDF content
- [x] **EXT-04**: Each extracted field includes a confidence score indicating extraction certainty
- [x] **EXT-05**: System handles PDFs in both Spanish and English

### Data Model

- [x] **DATA-01**: Database schema supports multiple insured parties (people or assets) per policy via relational table
- [x] **DATA-02**: Schema supports dynamic/variable fields per insurer type via JSON overflow column
- [x] **DATA-03**: All dates are stored in canonical ISO format regardless of source format
- [x] **DATA-04**: All monetary amounts are stored with explicit currency code
- [x] **DATA-05**: System stores the raw Claude API response for each extraction (provenance logging)

### Storage & Output

- [ ] **STOR-01**: All extracted data is persisted in a local SQLite database
- [ ] **STOR-02**: User can export extracted policy data as JSON
- [ ] **STOR-03**: System exposes a REST API (FastAPI) for querying stored policies
- [ ] **STOR-04**: API supports filtering by insurer, date range, agent, and policy type

### CLI & Operations

- [x] **CLI-01**: User can invoke single-file extraction from command line
- [x] **CLI-02**: User can invoke batch extraction from command line
- [x] **CLI-03**: Batch processing displays progress (current file, total, percentage)
- [x] **CLI-04**: System skips PDFs that have already been extracted (idempotent reprocessing)
- [x] **CLI-05**: System tracks and reports token usage and estimated API cost per execution

## v2 Requirements

### Reporting

- **RPT-01**: User can export policy data to Excel with filters by insurer/agent/date
- **RPT-02**: User can generate PDF summary reports of issued policies
- **RPT-03**: Dashboard with statistics (policies per insurer, per agent, per month)

### Quality

- **QAL-01**: Golden dataset regression suite to detect model drift
- **QAL-02**: Image preprocessing (deskew, denoise) for low-quality scans
- **QAL-03**: Human-in-the-loop review for low-confidence extractions

### Web Interface

- **WEB-01**: Web UI for uploading and viewing extracted policies
- **WEB-02**: Manual correction of extracted data in web UI
- **WEB-03**: Multi-user access with authentication

## Out of Scope

| Feature | Reason |
|---------|--------|
| Per-insurer templates | LLM approach eliminates need for fixed templates; maintaining 50-70 templates is unsustainable |
| Direct insurer API integration | Outside project scope; PDFs are the input interface |
| Real-time webhooks | No external consumers in v1; API polling is sufficient |
| ML fine-tuning | Claude API is sufficient; fine-tuning adds complexity without proven benefit |
| Mobile app | Web-first after desktop; mobile deferred indefinitely |
| Password-protected PDF handling | Edge case; user can decrypt before processing |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ING-01 | Phase 2 | Complete |
| ING-02 | Phase 2 | Complete |
| ING-03 | Phase 4 | Complete |
| ING-04 | Phase 4 | Complete |
| ING-05 | Phase 2 | Complete |
| EXT-01 | Phase 3 | Complete |
| EXT-02 | Phase 3 | Complete |
| EXT-03 | Phase 3 | Complete |
| EXT-04 | Phase 3 | Complete |
| EXT-05 | Phase 3 | Complete |
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| DATA-05 | Phase 1 | Complete |
| STOR-01 | Phase 5 | Pending |
| STOR-02 | Phase 5 | Pending |
| STOR-03 | Phase 5 | Pending |
| STOR-04 | Phase 5 | Pending |
| CLI-01 | Phase 4 | Complete |
| CLI-02 | Phase 4 | Complete |
| CLI-03 | Phase 4 | Complete |
| CLI-04 | Phase 4 | Complete |
| CLI-05 | Phase 4 | Complete |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0

---
*Requirements defined: 2026-03-18*
*Last updated: 2026-03-18 after roadmap creation*
