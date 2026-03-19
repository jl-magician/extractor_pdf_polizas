---
phase: 03
slug: extraction
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_extraction.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~3 seconds (all mocked, no live API calls) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_extraction.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | EXT-01 | unit (mocked) | `pytest tests/test_extraction.py::test_extract_all_fields -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | EXT-02 | unit (mocked) | `pytest tests/test_extraction.py::test_output_is_valid_schema -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | EXT-03 | unit (mocked) | `pytest tests/test_extraction.py::test_insurer_classification -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | EXT-04 | unit (mocked) | `pytest tests/test_extraction.py::test_confianza_populated -x` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 1 | EXT-05 | unit (mocked) | `pytest tests/test_extraction.py::test_spanish_and_english -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_extraction.py` — mocked API tests for EXT-01 through EXT-05
- [ ] `policy_extractor/schemas/poliza.py` — add `confianza: dict` field
- [ ] `policy_extractor/config.py` — add EXTRACTION_MODEL, EXTRACTION_MAX_RETRIES, EXTRACTION_PROMPT_VERSION
- [ ] `pyproject.toml` — add `anthropic>=0.86.0` to dependencies

*Note: All tests mock `anthropic.Anthropic.messages.create`. No live API calls in test suite — tests verify parsing/validation/retry logic.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Extraction quality on real policies | EXT-01 | Requires real PDF with known values | Run extraction on a known policy, compare output to expected values |
| Spanish PDF extraction accuracy | EXT-05 | Requires real Spanish PDF | Process a real Spanish policy, verify all fields correctly extracted |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
