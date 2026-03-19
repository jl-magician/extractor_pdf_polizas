---
phase: 04-cli-batch
plan: 02
subsystem: cli
tags: [typer, rich, progress-bar, batch-processing, idempotency, cost-tracking, cli-testing]

# Dependency graph
requires:
  - phase: 04-cli-batch plan 01
    provides: extract_policy tuple return, cli_helpers (estimate_cost, is_already_extracted)
  - phase: 03-extraction
    provides: extract_policy, PolicyExtraction
  - phase: 02-ingestion
    provides: ingest_pdf, compute_file_hash
provides:
  - policy_extractor/cli.py: Typer CLI app with extract and batch subcommands
  - poliza-extractor entry point registered in pyproject.toml
  - tests/test_cli.py: 12 passing tests including full CLI command coverage
affects: [end users, pyproject.toml entry point, tests/test_cli.py]

# Tech tracking
tech-stack:
  added:
    - typer>=0.9.0
    - rich>=13.0.0 (Rich progress bars, tables, console)
  patterns:
    - typer.testing.CliRunner for isolated CLI test invocation
    - Rich Progress with SpinnerColumn + BarColumn + MofNCompleteColumn + TimeElapsedColumn
    - Rich Table for batch summary and failure listing
    - Console(stderr=True) routes UI output to stderr; JSON data to stdout
    - patch() all pipeline entry points for fast mocked CLI tests

key-files:
  created:
    - policy_extractor/cli.py
  modified:
    - pyproject.toml
    - tests/test_cli.py

key-decisions:
  - "Rich console configured with stderr=True — JSON stays clean on stdout for piping while progress/cost go to stderr"
  - "Batch uses single SQLAlchemy session for all PDFs — one session opened before loop, closed in finally block"
  - "Batch exit code 1 on any failure — allows CI/shell scripts to detect partial failures"
  - "typer.Option(False, '--force') with flag pattern — consistent with project convention, force=True bypasses both ingestion cache and extraction idempotency"

patterns-established:
  - "CLI test pattern: patch all 6 pipeline entry points (init_db, SessionLocal, compute_file_hash, is_already_extracted, ingest_pdf, extract_policy) for full isolation"
  - "Rich progress bar disabled when quiet=True via disable=quiet parameter"

requirements-completed: [ING-03, ING-04, CLI-01, CLI-02, CLI-03, CLI-05]

# Metrics
duration: 3min
completed: 2026-03-18
---

# Phase 4 Plan 2: CLI Commands (extract, batch, progress, cost tracking) Summary

**Typer CLI with extract and batch subcommands, Rich progress bar, summary table, idempotency skip, and cost reporting — plus full mocked test coverage (12 tests, 0 stubs)**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-18T22:38:20Z
- **Completed:** 2026-03-18T22:41:23Z
- **Tasks:** 2
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- policy_extractor/cli.py: Typer app with `extract` (single PDF) and `batch` (directory) subcommands
- extract: ingest_pdf + extract_policy pipeline, idempotency skip via source_file_hash, cost reporting, --output-dir support
- batch: Rich progress bar (spinner, bar, X/Y count, %, elapsed), per-file error handling continues batch, Rich summary table + failure detail table
- pyproject.toml: typer + rich dependencies added, `poliza-extractor` entry point registered
- tests/test_cli.py: all 5 skip stubs replaced with 7 real tests (12 total); all pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Typer CLI module with extract and batch subcommands** - `e0aaa70` (feat)
2. **Task 2: Complete CLI test coverage with mocked pipeline** - `6b29103` (feat)

## Files Created/Modified

- `policy_extractor/cli.py` - New module: Typer app, extract command, batch command, cost helper
- `pyproject.toml` - Added typer>=0.9.0, rich>=13.0.0, [project.scripts] entry point
- `tests/test_cli.py` - Full CLI test coverage: 12 tests, 0 stubs

## Decisions Made

- Rich console writes to stderr; JSON output via print() goes to stdout — clean pipe behavior
- Batch uses single session for the whole loop to reduce DB connection overhead
- Exit code 1 on any batch failure so shell scripts and CI can detect incomplete runs
- Tests mock all 6 pipeline entry points for complete isolation from the actual API/DB

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

`poliza-extractor` command available via `pip install -e .`. The scripts directory may need to be on PATH depending on Python installation (warned during install on this machine — use `python -m policy_extractor.cli` as fallback).

## Test Results

- Full suite: 116 passed, 2 skipped (Tesseract-dependent), 0 failures
- CLI tests: 12/12 passed, 0 stubs remaining

## Self-Check: PASSED

- `policy_extractor/cli.py` exists and imports OK
- `pyproject.toml` contains `poliza-extractor = "policy_extractor.cli:app"` and typer dependency
- `tests/test_cli.py` has 12 tests, 0 skip stubs
- Commits e0aaa70, 6b29103 exist in git log

---
*Phase: 04-cli-batch*
*Completed: 2026-03-18*
