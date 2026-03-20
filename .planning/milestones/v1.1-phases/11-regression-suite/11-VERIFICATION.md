---
phase: 11-regression-suite
verified: 2026-03-19T22:45:00Z
status: passed
score: 14/14 must-haves verified
re_verification: false
---

# Phase 11: Regression Suite Verification Report

**Phase Goal:** A repeatable, automated test suite catches extraction quality regressions by comparing field-by-field output against known-good fixtures
**Verified:** 2026-03-19T22:45:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                     | Status     | Evidence                                                                                  |
|----|-------------------------------------------------------------------------------------------|------------|-------------------------------------------------------------------------------------------|
| 1  | PiiRedactor replaces all 6 PII fields with '[REDACTED]' recursively including nested asegurados | VERIFIED | `PII_FIELDS` frozenset in pii_redactor.py:15-24; `_redact_recursive` walks dicts/lists; 15 tests green |
| 2  | PiiRedactor strips _raw_response from campos_adicionales                                  | VERIFIED   | `SKIP_CAMPOS_KEYS = frozenset({"_raw_response"})` line 26; `_strip_skip_keys` called at top/asegurados/coberturas levels |
| 3  | FieldDiffer skips fields with value '[REDACTED]' in expected                              | VERIFIED   | `if exp_val == _REDACTED: continue` at field_differ.py:96-97; also inside `_compare_list` and `_compare_campos_adicionales` |
| 4  | FieldDiffer reports FAIL for missing campos_adicionales keys but PASS for extra keys      | VERIFIED   | `_compare_campos_adicionales`: missing key appends FAIL row; extra keys in actual are not iterated |
| 5  | FieldDiffer matches asegurados by nombre_descripcion and coberturas by nombre_cobertura (order-independent) | VERIFIED | `LIST_MATCH_KEYS` dict at line 29-32; `_compare_list` builds `actual_index` keyed by match_key |
| 6  | DriftReport.format_table() produces Field | Expected | Actual | Status rows              | VERIFIED   | Lines 65-71 in field_differ.py; header line is `"\nField | Expected | Actual | Status"` |
| 7  | pytest marker 'regression' is registered and excluded from default runs                   | VERIFIED   | `pyproject.toml` lines 44-47: marker registered + `addopts = "-m 'not regression'"`; `pytest tests/` shows 1 deselected |
| 8  | pdfs-to-test/ is in .gitignore                                                            | VERIFIED   | `.gitignore` line 11: `pdfs-to-test/`                                                    |
| 9  | poliza-extractor create-fixture runs extraction, redacts PII, strips _raw_response, saves JSON to golden dir | VERIFIED | cli.py:586-629; full pipeline: ingest_pdf -> extract_policy -> model_dump -> _source_pdf -> PiiRedactor().redact -> json.dumps -> write |
| 10 | create-fixture requires --insurer and --type flags; output includes _source_pdf key       | VERIFIED   | cli.py:592-593 both use `...` (required); line 615: `raw["_source_pdf"] = file.name`     |
| 11 | pytest -m regression discovers all fixture JSONs in tests/fixtures/golden/ and runs one test per fixture | VERIFIED | `_discover_fixtures()` glob at collection time; `@pytest.mark.parametrize("fixture_path", _discover_fixtures())` |
| 12 | Regression tests skip gracefully with pytest.skip() when real PDF is missing             | VERIFIED   | test_regression.py:41: `pytest.skip(f"Real PDF not found: {pdf_path} ...")` |
| 13 | Regression tests use FieldDiffer and assert on DriftReport.has_failures with format_table() as message | VERIFIED | test_regression.py:50-52: `FieldDiffer(fixture, actual).compare()` then `assert not drift.has_failures, f"...\n{drift.format_table()}"` |
| 14 | Running pytest without -m regression does NOT run any regression test                    | VERIFIED   | Live run: `258 passed, 3 skipped, 1 deselected` — regression test is deselected by addopts |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact                                         | Expected                                        | Status     | Details                                                     |
|--------------------------------------------------|-------------------------------------------------|------------|-------------------------------------------------------------|
| `policy_extractor/regression/__init__.py`        | Package init with exports                       | VERIFIED   | Exports PiiRedactor, PII_FIELDS, SKIP_CAMPOS_KEYS, FieldDiffer, DriftReport |
| `policy_extractor/regression/pii_redactor.py`    | PiiRedactor class with PII_FIELDS frozenset     | VERIFIED   | 86 lines; PII_FIELDS, SKIP_CAMPOS_KEYS, PiiRedactor.redact() all present |
| `policy_extractor/regression/field_differ.py`    | FieldDiffer + DriftReport for structured comparison | VERIFIED | 214 lines; SKIP_FIELDS, LIST_MATCH_KEYS, DriftReport, FieldDiffer all present |
| `tests/test_regression_helpers.py`               | 15 unit tests for PiiRedactor and FieldDiffer   | VERIFIED   | Exactly 15 `def test_` functions; all 15 pass               |
| `tests/test_regression.py`                       | Parametrized regression test module             | VERIFIED   | `@pytest.mark.regression`, `_discover_fixtures()`, `pytest.skip()`, `FieldDiffer`, `format_table()` all present |
| `policy_extractor/cli.py`                        | create-fixture subcommand                       | VERIFIED   | `@app.command(name="create-fixture")` at line 586; confirmed in `app.registered_commands` |
| `pyproject.toml`                                 | regression marker + addopts exclusion           | VERIFIED   | Both `markers` list and `addopts = "-m 'not regression'"` present |
| `.gitignore`                                     | pdfs-to-test/ entry                             | VERIFIED   | Line 11: `pdfs-to-test/`                                    |
| `tests/fixtures/golden/.gitkeep`                 | Directory tracked by git                        | VERIFIED   | File exists on disk                                         |

