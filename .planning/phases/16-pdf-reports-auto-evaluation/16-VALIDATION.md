---
phase: 16
slug: pdf-reports-auto-evaluation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/test_reports.py tests/test_auto_eval.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_reports.py tests/test_auto_eval.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | RPT-01 | unit | `pytest tests/test_reports.py -k "test_generate_pdf"` | ❌ W0 | ⬜ pending |
| 16-01-02 | 01 | 1 | RPT-02 | unit | `pytest tests/test_reports.py -k "test_per_insurer"` | ❌ W0 | ⬜ pending |
| 16-02-01 | 02 | 1 | QA-02 | unit | `pytest tests/test_auto_eval.py -k "test_auto_trigger"` | ❌ W0 | ⬜ pending |
| 16-02-02 | 02 | 1 | QA-03 | unit | `pytest tests/test_auto_eval.py -k "test_swap_detection"` | ❌ W0 | ⬜ pending |
| 16-03-01 | 03 | 2 | RPT-01 | integration | `pytest tests/test_reports.py -k "test_download_route"` | ❌ W0 | ⬜ pending |
| 16-03-02 | 03 | 2 | QA-02 | integration | `pytest tests/test_auto_eval.py -k "test_eval_scores_ui"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_reports.py` — stubs for RPT-01, RPT-02
- [ ] `tests/test_auto_eval.py` — stubs for QA-02, QA-03

*Existing infrastructure covers test framework and fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PDF visual layout per insurer | RPT-02 | Visual comparison needed | Generate reports for 2+ insurers, verify different colors/field order |
| PDF generation under 5 seconds | RPT-01 SC-1 | Performance varies by machine | Time the download route response |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
