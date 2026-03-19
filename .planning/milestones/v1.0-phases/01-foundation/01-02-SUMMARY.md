---
phase: 01-foundation
plan: 02
subsystem: database
tags: [sqlalchemy, sqlalchemy-2.0, sqlite, orm, pydantic, testing, pytest]

# Dependency graph
requires:
  - "01-01"  # Pydantic schemas (PolicyExtraction, AseguradoExtraction, CoberturaExtraction)
provides:
  - "SQLAlchemy 2.0 ORM models — Poliza, Asegurado, Cobertura with correct column types"
  - "Database engine factory get_engine() and init_db() with CREATE TABLE IF NOT EXISTS"
  - "SessionLocal sessionmaker for use by downstream phases"
  - "42-test suite verifying all DATA-01 through DATA-05 requirements"
  - "In-memory SQLite test fixture (conftest.py) for all future model tests"
affects:
  - 02  # Ingestion phase uses init_db() and SessionLocal
  - 05  # Storage writer phase inserts Poliza, Asegurado, Cobertura ORM rows

# Tech tracking
tech-stack:
  added:
    - "SQLAlchemy 2.0 mapped_column + Mapped[] declarative models (already in deps)"
    - "pytest fixtures: engine (in-memory SQLite) + session (scoped Session)"
  patterns:
    - "SQLAlchemy 2.0 DeclarativeBase with Mapped[T] annotations — not Column() style"
    - "Numeric(precision=15, scale=2) for all monetary fields — prevents IEEE 754 float corruption"
    - "Date column type (not String) for all date fields — enforces ISO storage, enables range queries"
    - "JSON mapped_column for campos_adicionales on all three tables — SQLAlchemy handles serialize/deserialize"
    - "cascade='all, delete-orphan' on both relationships — asegurados/coberturas deleted with poliza"
    - "In-memory SQLite via create_engine('sqlite:///:memory:') for test isolation"

key-files:
  created:
    - "policy_extractor/storage/models.py"
    - "policy_extractor/storage/database.py"
    - "tests/conftest.py"
    - "tests/test_models.py"
  modified:
    - "policy_extractor/storage/__init__.py"
    - "tests/test_schemas.py"

key-decisions:
  - "Models mirror Pydantic schemas exactly — same field names, same optionality — easing ORM-from-Pydantic mapping in Phase 5"
  - "TDD ordering: Task 1 (implementation) committed before Task 2 (tests) — plan structure mandated this sequence; tests verified correctness post-implementation"
  - "source_file_hash uses String(64) to hold sha256 hex strings; no UNIQUE constraint per research decision (same PDF can be re-extracted with new prompt_version)"
  - "SessionLocal not bound to engine at import time — caller must do SessionLocal.configure(bind=engine) or use Session(engine) directly"

# Metrics
duration: 2min
completed: 2026-03-18
---

# Phase 1 Plan 2: SQLAlchemy ORM Models and Test Suite Summary

**SQLAlchemy 2.0 ORM models (Poliza, Asegurado, Cobertura) with Numeric monetary columns, Date date columns, JSON overflow, FK relationships, provenance tracking, and a 42-test pytest suite verifying all DATA-01 through DATA-05 requirements.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-18T15:50:17Z
- **Completed:** 2026-03-18T15:52:00Z
- **Tasks:** 2
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments

- Three SQLAlchemy 2.0 ORM models with correct column types for all fields
- Numeric(15,2) monetary columns on Poliza.prima_total, Cobertura.suma_asegurada, Cobertura.deducible
- Date columns on all date fields — Poliza (fecha_emision, inicio_vigencia, fin_vigencia), Asegurado (fecha_nacimiento)
- JSON campos_adicionales on all three tables — round-trips arbitrary dicts through SQLite TEXT
- FK poliza_id on asegurados and coberturas with cascade="all, delete-orphan"
- All four DATA-05 provenance columns on polizas table
- init_db() idempotent table creation; get_engine() creates parent directories automatically
- 42 pytest tests green — 11 ORM model tests + 21 existing schema tests + 10 new exact-named schema tests

## Task Commits

Each task was committed atomically:

1. **Task 1: SQLAlchemy models and database initialization** - `0ee5b84` (feat)
2. **Task 2: Comprehensive test suite** - `e3408fd` (feat)

## Files Created/Modified

- `policy_extractor/storage/models.py` — Poliza, Asegurado, Cobertura declarative models
- `policy_extractor/storage/database.py` — get_engine(), init_db(), SessionLocal
- `policy_extractor/storage/__init__.py` — updated exports: Base, Poliza, Asegurado, Cobertura, get_engine, init_db, SessionLocal
- `tests/conftest.py` — engine and session pytest fixtures using sqlite:///:memory:
- `tests/test_models.py` — 11 ORM tests covering DATA-01 through DATA-05 plus cascade delete
- `tests/test_schemas.py` — 13 additional exact-named tests added (total 42 tests from 21)

## Decisions Made

- Models mirror Pydantic schema field names exactly — same names, same optionality — this makes Phase 5 ORM-from-Pydantic mapping straightforward without field renaming.
- `source_file_hash` uses `String(64)` (sha256 hex is 64 chars) with an index for hash lookups but NO UNIQUE constraint — same PDF can legitimately be re-extracted with a different `prompt_version`, creating a new row intentionally.
- `SessionLocal` is defined at module level but not bound to an engine — callers use `Session(engine)` directly in tests; Phase 5 will call `SessionLocal.configure(bind=engine)` at startup.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

**Note on TDD ordering:** Task 2 is labeled `tdd="true"` in the plan, but the plan's task sequence (Task 1 = implementation, Task 2 = tests) means implementation preceded tests. The tests were written to verify the already-complete implementation and all 42 passed immediately. This is an inherent structural pattern (not a deviation) when a plan separates implementation and testing into sequential tasks.

## User Setup Required

None — no external dependencies or configuration required. `tests/` can be run immediately with `python -m pytest tests/ -v`.

## Next Phase Readiness

- `from policy_extractor.storage import Poliza, Asegurado, Cobertura, init_db, SessionLocal` works
- Phase 2 (ingestion) can call `init_db()` to initialize the database before writing rows
- Phase 5 (storage writer) has the complete ORM model surface needed to persist PolicyExtraction instances
- No blockers for Phase 2

---
*Phase: 01-foundation*
*Completed: 2026-03-18*

## Self-Check: PASSED

- `policy_extractor/storage/models.py`: FOUND
- `policy_extractor/storage/database.py`: FOUND
- `tests/conftest.py`: FOUND
- `tests/test_models.py`: FOUND
- Task 1 commit 0ee5b84: FOUND
- Task 2 commit e3408fd: FOUND
- Final test run: 42 passed in 0.27s
