---
phase: 11
slug: regression-suite
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-19
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (installed) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_regression.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds (mocked extraction) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_regression.py -x` (or relevant test file)
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | REG-01 | unit | `pytest tests/test_regression.py -x -m regression` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | REG-02 | unit | `pytest tests/test_regression.py::test_field_comparison -x` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 1 | REG-03 | unit | `pytest tests/ -x -m "not regression"` | ❌ W0 | ⬜ pending |
| 11-01-04 | 01 | 1 | REG-04 | unit | `pytest tests/test_regression.py -x -v` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 2 | REG-01 | unit | `pytest tests/test_cli.py::test_create_fixture -x` | ❌ W0 | ⬜ pending |
| 11-02-02 | 02 | 2 | — | regression | `pytest tests/ -x` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_regression.py` — parametrized regression test functions
- [ ] `tests/fixtures/golden/` — directory (can be empty initially)
- [ ] `pyproject.toml` — `regression` marker + `addopts` exclusion

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Run create-fixture on real PDF, verify PII redaction | REG-01 | Requires real PDF + API key | 1. `poliza-extractor create-fixture pdfs-to-test/sample.pdf -o tests/fixtures/golden/` 2. Open JSON, verify [REDACTED] in PII fields |
| Run `pytest -m regression` with real PDFs + fixtures | REG-01/02 | Requires real PDFs + API key | 1. Generate fixtures 2. `pytest -m regression` 3. Verify pass/fail per fixture |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
