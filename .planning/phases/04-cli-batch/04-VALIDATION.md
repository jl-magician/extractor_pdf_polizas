---
phase: 04
slug: cli-batch
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_cli.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~3 seconds (all mocked, no live API calls) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_cli.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | ING-03, CLI-01 | unit (mocked) | `pytest tests/test_cli.py::test_extract_single_file -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | ING-04, CLI-02 | unit (mocked) | `pytest tests/test_cli.py::test_batch_directory -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | CLI-03 | unit (mocked) | `pytest tests/test_cli.py::test_batch_progress_display -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | CLI-04 | unit (in-memory DB) | `pytest tests/test_cli.py::test_idempotency_skip -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | CLI-04 | unit (in-memory DB) | `pytest tests/test_cli.py::test_force_reprocess -x` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 2 | CLI-05 | unit (mocked) | `pytest tests/test_cli.py::test_cost_tracking -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cli.py` — covers ING-03, ING-04, CLI-01 through CLI-05 with mocked API responses
- [ ] No new conftest.py entries needed — existing engine/session fixtures are reusable

*Note: All tests mock `ingest_pdf` and `extract_policy`. No live API calls or real PDF processing in test suite.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Rich progress bar visual appearance | CLI-03 | Visual rendering cannot be automated | Run `poliza-extractor batch tests/fixtures/` and visually confirm progress bar |
| Cost accuracy against real API usage | CLI-05 | Requires real API call | Run extraction on a real PDF, compare reported cost to Anthropic dashboard |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
