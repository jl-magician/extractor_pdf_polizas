---
phase: 17-golden-dataset-expansion
verified: 2026-03-24T12:00:00Z
status: gaps_found
score: 2/5 must-haves verified
gaps:
  - truth: "The golden dataset contains at least 20 PII-redacted fixtures, with at least one fixture per each of the 10 insurers"
    status: failed
    reason: "tests/fixtures/golden/ is empty — zero fixture files exist. The batch-fixtures tooling was built but never run against real PDFs. User-supplied PDFs in pdfs-to-test/ are a prerequisite that was not fulfilled."
    artifacts:
      - path: "tests/fixtures/golden/"
        issue: "Directory exists but contains 0 fixture files. Phase goal requires 20+."
    missing:
      - "20+ JSON fixture files named {insurer}_{type}_{seq:03d}.json across all 10 insurers"
      - "User must supply real PDFs in pdfs-to-test/ and run: poliza-extractor batch-fixtures pdfs-to-test/ --output tests/fixtures/golden/"
  - truth: "Running `pytest -m regression` passes all fixtures without any skipped tests due to missing fixture files"
    status: failed
    reason: "With 0 golden fixtures, pytest -m regression collects 1 skipped test (test_fixture_format_valid with no parametrize IDs) and runs 0 actual regression assertions. No fixture is tested."
    artifacts:
      - path: "tests/test_regression.py"
        issue: "test_regression_fixture is parametrized over golden/*.json — with an empty directory, zero test cases are generated and executed."
    missing:
      - "Golden fixtures must exist before regression test coverage is meaningful"
  - truth: "Any new extraction prompt change that causes a field regression on an existing fixture is caught by the test suite before merging"
    status: failed
    reason: "Regression detection requires fixtures to regress against. With 0 fixtures, no extraction change will be caught. The safety net the phase promises does not exist."
    artifacts: []
    missing:
      - "Golden fixtures for all 10 insurers must be committed to repo before this truth can hold"
human_verification:
  - test: "Run batch-fixtures against real PDFs to populate golden dataset"
    expected: "poliza-extractor batch-fixtures pdfs-to-test/ --output tests/fixtures/golden/ produces 20+ JSON files, each containing _source_pdf, _insurer, _tipo_seguro, _created_at metadata and PII-redacted fields"
    why_human: "Requires real insurance PDFs that Claude cannot supply. User must place 2+ PDFs per insurer (10 insurers, 20 files minimum) in pdfs-to-test/ and execute the command."
  - test: "Regression suite passes after fixture population"
    expected: "pytest -m regression exits 0 with 20+ passed tests; coverage matrix shows all 10 insurers with pass count >= 2"
    why_human: "Cannot run without real PDFs. Depends on successful batch-fixtures execution above."
---

# Phase 17: Golden Dataset Expansion Verification Report

**Phase Goal:** The regression suite covers all 10 insurers with 20+ fixtures, giving systematic confidence that extraction quality does not regress across insurer formats
**Verified:** 2026-03-24
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Golden dataset contains 20+ PII-redacted fixtures, at least 1 per each of 10 insurers | FAILED | tests/fixtures/golden/ is empty — 0 files |
| 2 | `pytest -m regression` passes all fixtures with no skipped tests | FAILED | Runs 1 skipped, 0 assertions — no fixtures to test |
| 3 | Extraction prompt changes that cause field regressions are caught before merging | FAILED | Impossible with 0 fixtures; no regression baseline exists |
| 4 | `batch-fixtures` CLI subcommand exists and processes PDFs into golden fixtures | VERIFIED | cli.py lines 688-801; all 6 unit tests pass |
| 5 | Coverage matrix prints after `pytest -m regression` showing all 10 insurers | VERIFIED | conftest.py plugin confirmed; matrix ran and showed 0/0/0 for all insurers |

