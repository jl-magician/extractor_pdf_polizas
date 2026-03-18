---
phase: 04-cli-batch
plan: 01
subsystem: extraction
tags: [anthropic, usage-tokens, cost-estimation, idempotency, cli-helpers, sqlalchemy]

# Dependency graph
requires:
  - phase: 03-extraction
    provides: extract_with_retry, extract_policy, PolicyExtraction, Poliza model with source_file_hash
provides:
  - extract_with_retry returns tuple[PolicyExtraction, dict, anthropic.types.Usage] | None
  - extract_policy accepts model override and returns tuple[PolicyExtraction | None, Usage | None]
  - cli_helpers.py with estimate_cost and is_already_extracted
  - tests/test_cli.py with 5 passing helper unit tests and 5 CLI stubs for Plan 02
affects: [04-02-cli-commands, any code calling extract_policy]

# Tech tracking
tech-stack:
  added: []
  patterns: [tuple return type for usage propagation, pricing key lookup via model_id substring match]

key-files:
  created:
    - policy_extractor/cli_helpers.py
    - tests/test_cli.py
  modified:
    - policy_extractor/extraction/client.py
    - policy_extractor/extraction/__init__.py
    - tests/test_extraction.py

key-decisions:
  - "extract_policy return type changed from PolicyExtraction | None to tuple[PolicyExtraction | None, Usage | None] — CLI needs usage data for cost reporting without a separate API call"
  - "PRICING hardcoded as module-level dict keyed by haiku/sonnet — avoids API calls for pricing lookup, values are stable and can be updated manually when Anthropic changes pricing"
  - "is_already_extracted uses select(Poliza.id).limit(1) — fetches minimal data (just id) for idempotency check, avoids loading full row"

patterns-established:
  - "Usage propagation: extract_with_retry returns Usage as third tuple element, extract_policy surfaces it to callers — avoids separate accounting layer"
  - "Model override pattern: effective_model = model or settings.EXTRACTION_MODEL allows per-call overrides without changing global config"

requirements-completed: [CLI-04, CLI-05]

# Metrics
duration: 2min
completed: 2026-03-18
---

# Phase 4 Plan 1: CLI Foundation (Usage Tokens, Model Override, Helpers) Summary

**Extraction pipeline extended to surface Anthropic usage tokens and model override; cli_helpers module with idempotency check and USD cost estimator ready for CLI consumption**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-18T22:13:33Z
- **Completed:** 2026-03-18T22:15:52Z
- **Tasks:** 2
- **Files modified:** 5 (3 modified, 2 created)

## Accomplishments
- extract_with_retry now returns (PolicyExtraction, dict, anthropic.types.Usage) — usage data flows to callers without extra API calls
- extract_policy accepts optional model override and returns (policy, usage) tuple — CLI --model flag and cost tracking both enabled
- cli_helpers.py provides estimate_cost() (haiku/sonnet pricing) and is_already_extracted() (hash-based idempotency check)
- test_cli.py: 5 passing helper unit tests + 5 skipped stubs for Plan 02 CLI commands

## Task Commits

Each task was committed atomically:

1. **Task 1: Surface usage tokens and add model override** - `af5d5b3` (feat)
2. **Task 2: Create cli_helpers module and test scaffold** - `d2cc278` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified
- `policy_extractor/extraction/client.py` - extract_with_retry return type extended to include anthropic.types.Usage
- `policy_extractor/extraction/__init__.py` - extract_policy signature updated with model override, return type changed to tuple
- `tests/test_extraction.py` - All extract_policy call sites updated to unpack (result, usage)
- `policy_extractor/cli_helpers.py` - New module: PRICING constants, estimate_cost(), is_already_extracted()
- `tests/test_cli.py` - New test file: 5 helper unit tests, 5 plan-02 stubs

## Decisions Made
- extract_policy return type changed to tuple to surface usage alongside policy — CLI needs both in one call
- PRICING dict hardcoded in cli_helpers: avoids network call, values stable on short timescale
- is_already_extracted queries only Poliza.id with limit(1) for minimal DB overhead

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 02 (CLI commands) can now call extract_policy(result, model=model_override) and get (policy, usage) back
- is_already_extracted and estimate_cost are importable from policy_extractor.cli_helpers
- Full test suite: 109 passed, 7 skipped (Tesseract-dependent tests), no failures

---
*Phase: 04-cli-batch*
*Completed: 2026-03-18*
