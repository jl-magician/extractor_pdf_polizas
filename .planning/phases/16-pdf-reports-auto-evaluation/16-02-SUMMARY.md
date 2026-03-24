---
phase: 16-pdf-reports-auto-evaluation
plan: "02"
subsystem: evaluation
requirements_completed: [QA-02, QA-03]
tags: [evaluation, auto-eval, swap-detection, batch, quality]
dependency_graph:
  requires: [16-01]
  provides: [auto-evaluation hook, swap detection, build_swap_warnings]
  affects: [policy_extractor/evaluation.py, policy_extractor/api/upload.py, policy_extractor/config.py]
tech_stack:
  added: []
  patterns: [lazy import inside function, random.sample, getattr settings fallback, append-not-overwrite warnings]
key_files:
  created: [tests/test_auto_eval.py]
  modified:
    - policy_extractor/config.py
    - policy_extractor/evaluation.py
    - policy_extractor/api/upload.py
    - tests/test_evaluation.py
decisions:
  - "EVAL_SAMPLE_PERCENT uses getattr(settings, 'EVAL_SAMPLE_PERCENT', 20) fallback for testability — allows patching settings instance directly"
  - "campos_swap_suggestions added to tool schema required list — Sonnet must always return the field (empty array if no swaps)"
  - "_auto_evaluate_batch uses lazy imports inside function body — consistent with existing upload.py pattern and avoids circular imports"
  - "Swap warnings appended via existing_warnings + swap_warnings — never overwrites Phase 13 financial validation warnings (Pitfall 4)"
  - "_auto_evaluate_batch skips polizas without retained PDF — batch auto-eval only works with PDF retention enabled"
metrics:
  duration_minutes: 15
  completed_date: "2026-03-24"
  tasks_completed: 2
  files_modified: 5
---

# Phase 16 Plan 02: Auto-Evaluation Pipeline and Swap Detection Summary

Extended the Sonnet evaluation pipeline with campos_adicionales swap detection and wired auto-triggered evaluation into batch and single extraction workflows.

## What Was Built

**Task 1: Extend evaluation prompt and tool schema with swap detection**

- Added `EVAL_SAMPLE_PERCENT: int = 20` to `Settings` in `config.py`, configurable via `EVAL_SAMPLE_PERCENT` env var
- Extended `EVAL_SYSTEM_PROMPT` with a "Deteccion de intercambio de campos" section instructing Sonnet to detect campos_adicionales field swaps (source_key, target_key, suspicious_value, reason)
- Added `campos_swap_suggestions` property to `build_evaluation_tool()` input_schema — array of swap objects with 4 required fields each
- Added `"campos_swap_suggestions"` to the schema's `required` list
- Updated `_parse_evaluation()` to extract `campos_swap_suggestions` from raw_input and embed in `eval_dict` (included in `evaluation_json`)
- Added `build_swap_warnings(evaluation_json: str) -> list[str]` public helper — converts swap suggestions to `"SWAP: campos_adicionales.{key} = ..."` warning strings

**Task 2: Wire auto-evaluation into batch and single extraction workflows**

- Added `_auto_evaluate_batch(session, summaries, model)` to `upload.py` — samples `EVAL_SAMPLE_PERCENT%` of successfully extracted polizas from a batch when `>= 10` succeed
- Wired `_auto_evaluate_batch()` into `_run_batch_extraction()` after the per-file loop, wrapped in try/except so evaluation errors never fail the batch
- Updated `_run_extraction()` single-file evaluate block to call `build_swap_warnings()` and append swap warnings to `validation_warnings` (never overwriting existing Phase 13 financial warnings)
- Created `tests/test_auto_eval.py` with 6 tests covering: threshold gate, sample rate ~20%, settings override to 50%, swap warning append preservation, and PDF-missing skip behavior

## Commits

| Task | Hash | Message |
|------|------|---------|
| Task 1 | af741d5 | feat(16-02): extend evaluation with swap detection and EVAL_SAMPLE_PERCENT |
| Task 2 | 15e90bd | feat(16-02): wire auto-evaluation into batch and single extraction workflows |

## Test Results

- `tests/test_evaluation.py`: 40 passed (up from 34; +4 new swap/prompt tests, +2 schema assertion updates)
- `tests/test_auto_eval.py`: 6 passed (new file)
- Combined: 46 passed, 0 failed

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written with one minor cleanup:

**[Rule 1 - Bug] Removed stray patch calls in test_auto_eval.py**
- Found during: Task 2 test run
- Issue: Test had leftover `patch("....__code__")` and `patch("....__globals__")` attempts from drafting; these raised `TypeError: __code__ must be set to a code object` on Python 3.14
- Fix: Removed the dead patch context managers; kept only the correct module-path patches
- Files modified: tests/test_auto_eval.py
- Commit: 15e90bd (included in Task 2 commit)

## Known Stubs

None — all paths are wired. The auto-evaluation requires PDF retention (data/pdfs/{id}.pdf) and will silently skip polizas whose PDF was not retained. This is expected behavior documented in the code.

## Self-Check: PASSED

Files exist:
- policy_extractor/config.py — contains EVAL_SAMPLE_PERCENT
- policy_extractor/evaluation.py — contains build_swap_warnings, campos_swap_suggestions
- policy_extractor/api/upload.py — contains _auto_evaluate_batch, random.sample, if total < 10
- tests/test_auto_eval.py — 6 test functions
- tests/test_evaluation.py — updated with campos_swap_suggestions tests

Commits exist: af741d5, 15e90bd (verified via git log)
