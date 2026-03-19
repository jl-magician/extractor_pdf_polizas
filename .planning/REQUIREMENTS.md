# Requirements: Extractor PDF Polizas

**Defined:** 2026-03-18
**Core Value:** Extract all available data from any insurance policy PDF automatically — regardless of insurer or format — and store it structured for query and integration.

## v1.1 Requirements

Requirements for v1.1 API & Quality release. Each maps to roadmap phases.

### Migrations & Infrastructure

- [x] **MIG-01**: Alembic initialized with `render_as_batch=True` for SQLite compatibility
- [x] **MIG-02**: Baseline migration stamps existing schema without altering tables
- [x] **MIG-03**: Evaluation columns migration adds Sonnet evaluator fields to polizas table

### Export

- [x] **EXP-01**: User can export polizas to Excel (.xlsx) with multi-sheet workbook (polizas, asegurados, coberturas)
- [x] **EXP-02**: User can export polizas to CSV format
- [x] **EXP-03**: CLI `export` command supports `--format xlsx` and `--format csv` flags
- [x] **EXP-04**: Excel/CSV exports use the same filter options as existing JSON export (aseguradora, date range, etc.)
- [x] **EXP-05**: Excel export produces correct numeric and date cell types (not text)

### PDF Upload API

- [x] **API-01**: User can POST a PDF file to `/polizas/upload` and receive extraction results
- [x] **API-02**: Upload endpoint accepts multipart/form-data with PDF file
- [x] **API-03**: Upload triggers the full pipeline: ingest → extract → persist → return structured result
- [x] **API-04**: Long-running uploads return 202 Accepted with a job ID
- [x] **API-05**: User can poll `GET /jobs/{id}` for job status and results
- [x] **API-06**: Uploaded PDF temp files are cleaned up after extraction completes

### Async Batch Processing

- [x] **ASYNC-01**: Batch processing runs extractions concurrently with configurable concurrency limit
- [x] **ASYNC-02**: SQLite WAL mode enabled for concurrent write safety
- [x] **ASYNC-03**: Each concurrent worker uses its own database session
- [x] **ASYNC-04**: Rate limit errors from Anthropic API trigger automatic retry with exponential backoff
- [x] **ASYNC-05**: CLI `batch` command accepts `--concurrency N` flag

### Quality Evaluation

- [ ] **QAL-01**: User can run Sonnet evaluation on an extraction via `--evaluate` CLI flag
- [x] **QAL-02**: Sonnet evaluator scores extraction completeness, accuracy, and hallucination risk
- [x] **QAL-03**: Evaluation results are stored in dedicated database columns
- [ ] **QAL-04**: Evaluation is opt-in only — never runs in the default extraction path
- [ ] **QAL-05**: API upload endpoint accepts optional `evaluate=true` query parameter

### Regression Testing

- [ ] **REG-01**: Golden dataset fixtures exist with known-good extraction results
- [ ] **REG-02**: Regression tests compare extractions field-by-field with tolerance (not exact match)
- [ ] **REG-03**: Regression tests are marked with `@pytest.mark.regression` and excluded from default test runs
- [ ] **REG-04**: Regression test failures identify which specific fields drifted

## v2.0 Requirements

Deferred to next milestone. Tracked but not in current roadmap.

### Web UI

- **UI-01**: Browser interface for uploading PDFs and viewing extraction results
- **UI-02**: Manual data editing/correction of extracted fields
- **UI-03**: Dashboard with extraction statistics and quality metrics

### Reports

- **RPT-01**: PDF report generation from extracted poliza data
- **RPT-02**: Customizable report templates per insurer

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full async SQLAlchemy | Sync sessions with local SQLite gain nothing from async I/O; adds complexity |
| Celery + Redis job queue | Overkill for local Windows app processing 200 PDFs/month |
| Permanent storage of uploaded PDFs | Disk management complexity; re-upload is idempotent via hash cache |
| Real-time SSE progress stream | Premature for CLI-first tool; poll-based status is sufficient |
| Sonnet evaluator as microservice | Network hop + deployment complexity for a local tool |
| Auto-running evaluator on every extraction | Sonnet costs ~20x Haiku; opt-in only |
| Mobile app | Out of scope for foreseeable future |
| Direct insurer system integrations | Out of scope |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MIG-01 | Phase 6 | Complete |
| MIG-02 | Phase 6 | Complete |
| MIG-03 | Phase 6 | Complete |
| EXP-01 | Phase 7 | Complete |
| EXP-02 | Phase 7 | Complete |
| EXP-03 | Phase 7 | Complete |
| EXP-04 | Phase 7 | Complete |
| EXP-05 | Phase 7 | Complete |
| API-01 | Phase 8 | Complete |
| API-02 | Phase 8 | Complete |
| API-03 | Phase 8 | Complete |
| API-04 | Phase 8 | Complete |
| API-05 | Phase 8 | Complete |
| API-06 | Phase 8 | Complete |
| ASYNC-01 | Phase 9 | Complete |
| ASYNC-02 | Phase 9 | Complete |
| ASYNC-03 | Phase 9 | Complete |
| ASYNC-04 | Phase 9 | Complete |
| ASYNC-05 | Phase 9 | Complete |
| QAL-01 | Phase 10 | Pending |
| QAL-02 | Phase 10 | Complete |
| QAL-03 | Phase 10 | Complete |
| QAL-04 | Phase 10 | Pending |
| QAL-05 | Phase 10 | Pending |
| REG-01 | Phase 11 | Pending |
| REG-02 | Phase 11 | Pending |
| REG-03 | Phase 11 | Pending |
| REG-04 | Phase 11 | Pending |

**Coverage:**
- v1.1 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-03-18*
*Last updated: 2026-03-18 — traceability complete after roadmap creation*
