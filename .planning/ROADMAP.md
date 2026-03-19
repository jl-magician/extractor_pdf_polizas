# Roadmap: Extractor PDF Polizas

## Overview

Six phases (6-11) that take the v1.0 shipped system and add HTTP integration, concurrency, schema versioning, export formats, and extraction quality tooling. All phases are strictly additive — no v1.0 component is replaced. Phase 6 (Alembic) is a hard prerequisite for Phase 10 (evaluation columns). Phases 7, 8, and 9 are independent of each other but all depend on the stable v1.0 pipeline. Phases 10 and 11 build on the stable pipeline and optionally on each other.

**Milestone:** v1.1 API & Quality
**Phases in this milestone:** 6-11 (continuing from v1.0 phases 1-5)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

**v1.0 Phases (complete):**
- [x] **Phase 1: Foundation** - Data model, Pydantic schemas, SQLite schema, project scaffolding (completed 2026-03-18)
- [x] **Phase 2: Ingestion** - PDF type detection, OCR pipeline, result caching (completed 2026-03-18)
- [x] **Phase 3: Extraction** - Claude API integration, structured output, confidence scoring (completed 2026-03-18)
- [x] **Phase 4: CLI & Batch** - Single-file and batch CLI, progress, idempotency, cost tracking (completed 2026-03-18)
- [x] **Phase 5: Storage & API** - SQLite persistence, JSON export, FastAPI query layer (completed 2026-03-18)

**v1.1 Phases (current milestone):**
- [x] **Phase 6: Migrations** - Alembic initialized with SQLite batch mode, baseline migration, evaluation columns migration (completed 2026-03-19)
- [x] **Phase 7: Export** - Excel and CSV export from stored polizas with multi-sheet workbook and correct numeric types (completed 2026-03-19)
- [ ] **Phase 8: PDF Upload API** - HTTP endpoint to POST a PDF and receive async extraction results with job polling
- [ ] **Phase 9: Async Batch** - Concurrent batch processing with configurable concurrency, WAL mode, and rate limit backoff
- [ ] **Phase 10: Quality Evaluator** - Opt-in Sonnet evaluation of Haiku extractions with stored scores and CLI/API flags
- [ ] **Phase 11: Regression Suite** - Golden dataset fixtures with field-level fuzzy comparison and regression pytest marker

## Phase Details

### Phase 6: Migrations
**Goal**: Schema versioning is in place so any future column addition or structural change is managed safely through a migration chain
**Depends on**: Phase 5 (v1.0 complete — existing schema to baseline)
**Requirements**: MIG-01, MIG-02, MIG-03
**Success Criteria** (what must be TRUE):
  1. Running `alembic upgrade head` on a fresh checkout applies all migrations and produces a correctly structured database
  2. Running `alembic upgrade head` on the existing production database stamps it without altering any table or losing any data
  3. After migration 002 runs, the polizas table has evaluation_score and evaluation_json columns
  4. `alembic current` shows the correct head revision on any database (new or existing)
**Plans:** 2/2 plans complete
Plans:
- [ ] 06-01-PLAN.md — Alembic infrastructure, migration files (001+002), ORM model updates, migration chain tests
- [ ] 06-02-PLAN.md — database.py guard logic (init_db + auto-migrate + WAL), integration tests

### Phase 7: Export
**Goal**: Users can export their stored polizas to Excel or CSV for use in spreadsheet tools, with correct numeric and date formatting
**Depends on**: Phase 6 (Alembic in place before any schema-touching module is introduced)
**Requirements**: EXP-01, EXP-02, EXP-03, EXP-04, EXP-05
**Success Criteria** (what must be TRUE):
  1. User runs `poliza-extractor export --format xlsx output.xlsx` and receives a multi-sheet workbook with polizas, asegurados, and coberturas sheets
  2. User runs `poliza-extractor export --format csv output.csv` and receives a CSV file with all poliza records
  3. Excel and CSV exports accept the same `--aseguradora`, `--desde`, and `--hasta` filter flags as the existing JSON export
  4. Opening the Excel file in a spreadsheet tool shows prima_total and other monetary values as numbers (not text), enabling SUM formulas to work correctly
  5. Date columns in the Excel file are formatted as dates, not strings
**Plans:** 2/2 plans complete
Plans:
- [ ] 07-01-PLAN.md — Export module (export.py) with xlsx multi-sheet and csv writers, unit tests
- [ ] 07-02-PLAN.md — CLI integration (--format flag, Spanish filter flags, openpyxl dep, integration tests)

