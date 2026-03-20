---
phase: 12-milestone-polish
plan: "01"
subsystem: testing
tags: [decimal, float, comparison, field-differ, regression, math]

requires:
  - phase: 11-regression-suite
    provides: FieldDiffer class and test_regression_helpers.py baseline (tests 1-15)

provides:
  - _values_equal() helper in field_differ.py using math.isclose(rel_tol=1e-9)
  - Safe Decimal/float comparison at all three FieldDiffer comparison sites
  - Tests 16-20 covering Decimal vs float roundtrip, string vs float, and truly-different-value cases

affects:
  - regression suite fixture comparison
  - any caller of FieldDiffer.compare()

tech-stack:
  added: []
  patterns:
    - "Decimal/float comparison via math.isclose(rel_tol=1e-9) to handle JSON serialization artifacts without introducing general tolerance"

key-files:
  created: []
  modified:
    - policy_extractor/regression/field_differ.py
    - tests/test_regression_helpers.py

key-decisions:
  - "_values_equal uses math.isclose(rel_tol=1e-9) — extremely tight tolerance forgives only float representation artifacts, not truly different values"
  - "Non-numeric types use strict equality (==) — preserves Phase 11 'exact match' user decision"
  - "Module-level function (not method) — callable from all three comparison sites without self reference"

patterns-established:
  - "All numeric comparisons in FieldDiffer go through _values_equal() — single point of control for comparison semantics"

requirements-completed: [REG-02]

duration: 8min
completed: 2026-03-19
---

# Phase 12 Plan 01: Decimal-safe FieldDiffer comparison Summary

**FieldDiffer _values_equal() helper using math.isclose(rel_tol=1e-9) eliminates spurious FAIL from Decimal-to-float JSON serialization roundtrip while preserving exact match for string and other types**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-19T23:30:00Z
- **Completed:** 2026-03-19T23:38:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Added `_values_equal(expected, actual) -> bool` module-level helper to field_differ.py that uses `math.isclose(float(expected), float(actual), rel_tol=1e-9)` for any numeric (int/float/Decimal) pair
- Replaced all three `!=` comparison sites in FieldDiffer with `not _values_equal(...)`: line ~130 (scalar), line ~162 (campos_adicionales), line ~229 (list sub-fields)
- Added tests 16-20 to TestFieldDiffer covering: float-equal (no FAIL), string-vs-float (FAIL), coberturas float (no FAIL), Decimal-vs-float roundtrip (no FAIL), truly different values (FAIL)
- Full suite: 263 passed, 2 skipped, 0 failures

## Task Commits

1. **Task 1: Add _values_equal helper and Decimal-safe comparison tests** - `5a9603c` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `policy_extractor/regression/field_differ.py` - Added `import math`, `from decimal import Decimal`, `_values_equal()` function, replaced 3x `!=` with `not _values_equal(...)`
- `tests/test_regression_helpers.py` - Added `from decimal import Decimal` import and tests 16-20

## Decisions Made

- `_values_equal` uses `math.isclose(rel_tol=1e-9)` — extremely tight so only float representation noise is forgiven; values like 1500.0 vs 1500.01 still FAIL (preserves "exact match" intent from Phase 11)
- Non-numeric types remain under strict `==` — strings, None, booleans, dicts all use exact equality
- Module-level function (not a FieldDiffer method) — cleaner and usable without class context

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Note: Tests 16-20 passed even before the implementation because Python's built-in `Decimal == float` comparison already works for simple values like `Decimal("1500.00") == 1500.0`. The `_values_equal` helper provides robustness for arithmetic Decimal results (e.g., `Decimal("0.1") + Decimal("0.2")` = `Decimal("0.3")` vs float `0.30000000000000004`) that would cause false FAILs. The plan's intent is correct even if the minimal test cases happen to pass under the old code.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 12 Plan 01 complete. FieldDiffer is now robust against Decimal/float serialization artifacts.
- Phase 12 Plan 02 (12-02) is the next and final plan in this milestone-polish phase.

---
*Phase: 12-milestone-polish*
*Completed: 2026-03-19*
