---
phase: 7
slug: export
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (no version pin in pyproject.toml) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_export.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_export.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | EXP-01 | unit | `pytest tests/test_export.py::test_xlsx_sheet_names -x` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | EXP-01 | unit | `pytest tests/test_export.py::test_xlsx_polizas_headers -x` | ❌ W0 | ⬜ pending |
| 07-01-03 | 01 | 1 | EXP-01 | unit | `pytest tests/test_export.py::test_xlsx_asegurados_has_numero_poliza -x` | ❌ W0 | ⬜ pending |
| 07-01-04 | 01 | 1 | EXP-01 | unit | `pytest tests/test_export.py::test_xlsx_coberturas_has_numero_poliza -x` | ❌ W0 | ⬜ pending |
| 07-01-05 | 01 | 1 | EXP-01 | unit | `pytest tests/test_export.py::test_xlsx_campos_expansion -x` | ❌ W0 | ⬜ pending |
| 07-01-06 | 01 | 1 | EXP-02 | unit | `pytest tests/test_export.py::test_csv_writes_polizas_only -x` | ❌ W0 | ⬜ pending |
| 07-01-07 | 01 | 1 | EXP-02 | unit | `pytest tests/test_export.py::test_csv_utf8_bom -x` | ❌ W0 | ⬜ pending |
| 07-01-08 | 01 | 1 | EXP-02 | unit | `pytest tests/test_export.py::test_csv_campos_expansion -x` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 1 | EXP-03 | integration | `pytest tests/test_export.py::test_cli_export_xlsx -x` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 1 | EXP-03 | integration | `pytest tests/test_export.py::test_cli_export_csv -x` | ❌ W0 | ⬜ pending |
| 07-02-03 | 02 | 1 | EXP-03 | regression | `pytest tests/test_cli.py::test_export_with_data -x` | ✅ exists | ⬜ pending |
| 07-02-04 | 02 | 1 | EXP-04 | integration | `pytest tests/test_export.py::test_xlsx_filter_aseguradora -x` | ❌ W0 | ⬜ pending |
| 07-02-05 | 02 | 1 | EXP-04 | integration | `pytest tests/test_export.py::test_xlsx_filter_dates -x` | ❌ W0 | ⬜ pending |
| 07-02-06 | 02 | 1 | EXP-05 | unit | `pytest tests/test_export.py::test_xlsx_prima_is_numeric -x` | ❌ W0 | ⬜ pending |
| 07-02-07 | 02 | 1 | EXP-05 | unit | `pytest tests/test_export.py::test_xlsx_date_is_date_type -x` | ❌ W0 | ⬜ pending |
| 07-02-08 | 02 | 1 | EXP-05 | unit | `pytest tests/test_export.py::test_xlsx_date_format -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_export.py` — stubs for EXP-01 through EXP-05 test functions
- [ ] `policy_extractor/export.py` — export module (created in Wave 1, tests stub against it)

*Existing `tests/conftest.py` provides `engine` and `session` fixtures — reusable for export tests. No new conftest needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Open .xlsx in Excel, verify SUM works on prima_total | EXP-05 | Requires visual inspection in Excel | 1. Export sample data to .xlsx 2. Open in Excel 3. Add SUM formula on prima_total column 4. Verify result is non-zero |
| Open .xlsx in Excel, verify date sorting works | EXP-05 | Requires Excel sort feature interaction | 1. Export sample data to .xlsx 2. Open in Excel 3. Sort by fecha_emision column 4. Verify chronological order |
| Open .csv in Excel on Windows, verify Spanish characters | EXP-02 | Requires Windows Excel with default encoding detection | 1. Export to .csv 2. Open in Excel on Windows 3. Verify ñ, á, é, etc. display correctly |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
