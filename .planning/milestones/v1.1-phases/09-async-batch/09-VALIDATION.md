---
phase: 9
slug: async-batch
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-19
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (configured in pyproject.toml) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_cli.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~6 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_cli.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | ASYNC-04 | unit | `pytest tests/test_cli.py::test_rate_limit_retry_succeeds -x` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | ASYNC-04 | unit | `pytest tests/test_cli.py::test_no_retry_on_4xx -x` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 1 | ASYNC-01 | unit | `pytest tests/test_cli.py::test_batch_concurrent_3_workers -x` | ❌ W0 | ⬜ pending |
| 09-02-02 | 02 | 1 | ASYNC-02 | integration | `pytest tests/test_cli.py::test_batch_no_lock_errors -x` | ❌ W0 | ⬜ pending |
| 09-02-03 | 02 | 1 | ASYNC-03 | unit | `pytest tests/test_cli.py::test_batch_worker_own_session -x` | ❌ W0 | ⬜ pending |
| 09-02-04 | 02 | 1 | ASYNC-05 | unit | `pytest tests/test_cli.py::test_concurrency_flag_validation -x` | ❌ W0 | ⬜ pending |
| 09-02-05 | 02 | 1 | ASYNC-05 | unit | `pytest tests/test_cli.py::test_concurrency_1_sequential -x` | ❌ W0 | ⬜ pending |
| 09-02-06 | 02 | 1 | ASYNC-01 | unit | `pytest tests/test_cli.py::test_batch_summary_retries_row -x` | ❌ W0 | ⬜ pending |
| 09-02-07 | 02 | 1 | ASYNC-01 | unit | `pytest tests/test_cli.py::test_batch_idempotency_concurrent -x` | ❌ W0 | ⬜ pending |
| 09-02-08 | 02 | 1 | — | regression | `pytest tests/test_cli.py::test_batch_directory -x` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] New test functions in `tests/test_cli.py` — covers ASYNC-01 through ASYNC-05
- [ ] No new test files required — all tests extend existing `test_cli.py`

*Existing `tests/test_cli.py` provides mock patterns, `_make_mock_session_cls()`, and batch test fixtures — all reusable.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Run real concurrent batch with 3 workers against Anthropic API | ASYNC-01 | Requires API key + real PDFs | 1. `poliza-extractor batch pdfs-to-test/ --concurrency 3` 2. Verify all PDFs processed 3. Check no "database is locked" in output |
| Verify Rich progress bar renders cleanly during concurrent execution | ASYNC-01 | Visual inspection required | 1. Run batch with --concurrency 3 2. Watch progress bar updates 3. Verify no garbled output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
