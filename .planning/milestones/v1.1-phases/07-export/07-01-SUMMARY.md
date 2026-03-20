---
phase: 07-export
plan: 01
subsystem: export
tags: [openpyxl, csv, excel, xlsx, export, decimal, date-formatting]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: SQLAlchemy ORM models (Poliza, Asegurado, Cobertura) and conftest fixtures
  - phase: 05-storage-api
    provides: storage writer pattern (confianza handling, campos_adicionales structure)
provides:
  - export_xlsx: 3-sheet Excel workbook writer with typed cells, auto-filter, frozen header
  - export_csv: flat UTF-8 BOM CSV writer for polizas
  - ExportError: file-lock error class for Windows PermissionError
  - 15 unit tests covering EXP-01, EXP-02, EXP-05
affects: [07-02-cli-wiring, 08-api-export]

# Tech tracking
tech-stack:
  added: [openpyxl>=3.1.5]
  patterns:
    - lazy openpyxl import inside export_xlsx function body (fast CLI startup)
    - two-pass union-of-all-keys expansion for campos_adicionales
    - Decimal-to-float coercion via _cell_value() helper before openpyxl cell write
    - number_format applied per-cell AFTER ws.append() to avoid openpyxl version pitfall
    - confianza key stripped via .pop() before expanding JSON overflow columns

key-files:
  created:
    - policy_extractor/export.py
    - tests/test_export.py
  modified:
    - pyproject.toml (added openpyxl>=3.1.5 dependency)

key-decisions:
  - "openpyxl lazy-imported inside export_xlsx body — keeps import cost out of CLI startup path"
  - "number_format applied per-cell after ws.append() rows — column-level format before append has no effect in openpyxl 3.x"
  - "Decimal converted to float via _cell_value() helper — openpyxl writes Decimal as string otherwise"
  - "confianza stripped with .pop('confianza', None) before union-of-keys scan — same pattern as writer.py orm_to_schema()"
  - "auto_filter.ref only set when ws.max_row > 1 — ws.dimensions returns 'A1:A1' on empty sheets causing garbled output"

patterns-established:
  - "_cell_value(val): Decimal->float, date passthrough, None passthrough"
  - "_collect_extra_keys(items, attr): two-pass insertion-order dedup with confianza strip"
  - "_apply_formats(ws, header_row): per-cell number_format after data written"
  - "_finalize_sheet(ws): auto_filter guarded by max_row > 1, freeze_panes always set"

requirements-completed: [EXP-01, EXP-02, EXP-05]

# Metrics
duration: 12min
completed: 2026-03-19
---

# Phase 7 Plan 01: Export Module Summary

**openpyxl 3-sheet xlsx writer and UTF-8 BOM CSV exporter with typed numeric/date cells and campos_adicionales JSON expansion**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-19T16:51:16Z
- **Completed:** 2026-03-19T17:03:00Z
- **Tasks:** 1 (TDD: RED + GREEN commits)
- **Files modified:** 3

## Accomplishments

- `export_xlsx()` writes 3-sheet workbook (polizas, asegurados, coberturas) with auto-filter and frozen header row
- `export_csv()` writes flat UTF-8 BOM CSV of polizas with campos_adicionales expansion
- Decimal monetary values written as floats (not strings); date objects written as Excel date serials with DD/MM/YYYY format
- confianza key stripped from campos_adicionales before export (internal metadata excluded)
- 15 unit tests covering all EXP-01, EXP-02, EXP-05 requirements; full 177-test suite green

## Task Commits

Each task was committed atomically (TDD):

1. **RED — failing tests** - `1c820de` (test)
2. **GREEN — export module** - `1bd46aa` (feat)

**Plan metadata:** docs commit (pending)

_Note: TDD task — test commit first, then implementation commit._

## Files Created/Modified

- `policy_extractor/export.py` - Core export logic: export_xlsx, export_csv, ExportError, helper functions
- `tests/test_export.py` - 15 unit tests covering sheet names, headers, numeric/date cell types, BOM, campos expansion, confianza stripping, empty-list edge case, comma-in-value quoting
- `pyproject.toml` - Added `openpyxl>=3.1.5` to project dependencies

## Decisions Made

- **Lazy import for openpyxl:** `from openpyxl import Workbook` placed inside `export_xlsx()` body. Keeps import cost out of CLI startup path for commands that don't export.
- **number_format per-cell after append:** Applied format to each cell in a column after all `ws.append()` calls. Setting column-level format before appending rows has no effect in openpyxl 3.x (cells created by append don't inherit column format).
- **Decimal → float via _cell_value():** Centralized coercion helper. openpyxl silently writes Decimal as string (left-aligned in Excel, breaks SUM formulas).
- **auto_filter guard on max_row > 1:** Empty sheets return `ws.dimensions == "A1:A1"` — setting auto_filter on a header-only sheet produces garbled output.

## Deviations from Plan

None — plan executed exactly as written. openpyxl installation was an expected pre-requisite (not a deviation).

## Issues Encountered

None — all 15 tests passed on first run of the implementation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `export_xlsx` and `export_csv` are importable, tested, and ready for CLI wiring (Plan 07-02)
- Plan 07-02 will add `--format xlsx/csv` flag to the existing Typer `export` command and new Spanish filter flags (`--aseguradora`, `--agente`, `--desde`, `--hasta`, `--tipo`)
- No blockers

---
*Phase: 07-export*
*Completed: 2026-03-19*
