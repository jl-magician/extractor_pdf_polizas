---
phase: 09-async-batch
plan: 02
subsystem: cli
tags: [concurrency, threadpool, batch, tdd]
dependency_graph:
  requires: [09-01]
  provides: [concurrent-batch-cli]
  affects: [policy_extractor/cli.py, tests/test_cli.py]
tech_stack:
  added: [threading, concurrent.futures.ThreadPoolExecutor, concurrent.futures.as_completed]
  patterns: [per-worker-session, thread-safe-counter-aggregation, sequential-bypass]
key_files:
  modified:
    - policy_extractor/cli.py
    - tests/test_cli.py
decisions:
  - "ThreadPoolExecutor with concurrency==1 bypass: sequential path skips thread pool entirely for identical pre-Phase 9 behavior"
  - "Per-worker SessionLocal(): each _process_single_pdf() creates and closes its own session, no shared state"
  - "threading.Lock guards counter aggregation in as_completed loop to prevent data races on succeeded/failed/skipped/total_retries"
  - "Retries row added to summary table threaded from extract_policy 3-tuple rl_retries value"
  - "TDD: RED commit (732068b) with 7 failing tests, then GREEN commit (1c0c0fb) with implementation"
metrics:
  duration: 3 minutes
  completed: 2026-03-19
  tasks_completed: 2
  files_modified: 2
---

# Phase 09 Plan 02: Concurrent Batch Processing Summary

**One-liner:** ThreadPoolExecutor concurrent batch with per-worker sessions, --concurrency flag (min=1, max=10), and Retries row in summary.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add concurrent batch tests (RED) | 732068b | tests/test_cli.py |
| 2 | Refactor batch command for concurrent execution (GREEN) | 1c0c0fb | policy_extractor/cli.py |

## What Was Built

### `_process_single_pdf()` worker function (cli.py)
Extracts all per-file logic from the batch loop into a standalone function that:
- Creates its own `SessionLocal()` session (ASYNC-03: thread-safe DB access)
- Runs idempotency check, ingestion, extraction, persistence, optional JSON output
- Unpacks `policy, usage, rl_retries = extract_policy(...)` from Plan 01's 3-tuple
- Returns a result dict with `"retries": rl_retries` (not hardcoded 0)
- Always closes session in `finally` block

### Updated `batch()` command
- Added `--concurrency` flag: `typer.Option(3, "--concurrency", min=1, max=10)`
- **Sequential path** (`concurrency == 1`): calls `_process_single_pdf()` in a for loop, no thread overhead
- **Concurrent path** (`concurrency > 1`): `ThreadPoolExecutor(max_workers=concurrency)` + `as_completed()`, guarded by `threading.Lock()` for counter aggregation
- Removed batch-scoped `session = SessionLocal()` — main thread no longer needs a session
- Added `total_retries` counter aggregated from worker results
- Added "Retries" row to summary table after "Skipped"

### Tests (7 new concurrent batch tests)
- `test_batch_concurrent_3_workers`: 3 PDFs, --concurrency 3, all succeed
- `test_concurrency_1_sequential`: --concurrency 1 does NOT instantiate ThreadPoolExecutor
- `test_concurrency_flag_validation`: --concurrency 0 and --concurrency 11 rejected (non-zero exit)
- `test_batch_worker_own_session`: SessionLocal() called >= 2 times for --concurrency 2
- `test_batch_summary_retries_row`: Retries row shows total across mixed retry counts (2+0=2)
- `test_batch_idempotency_concurrent`: already-extracted files skipped, extract_policy not called
- `test_batch_no_lock_errors`: 5 PDFs, --concurrency 3, no "locked" in output

## Verification Results

```
python -m pytest tests/test_cli.py -x -q   -> 32 passed
python -m pytest tests/ -x -q              -> 211 passed, 2 skipped
grep "ThreadPoolExecutor" cli.py            -> lines 17, 288
grep "_process_single_pdf" cli.py           -> lines 142, 262, 291
grep "threading.Lock" cli.py               -> line 286
grep '"Retries"' cli.py                    -> line 335
grep "rl_retries" cli.py                   -> lines 167, 188
```

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- policy_extractor/cli.py: FOUND (verified via grep)
- tests/test_cli.py: FOUND (verified via grep)
- Commit 732068b: FOUND
- Commit 1c0c0fb: FOUND
- 211 tests pass with 0 failures
