---
phase: 11-regression-suite
plan: "01"
subsystem: regression
tags: [testing, pii-redaction, field-diff, pytest-markers]
dependency_graph:
  requires: []
  provides:
    - policy_extractor.regression.PiiRedactor
    - policy_extractor.regression.FieldDiffer
    - policy_extractor.regression.DriftReport
  affects:
    - tests/test_regression_helpers.py
    - pyproject.toml
    - .gitignore
tech_stack:
  added: []
  patterns:
    - TDD (RED -> GREEN cycle for regression helpers)
    - frozenset for PII_FIELDS and SKIP_CAMPOS_KEYS (explicit, auditable list)
    - dataclass DriftReport with property + method pattern
    - pytest marker registration via pyproject.toml addopts
key_files:
  created:
    - policy_extractor/regression/__init__.py
    - policy_extractor/regression/pii_redactor.py
    - policy_extractor/regression/field_differ.py
    - tests/test_regression_helpers.py
    - tests/fixtures/golden/.gitkeep
  modified:
    - pyproject.toml
    - .gitignore
decisions:
  - "PII_FIELDS as frozenset — explicit hardcoded list preferred over pattern matching; auditable and zero false positives on domain field names"
  - "FieldDiffer operates on plain dicts (model_dump output) — decoupled from Pydantic models, testable with simple fixtures"
  - "SKIP_CAMPOS_KEYS handled before _redact_recursive to ensure _raw_response is removed even if it appears inside the dict"
  - "List matching by match_key value: items with REDACTED match key are skipped entirely (can't match by name if redacted)"
  - "addopts = \"-m 'not regression'\" with inner single quotes — required for correct marker expression parsing on Windows/shlex"
metrics:
  duration: "3m 16s"
  completed_date: "2026-03-19"
  tasks_completed: 2
  files_created: 5
  files_modified: 2
---

# Phase 11 Plan 01: Regression Infrastructure Summary

**One-liner:** PiiRedactor (6 PII fields + _raw_response strip) and FieldDiffer (structured FAIL/PASS drift report with list name-matching) with 15 passing unit tests, pytest marker registration, and pdfs-to-test/ gitignored.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (TDD RED) | Failing tests for PiiRedactor and FieldDiffer | 8ee94c9 | tests/test_regression_helpers.py |
| 1 (TDD GREEN) | Implement PiiRedactor and FieldDiffer | bca5bd4 | regression/__init__.py, pii_redactor.py, field_differ.py |
| 2 | pytest marker + gitignore + golden dir | 6caa62a | pyproject.toml, .gitignore, tests/fixtures/golden/.gitkeep |

## What Was Built

### PiiRedactor (`policy_extractor/regression/pii_redactor.py`)

- `PII_FIELDS` frozenset: `{nombre_contratante, nombre_descripcion, rfc, curp, direccion, parentesco}`
- `SKIP_CAMPOS_KEYS` frozenset: `{_raw_response}`
- `PiiRedactor.redact(data)`: deep copies input, strips SKIP_CAMPOS_KEYS from campos_adicionales at all levels, then walks the dict tree replacing PII field values with `"[REDACTED]"`
- Returns a safe-to-commit dict with no PII and no audit-log blob

### FieldDiffer (`policy_extractor/regression/field_differ.py`)

- `SKIP_FIELDS` frozenset: `{confianza, source_file_hash, model_id, prompt_version, extracted_at, _source_pdf}`
- `LIST_MATCH_KEYS`: `{asegurados: nombre_descripcion, coberturas: nombre_cobertura}`
- `DriftReport`: dataclass with `rows: list[tuple[str,str,str,str]]`, `has_failures` property, `format_table()` returning "Field | Expected | Actual | Status" table
- `FieldDiffer.compare()`: iterates expected keys, skips SKIP_FIELDS and REDACTED values, delegates to specialized comparators for campos_adicionales and list fields

### pytest Configuration

- Marker `regression` registered in `pyproject.toml` with description
- `addopts = "-m 'not regression'"` excludes regression tests from default `pytest` runs
- `pdfs-to-test/` added to `.gitignore` — real PDFs with PII never committed
- `tests/fixtures/golden/.gitkeep` — directory tracked by git for fixture storage

## Verification Results

1. `pytest tests/test_regression_helpers.py -x -v` — 15/15 passed
2. `pytest tests/ -x` — 258 passed, 2 skipped (Tesseract), 0 failures
3. `grep "pdfs-to-test" .gitignore` — match found
4. `grep "regression" pyproject.toml` — marker line present
5. `from policy_extractor.regression.pii_redactor import PiiRedactor` — OK
6. `from policy_extractor.regression.field_differ import FieldDiffer, DriftReport` — OK

## Deviations from Plan

None — plan executed exactly as written.

## Requirements Satisfied

| ID | Description | Status |
|----|-------------|--------|
| REG-01 | Golden dataset fixtures infrastructure in tests/fixtures/golden/ | DONE |
| REG-02 | FieldDiffer compares field-by-field, skips REDACTED, partial-matches campos_adicionales | DONE |
| REG-03 | regression marker registered and excluded from default runs | DONE |
| REG-04 | DriftReport.format_table() produces Field \| Expected \| Actual \| Status table | DONE |

## Self-Check: PASSED

All 5 created files verified on disk. All 3 task commits verified in git log.
