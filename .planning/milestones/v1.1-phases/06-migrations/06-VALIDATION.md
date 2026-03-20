---
phase: 6
slug: migrations
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-19
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already in dev dependencies) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` testpaths = ["tests"] |
| **Quick run command** | `pytest tests/test_migrations.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_migrations.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | MIG-01 | integration | `pytest tests/test_migrations.py::test_fresh_db_upgrade_head -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | MIG-02 | integration | `pytest tests/test_migrations.py::test_existing_db_upgrade_head_no_data_loss -x` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | MIG-03 | integration | `pytest tests/test_migrations.py::test_evaluation_columns_present_after_002 -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_migrations.py` — stubs for MIG-01, MIG-02, MIG-03 (new file)
- [ ] `alembic/` directory — Alembic initialization
- [ ] `alembic.ini` — Alembic configuration
- [ ] `alembic/versions/001_baseline.py` — baseline migration
- [ ] `alembic/versions/002_evaluation_columns.py` — evaluation columns migration
- [ ] `alembic` package added to `pyproject.toml` dependencies

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Auto-migrate on CLI startup | CONTEXT decision | Requires running actual CLI | Run `poliza-extractor extract --help` after fresh DB setup, verify no migration errors |
| Backup creation before migration | CONTEXT decision | Requires file system inspection | Run migration on existing DB, verify `.bak` file created |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
