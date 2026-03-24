---
phase: 17-golden-dataset-expansion
plan: 01
subsystem: testing
tags: [cli, typer, rich, pii-redaction, golden-fixtures, regression]

# Dependency graph
requires:
  - phase: 11-regression-suite
    provides: PiiRedactor, create-fixture pattern, golden fixtures directory convention
provides:
  - batch-fixtures CLI subcommand that processes a directory of PDFs into golden JSON fixtures
  - _infer_insurer and _infer_type helpers for slug detection from filenames
  - --insurer-map flag for explicit insurer/type mapping overrides
affects:
  - 17-02-golden-dataset-population
  - any future phase referencing batch fixture creation workflow

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Lazy import of PiiRedactor inside subcommand body (consistent with create-fixture pattern)
    - _infer_insurer + _infer_type substring matchers for automatic slug detection
    - Sequence numbering by counting existing {insurer}_{type}_*.json files in output dir
    - TDD red/green cycle for CLI subcommands using typer.testing.CliRunner

key-files:
  created:
    - tests/test_batch_fixture.py
  modified:
    - policy_extractor/cli.py

key-decisions:
  - "Added _infer_type helper alongside _infer_insurer — plan only specified insurer inference but test behavior required type inference from filename (e.g. zurich_auto.pdf -> type=auto)"
  - "_KNOWN_TYPES list uses common insurance policy type slugs; 'general' is the fallback when no type is found in filename"
  - "Sequence number determined by counting existing {insurer}_{type}_*.json files at write time — simple and idempotent across multiple runs"
  - "Exception during ingest_pdf/extract_policy is caught and skipped (not just None result) — defensive against partial ingestion failures"

patterns-established:
  - "batch-fixtures naming: {insurer}_{type}_{seq:03d}.json per D-07"
  - "Fixture metadata keys: _source_pdf, _insurer, _tipo_seguro, _created_at per D-08"
  - "PII redacted via PiiRedactor().redact() before any fixture is written to disk"

requirements-completed: [QA-01]

# Metrics
duration: 2min
completed: 2026-03-24
---

# Phase 17 Plan 01: batch-fixtures CLI Subcommand Summary

**`poliza-extractor batch-fixtures <dir>` command that auto-discovers PDFs, extracts policies, redacts PII via PiiRedactor, and writes golden JSON fixtures named `{insurer}_{type}_{seq:03d}.json`**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T06:23:26Z
- **Completed:** 2026-03-24T06:25:30Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments

- Added `batch-fixtures` CLI subcommand to `policy_extractor/cli.py` after existing `create-fixture`
- Implemented `_KNOWN_INSURERS`, `_KNOWN_TYPES`, `_infer_insurer`, `_infer_type` module-level helpers
- Supports `--insurer-map` JSON file for explicit pattern-to-slug overrides
- Failed extractions skip with warning, not crash; exceptions in ingest/extract also skipped
- 6 unit tests covering: file creation, metadata keys, naming convention, skip behavior, insurer-map, PII redaction

## Task Commits

Each task was committed atomically:

1. **Task 1: Add batch-fixtures CLI subcommand** - `16cce5a` (feat)

**Plan metadata:** _(docs commit follows)_

_Note: TDD task had RED (failing tests) verified before GREEN (implementation)._

## Files Created/Modified

- `policy_extractor/cli.py` - Added `_KNOWN_INSURERS`, `_KNOWN_TYPES`, `_infer_insurer`, `_infer_type`, and `batch_fixtures` subcommand (~130 lines)
- `tests/test_batch_fixture.py` - 6 unit tests for batch fixture creation behaviors (created)

## Decisions Made

- Added `_infer_type` helper (not in plan spec) because Test 3 expected `zurich_auto_001.json` from `zurich_auto.pdf` input — the type must be inferred from filename, not defaulted to `"general"` when a known type appears in the filename.
- Used `_KNOWN_TYPES` list with same substring-match approach as `_infer_insurer` for consistency.
- Sequence counter counts existing `{insurer}_{type}_*.json` files at write time — robust to interrupted runs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added `_infer_type` helper to correctly resolve type slug from filename**
- **Found during:** Task 1 (GREEN phase — test 3 failing)
- **Issue:** Plan spec said `type defaults to "general"` when no insurer-map provided, but test asserted `zurich_auto_001.json` for input `zurich_auto.pdf` — meaning type must be inferred from filename
- **Fix:** Added `_KNOWN_TYPES` list and `_infer_type(filename)` helper using the same substring-match pattern as `_infer_insurer`; called `_infer_type` in the else branch alongside `_infer_insurer`
- **Files modified:** `policy_extractor/cli.py`
- **Verification:** All 6 tests pass including test_batch_fixtures_filename_naming_convention
- **Committed in:** `16cce5a` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - behavior mismatch between plan prose and test spec)
**Impact on plan:** Required for correctness — test behavior is authoritative; type inference from filename is better UX than defaulting to "general" when type is clear in filename.

## Issues Encountered

None beyond the deviation noted above.

## User Setup Required

The plan notes that real PDFs in `pdfs-to-test/` are needed to actually run `batch-fixtures` in production. This is a user-side prerequisite (not automated):

- Place 2+ real PDF files per insurer in `pdfs-to-test/` directory
- Run: `poliza-extractor batch-fixtures pdfs-to-test/ --output tests/fixtures/golden/`

No environment variables or dashboard configuration required.

## Next Phase Readiness

- `batch-fixtures` subcommand is functional and tested — user can now generate 20+ golden fixtures from real PDFs
- Plan 17-02 (golden dataset population) can proceed: user runs `batch-fixtures` on their real PDFs, reviews output, commits fixtures
- No blockers

---
*Phase: 17-golden-dataset-expansion*
*Completed: 2026-03-24*
