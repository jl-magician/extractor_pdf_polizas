---
phase: 09-async-batch
plan: 01
subsystem: extraction
tags: [retry, rate-limit, backoff, jitter, tdd]
dependency_graph:
  requires: []
  provides:
    - rate-limit-retry-in-extract_with_retry
    - rl_retries-count-in-extract_policy-return
  affects:
    - policy_extractor/extraction/client.py
    - policy_extractor/extraction/__init__.py
    - policy_extractor/cli.py
tech_stack:
  added: [random, time]
  patterns:
    - nested-for-retry-loop-inside-outer-validation-retry
    - 4-tuple-return-threading-retry-count-to-callers
key_files:
  created: []
  modified:
    - policy_extractor/extraction/client.py
    - policy_extractor/extraction/__init__.py
    - policy_extractor/cli.py
    - tests/test_cli.py
    - tests/test_extraction.py
decisions:
  - "Rate limit retry placed INSIDE extract_with_retry wrapping call_extraction_api — avoids broad except Exception swallowing errors before retry can act"
  - "extract_with_retry returns 4-tuple (policy, raw_response, usage, rl_retries) to surface retry count to callers"
  - "extract_policy returns 3-tuple (policy, usage, rl_retries) threading count all the way to CLI"
  - "Non-429 4xx errors (BadRequestError) fall through to outer except Exception and return None immediately — not retried"
metrics:
  duration: ~10m
  completed_date: "2026-03-19"
  tasks: 2
  files: 5
---

# Phase 9 Plan 01: Rate Limit Retry with Exponential Backoff Summary

**One-liner:** Rate limit retry loop (2s/4s/8s + jitter) added inside `extract_with_retry` wrapping `call_extraction_api`, threading retry count as 4-tuple through to 3-tuple `extract_policy` return.

## What Was Built

Added automatic retry logic for Anthropic API transient errors to the extraction pipeline. When the API returns a 429 rate limit, 5xx server error, or connection error, the system now retries up to 3 times with exponential backoff (2s, 4s, 8s) plus random jitter (0-1s) to prevent thundering herd.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add rate limit retry tests (TDD RED) | e8ebeda | tests/test_cli.py |
| 2 | Implement rate limit retry + thread count | e8450d5 | client.py, __init__.py, cli.py, test_cli.py, test_extraction.py |

## Key Changes

### `policy_extractor/extraction/client.py`
- Added `import random` and `import time`
- Added `_RATE_LIMIT_MAX_RETRIES = 3` and `_RATE_LIMIT_BACKOFF = [2, 4, 8]` constants
- Added `max_rate_limit_retries: int = 3` parameter to `extract_with_retry`
- Added inner `for rl_attempt in range(max_rate_limit_retries + 1)` loop inside existing `for attempt` loop, wrapping `call_extraction_api`
- Catches `anthropic.RateLimitError`, `anthropic.InternalServerError`, `anthropic.APIConnectionError`
- On success, returns 4-tuple `(policy, raw_response, usage, rl_retries)`

### `policy_extractor/extraction/__init__.py`
- `extract_policy` now returns `tuple[PolicyExtraction | None, Usage | None, int]`
- Unpacks 4-tuple from `extract_with_retry`: `policy, raw_response, usage, rl_retries = outcome`
- Returns `(verified_policy, usage, rl_retries)` on success, `(None, None, 0)` on failure

### `policy_extractor/cli.py`
- Both `extract` and `batch` commands updated: `policy, usage, _retries = extract_policy(...)`

### `tests/test_cli.py`
- 5 new rate limit retry tests added in `# Tests -- rate limit retry (Phase 9)` section
- All 7 existing `extract_policy` mock return values updated from 2-tuple to 3-tuple

### `tests/test_extraction.py`
- 9 `extract_policy` unpack sites updated from `result, usage = ...` to `result, usage, _rl_retries = ...`

## Decisions Made

1. **Retry placement:** Rate limit retry is placed INSIDE `extract_with_retry` (not outside), wrapping `call_extraction_api` directly. This is above the broad `except Exception` handler that would otherwise swallow transient errors before retries could occur (per RESEARCH.md Pitfall 1).

2. **Return type extension:** `extract_with_retry` returns a 4-tuple to surface retry count. `extract_policy` returns a 3-tuple. This is the minimal change needed to thread the count to Plan 02's batch summary table.

3. **Non-429 4xx behavior:** `BadRequestError` and other non-429 client errors fall through to the outer `except Exception` handler and return `None` immediately — not retried. Only transient errors (rate limit, server error, connection error) retry.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Retry loop re-raise not caught by outer except Exception**
- **Found during:** Task 2 implementation + test run (test_rate_limit_retry_exhausted failing)
- **Issue:** Rate limit retry loop's `raise` on exhaustion propagated out of both `for` loops, escaping the outer `except Exception` handler (which was in a separate try block wrapping only `parse_and_validate`, not `call_extraction_api`)
- **Fix:** Wrapped the entire rate limit retry loop AND `parse_and_validate` in a single `try` block so the outer `except Exception` catches both rate limit exhaustion and parse failures
- **Files modified:** `policy_extractor/extraction/client.py`
- **Commit:** e8450d5 (included in Task 2 commit)

**2. [Rule 1 - Bug] test_extraction.py 9 sites unpacking 2-tuple from extract_policy**
- **Found during:** Task 2 full suite run
- **Issue:** All 9 call sites in `tests/test_extraction.py` still did `result, usage = extract_policy(...)` after extract_policy changed to return a 3-tuple
- **Fix:** Updated all 9 sites to `result, usage, _rl_retries = extract_policy(...)`
- **Files modified:** `tests/test_extraction.py`
- **Commit:** e8450d5

## Test Results

- **Before plan:** 153 passing (pre-v1.1 baseline), 199 passing (end of phase 8)
- **After plan:** 204 passing, 2 skipped, 0 failures
- **New tests added:** 5 rate limit retry tests
- **Regressions:** 0

## Self-Check: PASSED

- `policy_extractor/extraction/client.py`: FOUND
- `policy_extractor/extraction/__init__.py`: FOUND
- `policy_extractor/cli.py`: FOUND
- `tests/test_cli.py`: FOUND
- `tests/test_extraction.py`: FOUND
- Commit e8ebeda (TDD RED): FOUND
- Commit e8450d5 (implementation): FOUND
- All 204 tests pass: CONFIRMED
