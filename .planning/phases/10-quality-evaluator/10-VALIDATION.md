---
phase: 10
slug: quality-evaluator
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (installed) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_evaluation.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~6 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_evaluation.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | QAL-02 | unit | `pytest tests/test_evaluation.py::test_evaluate_policy_returns_scores -x` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | QAL-02 | unit | `pytest tests/test_evaluation.py::test_evaluation_tool_schema -x` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 1 | QAL-03 | unit | `pytest tests/test_evaluation.py::test_update_evaluation_columns -x` | ❌ W0 | ⬜ pending |
| 10-01-04 | 01 | 1 | QAL-03 | unit | `pytest tests/test_evaluation.py::test_evaluation_json_is_valid_json -x` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 2 | QAL-01 | unit | `pytest tests/test_evaluation.py::test_evaluate_called_with_flag -x` | ❌ W0 | ⬜ pending |
| 10-02-02 | 02 | 2 | QAL-04 | unit | `pytest tests/test_evaluation.py::test_evaluate_not_called_without_flag -x` | ❌ W0 | ⬜ pending |
| 10-02-03 | 02 | 2 | QAL-01 | unit | `pytest tests/test_evaluation.py::test_batch_evaluate_flag -x` | ❌ W0 | ⬜ pending |
| 10-02-04 | 02 | 2 | QAL-05 | unit | `pytest tests/test_upload.py::test_upload_evaluate_param -x` | ❌ W0 | ⬜ pending |
| 10-02-05 | 02 | 2 | QAL-05 | unit | `pytest tests/test_upload.py::test_upload_no_evaluate_by_default -x` | ❌ W0 | ⬜ pending |
| 10-02-06 | 02 | 2 | — | regression | `pytest tests/test_cli.py -x -q` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_evaluation.py` — new file covering QAL-01 through QAL-04
- [ ] New tests in `tests/test_upload.py` — QAL-05 upload evaluate param

*Existing test patterns in test_extraction.py (MockMessage) and test_upload.py (TestClient) are reusable.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Run real extraction + evaluation against Anthropic API | QAL-01 | Requires API key + real PDF + Sonnet access | 1. `poliza-extractor extract poliza.pdf --evaluate` 2. Verify two cost lines (extraction + evaluation) 3. Check evaluation_score in DB |
| Verify evaluation scores are sensible for known PDF | QAL-02 | Requires domain judgment on score quality | 1. Extract + evaluate a well-known poliza 2. Check scores make sense for completeness/accuracy 3. Review flagged fields |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
