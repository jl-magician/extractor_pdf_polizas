---
phase: 06-migrations
plan: 01
subsystem: database
tags: [alembic, sqlalchemy, sqlite, migrations, schema-versioning]

# Dependency graph
requires:
  - phase: 05-storage-api
    provides: SQLAlchemy ORM models (Poliza, Asegurado, Cobertura, IngestionCache) and database.py
provides:
  - Alembic migration infrastructure with SQLite batch mode (render_as_batch=True)
  - Baseline migration 001 with inspector-based detection for existing DBs
  - Evaluation columns migration 002 (evaluation_score, evaluation_json, evaluated_at, evaluated_model_id)
  - Updated Poliza ORM model with four evaluation fields
  - End-to-end migration chain test suite (5 tests)
affects: [07-auto-migrate, 10-evaluator, all future phases using polizas table]

# Tech tracking
tech-stack:
  added: [alembic>=1.13.0]
  patterns:
    - env.py preserves caller-set URL (only falls back to settings.DB_PATH if placeholder URL detected)
    - Baseline migration uses separate engine for create_all to avoid SQLAlchemy 2.0 transaction boundary issues
    - Migration 002 guards add_column with inspector check to handle fresh DBs (where 001 create_all already includes evaluation columns)
    - WAL PRAGMA committed before migration transaction begins (conn.commit() after PRAGMA)
    - Tests use tmp_path with absolute alembic.ini path for isolation

key-files:
  created:
    - alembic.ini
    - alembic/env.py
    - alembic/script.py.mako
    - alembic/versions/001_baseline.py
    - alembic/versions/002_evaluation_columns.py
    - tests/test_migrations.py
  modified:
    - pyproject.toml (added alembic>=1.13.0 dependency)
    - policy_extractor/storage/models.py (added 4 evaluation columns to Poliza)

key-decisions:
  - "env.py URL override: only apply settings.DB_PATH fallback when alembic.ini has placeholder URL — preserves test and _auto_migrate caller-set URLs"
  - "Baseline migration 001 uses separate engine for create_all (not the Alembic migration connection) due to SQLAlchemy 2.0 autobegin transaction isolation"
  - "Migration 002 guards add_column operations with inspector check to avoid duplicate column error on fresh DBs"
  - "WAL PRAGMA requires conn.commit() before context.begin_transaction() to avoid transaction conflicts"

patterns-established:
  - "Migration URL isolation: cfg.set_main_option('sqlalchemy.url', ...) in callers + env.py placeholder check"
  - "Idempotent baseline: 001 uses create_all for fresh DB, does nothing for existing DB (inspector guard)"
  - "Idempotent column migrations: guard add_column with inspector.get_columns() check"
  - "WAL PRAGMA pattern: execute + commit before migration transaction"

requirements-completed: [MIG-01, MIG-02, MIG-03]

# Metrics
duration: 9min
completed: 2026-03-19
---

# Phase 6 Plan 01: Alembic Migration Infrastructure Summary

**Alembic 1.13+ with SQLite batch mode, two-migration chain (baseline + evaluation columns), and 5 end-to-end tests covering fresh DB, existing DB, downgrade, and WAL mode**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-19T15:53:07Z
- **Completed:** 2026-03-19T16:02:XX Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Alembic installed and configured with `render_as_batch=True` and WAL PRAGMA for SQLite compatibility
- Two-migration chain: 001 baseline (inspector-based detection) + 002 evaluation columns (4 fields)
- Poliza ORM model updated with evaluation_score, evaluation_json, evaluated_at, evaluated_model_id
- 5 migration tests pass covering all critical scenarios; full suite: 158 passed, 2 skipped

## Task Commits

Each task was committed atomically:

1. **Task 1: Install Alembic and create migration infrastructure** - `f809939` (feat)
2. **Task 2: Write end-to-end migration chain tests** - `dde7a32` (test, includes bug fixes)

_Note: Task 2 TDD combined test + fix commits since fixes were inseparable from making tests green._

## Files Created/Modified

- `alembic.ini` - Alembic config with script_location and placeholder URL
- `alembic/env.py` - Migration environment with render_as_batch=True, WAL PRAGMA, URL isolation fix
- `alembic/script.py.mako` - Standard migration file template
- `alembic/versions/001_baseline.py` - Baseline migration with inspector guard and separate engine create_all
- `alembic/versions/002_evaluation_columns.py` - Adds 4 evaluation columns with idempotent guard
- `tests/test_migrations.py` - 5 end-to-end migration tests
- `pyproject.toml` - Added alembic>=1.13.0 to dependencies
- `policy_extractor/storage/models.py` - Added 4 evaluation columns to Poliza class

