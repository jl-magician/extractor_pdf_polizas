---
phase: 02
slug: ingestion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_ingestion.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds (unit), ~15 seconds (with OCR integration) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_ingestion.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | ING-01 | unit | `pytest tests/test_ingestion.py::test_classify_digital_page -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | ING-01 | unit | `pytest tests/test_ingestion.py::test_classify_scanned_page -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | ING-01 | unit | `pytest tests/test_ingestion.py::test_watermark_not_false_scanned -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | ING-02 | integration | `pytest tests/test_ingestion.py::test_ocr_spanish_text -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | ING-02 | unit | `pytest tests/test_ingestion.py::test_ocr_english_fallback -x` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 2 | ING-02 | unit | `pytest tests/test_ingestion.py::test_ocr_output_page_tuples -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 3 | ING-05 | unit | `pytest tests/test_ingestion.py::test_cache_hit_skips_ocr -x` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 3 | ING-05 | unit | `pytest tests/test_ingestion.py::test_force_reprocess_bypasses_cache -x` | ❌ W0 | ⬜ pending |
| 02-03-03 | 03 | 3 | ING-05 | unit | `pytest tests/test_ingestion.py::test_cache_hit_path_independent -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ingestion.py` — stubs for ING-01, ING-02, ING-05
- [ ] `tests/fixtures/digital_sample.pdf` — minimal digital PDF with selectable text
- [ ] `tests/fixtures/scanned_sample.pdf` — minimal image-only PDF for OCR tests
- [ ] `tests/conftest.py` — add `ingestion_session` fixture (in-memory SQLite with IngestionCache table)

*Note: ING-02 OCR integration tests require Tesseract installed with Spanish language pack. Mark with `@pytest.mark.requires_tesseract` and skip in CI if absent.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OCR extracts Spanish text accurately | ING-02 | Requires real scanned PDF with known content | Process a known scanned policy, verify extracted text matches expected content |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
