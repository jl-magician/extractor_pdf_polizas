---
phase: 05-storage-api
plan: 01
subsystem: storage
tags: [persistence, upsert, orm, cli, sqlite, tdd]
dependency_graph:
  requires:
    - policy_extractor/storage/models.py
    - policy_extractor/schemas/poliza.py
    - policy_extractor/schemas/asegurado.py
    - policy_extractor/schemas/cobertura.py
    - policy_extractor/cli.py
  provides:
    - policy_extractor/storage/writer.py (upsert_policy, orm_to_schema)
    - auto-persist in CLI extract + batch commands
  affects:
    - policy_extractor/storage/__init__.py
    - policy_extractor/cli.py
    - pyproject.toml
tech_stack:
  added:
    - fastapi>=0.135.1
    - uvicorn[standard]>=0.42.0
  patterns:
    - upsert by (numero_poliza, aseguradora) with child replacement
    - confianza stored inside campos_adicionales['confianza'] in DB
    - persistence-failure-safe CLI (stdout JSON always emitted first)
key_files:
  created:
    - policy_extractor/storage/writer.py
    - tests/test_storage_writer.py
  modified:
    - policy_extractor/storage/__init__.py
    - policy_extractor/cli.py
    - pyproject.toml
decisions:
  - "confianza stored inside campos_adicionales['confianza'] in ORM; orm_to_schema extracts it back to top-level field — avoids adding a new DB column while preserving round-trip fidelity"
  - "Persistence import is deferred (inside try block in CLI) — decouples CLI startup from storage module import errors"
  - "asegurados.clear() + session.flush() before re-adding children ensures cascade delete-orphan removes old rows before new ones are inserted — avoids FK constraint issues"
metrics:
  duration: "~8 min"
  completed_date: "2026-03-18"
  tasks_completed: 2
  files_created: 2
  files_modified: 3
---

# Phase 5 Plan 1: Storage Writer and CLI Auto-Persist Summary

**One-liner:** SQLite upsert writer with child replacement, confianza-in-campos_adicionales pattern, wired into both CLI commands with stderr-safe error handling.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Writer module with upsert_policy and orm_to_schema + tests | 5a5ffd9 | writer.py, __init__.py, test_storage_writer.py, pyproject.toml |
| 2 | Wire auto-persist into extract and batch CLI commands | 973b80c | cli.py |

## What Was Built

### writer.py

`upsert_policy(session, extraction) -> Poliza`:
- Deduplicates by `(numero_poliza, aseguradora)` using `filter_by(...).first()`
- On update: clears `asegurados` and `coberturas` lists and calls `session.flush()` before re-adding children (ensures cascade delete-orphan removes old rows)
- Copies 14 scalar fields via setattr loop
- Merges `extraction.confianza` into `campos_adicionales["confianza"]` before persisting
- Appends Asegurado and Cobertura ORM rows from extraction lists
- Commits and returns the Poliza row

`orm_to_schema(poliza) -> PolicyExtraction`:
- Reconstructs PolicyExtraction from ORM columns
- Pops `confianza` from `campos_adicionales` dict, assigns to dedicated `confianza` field
- Maps `poliza.asegurados` to `AseguradoExtraction` list
- Maps `poliza.coberturas` to `CoberturaExtraction` list

### storage/__init__.py

Added `upsert_policy` and `orm_to_schema` to exports.

### cli.py

Both `extract` and `batch` commands:
- JSON stdout is printed BEFORE the persistence call
- Persistence is wrapped in `try/except` — any failure logs a yellow WARN to stderr only
- Import is inside the try block to decouple CLI startup from writer module

### pyproject.toml

Added `fastapi>=0.135.1` and `uvicorn[standard]>=0.42.0` to dependencies (needed for Plan 02 API layer).

## Test Coverage

13 tests in `tests/test_storage_writer.py`:
- create new Poliza with correct scalar fields
- dedup — re-upsert stays count=1, fields updated
- child persistence (asegurados and coberturas) with correct FK
- child replacement on upsert (old rows deleted, not duplicated)
- confianza stored in campos_adicionales
- Decimal fields survive round-trip
- orm_to_schema scalar fields, confianza extraction, asegurados, coberturas
- full round-trip fidelity including Decimal

All 25 tests pass (13 new + 12 existing CLI tests).

## Deviations from Plan

None — plan executed exactly as written.

## Decisions Made

1. **confianza stored in campos_adicionales:** Avoids a new DB column while preserving full round-trip fidelity. orm_to_schema pops it back to the top-level field.
2. **Deferred import in CLI:** `from policy_extractor.storage.writer import upsert_policy` inside the try block isolates CLI startup from storage import errors.
3. **flush before child re-add:** `session.flush()` after clearing children ensures cascade delete-orphan fires before new children are appended — prevents FK violation.
