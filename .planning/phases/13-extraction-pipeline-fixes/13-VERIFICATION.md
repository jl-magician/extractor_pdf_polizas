---
phase: 13-extraction-pipeline-fixes
verified: 2026-03-20T21:00:00Z
status: passed
score: 16/16 must-haves verified
re_verification: false
---

# Phase 13: Extraction Pipeline Fixes — Verification Report

**Phase Goal:** Systematic extraction errors are eliminated before any UI is built on top of them
**Verified:** 2026-03-20T21:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Digital PDF page with <10 extractable characters is auto-reclassified as scanned and OCR applied | VERIFIED | `ingestion/__init__.py` line 130: `if classification == "digital" and len(text.strip()) < settings.OCR_MIN_CHARS_THRESHOLD` |
| 2  | OCR_MIN_CHARS_THRESHOLD is configurable via env var with default 10 | VERIFIED | `config.py` line 20: `OCR_MIN_CHARS_THRESHOLD: int = int(os.getenv("OCR_MIN_CHARS_THRESHOLD", "10"))` |
| 3  | Classification "scanned (auto-reclassified)" appears in ingestion results for reclassified pages | VERIFIED | `schemas/ingestion.py` line 11: `Literal["digital", "scanned", "scanned (auto-reclassified)"]` |
| 4  | Single OCR failure does not crash the batch (try/except wraps OCR calls) | VERIFIED | `ingestion/__init__.py` lines 76, 114, 153, 182: four independent `except Exception` guards |
| 5  | Whole-PDF OCR retry fires when all reclassified pages yield empty text (D-16) | VERIFIED | `ingestion/__init__.py` line 164: `if all(t.strip() == "" for t in reclassified_texts)` + "triggering whole-PDF OCR retry per D-16" log message at line 167 |
| 6  | Financial invariant check (primer_pago + subsecuentes vs prima_total, 1% tolerance) writes warning | VERIFIED | `extraction/validation.py` line 60: `if diff_pct > Decimal("0.01")` using `campos.get("primer_pago")` and `campos.get("subsecuentes")` |
| 7  | Date logic check (inicio_vigencia < fin_vigencia) writes warning when violated | VERIFIED | `extraction/validation.py` lines 85-96: both fin/inicio and emision/inicio checks present |
| 8  | validation_warnings column exists on polizas table via Alembic migration 003 | VERIFIED | `alembic/versions/003_validation_warnings.py` lines 13-14: revision "003", down_revision "002"; line 29: `batch_op.add_column(sa.Column("validation_warnings", sa.JSON(), nullable=True))` |
| 9  | Validator registry is extensible via @register decorator | VERIFIED | `extraction/validation.py` lines 22-28: module-level `_VALIDATORS` list + `register()` decorator; both validators decorated at lines 38 and 77 |
| 10 | Extraction prompt is v2.0.0 with explicit field-mapping rules preventing known value swaps | VERIFIED | `extraction/prompt.py` line 90: `PROMPT_VERSION_V2 = "v2.0.0"`; Financial Breakdown Field Mapping section documents all swap pairs |
| 11 | Zurich overlay is automatically appended when insurer detected in PDF text | VERIFIED | `extraction/prompt.py` lines 186-218: `detect_insurer()` and `get_system_prompt()` present; `client.py` line 39: `system=get_system_prompt(assembled_text)` |
| 12 | Financial breakdown table pages tagged with [FINANCIAL BREAKDOWN TABLE BELOW] hint | VERIFIED | `extraction/prompt.py` lines 220-253: `assemble_text_v2()` adds tag for pages with financial keywords; `extraction/__init__.py` line 41: `assembled_text = assemble_text_v2(ingestion_result)` |
| 13 | Per-insurer field exclusion config controls which campos_adicionales fields are dropped before save | VERIFIED | `insurer_config.json` exists with `"default": []`; `storage/writer.py` lines 38-71: `_load_exclusion_config()` and `_apply_exclusions()` present |
| 14 | Excluded fields are silently dropped — no logging, no warnings (D-14) | VERIFIED | `_apply_exclusions()` in `writer.py`: returns filtered dict with no log calls |
| 15 | validate_extraction() is called after verify_no_hallucination() and warnings stored in DB | VERIFIED | `extraction/__init__.py` lines 65-71: lazy import + call + `model_copy` with `"validation_warnings": warnings`; `storage/writer.py` line 139: `poliza.validation_warnings = extraction.validation_warnings or None` |
| 16 | Full pipeline writes validation_warnings to polizas table at all three campo levels | VERIFIED | `writer.py` lines 134, 152, 163: `_apply_exclusions()` applied to poliza, asegurado, and cobertura campos_adicionales |

**Score:** 16/16 truths verified

---

## Required Artifacts

### Plan 01 (EXT-03)

