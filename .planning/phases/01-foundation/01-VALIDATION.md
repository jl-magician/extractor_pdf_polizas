---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | DATA-01 | unit | `pytest tests/test_schemas.py -k insured_parties` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | DATA-02 | unit | `pytest tests/test_schemas.py -k campos_adicionales` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | DATA-03 | unit | `pytest tests/test_schemas.py -k date_normalization` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 1 | DATA-04 | unit | `pytest tests/test_schemas.py -k currency` | ❌ W0 | ⬜ pending |
| 01-01-05 | 01 | 1 | DATA-05 | unit | `pytest tests/test_schemas.py -k provenance` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | DATA-01 | unit | `pytest tests/test_database.py -k insured_parties_table` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 1 | DATA-02 | unit | `pytest tests/test_database.py -k json_overflow` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 1 | DATA-03 | unit | `pytest tests/test_database.py -k iso_dates` | ❌ W0 | ⬜ pending |
| 01-02-04 | 02 | 1 | DATA-05 | unit | `pytest tests/test_database.py -k provenance_columns` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_schemas.py` — stubs for DATA-01 through DATA-05 Pydantic schema validation
- [ ] `tests/test_database.py` — stubs for DATA-01 through DATA-05 SQLAlchemy model checks
- [ ] `tests/conftest.py` — shared fixtures (in-memory SQLite, sample policy data)
- [ ] `pytest` — install via `uv add --dev pytest`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| JSON overflow readable | DATA-02 | Visual inspection of JSON structure in SQLite | Insert sample record, query with json_extract(), verify fields |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
