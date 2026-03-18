# Requirements: Extractor PDF Pólizas

**Defined:** 2026-03-18
**Core Value:** Extraer automáticamente toda la información posible de cualquier póliza de seguro en PDF y almacenarla de forma estructurada.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Ingestion

- [ ] **ING-01**: System detects whether a PDF contains selectable text or is a scanned image
- [ ] **ING-02**: System extracts text from scanned PDFs using OCR with Spanish and English support
- [ ] **ING-03**: User can process a single PDF file via CLI
- [ ] **ING-04**: User can process a directory of PDFs in batch via CLI
- [ ] **ING-05**: System caches OCR results to avoid reprocessing the same PDF

### Extraction

- [ ] **EXT-01**: System extracts all available fields from a policy PDF using Claude API (contratante, asegurado(s), costo, coberturas, sumas aseguradas, compañía, vigencia, agente, forma de pago, deducibles, and any additional fields)
- [ ] **EXT-02**: Extraction output is structured JSON validated against Pydantic schemas
- [ ] **EXT-03**: System automatically classifies the insurer and insurance type from the PDF content
- [ ] **EXT-04**: Each extracted field includes a confidence score indicating extraction certainty
- [ ] **EXT-05**: System handles PDFs in both Spanish and English

### Data Model

- [ ] **DATA-01**: Database schema supports multiple insured parties (people or assets) per policy via relational table
- [ ] **DATA-02**: Schema supports dynamic/variable fields per insurer type via JSON overflow column
- [ ] **DATA-03**: All dates are stored in canonical ISO format regardless of source format
- [ ] **DATA-04**: All monetary amounts are stored with explicit currency code
- [ ] **DATA-05**: System stores the raw Claude API response for each extraction (provenance logging)

### Storage & Output

- [ ] **STOR-01**: All extracted data is persisted in a local SQLite database
- [ ] **STOR-02**: User can export extracted policy data as JSON
- [ ] **STOR-03**: System exposes a REST API (FastAPI) for querying stored policies
- [ ] **STOR-04**: API supports filtering by insurer, date range, agent, and policy type

### CLI & Operations

- [ ] **CLI-01**: User can invoke single-file extraction from command line
- [ ] **CLI-02**: User can invoke batch extraction from command line
- [ ] **CLI-03**: Batch processing displays progress (current file, total, percentage)
- [ ] **CLI-04**: System skips PDFs that have already been extracted (idempotent reprocessing)
- [ ] **CLI-05**: System tracks and reports token usage and estimated API cost per execution

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
| ING-01 | — | Pending |
| ING-02 | — | Pending |
| ING-03 | — | Pending |
| ING-04 | — | Pending |
| ING-05 | — | Pending |
| EXT-01 | — | Pending |
| EXT-02 | — | Pending |
| EXT-03 | — | Pending |
| EXT-04 | — | Pending |
| EXT-05 | — | Pending |
| DATA-01 | — | Pending |
| DATA-02 | — | Pending |
| DATA-03 | — | Pending |
| DATA-04 | — | Pending |
| DATA-05 | — | Pending |
| STOR-01 | — | Pending |
| STOR-02 | — | Pending |
| STOR-03 | — | Pending |
| STOR-04 | — | Pending |
| CLI-01 | — | Pending |
| CLI-02 | — | Pending |
| CLI-03 | — | Pending |
| CLI-04 | — | Pending |
| CLI-05 | — | Pending |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 0
- Unmapped: 24 ⚠️

---
*Requirements defined: 2026-03-18*
*Last updated: 2026-03-18 after initial definition*
