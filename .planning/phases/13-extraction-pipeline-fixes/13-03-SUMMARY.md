---
phase: 13-extraction-pipeline-fixes
plan: "03"
subsystem: extraction-pipeline
tags: [prompt-engineering, field-exclusion, validation-wiring, zurich-overlay, financial-tagging]
requirements_completed: [EXT-01, EXT-04]
dependency_graph:
  requires: [13-02]
  provides: [SYSTEM_PROMPT_V2, ZURICH_OVERLAY, detect_insurer, get_system_prompt, assemble_text_v2, _load_exclusion_config, _apply_exclusions, validate_extraction-wiring]
  affects: [policy_extractor/extraction/prompt.py, policy_extractor/extraction/client.py, policy_extractor/extraction/__init__.py, policy_extractor/storage/writer.py, policy_extractor/insurer_config.json]
tech_stack:
  added: []
  patterns: [tdd-red-green, lru_cache-exclusion-config, lazy-import-validation, decorator-registry, insurer-overlay-detection]
key_files:
  created:
    - policy_extractor/insurer_config.json
    - tests/test_prompt.py
  modified:
    - policy_extractor/extraction/prompt.py
    - policy_extractor/extraction/client.py
    - policy_extractor/extraction/__init__.py
    - policy_extractor/storage/writer.py
    - tests/test_storage_writer.py
    - tests/test_extraction.py
decisions:
  - "PROMPT_VERSION_V2 = v2.0.0 is a major version bump — clear break from v1.x prompts per D-06"
  - "detect_insurer() uses simple substring match (case-insensitive) on insurer key — sufficient for current insurer set, extensible"
  - "assemble_text_v2() tags pages with financial keywords rather than structure-based detection — robust to OCR noise"
  - "validate_extraction() called via lazy import inside extract_policy() — consistent with project pattern for optional dependencies"
  - "_load_exclusion_config uses lru_cache(maxsize=1) — zero file I/O overhead after first call; tests patch or clear cache"
  - "validation_warnings written as None (not []) when empty — avoids storing empty arrays in DB"
  - "Field exclusion applied to asegurado and cobertura campos_adicionales via _apply_exclusions() inline in upsert_policy()"
metrics:
  duration_minutes: 5
  completed_date: "2026-03-20"
  tasks_completed: 2
  files_created: 3
  files_modified: 5
  tests_added: 64
  tests_total: 327
---

# Phase 13 Plan 03: Prompt v2.0.0, Field Exclusion, and Validation Wiring Summary

**One-liner:** Prompt v2.0.0 with explicit field-mapping rules, Zurich overlay detection, and per-insurer field exclusion applied at all three campos_adicionales levels with validation warnings persisted to DB.

## What Was Built

### Task 1: Prompt v2.0.0 with Zurich overlay, financial page tagging, and insurer detection

**`policy_extractor/extraction/prompt.py`** — Extended with:
- `PROMPT_VERSION_V2 = "v2.0.0"` — major version bump (D-06)
- `SYSTEM_PROMPT_V2` — base prompt with explicit "Financial Breakdown Field Mapping" section documenting all known confused pairs: financiamiento/otros_servicios_contratados, primer_pago/subsecuentes, folio/clave, numero_poliza/numero_cotizacion, plus vehicle identification rules (numero_serie uses VIN not engine serial)
- `ZURICH_OVERLAY` — insurer-specific rules appended when Zurich is detected, targeting the exact value swaps from v2-extraction-errors.md
- `detect_insurer(text)` — lightweight case-insensitive substring match on the assembled text; returns insurer key (e.g. "zurich") or None
- `get_system_prompt(text)` — returns SYSTEM_PROMPT_V2 + overlay if insurer detected, otherwise just SYSTEM_PROMPT_V2
- `assemble_text_v2(ingestion)` — like assemble_text() but tags pages containing financial keywords with `[FINANCIAL BREAKDOWN TABLE BELOW]` before the page content
- Original `PROMPT_VERSION_V1`, `SYSTEM_PROMPT_V1`, `assemble_text()` kept for historical reference