**Score:** 2/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `policy_extractor/cli.py` | batch-fixtures CLI subcommand | VERIFIED | `def batch_fixtures` at line 689; `@app.command(name="batch-fixtures")` at line 688; `_KNOWN_INSURERS`, `_infer_insurer`, `_infer_type` present |
| `tests/test_batch_fixture.py` | Unit tests for batch fixture creation | VERIFIED | 6 tests present; all pass (`6 passed in 1.26s`) |
| `tests/conftest.py` | Coverage matrix pytest plugin | VERIFIED | `_ALL_INSURERS`, `_parse_insurer_from_nodeid`, `_format_coverage_matrix`, `RegressionCoveragePlugin`, `pytest_terminal_summary`, `pytest_configure` all confirmed |
| `tests/test_coverage_matrix.py` | Tests for coverage matrix helpers | VERIFIED | 11 tests present; all pass (`11 passed in 0.07s`) |
| `tests/fixtures/golden/*.json` | 20+ golden fixture files | MISSING | Directory exists but contains 0 files — the core deliverable of QA-01 is absent |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `policy_extractor/cli.py` | `policy_extractor/regression/pii_redactor.py` | `PiiRedactor().redact()` call | WIRED | Lazy import at line 718; `PiiRedactor().redact(raw)` at line 781 |
| `policy_extractor/cli.py` | `policy_extractor/extraction/__init__.py` | `extract_policy()` for each PDF | WIRED | `from policy_extractor.extraction import extract_policy` at line 37; called at line 759 |
| `tests/conftest.py` | `tests/fixtures/golden/` | Reads fixture filenames to extract insurer slugs | PARTIAL | Plugin reads node IDs from pytest (not directly from directory). `_parse_insurer_from_nodeid` parses slugs from parametrize IDs that originate from fixture filenames. Works correctly when fixtures exist — currently parses 0 IDs because directory is empty. |
| `tests/conftest.py` | `tests/test_regression.py` | pytest hooks collect results from regression-marked tests | WIRED | `pytest_runtest_logreport` filters on `"regression" not in report.keywords`; `pytest_terminal_summary` prints matrix; confirmed working in live run |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `batch_fixtures` in cli.py | `policy` (PolicyExtraction object) | `extract_policy(ingest_pdf(pdf))` | Yes — real LLM extraction pipeline | FLOWING (when PDFs exist) |
| `RegressionCoveragePlugin` in conftest.py | `self._results` dict | `pytest_runtest_logreport` hooks from live test execution | Yes — real pytest outcome data | FLOWING (when fixtures/tests exist) |
| `tests/fixtures/golden/` | 20+ JSON files | `batch-fixtures` CLI writes them from extraction output | NO DATA — directory empty | DISCONNECTED — tooling ready but not run |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| batch-fixtures --help shows usage | `poliza-extractor batch-fixtures --help` | Not run (requires live CLI entry point) | SKIP — human verification |
| test_batch_fixture.py all pass | `python -m pytest tests/test_batch_fixture.py -q` | `6 passed in 1.26s` | PASS |
| test_coverage_matrix.py all pass | `python -m pytest tests/test_coverage_matrix.py -q` | `11 passed in 0.07s` | PASS |
| `pytest -m regression` coverage matrix prints | `python -m pytest -m regression -q` | Matrix printed; all 10 insurers show 0/0/0; 1 skipped, 0 passed | FAIL — no fixtures to run |
| Full test suite has no regressions | `python -m pytest tests/ -q` | `480 passed, 3 skipped, 2 xpassed in 8.23s` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| QA-01 | 17-01-PLAN.md, 17-02-PLAN.md | Golden dataset expanded to 20+ fixtures covering all 10 insurers | BLOCKED | REQUIREMENTS.md marks it Complete (line 88), but `tests/fixtures/golden/` is empty. The tooling to satisfy QA-01 was built; the dataset itself was not populated. QA-01 cannot be considered satisfied until 20+ fixtures are committed. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | No code stubs, TODO comments, empty implementations, or hardcoded empty returns found in phase-modified files | — | — |

No anti-patterns detected. The implementation code is complete and substantive. The gap is a missing user action (supplying real PDFs), not a code deficiency.

### Human Verification Required

#### 1. Populate the golden dataset with real PDFs

**Test:** Place 2 real PDF files per insurer (20+ total) in `pdfs-to-test/`, then run:
```
poliza-extractor batch-fixtures pdfs-to-test/ --output tests/fixtures/golden/
```
**Expected:** 20+ JSON files created in `tests/fixtures/golden/`, each named `{insurer}_{type}_{seq:03d}.json`, each containing `_source_pdf`, `_insurer`, `_tipo_seguro`, `_created_at` keys, with PII fields replaced by `[REDACTED]`.
**Why human:** Requires real insurance PDFs that cannot be programmatically supplied. User must provide PDFs from the 10 insurers (Zurich, Qualitas, Mapfre, AXA, GNP, Chubb, Ana, HDI, Plan Seguro, Prudential).

#### 2. Verify regression suite passes after fixture population

**Test:** After step 1, run:
```
python -m pytest -m regression -v
```
**Expected:** 20+ tests pass; coverage matrix at end shows all 10 insurers with pass count >= 1 (preferably >= 2). Zero skipped tests due to missing fixture files.
**Why human:** Cannot run without real PDFs. Depends on step 1 completing successfully.

#### 3. Verify fixture PII redaction quality

**Test:** Open any created fixture JSON and confirm PII fields (`nombre_contratante`, `rfc`, `domicilio`, etc.) contain `[REDACTED]` and not real personal data.
**Expected:** All personal identifiable fields show `[REDACTED]` placeholder.
**Why human:** PII field list varies by insurer format; automated check cannot enumerate all possible PII field names without domain knowledge.

### Gaps Summary

The phase built all the tooling required to achieve its goal, but the goal itself — having 20+ fixtures in the golden dataset — was not achieved. The `tests/fixtures/golden/` directory is empty.

**Root cause:** The phase requires user-supplied real PDFs (noted in 17-01-PLAN.md `user_setup` section) before the `batch-fixtures` command can populate the dataset. This is a user-action prerequisite that was documented but not executed.

**What the tooling delivers (working):**
- `batch-fixtures` CLI subcommand — fully implemented, 6 tests pass
- Coverage matrix pytest plugin — fully implemented, 11 tests pass, prints correct output after regression runs
- PiiRedactor wiring — confirmed connected via lazy import + call
- Sequence-numbered naming convention `{insurer}_{type}_{seq:03d}.json` — implemented and tested

**What is missing (blocking QA-01):**
- 20+ committed golden fixture files covering all 10 insurers
- At least 1 fixture per insurer in `tests/fixtures/golden/`
- Regression tests that actually run (currently 0 tests collected under `-m regression`)

The phase is in a "tooling complete, data not yet populated" state. QA-01 cannot be marked satisfied until the user runs `batch-fixtures` against real PDFs and commits the resulting fixtures.

---

_Verified: 2026-03-24_
_Verifier: Claude (gsd-verifier)_
