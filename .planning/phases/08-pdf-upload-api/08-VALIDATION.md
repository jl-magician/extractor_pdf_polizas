---
phase: 8
slug: pdf-upload-api
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (installed) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_upload.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_upload.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | API-01 | unit | `pytest tests/test_upload.py::test_upload_returns_202 -x` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | API-02 | unit | `pytest tests/test_upload.py::test_upload_multipart -x` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | API-02 | unit | `pytest tests/test_upload.py::test_upload_non_pdf_rejected -x` | ❌ W0 | ⬜ pending |
| 08-01-04 | 01 | 1 | API-04 | unit | `pytest tests/test_upload.py::test_upload_returns_job_object -x` | ❌ W0 | ⬜ pending |
| 08-01-05 | 01 | 1 | API-05 | unit | `pytest tests/test_upload.py::test_job_polling -x` | ❌ W0 | ⬜ pending |
| 08-01-06 | 01 | 1 | API-05 | unit | `pytest tests/test_upload.py::test_job_not_found -x` | ❌ W0 | ⬜ pending |
| 08-01-07 | 01 | 1 | API-05 | unit | `pytest tests/test_upload.py::test_list_jobs -x` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | API-03 | unit | `pytest tests/test_upload.py::test_upload_pipeline_called -x` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 2 | API-06 | unit | `pytest tests/test_upload.py::test_pdf_cleanup_on_success -x` | ❌ W0 | ⬜ pending |
| 08-02-03 | 02 | 2 | API-06 | unit | `pytest tests/test_upload.py::test_pdf_kept_on_failure -x` | ❌ W0 | ⬜ pending |
| 08-02-04 | 02 | 2 | API-03 | unit | `pytest tests/test_upload.py::test_idempotent_upload -x` | ❌ W0 | ⬜ pending |
| 08-02-05 | 02 | 2 | — | regression | `pytest tests/test_api.py -x -q` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_upload.py` — stubs for API-01 through API-06 test functions
- [ ] `policy_extractor/api/upload.py` — upload route module (created in Wave 1)
- [ ] `python-multipart` added to `pyproject.toml` dependencies

*Existing `tests/test_api.py` provides TestClient + dependency_overrides patterns — reusable for upload tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Upload real PDF via curl/Postman, verify extraction completes | API-03 | Requires Anthropic API key + real PDF | 1. Start server with `poliza-extractor serve` 2. `curl -F "file=@poliza.pdf" localhost:8000/polizas/upload` 3. Poll job URL until complete 4. Verify result contains poliza data |
| Restart server, upload same PDF, verify no crash | API-04 (success criteria 4) | Requires server restart cycle | 1. Upload PDF, wait for complete 2. Stop server 3. Start server 4. Upload same PDF 5. Verify 202 + job completes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
