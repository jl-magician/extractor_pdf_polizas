---
phase: 03-extraction
plan: 02
subsystem: api
tags: [anthropic, tool-use, retry, hallucination-verification, provenance, pydantic]

# Dependency graph
requires:
  - phase: 03-extraction plan-01
    provides: prompt.py (assemble_text, SYSTEM_PROMPT_V1), schema_builder.py (build_extraction_tool, TOOL_NAME), 9 failing TDD tests, confianza field on PolicyExtraction

provides:
  - extract_policy(ingestion_result) public API in policy_extractor/extraction/__init__.py
  - call_extraction_api() with forced tool_use + tool_choice in client.py
  - extract_with_retry() with one retry on ValidationError in client.py
  - verify_no_hallucination() post-hoc hallucination check in verification.py
  - Raw API response stored in campos_adicionales["_raw_response"] for auditing
  - Provenance fields (source_file_hash, model_id, prompt_version, extracted_at) injected programmatically

affects: [04-pipeline (calls extract_policy per PDF), 05-storage (reads campos_adicionales._raw_response)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "forced tool_use with tool_choice={type:tool, name:TOOL_NAME} guarantees structured output — no freeform text paths"
    - "retry prompt augmentation: append ValidationError to user message with IMPORTANT correction instruction"
    - "provenance injection in parse_and_validate after tool_use block extraction, before Pydantic instantiation"
    - "hallucination check on key string fields only (numero_poliza, aseguradora) using case-insensitive substring search"
    - "raw response preserved via model_copy(update={campos_adicionales: {..., '_raw_response': raw}})"

key-files:
  created:
    - policy_extractor/extraction/client.py
    - policy_extractor/extraction/verification.py
  modified:
    - policy_extractor/extraction/__init__.py

key-decisions:
  - "extract_policy returns PolicyExtraction directly (not tuple) — tests contract; raw response stored in campos_adicionales['_raw_response']"
  - "extract_with_retry uses attempt loop (max_retries + 1 total attempts) not recursive call — cleaner retry budget tracking"
  - "parse_and_validate returns (policy, raw_input) where raw_input includes injected provenance — caller decides what to keep"

patterns-established:
  - "model_copy(update=...) for immutable field updates on Pydantic v2 models"
  - "confianza override: copy dict, mutate copy, model_copy — never mutate original"

requirements-completed: [EXT-01, EXT-02, EXT-03, EXT-04, EXT-05]

# Metrics
duration: 5min
completed: 2026-03-18
---

# Phase 3 Plan 02: Extraction Client Summary

**Anthropic extraction client with forced tool_use, one-retry ValidationError recovery, post-hoc hallucination downgrade for key fields, and provenance injection — all 10 extraction tests pass**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-18T20:34:17Z
- **Completed:** 2026-03-18T20:39:00Z
- **Tasks:** 2
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments
- Created `client.py` with `call_extraction_api`, `parse_and_validate`, and `extract_with_retry` with one-retry ValidationError recovery
- Created `verification.py` with `verify_no_hallucination` that downgrades confianza to 'low' for fields absent from source text
- Wired `extract_policy()` in `__init__.py` as the public entry point — assembles text, calls API with retry, verifies, stores raw response
- All 10 extraction tests pass; full suite 104 passed, 2 skipped, 0 failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Extraction client and hallucination verification** - `9a82447` (feat)
2. **Task 2: Wire public extract_policy() and make all tests pass** - `b28f92c` (feat)

**Plan metadata:** (docs commit — added after state updates)

## Files Created/Modified
- `policy_extractor/extraction/client.py` - call_extraction_api, parse_and_validate, extract_with_retry with retry logic
- `policy_extractor/extraction/verification.py` - verify_no_hallucination post-hoc confidence downgrade
- `policy_extractor/extraction/__init__.py` - extract_policy() public orchestrator; exports PROMPT_VERSION_V1, TOOL_NAME

## Decisions Made
- `extract_policy` returns `PolicyExtraction` directly (not a tuple) — this is what all 9 field-access tests require; raw response stored in `campos_adicionales["_raw_response"]` for auditing (test_raw_response_stored accepts either pattern)
- `extract_with_retry` uses a `for attempt in range(attempts)` loop with `attempts = max_retries + 1` — clean budget tracking, no recursion
- `parse_and_validate` injects provenance into the raw_input dict before Pydantic instantiation so provenance is part of the validated model

## Deviations from Plan

None - plan executed exactly as written. The only interpretation clarification was that the tests (which define the contract) require `extract_policy` to return a plain `PolicyExtraction`, not a tuple — the plan's tuple mention was aspirational; `test_raw_response_stored` explicitly accepts both patterns.

## Issues Encountered
None

## User Setup Required
None — ANTHROPIC_API_KEY is already managed by Settings class from Phase 1. All tests use mocked Anthropic client.

## Next Phase Readiness
- `extract_policy(ingestion_result)` is complete and tested — ready for Phase 4 batch pipeline
- Raw API response preserved for any audit/debug needs
- Hallucination verification guards the two most critical identity fields
- Phase 4 will need asyncio-safe client creation (one Anthropic client per async task or shared with semaphore)

---
*Phase: 03-extraction*
*Completed: 2026-03-18*

## Self-Check: PASSED

- FOUND: policy_extractor/extraction/client.py
- FOUND: policy_extractor/extraction/verification.py
- FOUND: .planning/phases/03-extraction/03-02-SUMMARY.md
- FOUND commit: 9a82447 (Task 1)
- FOUND commit: b28f92c (Task 2)
- Full test suite: 104 passed, 2 skipped, 0 failures
