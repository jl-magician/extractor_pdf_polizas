---
phase: 06-migrations
plan: 02
subsystem: storage/migrations
tags: [alembic, sqlite, wal, migration-guard, database]
dependency_graph:
  requires: [06-01]
  provides: [auto-migration-on-startup, wal-mode, migration-backup]
  affects: [policy_extractor/storage/database.py, policy_extractor/cli.py]
tech_stack:
  added: []
  patterns: [alembic-guard-pattern, wal-mode-pragma, lazy-import-alembic]
key_files:
  created: []
  modified:
    - policy_extractor/storage/database.py
    - tests/test_migrations.py
decisions:
  - "_get_alembic_cfg resolves alembic.ini via Path(__file__).parent.parent.parent to work from any CWD"
  - "Lazy alembic imports inside functions avoid overhead when migration not needed"
  - "Backup created only when current_rev != head_rev to avoid unnecessary I/O on up-to-date DBs"
metrics:
  duration: "2m"
  completed_date: "2026-03-19"
  tasks_completed: 2
  files_modified: 2
---

# Phase 06 Plan 02: Runtime Migration Guard Summary

**One-liner:** Rewrote database.py with WAL mode via PRAGMA, init_db guard logic (fresh=create_all+stamp, existing=auto-migrate with .bak backup), and 4 integration tests covering all paths.

## What Was Built

### Task 1: Rewrite database.py with WAL mode, migration guard, stamp, and auto-migrate

Rewrote `policy_extractor/storage/database.py` with five new/updated functions:

- **`get_engine()`** — Now sets `PRAGMA journal_mode=WAL` on every connection via `conn.execute(text(...))` + `conn.commit()`.
- **`init_db()`** — Checks for `alembic_version` table presence via `inspect(engine).get_table_names()`. Absent = fresh path (`create_all` + `_stamp_head`). Present = existing path (`_auto_migrate`).
- **`_get_alembic_cfg()`** — Resolves `alembic.ini` via `Path(__file__).parent.parent.parent` so CLI works from any working directory.
- **`_stamp_head()`** — Calls `command.stamp(cfg, "head")` to mark fresh DBs without running migration upgrade functions.
- **`_auto_migrate()`** — Compares `current_rev` vs `head_rev` via `MigrationContext`. If different: creates `.bak` backup via `shutil.copy2`, then runs `command.upgrade(cfg, "head")`.

All alembic imports are lazy (inside functions) to avoid import overhead when migrations are not needed.

### Task 2: Integration tests for init_db guard logic

Appended 4 integration tests to `tests/test_migrations.py`:

| Test | What it verifies |
|------|-----------------|
| `test_init_db_fresh_creates_and_stamps` | Fresh DB gets all tables + non-None head stamp |
| `test_init_db_existing_db_auto_migrates` | DB stamped at 001 auto-migrates to 002, data preserved |
| `test_auto_migrate_creates_backup` | `.bak` file exists after migration runs |
| `test_get_engine_enables_wal` | `get_engine()` sets WAL journal mode directly |

Full suite result: **162 passed, 2 skipped** (153 existing + 9 migration tests).

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files exist:
- `policy_extractor/storage/database.py` — contains `_auto_migrate`, `_stamp_head`, `PRAGMA journal_mode=WAL`, `shutil.copy2`
- `tests/test_migrations.py` — contains all 4 new integration tests

### Commits exist:
- `0bd7b0b` — feat(06-02): rewrite database.py
- `1dabf34` — test(06-02): integration tests

## Self-Check: PASSED
