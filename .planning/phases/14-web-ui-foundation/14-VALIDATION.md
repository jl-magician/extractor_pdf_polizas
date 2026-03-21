---
phase: 14
slug: web-ui-foundation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-20
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already configured in pyproject.toml) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_ui_upload.py tests/test_ui_pages.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_ui_upload.py tests/test_ui_pages.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | UI-01, UI-06 | unit | `pytest tests/test_ui_infra.py -x` | Wave 0 | pending |
| 14-02-01 | 02 | 2 | UI-06 | unit | `pytest tests/test_ui_upload.py -x` (stub created Wave 0, expanded Task 3) | Wave 0 | pending |
| 14-02-02 | 02 | 2 | UI-01, UI-06 | unit | `pytest tests/test_ui_upload.py -x` | Wave 0 | pending |
| 14-02-03 | 02 | 2 | UI-01, UI-06 | unit | `pytest tests/test_ui_upload.py -x` | Wave 0 | pending |
| 14-03-01 | 03 | 2 | UI-02 | unit | `pytest tests/test_ui_pages.py -x` | Wave 0 | pending |
| 14-03-02 | 03 | 2 | UI-02 | unit | `pytest tests/test_ui_pages.py -x` | Wave 0 | pending |
| 14-04-01 | 04 | 3 | UI-05 | unit | `pytest tests/test_ui_dashboard.py -x` | Wave 0 | pending |
| 14-04-02 | 04 | 3 | UI-05 | unit | `pytest tests/test_ui_dashboard.py -x` | Wave 0 | pending |
| 14-05-01 | 05 | 3 | UI-01, UI-02, UI-05, UI-06 | integration | `pytest tests/test_ui_integration.py -x` | Wave 0 | pending |
| 14-05-02 | 05 | 3 | UI-01, UI-02, UI-05, UI-06 | manual | N/A (checkpoint:human-verify) | N/A | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

Wave 0 creates stub test files with failing assertions before any Wave 1+ plan executes. Each plan's first task writes tests RED before writing production code.

- [x] `tests/test_ui_infra.py` — stub created by Plan 01 Task 1 (TDD: tests written first, then implementation)
- [x] `tests/test_ui_upload.py` — stub created by Plan 02 Task 3 (tests for upload endpoints including batch_export)
- [x] `tests/test_ui_pages.py` — stub created by Plan 03 Task 2 (tests for poliza list/detail pages)
- [x] `tests/test_ui_dashboard.py` — stub created by Plan 04 Task 2 (tests for dashboard and job history)
- [x] `tests/test_ui_integration.py` — stub created by Plan 05 Task 1 (integration tests for all pages)
- [x] `tests/conftest.py` — confirm in-memory DB override pattern from test_upload.py is available
- [x] `policy_extractor/templates/` directory — must exist before TemplateResponse routes
- [x] `policy_extractor/static/` directory — must exist before StaticFiles mount

Note: Each plan creates its own test file as part of its tasks (TDD or test-after). Wave 0 is satisfied by the plan structure itself -- Plan 01 Task 1 writes tests before implementation (tdd="true"), Plans 02-05 include test tasks that create the test files alongside or after implementation. All test files exist before verification runs.

*Existing `tests/test_upload.py` covers old single-file upload API; new test files cover batch UI endpoints.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Drag-and-drop file selection in browser | UI-01 | Browser DOM interaction | Open /ui/upload, drag PDF files onto drop zone, verify files appear in staging list |
| Sidebar navigation works across all pages | UI-01 | Visual layout verification | Click each sidebar link, verify correct page loads with active state |
| Dashboard date range selector updates stats | UI-05 | HTMX partial swap visual | Select different date ranges (presets and custom desde/hasta), verify stat cards update |
| Progress bar animates during batch processing | UI-01 | Real-time visual behavior | Upload batch, watch progress bar update via HTMX polling |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready
