---
phase: 05
slug: storage-api
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_storage_writer.py tests/test_api.py -x -q` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~5 seconds (all in-memory DB, no live API) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_storage_writer.py tests/test_api.py -x -q`
- **After every plan wave:** Run `pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | STOR-01 | unit | `pytest tests/test_storage_writer.py -x -q` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | STOR-01 | unit (CLI) | `pytest tests/test_cli.py -x -q -k persist` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 2 | STOR-02 | unit (CLI) | `pytest tests/test_cli.py -x -q -k export` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 2 | STOR-02 | integration | `pytest tests/test_cli.py -x -q -k import` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 3 | STOR-03 | unit (TestClient) | `pytest tests/test_api.py -x -q` | ❌ W0 | ⬜ pending |
| 05-03-02 | 03 | 3 | STOR-04 | unit (TestClient) | `pytest tests/test_api.py -x -q -k filter` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_storage_writer.py` — upsert, update, round-trip tests for STOR-01
- [ ] `tests/test_api.py` — FastAPI TestClient tests for STOR-03 and STOR-04
- [ ] `pyproject.toml` — add `fastapi>=0.135.1` and `uvicorn[standard]>=0.42.0`

*Note: All tests use in-memory SQLite and FastAPI TestClient. No live server needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| FastAPI server starts and serves real requests | STOR-03 | Requires running server | Run `poliza-extractor serve`, visit localhost:8000/docs |
| End-to-end: extract PDF → persist → query via API | STOR-01, STOR-03 | Requires real PDF + API key | Extract a real PDF, then GET /polizas to verify data |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
