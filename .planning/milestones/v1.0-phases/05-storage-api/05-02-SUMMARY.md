---
phase: 05-storage-api
plan: 02
subsystem: api
tags: [fastapi, crud, filtering, pagination, cli, export, import, uvicorn, tdd, sqlite]
dependency_graph:
  requires:
    - policy_extractor/storage/writer.py (upsert_policy, orm_to_schema)
    - policy_extractor/storage/database.py (SessionLocal, init_db)
    - policy_extractor/storage/models.py (Poliza, Asegurado, Cobertura)
    - policy_extractor/schemas/poliza.py (PolicyExtraction)
    - policy_extractor/cli.py
    - policy_extractor/config.py
  provides:
    - policy_extractor/api/__init__.py (FastAPI app with full CRUD + filters)
    - export CLI subcommand (JSON array to stdout or file)
    - import CLI subcommand (JSON array or object into DB)
    - serve CLI subcommand (starts uvicorn)
  affects:
    - policy_extractor/cli.py
    - tests/test_cli.py
    - tests/test_api.py
tech_stack:
  added: []
  patterns:
    - StaticPool for in-memory SQLite sharing across test connections
    - model_dump(mode='json') for Decimal field serialization
    - selectinload for eager loading of asegurados and coberturas
    - dependency_overrides for FastAPI test isolation
    - confianza stored inside campos_adicionales in ORM (round-trip pattern from Plan 01)
key_files:
  created:
    - policy_extractor/api/__init__.py
    - tests/test_api.py
  modified:
    - policy_extractor/cli.py
    - tests/test_cli.py
decisions:
  - "StaticPool required for in-memory SQLite test engine: SQLite :memory: creates a new DB per connection; StaticPool forces all connections to reuse one underlying connection, preserving tables across test sessions"
  - "Import inside export/import functions avoids circular imports: storage.writer imported locally inside subcommand functions, keeping CLI startup decoupled from storage module"
  - "model_dump(mode='json') handles Decimal serialization: Pydantic converts Decimal to string in JSON mode, preventing JSONResponse TypeError"
  - "PUT /polizas/{id} updates by ID (not by numero_poliza+aseguradora): clears and rebuilds children directly on the located Poliza row, bypassing upsert_policy's dedup logic"
metrics:
  duration: "~5 min"
  completed_date: "2026-03-18"
  tasks_completed: 2
  files_created: 2
  files_modified: 2
---

# Phase 5 Plan 2: Export/Import CLI + FastAPI CRUD Summary

**One-liner:** FastAPI CRUD with 5-field filtering and pagination, plus export/import/serve CLI subcommands completing the full storage and query layer.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for export, import, serve | 1f31465 | tests/test_cli.py |
| 1 (GREEN) | Export, import, and serve CLI subcommands | b5bd55b | policy_extractor/cli.py |
| 2 (RED) | Failing tests for FastAPI CRUD endpoints | 9b6fa60 | tests/test_api.py |
| 2 (GREEN) | FastAPI app with full CRUD and filtering | 36ec20f | policy_extractor/api/__init__.py, tests/test_api.py |

## What Was Built

### CLI Subcommands (cli.py)

**`export` subcommand:**
- Queries Poliza with `selectinload(asegurados)` and `selectinload(coberturas)`
- Filters: `--insurer`, `--agent`, `--type`, `--from-date`, `--to-date` (all optional)
- Output: JSON array to stdout (default) or `--output file.json`
- Uses `orm_to_schema(p).model_dump(mode="json")` for Decimal-safe serialization

**`import` subcommand:**
- Reads JSON file, detects array vs single object (wraps dict in list)
- Validates each record via `PolicyExtraction.model_validate(record)`
- Upserts via `upsert_policy(session, extraction)`
- Reports count to stderr: "Imported N policy/policies"

**`serve` subcommand:**
- Delegates to `uvicorn.run("policy_extractor.api:app", host, port, reload)`

### FastAPI App (api/__init__.py)

**Routes:**
- `GET /polizas` — list with filters (aseguradora, tipo_seguro, nombre_agente, desde, hasta) and pagination (skip, limit)
- `GET /polizas/{id}` — single policy, 404 on missing
- `POST /polizas` — create via `upsert_policy`, returns 201
- `PUT /polizas/{id}` — locate by ID (404 if missing), clear+rebuild children, update scalar fields, commit
- `DELETE /polizas/{id}` — `session.delete(poliza)` cascades to children, returns 200

**Key patterns:**
- All list/single responses use `selectinload(Poliza.asegurados)` + `selectinload(Poliza.coberturas)`
- All responses use `orm_to_schema(p).model_dump(mode="json")` wrapped in `JSONResponse`
- `get_db` dependency is fully overridable for testing
- `on_startup` configures SessionLocal for production; tests override `get_db` to bypass

### Test Infrastructure

**tests/test_api.py:**
- 16 tests covering all CRUD endpoints, filters, pagination, 404 cases, Decimal serialization, /docs
- Uses `StaticPool` to share one in-memory SQLite connection across all test sessions
- `autouse=True` `clean_db` fixture drops/recreates tables before each test
- `dependency_overrides[get_db]` ensures tests never touch the real DB

**tests/test_cli.py (additions):**
- 8 new tests for export (empty, with data, filter, to-file), import (array, single, roundtrip), serve registration
- Uses `_make_mock_session_cls` helper to inject a real session backed by in-memory engine

## Test Coverage

- Total suite: 153 passed, 2 skipped (Tesseract-dependent OCR tests)
- CLI tests: 20 passed (12 existing + 8 new)
- API tests: 16 passed (all new)
- Storage writer tests: 13 passed (unchanged from Plan 01)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLite :memory: connection isolation**
- **Found during:** Task 2 GREEN — first API test failed with "no such table: polizas"
- **Issue:** `create_engine("sqlite:///:memory:")` creates a new empty DB for each connection. `drop_all/create_all` ran on one connection; `TestingSessionLocal()` opened a second connection to a separate empty DB.
- **Fix:** Added `poolclass=StaticPool` to the test engine — forces all connections to reuse one underlying connection, preserving schema across sessions.
- **Files modified:** `tests/test_api.py`
- **Commit:** 36ec20f (inline fix during GREEN phase)

## Decisions Made

1. **StaticPool for test SQLite:** Required to share schema state across multiple DB connections in the same in-memory instance.
2. **Local imports in CLI subcommands:** `from policy_extractor.storage.writer import upsert_policy` inside the function body — consistent with Plan 01's deferred-import pattern, avoids circular imports.
3. **PUT updates by ID, not by (numero_poliza, aseguradora):** REST semantics require update-by-ID. Implemented inline update logic rather than routing through `upsert_policy`, which deduplicates by business key.
4. **model_dump(mode='json') everywhere:** Pydantic renders Decimal as string in JSON mode — consistent with Plan 01's `model_dump_json()` approach, prevents JSONResponse TypeError on Decimal fields.

## Self-Check: PASSED

- policy_extractor/api/__init__.py: FOUND
- tests/test_api.py: FOUND
- .planning/phases/05-storage-api/05-02-SUMMARY.md: FOUND
- Commit 1f31465 (test RED Task 1): FOUND
- Commit b5bd55b (feat GREEN Task 1): FOUND
- Commit 9b6fa60 (test RED Task 2): FOUND
- Commit 36ec20f (feat GREEN Task 2): FOUND
