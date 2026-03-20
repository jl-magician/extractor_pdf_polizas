---
phase: 13-extraction-pipeline-fixes
plan: "02"
subsystem: extraction-validation
tags: [validation, migration, pydantic, alembic, tdd]
dependency_graph:
  requires: []
  provides: [validation-module, migration-003, validation-warnings-column]
  affects: [policy_extractor.extraction.validation, policy_extractor.storage.models, policy_extractor.schemas.poliza]
tech_stack:
  added: []
  patterns: [decorator-registry, annotate-only-validators, alembic-batch-inspector-guard]
key_files:
  created:
    - alembic/versions/003_validation_warnings.py
    - policy_extractor/extraction/validation.py
    - tests/test_validation.py
  modified:
    - policy_extractor/storage/models.py
    - policy_extractor/schemas/poliza.py
    - tests/test_migrations.py
key_decisions:
  - "Validator registry uses module-level list with @register decorator — extensible, discoverable, zero framework overhead"
  - "primer_pago and subsecuentes read from campos_adicionales.get() not top-level fields — per research pitfall D-09"
  - "1% tolerance uses Decimal('0.01') with strict > comparison — exactly 1% is safe, only >1% triggers warning"
  - "Validators return list[dict] and never raise — annotate-only contract (D-08)"
metrics:
  duration_seconds: 156
  completed_date: "2026-03-20"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 3
requirements_completed: [EXT-02]
---

# Phase 13 Plan 02: Validation Infrastructure Summary

Post-extraction validation module with decorator registry, financial cross-check (primer_pago + subsecuentes vs prima_total within 1%), and date logic validators; plus Alembic migration 003 adding validation_warnings JSON column.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Migration 003, ORM model, PolicyExtraction schema | 60e184e | alembic/versions/003_validation_warnings.py, models.py, poliza.py, test_migrations.py |
| 2 | Validation module with financial and date validators (TDD) | 931e449 | policy_extractor/extraction/validation.py, tests/test_validation.py |

## What Was Built

### Migration 003 (alembic/versions/003_validation_warnings.py)
Follows established project pattern from migration 002: inspector guard prevents duplicate column error on fresh DBs, batch_alter_table for SQLite compatibility, JSON column type for flexible warning list storage.

### ORM and Schema Updates
- `Poliza.validation_warnings: Mapped[Optional[list]]` — persists warnings from extraction pipeline
- `PolicyExtraction.validation_warnings: list[dict]` — carries warnings through extraction flow before storage

### Validation Module (policy_extractor/extraction/validation.py)
Decorator-based registry pattern. Two validators registered at import time:

1. **check_financial_invariant**: Reads `primer_pago` and `subsecuentes` from `campos_adicionales` (not top-level fields — critical distinction per research D-09). Computes `abs(prima_total - (primer_pago + subsecuentes)) / prima_total`. Flags when > 1% using `Decimal("0.01")` for precise comparison.

2. **check_date_logic**: Two checks — `fin_vigencia <= inicio_vigencia` (must be strictly before) and `fecha_emision > inicio_vigencia` (emission must not be after coverage start). Both return `[]` when any involved date is `None`.

All validators: annotate-only, never raise, never block (D-08 contract).

### Tests (tests/test_validation.py)
15 test functions covering:
- validate_extraction() with no fields (empty) and with multiple violation sources (aggregation)
- Financial invariant: 20% mismatch, exact match, None fields, exactly 1% boundary (no warning), 1.02% boundary (warning), message contains percentage
- Date logic: fin < inicio, emision > inicio, valid dates, all None, warning key shape

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

```
python -m pytest tests/test_validation.py tests/test_migrations.py -x -q -m "not regression"
27 passed in 3.36s

python -m pytest tests/ -x -q -m "not regression"
289 passed, 3 skipped, 47 warnings in 8.02s (0 regressions)

grep validation_warnings policy_extractor/storage/models.py  → found line 56
grep validation_warnings policy_extractor/schemas/poliza.py  → found line 57
grep campos.get policy_extractor/extraction/validation.py    → found lines 48-49
```

## Known Stubs

None. The validation module is fully functional. Plan 03 will wire `validate_extraction()` into the extraction pipeline and populate `validation_warnings` on the `PolicyExtraction` object before persistence.

## Self-Check: PASSED
