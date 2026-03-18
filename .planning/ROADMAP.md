# Roadmap: Extractor PDF Pólizas

## Overview

Five phases that take the project from nothing to a fully operational CLI tool for extracting insurance policy data from any PDF — regardless of insurer or format — and persisting it in a queryable local database with a REST API. Phase 1 establishes the non-retrofittable data contract. Phases 2-3 build the processing pipeline. Phase 4 delivers the user-facing CLI. Phase 5 wires storage and the API layer.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Data model, Pydantic schemas, SQLite schema, project scaffolding (completed 2026-03-18)
- [x] **Phase 2: Ingestion** - PDF type detection, OCR pipeline, result caching (completed 2026-03-18)
- [ ] **Phase 3: Extraction** - Claude API integration, structured output, confidence scoring
- [ ] **Phase 4: CLI & Batch** - Single-file and batch CLI, progress, idempotency, cost tracking
- [ ] **Phase 5: Storage & API** - SQLite persistence, JSON export, FastAPI query layer

## Phase Details

### Phase 1: Foundation
**Goal**: The non-retrofittable data contracts are in place before any extraction code is written
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05
**Success Criteria** (what must be TRUE):
  1. A Pydantic schema exists that captures all required policy fields including a list of insured parties and a list of coverages
  2. The SQLite schema has a policies table, a separate insured_parties table (one-to-many), and all monetary amounts stored with an explicit currency code column
  3. All date fields in the schema are typed as ISO 8601 (YYYY-MM-DD) with explicit format conversion documented
  4. Every policy record stores source_file_hash, model_id, prompt_version, and extracted_at (provenance columns)
  5. The dynamic/variable fields per insurer are stored in a JSON overflow column without breaking the core typed columns
**Plans**: 2 plans
Plans:
- [x] 01-01-PLAN.md — Project scaffolding + Pydantic v2 extraction schemas
- [x] 01-02-PLAN.md — SQLAlchemy ORM models + comprehensive test suite

### Phase 2: Ingestion
**Goal**: The system reliably routes any PDF — digital or scanned — to the correct processing path before touching the LLM
**Depends on**: Phase 1
**Requirements**: ING-01, ING-02, ING-05
**Success Criteria** (what must be TRUE):
  1. A digital PDF with selectable text is classified as "digital" without invoking OCR
  2. A scanned PDF (image-only pages) is classified as "scanned" and OCR is applied before any further processing
  3. OCR output includes Spanish-language text accurately extracted from a sample scanned policy
  4. A PDF that has already been processed returns the cached result without re-running OCR or paying API costs
**Plans**: 2 plans
Plans:
- [x] 02-01-PLAN.md — Ingestion contracts, dependencies, PDF classifier (ING-01)
- [x] 02-02-PLAN.md — OCR runner, cache, ingest_pdf() orchestrator (ING-02, ING-05)

### Phase 3: Extraction
**Goal**: The system extracts all available policy fields from any PDF using Claude API with validated structured output
**Depends on**: Phase 2
**Requirements**: EXT-01, EXT-02, EXT-03, EXT-04, EXT-05
**Success Criteria** (what must be TRUE):
  1. Running extraction on a digital or scanned PDF produces a Pydantic-validated JSON object with all core fields populated (or null where absent — never invented values)
  2. The insurer name and insurance type are automatically classified from PDF content without any hard-coded template
  3. Each extracted field in the output includes a confidence indicator
  4. Extraction works correctly on PDFs written entirely in Spanish and on PDFs written in English
**Plans**: TBD

### Phase 4: CLI & Batch
**Goal**: Users can process one or many PDFs from the command line with full visibility into progress and cost
**Depends on**: Phase 3
**Requirements**: ING-03, ING-04, CLI-01, CLI-02, CLI-03, CLI-04, CLI-05
**Success Criteria** (what must be TRUE):
  1. User can run `extract <file.pdf>` from the command line and receive extraction output for a single policy
  2. User can run `batch <folder/>` and all PDFs in that folder are processed, with a live progress display showing current file, total count, and percentage
  3. If one PDF in a batch fails, processing continues with the remaining files and the failure is reported in the final summary
  4. Re-running the same command on already-processed PDFs skips those files without re-extracting or creating duplicate records
  5. After each execution the tool reports the number of tokens consumed and the estimated API cost in USD
**Plans**: TBD

### Phase 5: Storage & API
**Goal**: All extracted data is persisted in SQLite and queryable via both JSON export and a REST API
**Depends on**: Phase 4
**Requirements**: STOR-01, STOR-02, STOR-03, STOR-04
**Success Criteria** (what must be TRUE):
  1. After extraction, the complete structured policy data is retrievable from the local SQLite database
  2. User can export a policy (or set of policies) as a JSON file from the command line
  3. The FastAPI server starts locally and responds to GET requests returning policy data in JSON format
  4. API supports filtering results by insurer, date range, agent name, and policy type
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 2/2 | Complete   | 2026-03-18 |
| 2. Ingestion | 2/2 | Complete   | 2026-03-18 |
| 3. Extraction | 0/TBD | Not started | - |
| 4. CLI & Batch | 0/TBD | Not started | - |
| 5. Storage & API | 0/TBD | Not started | - |
