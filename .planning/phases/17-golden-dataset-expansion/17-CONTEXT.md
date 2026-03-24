# Phase 17: Golden Dataset Expansion - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

The regression suite is expanded to 20+ PII-redacted golden fixtures covering all 10 insurers the agency works with. A batch script creates fixtures from real PDFs, and regression tests catch extraction quality regressions. This phase delivers:
- A batch fixture creation script that processes PDFs, extracts, redacts PII, and writes golden JSON fixtures
- 20+ fixtures (2 per insurer) covering the 10 insurers
- A coverage matrix summary after regression test runs
- Self-validation (regression tests pass on all created fixtures)

</domain>

<decisions>
## Implementation Decisions

### Fixture Creation Workflow
- **D-01:** Batch script processes all PDFs in `pdfs-to-test/`, runs extraction, applies PII redaction via PiiRedactor, and writes golden fixtures to `tests/fixtures/golden/`. No manual one-by-one creation.
- **D-02:** Two-step process — script creates raw fixtures from extraction output first. User reviews and corrects data in HITL review UI, then re-exports corrected data as the final fixture.
- **D-03:** After creating all fixtures, the batch script runs `pytest -m regression` to self-validate that all fixtures pass immediately.

### Insurer Coverage Strategy
- **D-04:** 10 insurers to cover: Zurich, Qualitas, Mapfre, AXA, GNP, Chubb, Ana, HDI, Plan Seguro, Prudential.
- **D-05:** 2 fixtures per insurer = 20 fixtures minimum. Each fixture covers the 2 most common policy types the agency processes for that insurer.
- **D-06:** User provides real PDFs in `pdfs-to-test/` organized or named by insurer. The batch script discovers and processes them.

### Fixture Naming & Organization
- **D-07:** Fixture naming convention: `{insurer}_{type}_{seq}.json` — e.g., `zurich_auto_001.json`, `qualitas_auto_001.json`, `axa_vida_001.json`. Lowercase, underscore-separated, sortable.
- **D-08:** Minimal metadata in each fixture: `_source_pdf` (filename), `_insurer`, `_tipo_seguro`, `_created_at`. Enough for test discovery and reporting. No extra provenance fields.
- **D-09:** All fixtures stored in `tests/fixtures/golden/` (existing directory from Phase 11).

### Regression Test Improvements
- **D-10:** New fields appearing in re-extraction but not in the fixture are ignored — FieldDiffer already supports this. Only fields present in the fixture are compared.
- **D-11:** After `pytest -m regression` runs, print a coverage matrix showing insurer x type coverage with pass/fail/skip counts. Helps spot gaps in coverage.
- **D-12:** Coverage matrix implemented as a pytest plugin or conftest fixture that collects results and prints the summary at the end.

### Claude's Discretion
- Batch script implementation details (Python script, CLI subcommand, or standalone)
- Coverage matrix formatting and presentation
- How to handle PDFs that fail extraction (skip and report vs. fail the batch)
- FieldDiffer tolerance thresholds for numeric comparisons (existing defaults are fine)
- Whether to add a `--update-fixtures` flag to re-generate fixtures from corrected data

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Regression Infrastructure (Phase 11)
- `tests/test_regression.py` — Existing parametrized golden fixture tests, `_discover_fixtures()`, `test_regression_fixture()`, `test_fixture_format_valid()`
- `policy_extractor/regression/pii_redactor.py` — PiiRedactor class for stripping PII fields from fixture data
- `policy_extractor/regression/field_differ.py` — FieldDiffer for field-by-field comparison with drift detection
- `policy_extractor/regression/__init__.py` — Regression module public API

### Fixture Creation
- `tests/create_fixtures.py` — Existing fixture creation script (creates test PDFs, not golden fixtures)
- `policy_extractor/cli.py` — `create-fixture` CLI subcommand for single-fixture creation
- `tests/fixtures/golden/` — Target directory for golden fixtures (currently empty)

### Extraction Pipeline
- `policy_extractor/extraction/__init__.py` — `extract_policy()` used by regression tests
- `policy_extractor/ingestion/__init__.py` — `ingest_pdf()` used by regression tests

### Requirements
- `.planning/REQUIREMENTS.md` QA-01 — Golden dataset expanded to 20+ fixtures covering all 10 insurers

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PiiRedactor.redact()` — Ready-to-use PII stripping for fixture creation
- `FieldDiffer.compare()` — Field-by-field comparison returning `DriftResult` with `has_failures` and `format_table()`
- `create-fixture` CLI subcommand — Single-file fixture creation, can be extended or batch-wrapped
- `test_regression.py` — Parametrized test discovery from `tests/fixtures/golden/*.json`

### Established Patterns
- Fixtures are JSON files with `_source_pdf` key pointing to the real PDF filename in `pdfs-to-test/`
- PII fields replaced with `[REDACTED]` before committing
- Real PDFs are gitignored, fixture JSONs are committed
- `pytest -m regression` marker for regression-only tests
- `pyproject.toml` has `[tool.pytest.ini_options] markers = ["regression: ..."]`

### Integration Points
- Batch script writes to `tests/fixtures/golden/` — existing test discovery picks up new files automatically
- Coverage matrix plugin added to `conftest.py` or as a separate pytest plugin
- Batch script reuses `ingest_pdf()` → `extract_policy()` → `PiiRedactor.redact()` pipeline

</code_context>

<specifics>
## Specific Ideas

### Insurer List (locked)
The 10 insurers are: Zurich, Qualitas, Mapfre, AXA, GNP, Chubb, Ana, HDI, Plan Seguro, Prudential.

### Fixture Count Target
20 fixtures minimum (2 per insurer), covering the 2 most common policy types per insurer.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-golden-dataset-expansion*
*Context gathered: 2026-03-24*
