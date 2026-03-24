---
phase: 15
slug: hitl-review-workflow
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/test_ui_review.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_ui_review.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 1 | UI-03, UI-04 | unit | `pytest tests/test_ui_review.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ui_review.py` — stubs for UI-03, UI-04
- [ ] `alembic/versions/005_corrections.py` — migration for corrections table

*Existing test infrastructure (conftest.py, StaticPool pattern) covers shared fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PDF renders in left pane | UI-03 | Browser rendering not testable in pytest | Open /ui/polizas/{id}/review, verify PDF iframe loads |
| Resizable divider works | UI-03 | CSS/JS interaction | Drag divider, verify both panes resize |
| Click-to-edit activates input | UI-04 | HTMX DOM interaction | Click a field value, verify input appears |
| Blue dot appears after correction | UI-04 | Visual indicator | Edit a field, verify blue dot on saved field |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