| Artifact | Provides | Status | Evidence |
|----------|----------|--------|----------|
| `policy_extractor/schemas/ingestion.py` | Extended PageResult classification Literal | VERIFIED | Line 11: `Literal["digital", "scanned", "scanned (auto-reclassified)"]` |
| `policy_extractor/config.py` | OCR_MIN_CHARS_THRESHOLD setting | VERIFIED | Line 20: `OCR_MIN_CHARS_THRESHOLD: int = int(os.getenv(..., "10"))` |
| `policy_extractor/ingestion/__init__.py` | Auto-OCR reclassification + whole-PDF retry | VERIFIED | Lines 130-182: gate, reclassification, D-16 retry, all four except guards |
| `policy_extractor/ingestion/cache.py` | Updated ocr_applied detection | VERIFIED | Line 47: `p.classification in ("scanned", "scanned (auto-reclassified)")` |
| `tests/test_ingestion.py` | 7 required test functions | VERIFIED | All 7 functions found in `TestAutoOcrReclassification` class (lines 412-628) |

### Plan 02 (EXT-02)

| Artifact | Provides | Status | Evidence |
|----------|----------|--------|----------|
| `alembic/versions/003_validation_warnings.py` | Migration 003 adding validation_warnings JSON column | VERIFIED | revision "003", down_revision "002", inspector guard, `sa.JSON()` column |
| `policy_extractor/extraction/validation.py` | Validator registry with financial and date checks | VERIFIED | `validate_extraction()`, `register()`, `check_financial_invariant()`, `check_date_logic()` all present |
| `policy_extractor/storage/models.py` | validation_warnings ORM column | VERIFIED | Line 56: `validation_warnings: Mapped[Optional[list]] = mapped_column(sa.JSON, nullable=True)` |
| `policy_extractor/schemas/poliza.py` | validation_warnings field on PolicyExtraction | VERIFIED | Line 57: `validation_warnings: list[dict] = Field(default_factory=list)` |
| `tests/test_validation.py` | 15 unit tests covering all validator behaviors | VERIFIED | 15 test functions present, including boundary tests |

### Plan 03 (EXT-01, EXT-04)

| Artifact | Provides | Status | Evidence |
|----------|----------|--------|----------|
| `policy_extractor/extraction/prompt.py` | SYSTEM_PROMPT_V2, PROMPT_VERSION_V2, ZURICH_OVERLAY, detect_insurer(), get_system_prompt(), assemble_text_v2() | VERIFIED | All 6 symbols present (lines 90, 166, 182, 186, 205, 234) |
| `policy_extractor/extraction/client.py` | Updated API call using get_system_prompt() and PROMPT_VERSION_V2 | VERIFIED | Line 12: import; line 39: `system=get_system_prompt(assembled_text)`; line 77: `PROMPT_VERSION_V2` |
| `policy_extractor/extraction/__init__.py` | Validation wiring: validate_extraction() + validation_warnings on result | VERIFIED | Lines 65-71: lazy import, call, model_copy |
| `policy_extractor/storage/writer.py` | Field exclusion + validation_warnings persistence | VERIFIED | `_load_exclusion_config()`, `_apply_exclusions()`, `poliza.validation_warnings` all present |
| `policy_extractor/insurer_config.json` | Per-insurer field exclusion config | VERIFIED | Exists; `"default": []`; comment and example keys present |
| `tests/test_prompt.py` | 25+ tests for prompt v2.0.0 structure, overlay detection, text assembly | VERIFIED | 25 test functions confirmed |
| `tests/test_storage_writer.py` | Tests for exclusion and validation_warnings persistence | VERIFIED | 7+ functions including `test_load_exclusion_config_*`, `test_apply_exclusions_*`, `test_upsert_writes_validation_warnings_*` |

---

## Key Link Verification

