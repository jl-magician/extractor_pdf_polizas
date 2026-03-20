---
phase: 13
slug: extraction-pipeline-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 |
| **Config file** | pyproject.toml ([tool.pytest.ini_options]) |
| **Quick run command** | `python -m pytest tests/ -x -q -m "not regression"` |
| **Full suite command** | `python -m pytest tests/ -q -m "not regression"` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q -m "not regression"`
- **After every plan wave:** Run `python -m pytest tests/ -q -m "not regression"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | EXT-01 | unit | `pytest tests/test_prompt.py -q` | ❌ W0 | ⬜ pending |
| 13-01-02 | 01 | 1 | EXT-03 | unit | `pytest tests/test_ingestion.py -q` | ✅ | ⬜ pending |
| 13-02-01 | 02 | 1 | EXT-02 | unit | `pytest tests/test_validation.py -q` | ❌ W0 | ⬜ pending |
| 13-02-02 | 02 | 1 | EXT-04 | unit | `pytest tests/test_extraction.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_prompt.py` — stubs for EXT-01 prompt structure and overlay tests
- [ ] `tests/test_validation.py` — stubs for EXT-02 financial validator and registry tests

*Existing test files cover ingestion (test_ingestion.py) and extraction (test_extraction.py).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Zurich fixture extracts correct field mapping | EXT-01 | Requires real PDF + API call | Run `poliza-extractor extract 112234653_Poliza.pdf` and verify financiamiento=0.0, otros_servicios=808.2 |
| Zero-text PDF auto-OCR produces non-null extraction | EXT-03 | Requires real PDF + Tesseract | Run `poliza-extractor extract "Poliza 8650156226.pdf"` and verify core fields are not null |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