**`policy_extractor/extraction/client.py`** — Updated:
- Import changed from `SYSTEM_PROMPT_V1, PROMPT_VERSION_V1` to `PROMPT_VERSION_V2, get_system_prompt`
- `call_extraction_api()` now uses `system=get_system_prompt(assembled_text)` — overlay is automatically applied for Zurich PDFs
- `parse_and_validate()` now injects `PROMPT_VERSION_V2` into provenance

**`policy_extractor/extraction/__init__.py`** — Updated:
- Uses `assemble_text_v2()` and `PROMPT_VERSION_V2`

**`tests/test_prompt.py`** — New file with 35 tests covering all prompt behaviors.

### Task 2: Field exclusion config, writer updates, and validation wiring

**`policy_extractor/insurer_config.json`** — New config file:
- Per-insurer exclusion list keyed by lowercase insurer name or `"*"` for global
- Starts with empty `"default": []` per D-13 (user configures what to exclude)

**`policy_extractor/storage/writer.py`** — Extended:
- `_load_exclusion_config()` — `@lru_cache(maxsize=1)` function reads insurer_config.json; strips comment and default keys; returns `{insurer: [fields]}` dict
- `_apply_exclusions(campos, insurer)` — filters campos dict by union of insurer-specific and `"*"` global exclusions; case-insensitive on insurer name; silent drop per D-14
- `upsert_policy()` now applies `_apply_exclusions()` at all three levels: poliza campos_adicionales, asegurado campos_adicionales, cobertura campos_adicionales
- `upsert_policy()` writes `poliza.validation_warnings = extraction.validation_warnings or None`

**`policy_extractor/extraction/__init__.py`** — Validation wired in:
- After `verify_no_hallucination()`, calls `validate_extraction(verified_policy)` via lazy import
- Logs info if warnings produced
- Updates `verified_policy` with `validation_warnings` field before storing `_raw_response`
- Annotate-only per D-08 — never blocks extraction

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 6744698 | test | RED: failing tests for prompt v2.0.0 (35 tests) |
| 0c95d2d | feat | GREEN: prompt v2.0.0 with Zurich overlay and financial page tagging |
| 75cd0d6 | test | RED: failing tests for field exclusion and validation wiring (29 tests) |
| bdb26b6 | feat | GREEN: field exclusion config, writer updates, and validation pipeline wiring |

## Decisions Made

1. **PROMPT_VERSION_V2 = "v2.0.0"** — major version bump per D-06; stored in provenance field of every extracted policy going forward
2. **Insurer detection via simple substring match** — case-insensitive search for insurer key in assembled text; no regex needed for current insurer set; extensible by adding to `_INSURER_OVERLAYS` dict
3. **Financial page tagging via keyword list** — tags pages containing any of: prima, pago, financiamiento, desglose, breakdown, importe, subtotal, recargo, derecho de poliza; robust to OCR noise and varied formatting
4. **lru_cache(maxsize=1) on _load_exclusion_config** — zero file I/O overhead after first call; test isolation via `patch()` not `cache_clear()` to avoid cross-test coupling
5. **validation_warnings = None (not []) when empty** — avoids storing empty JSON arrays; None is the DB convention for "not evaluated"
6. **Lazy import of validate_extraction inside extract_policy** — consistent with project-wide pattern for optional dependencies; avoids module-level circular import risk

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all new functionality is fully wired. The insurer_config.json exclusion list starts empty by design (D-13): users configure what to exclude based on their actual data.

## Self-Check: PASSED

**Files verified:**
- FOUND: policy_extractor/extraction/prompt.py
- FOUND: policy_extractor/extraction/client.py
- FOUND: policy_extractor/extraction/__init__.py
- FOUND: policy_extractor/storage/writer.py
- FOUND: policy_extractor/insurer_config.json
- FOUND: tests/test_prompt.py

**Commits verified:**
- FOUND: 6744698 — test(13-03): add failing tests for prompt v2.0.0 (RED)
- FOUND: 0c95d2d — feat(13-03): implement prompt v2.0.0 with Zurich overlay and financial page tagging
- FOUND: 75cd0d6 — test(13-03): add failing tests for field exclusion and validation wiring (RED)
- FOUND: bdb26b6 — feat(13-03): field exclusion config, writer updates, and validation pipeline wiring