### Key Link Verification

| From                                                  | To                                            | Via                            | Status   | Details                                                  |
|-------------------------------------------------------|-----------------------------------------------|--------------------------------|----------|----------------------------------------------------------|
| `policy_extractor/regression/pii_redactor.py`         | PII_FIELDS frozenset                          | hardcoded field list           | VERIFIED | Contains nombre_contratante, nombre_descripcion, rfc, curp, direccion, parentesco |
| `policy_extractor/regression/field_differ.py`         | DriftReport.format_table                      | string formatting              | VERIFIED | Line 65: `"\nField | Expected | Actual | Status"` header present |
| `policy_extractor/cli.py`                             | `policy_extractor/regression/pii_redactor.py` | lazy import inside create-fixture | VERIFIED | cli.py:602: `from policy_extractor.regression.pii_redactor import PiiRedactor` |
| `tests/test_regression.py`                            | `policy_extractor/regression/field_differ.py` | import                         | VERIFIED | test_regression.py:29: `from policy_extractor.regression.field_differ import FieldDiffer` |
| `tests/test_regression.py`                            | `policy_extractor/extraction`                 | extract_policy call            | VERIFIED | test_regression.py:27-28, 45: lazy imports + `extract_policy(ingestion_result)` |

### Requirements Coverage

| Requirement | Source Plan   | Description                                                                                 | Status    | Evidence                                                                              |
|-------------|---------------|---------------------------------------------------------------------------------------------|-----------|---------------------------------------------------------------------------------------|
| REG-01      | 11-01, 11-02  | Golden dataset fixtures exist with known-good extraction results                            | SATISFIED | `tests/fixtures/golden/` directory tracked; `create-fixture` CLI generates fixtures via extraction + PII redaction |
| REG-02      | 11-01, 11-02  | Regression tests compare extractions field-by-field with tolerance (not exact match)        | SATISFIED | FieldDiffer: skips REDACTED fields, skips provenance fields, partial match on campos_adicionales (extra keys allowed) |
| REG-03      | 11-01, 11-02  | Regression tests marked with `@pytest.mark.regression` and excluded from default test runs  | SATISFIED | `@pytest.mark.regression` on test_regression_fixture; `addopts = "-m 'not regression'"` confirmed active — 1 deselected in live run |
| REG-04      | 11-01, 11-02  | Regression test failures identify which specific fields drifted                             | SATISFIED | DriftReport rows contain (field_path, expected, actual, status); `format_table()` renders "Field | Expected | Actual | Status" table shown in assertion message |

No orphaned requirements — all four IDs declared in both plans and all four are fully satisfied.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_regression.py` | 19 | `return []` | Info | Intentional guard: `_discover_fixtures()` returns empty list when golden dir is empty/missing — correct behavior, not a stub |

No blocker or warning anti-patterns found. The single `return []` is an intentional design decision documented in 11-02-SUMMARY.md.

### Human Verification Required

None — all must-haves are fully verifiable programmatically.

The regression suite will require human action to exercise end-to-end (adding a real PDF to `pdfs-to-test/`, running `create-fixture`, then `pytest -m regression`) but the infrastructure itself is fully verified.

### Gaps Summary

No gaps. All 14 truths are verified. All 9 artifacts are substantive and wired. All 5 key links are confirmed. All 4 requirements (REG-01 through REG-04) are satisfied.

The phase goal is achieved: a repeatable, automated test suite exists that catches extraction quality regressions by comparing field-by-field output against known-good fixtures. The loop is complete — `create-fixture` generates PII-safe golden JSONs, `pytest -m regression` re-runs extraction and compares via FieldDiffer, failures show structured drift tables, and the suite is isolated from default runs.

---

_Verified: 2026-03-19T22:45:00Z_
_Verifier: Claude (gsd-verifier)_
