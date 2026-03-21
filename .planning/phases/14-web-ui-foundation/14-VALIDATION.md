---
phase: 14
slug: web-ui-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| 14-01-01 | 01 | 1 | UI-01, UI-06 | unit | `pytest tests/test_ui_upload.py -x` | Wave 0 | ⬜ pending |
| 14-02-01 | 02 | 1 | UI-01, UI-02, UI-05 | unit | `pytest tests/test_ui_pages.py -x` | Wave 0 | ⬜ pending |
| 14-03-01 | 03 | 2 | UI-01 | unit | `pytest tests/test_ui_upload.py::test_batch_status_html -x` | Wave 0 | ⬜ pending |
| 14-03-02 | 03 | 2 | UI-02 | unit | `pytest tests/test_ui_pages.py::test_poliza_search -x` | Wave 0 | ⬜ pending |
| 14-03-03 | 03 | 2 | UI-05 | unit | `pytest tests/test_ui_pages.py::test_dashboard_stats -x` | Wave 0 | ⬜ pending |
| 14-03-04 | 03 | 2 | UI-06 | unit | `pytest tests/test_ui_upload.py::test_pdf_retained -x` | Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ui_upload.py` — stubs for UI-01, UI-06 batch upload endpoint and PDF retention
- [ ] `tests/test_ui_pages.py` — stubs for UI-01, UI-02, UI-05 HTML page rendering
- [ ] `tests/conftest.py` — confirm in-memory DB override pattern from test_upload.py is available
- [ ] `policy_extractor/templates/` directory — must exist before TemplateResponse routes
- [ ] `policy_extractor/static/` directory — must exist before StaticFiles mount

*Existing `tests/test_upload.py` covers old single-file upload API; new test files cover batch UI endpoints.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Drag-and-drop file selection in browser | UI-01 | Browser DOM interaction | Open /ui/upload, drag PDF files onto drop zone, verify files appear in staging list |
| Sidebar navigation works across all pages | UI-01 | Visual layout verification | Click each sidebar link, verify correct page loads with active state |
| Dashboard date range selector updates stats | UI-05 | HTMX partial swap visual | Select different date ranges, verify stat cards update |
| Progress bar animates during batch processing | UI-01 | Real-time visual behavior | Upload batch, watch progress bar update via HTMX polling |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
