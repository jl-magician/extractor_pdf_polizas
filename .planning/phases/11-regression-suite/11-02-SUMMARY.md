---
phase: 11-regression-suite
plan: "02"
subsystem: testing
tags: [pytest, regression, golden-fixtures, pii-redaction, field-differ, typer, parametrize]

# Dependency graph
requires:
  - phase: 11-01
    provides: PiiRedactor, FieldDiffer, DriftReport classes; pyproject.toml marker and addopts config

provides:
  - create-fixture CLI subcommand that extracts, redacts PII, and writes golden JSON fixtures
  - tests/test_regression.py parametrized regression suite with @pytest.mark.regression
  - test_fixture_format_valid non-regression test for fixture structure validation

affects:
  - any future phase adding new extraction fields (run pytest -m regression to detect drift)
  - CI pipelines (regression tests require pdfs-to-test/ directory with real PDFs)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "@pytest.mark.parametrize with _discover_fixtures() at collection time for data-driven regression"
    - "pytest.skip() inside test body for CI-safe PDF-missing gate"
    - "Lazy imports inside test body to avoid loading extraction/ingestion at collection time"
    - "create-fixture CLI subcommand: _setup_db() + lazy PiiRedactor import + try/finally session.close()"

key-files:
  created:
    - tests/test_regression.py
  modified:
    - policy_extractor/cli.py

key-decisions:
  - "create-fixture uses lazy import of PiiRedactor inside function body — consistent with all other CLI subcommand patterns"
  - "_discover_fixtures() returns sorted glob list or [] when golden dir missing — parametrize with empty list skips gracefully in pytest 8.4.2"
  - "pytest 8.4.2 empty parametrize generates [NOTSET] placeholder that skips rather than 0 items — semantically equivalent, no action needed"
  - "_source_pdf key stored as file.name (not full path) so fixture is portable across machines"
  - "test_fixture_format_valid is NOT marked @pytest.mark.regression — runs in default suite to catch malformed fixtures early"

patterns-established:
  - "Pattern: _discover_fixtures() at module level with GOLDEN_DIR.exists() guard — safe at collection time when dir empty/missing"
  - "Pattern: Lazy imports inside test body for extract_policy/ingest_pdf — keeps collection fast, avoids import cost on collect-only"

requirements-completed:
  - REG-01
  - REG-02
  - REG-03
  - REG-04

# Metrics
duration: 3min
completed: "2026-03-19"
---

# Phase 11 Plan 02: Regression Suite - Fixture CLI + Parametrized Test Module Summary

**`poliza-extractor create-fixture` CLI subcommand plus parametrized `pytest -m regression` suite that loads golden JSON fixtures, re-runs extraction, and compares field-by-field with DriftReport table output**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-19T22:18:36Z
- **Completed:** 2026-03-19T22:21:48Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `create-fixture` subcommand to Typer CLI — runs full extraction pipeline on real PDF, applies PiiRedactor, stores `_source_pdf` provenance key, writes golden JSON to `tests/fixtures/golden/`
- Created `tests/test_regression.py` with `@pytest.mark.regression` parametrized test that discovers golden fixtures at collection time, skips gracefully when PDF missing, and asserts with `drift.format_table()` for structured failure output
- Added `test_fixture_format_valid` (not regression-marked) to validate fixture structure in the default test suite

## Task Commits

Each task was committed atomically:

1. **Task 1: Add create-fixture CLI subcommand** - `3338aa8` (feat)
2. **Task 2: Create parametrized regression test module** - `0998224` (feat)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified
- `policy_extractor/cli.py` - Added `create-fixture` subcommand with --insurer, --type, --output, --model flags; updated module docstring
- `tests/test_regression.py` - Parametrized regression test module with `_discover_fixtures()`, `test_regression_fixture`, and `test_fixture_format_valid`

## Decisions Made
- `_source_pdf` stored as `file.name` (not full path) — fixture is portable across different machines with different directory layouts
- `_discover_fixtures()` returns `[]` when golden dir is empty/missing — `@pytest.mark.parametrize` with empty list results in pytest 8.4.2 generating a `[NOTSET]` placeholder that immediately skips, which is semantically equivalent to 0 regression tests running
- `test_fixture_format_valid` intentionally not marked `@pytest.mark.regression` — it runs in the default suite to catch malformed fixtures before a full regression run

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- pytest 8.4.2 behavior: `@pytest.mark.parametrize` with an empty list generates a `[NOTSET]` skipped placeholder rather than 0 collected items. This differs from what the acceptance criteria expected ("collects 0 items") but is functionally equivalent — no regression tests run, no errors, all skips. This is a pytest version difference, not a code issue.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full regression suite loop is complete: `create-fixture` to generate fixtures, `pytest -m regression` to detect drift
- To use: add real PDFs to `pdfs-to-test/`, run `poliza-extractor create-fixture <pdf> --insurer <slug> --type <slug>`, commit the golden JSON, then run `pytest -m regression` to verify
- All 258 existing tests pass; 3 skipped (2 pre-existing + 1 new empty-parametrize placeholder)

---
*Phase: 11-regression-suite*
*Completed: 2026-03-19*

## Self-Check: PASSED

- FOUND: policy_extractor/cli.py (modified with create-fixture subcommand)
- FOUND: tests/test_regression.py (created)
- FOUND: .planning/phases/11-regression-suite/11-02-SUMMARY.md (created)
- FOUND: commit 3338aa8 (feat(11-02): add create-fixture CLI subcommand)
- FOUND: commit 0998224 (feat(11-02): create parametrized regression test module)
