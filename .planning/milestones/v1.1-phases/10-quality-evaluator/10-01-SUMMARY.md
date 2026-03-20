---
phase: 10-quality-evaluator
plan: 01
subsystem: evaluation
tags: [anthropic, sonnet, quality-scoring, tdd, json-persistence]

# Dependency graph
requires:
  - phase: 03-extraction
    provides: call_extraction_api pattern, build_extraction_tool pattern, assemble_text
  - phase: 05-storage-api
    provides: writer.py upsert_policy, Poliza ORM model with evaluation columns

provides:
  - evaluate_policy() entry point for Sonnet-based quality scoring of Haiku extractions
  - build_evaluation_tool() Claude tool definition for completeness/accuracy/hallucination_risk
  - call_evaluation_api() with forced tool_choice=evaluate_policy
  - EvaluationResult dataclass with score, evaluation_json, evaluated_at, model_id, usage
  - update_evaluation_columns() DB persistence function for 4 evaluation columns on Poliza
  - EVAL_MODEL_ID, EVAL_TOOL_NAME, LOW_SCORE_THRESHOLD constants

affects: [10-02-cli-api-integration, plan-02-cli-evaluate-flag, batch-summary-low-score-counting]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Mirror build_extraction_tool() / call_extraction_api() structure for evaluation
    - evaluate_policy() wraps API call in try/except and returns None on failure
    - json.dumps(eval_dict, ensure_ascii=False) for TEXT column serialization (null not None)
    - Scores clamped to [0.0, 1.0] before formula: (completeness + accuracy + (1-hallucination_risk)) / 3

key-files:
  created:
    - policy_extractor/evaluation.py
    - tests/test_evaluation.py
  modified:
    - policy_extractor/storage/writer.py

key-decisions:
  - "EVAL_MODEL_ID hardcoded to claude-sonnet-4-5-20250514 per prior user decision — no settings override"
  - "evaluate_policy() returns None on any Exception — never raises — batch callers rely on this contract"
  - "evaluation_json stored as TEXT (json.dumps string), not JSON column — TEXT preserves exact serialization"
  - "Score formula: (completeness + accuracy + (1 - hallucination_risk)) / 3 — hallucination inverted so higher is better"
  - "Scores clamped to [0.0, 1.0] before formula to guard against malformed API responses"
  - "update_evaluation_columns() raises ValueError for missing Poliza — caller must verify poliza exists before calling"
  - "EVAL_SYSTEM_PROMPT written in Spanish — domain terms and flag issues are Spanish-language"

patterns-established:
  - "Evaluation module mirrors extraction module structure (build_tool / call_api / parse / entry_point)"
  - "TDD: RED commit (failing tests) then GREEN commit (implementation) — both atomically committed"

requirements-completed: [QAL-02, QAL-03]
requirements_completed: [QAL-01, QAL-02, QAL-03]

# Metrics
duration: 4min
completed: 2026-03-19
---

# Phase 10 Plan 01: Quality Evaluator Core Summary

**Sonnet evaluation engine scoring Haiku extractions on completeness, accuracy, and hallucination_risk via forced tool_use, with DB persistence of 4 evaluation columns on existing Poliza rows**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-19T20:30:52Z
- **Completed:** 2026-03-19T20:34:06Z
- **Tasks:** 1 (TDD: test commit + implementation commit)
- **Files modified:** 3

## Accomplishments
- Created `policy_extractor/evaluation.py` with `evaluate_policy()`, `build_evaluation_tool()`, `call_evaluation_api()`, `_parse_evaluation()`, and `EvaluationResult` dataclass
- Added `update_evaluation_columns()` to `writer.py` — sets evaluation_score, evaluation_json, evaluated_at, evaluated_model_id on existing Poliza by (numero_poliza, aseguradora)
- 27 new tests all pass; full suite 238 passed, 2 skipped, 0 regressions

## Task Commits

Each task was committed atomically (TDD style):

1. **RED: Failing tests** - `e2de348` (test)
2. **GREEN: Implementation** - `77297ec` (feat)

## Files Created/Modified
- `policy_extractor/evaluation.py` - Full evaluation module: constants, EvaluationResult, EVAL_SYSTEM_PROMPT, build_evaluation_tool(), call_evaluation_api(), _parse_evaluation(), evaluate_policy()
- `policy_extractor/storage/writer.py` - Added update_evaluation_columns() function
- `tests/test_evaluation.py` - 27 unit tests covering tool schema, API call, score formula, clamping, JSON serialization, DB persistence, error handling

## Decisions Made
- EVAL_MODEL_ID hardcoded to `claude-sonnet-4-5-20250514` — no settings override per prior decision
- `evaluate_policy()` catches all exceptions and returns None so batch processing can continue
- evaluation_json stored as a TEXT string via `json.dumps` (not a JSON column) to preserve exact serialization
- Score formula: `(completeness + accuracy + (1 - hallucination_risk)) / 3` — hallucination_risk inverted so all three dimensions are "higher is better"
- Scores clamped to `[0.0, 1.0]` before the formula to guard against API responses outside range
- `update_evaluation_columns()` raises `ValueError` for missing Poliza — callers must ensure the policy exists first
- EVAL_SYSTEM_PROMPT authored in Spanish so flag descriptions use correct domain terminology

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed IngestionResult fixture missing required fields**
- **Found during:** Task 1 (TDD GREEN — test run after implementation)
- **Issue:** `IngestionResult` fixture in test file was missing 4 required fields (total_pages, file_size_bytes, created_at, ocr_applied) — Pydantic validation error
- **Fix:** Added the 4 missing fields with sensible test values to the `sample_ingestion_result` fixture
- **Files modified:** tests/test_evaluation.py
- **Verification:** All 27 tests pass after fix
- **Committed in:** 77297ec (feat commit includes updated test file)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug in test fixture)
**Impact on plan:** Single fixture fix, no scope change. All planned functionality delivered.

## Issues Encountered
- `IngestionResult` schema has more required fields than the `test_extraction.py` fixture (which uses a different version). Discovered immediately during first GREEN test run; fixed inline.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `evaluate_policy()` is ready for CLI integration (Plan 02 --evaluate flag)
- `update_evaluation_columns()` is ready for DB writes after evaluation
- `EVAL_MODEL_ID` and `LOW_SCORE_THRESHOLD` are importable for batch summary reporting
- Plan 02 can import directly: `from policy_extractor.evaluation import evaluate_policy, EvaluationResult, EVAL_MODEL_ID, LOW_SCORE_THRESHOLD`

---
*Phase: 10-quality-evaluator*
*Completed: 2026-03-19*