## Decisions Made

- **env.py URL isolation**: env.py only applies `settings.DB_PATH` when alembic.ini has the placeholder URL. This preserves URLs set by tests (`make_alembic_cfg`) and `_auto_migrate`. Without this fix, all migrations ran against production DB instead of the test temp DB.
- **Separate engine for create_all in 001**: SQLAlchemy 2.0 autobegin means the Alembic migration connection's transaction doesn't commit `create_all` DDL properly. Using a fresh engine with explicit `conn.commit()` ensures tables land on disk.
- **Idempotent 002**: `batch_alter_table` + inspector guard prevents "duplicate column name" error when a fresh DB is created via 001's `create_all` (which includes evaluation columns from current ORM model).
- **WAL PRAGMA commit**: `connection.commit()` after `PRAGMA journal_mode=WAL` ensures the pragma is applied before the migration transaction starts, preventing `alembic_version` inserts from failing silently.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLAlchemy 2.0 removed `bind=` kwarg from `create_all` in migration context**
- **Found during:** Task 2 (TDD RED phase — tests revealed empty tables after upgrade)
- **Issue:** `Base.metadata.create_all(bind=bind)` raises no error but does nothing in SQLAlchemy 2.0 Alembic migration context due to transaction boundary issue
- **Fix:** Switched to a separate `create_engine(db_url)` with explicit `conn.commit()` inside migration 001
- **Files modified:** `alembic/versions/001_baseline.py`
- **Verification:** `pytest tests/test_migrations.py::test_fresh_db_upgrade_head` passes
- **Committed in:** dde7a32 (Task 2 commit)

**2. [Rule 1 - Bug] env.py unconditionally overwrote caller-set URL with settings.DB_PATH**
- **Found during:** Task 2 (tests ran migrations against production DB instead of tmp_path DB)
- **Issue:** `config.set_main_option("sqlalchemy.url", ...)` in env.py ran after caller set the test URL, silently redirecting all migrations
- **Fix:** Added placeholder check — only override if URL is None or equals `"sqlite:///data/polizas.db"` (alembic.ini default)
- **Files modified:** `alembic/env.py`
- **Verification:** Migration tests use correct tmp_path DB; production path still correct via settings
- **Committed in:** dde7a32 (Task 2 commit)

**3. [Rule 1 - Bug] WAL PRAGMA without commit caused alembic_version INSERT to not persist**
- **Found during:** Task 2 (current_revision returned None despite tables existing)
- **Issue:** PRAGMA started implicit transaction; migration transaction's version INSERT was silently rolled back
- **Fix:** Added `connection.commit()` after PRAGMA before `context.configure`
- **Files modified:** `alembic/env.py`
- **Verification:** `alembic_version` table shows `('002',)` after upgrade head
- **Committed in:** dde7a32 (Task 2 commit)

**4. [Rule 1 - Bug] Migration 002 failed with "duplicate column name" on fresh DBs**
- **Found during:** Task 2 (after fix 1, upgrade head failed in migration 002)
- **Issue:** Fresh DB via 001 `create_all` already includes evaluation columns (current ORM model); 002 then tries to ALTER TABLE to add them again
- **Fix:** Added inspector guard in 002's upgrade() — skip `add_column` if column already exists
- **Files modified:** `alembic/versions/002_evaluation_columns.py`
- **Verification:** All 5 migration tests pass including fresh DB and existing DB scenarios
- **Committed in:** dde7a32 (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (all Rule 1 — bugs)
**Impact on plan:** All fixes required for correctness. SQLAlchemy 2.0 transaction boundary semantics and Alembic URL precedence are subtle; fixes establish correct patterns for all future migrations.

## Issues Encountered

Multiple SQLAlchemy 2.0 + Alembic compatibility issues discovered during TDD (all fixed):
1. `create_all` in migration context requires separate engine (not Alembic's connection)
2. env.py URL override must check for placeholder, not unconditionally override
3. WAL PRAGMA needs explicit commit before migration transaction
4. Fresh DB created by 001 already has columns that 002 would duplicate

All discovered via TDD RED phase — tests failed in useful ways that pinpointed each issue.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Alembic infrastructure complete; all future column additions go through migrations
- `alembic upgrade head` on both fresh and existing DBs is idempotent and correct
- Phase 7 (auto-migrate in CLI startup) can now use `_auto_migrate()` pattern from RESEARCH.md
- Pending todo from STATE.md: run `alembic stamp head` on existing `polizas.db` before applying Phase 7 auto-migrate

---
*Phase: 06-migrations*
*Completed: 2026-03-19*
