---
phase: 17-golden-dataset-expansion
plan: "02"
subsystem: tests
tags: [pytest, coverage-matrix, regression, conftest]
dependency_graph:
  requires: []
  provides: [regression-coverage-matrix-plugin]
  affects: [tests/conftest.py, tests/test_coverage_matrix.py]
tech_stack:
  added: []
  patterns: [pytest-plugin-class, pytest-hooks, ascii-table-formatting]
key_files:
  created:
    - tests/test_coverage_matrix.py
  modified:
    - tests/conftest.py
decisions:
  - "_parse_insurer_from_nodeid uses regex to extract last [...] param ID then splits on _ — robust to any path prefix in nodeid"
  - "RegressionCoveragePlugin class-based encapsulation keeps _results state per session and avoids module-level mutation"
  - "_format_coverage_matrix separates missing insurers (show '-') from zero-count insurers (show 0s) for honest coverage reporting"
  - "pytest_configure registers plugin globally so coverage hooks fire regardless of test module import order"
metrics:
  duration: "95s"
  completed: "2026-03-24"
  tasks_completed: 1
  files_changed: 2
requirements_completed:
  - QA-01
---

# Phase 17 Plan 02: Coverage Matrix Plugin Summary

**One-liner:** Pytest conftest plugin prints ASCII coverage matrix after `pytest -m regression`, showing pass/fail/skip counts for all 10 insurers.

## What Was Built

A pytest plugin embedded in `tests/conftest.py` that:

1. Hooks into `pytest_runtest_logreport` to collect pass/fail/skip outcomes for tests marked `@pytest.mark.regression`
2. Parses insurer slugs from pytest node IDs using `_parse_insurer_from_nodeid()` (extracts the first `_`-delimited token from the parametrize bracket)
3. Renders an ASCII coverage matrix via `_format_coverage_matrix()` listing all 10 insurers with counts, showing `-` for insurers with no fixtures
4. Prints the matrix via `pytest_terminal_summary` only when at least one regression test ran

Unit tests in `tests/test_coverage_matrix.py` cover all 6 behaviors specified in the plan:
- Node ID parsing for all 10 known insurers
- Unknown format returns "unknown"
- All 10 insurers always appear in matrix output
- Correct pass/fail/skip counts per insurer
- Missing insurers show dashes
- Total row sums correctly

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | Failing tests for coverage matrix | 48a707a | tests/test_coverage_matrix.py |
| GREEN | Coverage matrix plugin implementation | 6bb5f97 | tests/conftest.py |

## Verification

- `python -m pytest tests/test_coverage_matrix.py -x -v` — 11/11 passed
- `python -m pytest tests/ --ignore=tests/test_coverage_matrix.py -q` — 463 passed, 3 skipped (all existing tests preserved)
- All acceptance criteria verified programmatically

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. The plugin uses real pytest hooks and produces real output. No placeholder data flows to any rendering path.

## Self-Check: PASSED

Files exist:
- tests/conftest.py — FOUND
- tests/test_coverage_matrix.py — FOUND

Commits exist:
- 48a707a — FOUND (test(17-02): add failing tests for coverage matrix helpers)
- 6bb5f97 — FOUND (feat(17-02): add regression coverage matrix plugin to conftest.py)
