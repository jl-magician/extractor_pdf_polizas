---
phase: 10-quality-evaluator
plan: "02"
subsystem: cli-api-integration
tags: [evaluation, cli, api, quality-scoring, batch]
dependency_graph:
  requires:
    - 10-01  # evaluation.py and update_evaluation_columns from Plan 01
    - 09-02  # batch concurrency with ThreadPoolExecutor
    - 08-02  # upload API _run_extraction pipeline
  provides:
    - "--evaluate flag on CLI extract command"
    - "--evaluate flag on CLI batch command with per-batch summary stats"
    - "evaluate=true query param on POST /polizas/upload"
    - "evaluation_score + evaluation_json always present in API result dict"
  affects:
    - policy_extractor/cli.py
    - policy_extractor/api/upload.py
    - tests/test_evaluation.py
    - tests/test_upload.py
tech_stack:
  added: []
  patterns:
    - "Lazy import inside if evaluate: branch (avoids Sonnet overhead in default path)"
    - "evaluate=False keyword arg threaded through _process_single_pdf and _run_extraction"
    - "evaluation fields always present in API result dict (None when not evaluated)"
key_files:
  created: []
  modified:
    - policy_extractor/cli.py
    - policy_extractor/api/upload.py
    - tests/test_evaluation.py
    - tests/test_upload.py
decisions:
  - "evaluate_policy lazy-imported inside if evaluate: branch in all three entry points (cli extract, _process_single_pdf, _run_extraction) — zero Sonnet overhead unless opt-in"
  - "eval_score/eval_input_tokens/eval_output_tokens always present in _process_single_pdf result dict — avoids KeyError in aggregation"
  - "evaluation_score/evaluation_json always present in _run_extraction result dict — API callers always get consistent shape"
  - "Batch eval token tracking via eval_input_tokens/eval_output_tokens fields — enables accurate Eval Cost (USD) row in summary"
  - "Rule 1 auto-fix: extract_policy returns 3-tuple; upload.py had 2-tuple unpack and test mocks had 2-tuple — all corrected"
metrics:
  duration: "4m 22s"
  completed_date: "2026-03-19"
  tasks: 2
  files_modified: 4
requirements_completed: [QAL-04, QAL-05]
---

# Phase 10 Plan 02: Quality Evaluator — CLI and API Integration Summary

**One-liner:** Wired opt-in Sonnet quality scoring via `--evaluate` flag into CLI extract/batch commands and `evaluate=true` query param into the upload API background worker.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add --evaluate flag to extract command | bbcfda8 | cli.py, tests/test_evaluation.py |
| 2 | Add --evaluate to batch + evaluate param to upload API | 7565140 | cli.py, api/upload.py, tests/test_evaluation.py, tests/test_upload.py |

## What Was Built

### Task 1: extract command --evaluate flag

- Added `evaluate: bool = typer.Option(False, "--evaluate", ...)` to `extract()` signature
- After `upsert_policy()` succeeds, lazy-imports `evaluate_policy` and `update_evaluation_columns`
- On eval success: persists scores, prints `Quality score: X.XX` and separate eval cost line
- On eval failure: warns user with yellow WARN, extraction still saved
- `ingestion_result` already in scope — no re-assembly needed
- Tests `test_evaluate_called_with_flag` and `test_evaluate_not_called_without_flag` added

### Task 2: batch --evaluate + upload evaluate param

**batch command:**
- Added `evaluate: bool = typer.Option(False, "--evaluate", ...)` to `batch()` signature
- `_process_single_pdf()` gets `evaluate: bool = False` kwarg; runs evaluate_policy after upsert; returns `eval_score`, `eval_input_tokens`, `eval_output_tokens` in dict (always present including skipped/failed paths)
- Both sequential and concurrent call sites pass `evaluate=evaluate`
- Aggregation (under threading.Lock for concurrent path) accumulates eval stats
- Summary table conditionally adds `Avg Score`, `Low Score Files`, `Eval Cost (USD)` rows when `--evaluate` given
- `test_batch_evaluate_flag` verifies "Avg Score" appears in output

**upload API:**
- Added `evaluate: bool = Query(False, ...)` to `upload_pdf()` route
- `evaluate` threaded as 5th positional arg to `threading.Thread(args=(job_id, save_path, model, force, evaluate))`
- `_run_extraction()` signature updated to `(job_id, pdf_path, model, force, evaluate=False)`
- Evaluation runs after `upsert_policy()` when `evaluate=True`; `evaluation_score` and `evaluation_json` always present in result dict (None when not evaluated), including the already-extracted skip path
- `test_upload_evaluate_param` verifies evaluate=True passed through
- `test_upload_no_evaluate_by_default` verifies evaluate=False default

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed 2-tuple unpack of extract_policy in upload.py and test mocks**

- **Found during:** Task 2 — reading upload.py
- **Issue:** `extract_policy()` returns a 3-tuple `(policy, usage, rl_retries)` but `_run_extraction()` was unpacking as `policy, _ = extract_policy(...)` (2-tuple), which would raise `ValueError: too many values to unpack` at runtime. Three test mocks in test_upload.py also used `(fake_extraction, MagicMock())` 2-tuple, which only passed because the function was mocked end-to-end.
- **Fix:** Changed unpack to `policy, _usage, _retries = extract_policy(...)` in upload.py; updated all three affected test mocks to `(fake_extraction, MagicMock(), 0)`
- **Files modified:** `policy_extractor/api/upload.py`, `tests/test_upload.py`
- **Commit:** 7565140

## Test Results

- Tests before plan: 243 passing (2 skipped)
- Tests after plan: 243 passing (2 skipped)
- New tests added: 5 (test_evaluate_called_with_flag, test_evaluate_not_called_without_flag, test_batch_evaluate_flag, test_upload_evaluate_param, test_upload_no_evaluate_by_default)
- Regressions: 0

## Self-Check: PASSED