### Phase 8: PDF Upload API
**Goal**: External systems can POST a PDF over HTTP and receive structured extraction results without running the CLI
**Depends on**: Phase 6 (stable schema), Phase 5 (existing FastAPI app to extend)
**Requirements**: API-01, API-02, API-03, API-04, API-05, API-06
**Success Criteria** (what must be TRUE):
  1. User sends `POST /polizas/upload` with a PDF file as multipart/form-data and receives a 202 response with a job ID
  2. User polls `GET /jobs/{id}` and eventually sees status "complete" with the full extracted poliza in the response body
  3. The uploaded PDF triggers the complete pipeline (ingest -> extract -> persist) and the result is queryable via existing CRUD endpoints
  4. If the server is restarted, uploading the same PDF again succeeds and produces a result (job_store loss on restart is documented, not a crash)
  5. After extraction completes, no temporary PDF files remain on disk
**Plans:** 2 plans
Plans:
- [ ] 08-01-PLAN.md — Upload module (upload.py) with job store, routes, validation, python-multipart dep, unit tests
- [ ] 08-02-PLAN.md — Pipeline integration tests for background extraction, cleanup, idempotency

### Phase 9: Async Batch
**Goal**: Users can process large PDF batches significantly faster by running extractions concurrently without hitting SQLite lock errors or API rate limits
**Depends on**: Phase 6 (WAL mode configuration is a migration-adjacent DB concern), Phase 4 (existing sync batch to extend)
**Requirements**: ASYNC-01, ASYNC-02, ASYNC-03, ASYNC-04, ASYNC-05
**Success Criteria** (what must be TRUE):
  1. User runs `poliza-extractor batch folder/ --concurrency 3` and all PDFs are processed with 3 concurrent workers
  2. Processing 10 PDFs concurrently completes without any "database is locked" errors
  3. When the Anthropic API returns a rate limit error, the CLI automatically retries with backoff and eventually succeeds (no silent None results)
  4. The Rich progress bar and final summary table still display correctly during concurrent runs
  5. Running the same batch twice (idempotency) still skips already-processed files and produces no duplicate records
**Plans:** 2 plans
Plans:
- [ ] 09-01-PLAN.md — [to be planned]
- [ ] 09-02-PLAN.md — [to be planned]

### Phase 10: Quality Evaluator
**Goal**: Users can optionally invoke a Sonnet-powered scoring pass on any extraction to assess completeness, accuracy, and hallucination risk
**Depends on**: Phase 6 (evaluation columns from migration 002), Phase 3 (stable extraction pipeline to evaluate)
**Requirements**: QAL-01, QAL-02, QAL-03, QAL-04, QAL-05
**Success Criteria** (what must be TRUE):
  1. User runs `poliza-extractor extract file.pdf --evaluate` and receives extraction output plus a quality score and field-level assessment
  2. Running extraction without `--evaluate` completes without any Sonnet API call (evaluator is never in the default path)
  3. Evaluation scores and details are retrievable from the database after the command completes
  4. User sends `POST /polizas/upload?evaluate=true` and the returned job result includes evaluation fields alongside the extraction
  5. The CLI output clearly separates Haiku extraction cost from Sonnet evaluation cost
**Plans:** 2 plans
Plans:
- [ ] 10-01-PLAN.md — [to be planned]
- [ ] 10-02-PLAN.md — [to be planned]

### Phase 11: Regression Suite
**Goal**: A repeatable, automated test suite catches extraction quality regressions by comparing field-by-field output against known-good fixtures
**Depends on**: Phase 3 (stable extraction pipeline), Phase 10 (evaluator available to enrich fixtures if desired)
**Requirements**: REG-01, REG-02, REG-03, REG-04
**Success Criteria** (what must be TRUE):
  1. Running `pytest -m regression` executes the golden dataset suite and produces a pass/fail result per fixture
  2. Running `pytest` (default, no marker) does NOT run regression tests (they are excluded from the default suite)
  3. When an extraction result differs from the fixture, the test output identifies exactly which fields drifted and by how much
  4. The fixture set covers at least one real policy PDF per insurer type represented in pdfs-to-test/ with no PII committed to the repository
**Plans:** 2 plans
Plans:
- [ ] 11-01-PLAN.md — [to be planned]
- [ ] 11-02-PLAN.md — [to be planned]

## Progress

**Execution Order:**
Phases execute in numeric order: 6 -> 7 -> 8 -> 9 -> 10 -> 11

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 2/2 | Complete | 2026-03-18 |
| 2. Ingestion | 2/2 | Complete | 2026-03-18 |
| 3. Extraction | 2/2 | Complete | 2026-03-18 |
| 4. CLI & Batch | 2/2 | Complete | 2026-03-18 |
| 5. Storage & API | 2/2 | Complete | 2026-03-18 |
| 6. Migrations | 2/2 | Complete   | 2026-03-19 |
| 7. Export | 2/2 | Complete   | 2026-03-19 |
| 8. PDF Upload API | 0/2 | Not started | - |
| 9. Async Batch | 0/? | Not started | - |
| 10. Quality Evaluator | 0/? | Not started | - |
| 11. Regression Suite | 0/? | Not started | - |