| From | To | Via | Status | Evidence |
|------|----|-----|--------|----------|
| `ingestion/__init__.py` | `config.py` | `settings.OCR_MIN_CHARS_THRESHOLD` | WIRED | Line 130: `settings.OCR_MIN_CHARS_THRESHOLD` used in gate condition |
| `ingestion/__init__.py` | `ingestion/ocr_runner.py` | `ocr_with_fallback()` calls | WIRED | Lines 97, 144, 170: three call sites; function imported at line 15 |
| `extraction/validation.py` | `schemas/poliza.py` | `PolicyExtraction` input to validators | WIRED | Line 15: `from policy_extractor.schemas.poliza import PolicyExtraction`; all validator signatures use it |
| `alembic/versions/003_validation_warnings.py` | `storage/models.py` | Both define validation_warnings column | WIRED | Both contain `validation_warnings` — migration adds DB column, model maps it to ORM |
| `extraction/client.py` | `extraction/prompt.py` | `get_system_prompt(assembled_text)` call | WIRED | Line 12: import; line 39: `system=get_system_prompt(assembled_text)` |
| `extraction/__init__.py` | `extraction/validation.py` | `validate_extraction(verified_policy)` call | WIRED | Line 65: lazy import; line 66: call; line 71: result applied to model |
| `storage/writer.py` | `insurer_config.json` | `_load_exclusion_config()` reads config file | WIRED | `_load_exclusion_config()` constructs path relative to `__file__` and reads it |
| `storage/writer.py` | `schemas/poliza.py` | `extraction.validation_warnings` written to `poliza.validation_warnings` | WIRED | Line 139: `poliza.validation_warnings = extraction.validation_warnings or None` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| EXT-01 | Plan 03 | System improves extraction prompts to prevent financial value swaps in breakdown tables | SATISFIED | `SYSTEM_PROMPT_V2` contains "Financial Breakdown Field Mapping" section documenting all known swap pairs; `client.py` uses `get_system_prompt()` |
| EXT-02 | Plan 02 | System validates extracted financial fields cross-referentially and flags mismatches as warnings | SATISFIED | `validation.py` with `check_financial_invariant()` (1% tolerance, `campos_adicionales` sourced) and `check_date_logic()`; warnings persisted via `upsert_policy()` |
| EXT-03 | Plan 01 | System auto-reclassifies "digital" PDF pages with <10 extractable characters as scanned and applies OCR | SATISFIED | Per-page gate in `ingestion/__init__.py`; D-16 whole-PDF retry; `schemas/ingestion.py` Literal extended |
| EXT-04 | Plan 03 | User can configure a field exclusion list to prevent extraction of irrelevant campos_adicionales | SATISFIED | `insurer_config.json` config file; `_load_exclusion_config()` + `_apply_exclusions()` applied at poliza, asegurado, and cobertura levels in `writer.py` |

All four requirements are satisfied. No orphaned requirements found.

---

## Anti-Patterns Found

None detected. Scan of all modified files:

- No `TODO`, `FIXME`, `XXX`, `HACK`, or `PLACEHOLDER` comments found in production code
- No `return null` / `return {}` / `return []` stubs in any modified function
- No hardcoded empty data masquerading as real data
- No form handlers with only `preventDefault()`
- No fetch calls without response handling

The one `DeprecationWarning` about `datetime.utcnow()` in `cache.py` (line 72) is a pre-existing issue unrelated to this phase and does not affect functionality.

---

## Test Suite Results

| Suite | Command | Result |
|-------|---------|--------|
| Plan 01 (ingestion) | `pytest tests/test_ingestion.py -x -q -m "not regression"` | 82 passed, 1 skipped |
| Plan 02 (validation + migrations) | `pytest tests/test_validation.py tests/test_migrations.py -x -q -m "not regression"` | 27 passed (per summary; confirmed by full suite) |
| Plan 03 (prompt + writer + extraction) | `pytest tests/test_storage_writer.py tests/test_extraction.py -x -q -m "not regression"` | 37 passed |
| Full suite | `pytest tests/ -x -q -m "not regression"` | **327 passed, 3 skipped, 0 failures** |

---

## Human Verification Required

### 1. Zurich extraction quality on real PDFs

**Test:** Run `extract_policy()` on an actual Zurich auto insurance PDF containing a financial breakdown table
**Expected:** Prompt v2.0.0 with Zurich overlay produces correct financiamiento/otros_servicios_contratados and folio/clave values (no swaps)
**Why human:** Cannot programmatically verify LLM output quality; requires real PDF and visual inspection of extracted JSON

### 2. Auto-OCR reclassification on a real vector-graphics PDF

**Test:** Pass a digital PDF whose pages contain embedded vector graphics but no selectable text through `ingest_pdf()`
**Expected:** Pages reclassified as "scanned (auto-reclassified)", OCR applied, non-empty text extracted
**Why human:** Unit tests mock fitz and OCR; real-world behavior depends on actual tesseract/ocrmypdf pipeline

---

## Summary

Phase 13 fully achieves its goal. All four requirements (EXT-01 through EXT-04) are satisfied with substantive, wired implementations — no stubs, no orphaned code. The test suite grew from 263 to 327 tests (64 new tests across this phase), all green. The three plans delivered:

- **Plan 01 (EXT-03):** Auto-OCR reclassification gate with configurable threshold, D-16 whole-PDF retry, and try/except resilience at every OCR call site.
- **Plan 02 (EXT-02):** Decorator-based validator registry with financial cross-check and date logic validators; Alembic migration 003 adds validation_warnings JSON column.
- **Plan 03 (EXT-01, EXT-04):** Prompt v2.0.0 with explicit field-mapping rules, Zurich overlay detection, financial page tagging, per-insurer field exclusion at all three campos_adicionales levels, and full pipeline wiring of validation warnings to the DB.

---

_Verified: 2026-03-20T21:00:00Z_
_Verifier: Claude (gsd-verifier)_
