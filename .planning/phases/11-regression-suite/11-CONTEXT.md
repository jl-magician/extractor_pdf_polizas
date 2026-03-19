# Phase 11: Regression Suite - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Automated golden dataset test suite that catches extraction quality regressions by comparing field-by-field output against known-good fixtures. Includes fixture generation CLI, PII redaction, and structured drift reporting. No changes to the extraction pipeline itself.

</domain>

<decisions>
## Implementation Decisions

### Golden fixture format & PII handling
- Real PDFs in `pdfs-to-test/` are `.gitignored` — never committed to repo
- Fixture JSON files use `PolicyExtraction.model_dump(mode='json')` format — full Pydantic model dump, same as CLI JSON output
- PII fields (nombre_contratante, nombre_descripcion, RFC, CURP, direccion, parentesco) are redacted to `"[REDACTED]"` in fixture JSONs
- Redacted fixture JSONs are committed to `tests/fixtures/golden/` — safe for version control
- Regression tests require real PDFs to be present locally in `pdfs-to-test/`; tests skip gracefully if PDFs missing (CI-safe)

### Field comparison & tolerance
- **Exact match** for all fields — no numeric or date tolerance. LLM extraction should produce deterministic results from the same PDF text
- **Redacted fields skipped** — any field with value `"[REDACTED]"` in the fixture is excluded from comparison
- **campos_adicionales: compare all known keys** — for each insurer/policy type, the fixture defines the expected key set. All fixture keys must match. Extra keys in the extraction are acceptable (improvement), but missing keys are failures
- Asegurados and coberturas compared by count and field values (order-independent matching by nombre_descripcion or nombre_cobertura)

### Drift reporting format
- **Structured diff table** on failure: `Field | Expected | Actual | Status` for each drifted field
- Uses pytest's built-in assertion message formatting + custom diff helper
- On success: fixture count only (e.g., "8 fixtures passed")
- Per-fixture pass/fail — each fixture file is a separate test function via `@pytest.mark.parametrize`

### Fixture management workflow
- **CLI command `poliza-extractor create-fixture file.pdf --output tests/fixtures/golden/`** — extracts, redacts PII fields, saves JSON fixture. Repeatable.
- Fixture updates: re-run `create-fixture` with new prompt, diff against old fixtures, manually approve changes
- No auto-update flag on test runner — all fixture changes are intentional and reviewed
- Fixture naming: `golden_{insurer}_{type}.json` (e.g., `golden_axa_auto.json`, `golden_gnp_vida.json`)
- Fixtures live in `tests/fixtures/golden/`

### pytest integration
- Tests marked with `@pytest.mark.regression`
- Default test runs (`pytest`) exclude regression tests via `addopts = "-m 'not regression'"` or `markers` config in `pyproject.toml`
- Regression suite runs explicitly with `pytest -m regression`

### Claude's Discretion
- Exact PII field detection logic (hardcoded field list vs pattern matching)
- How to match asegurados/coberturas when order differs (hash-based vs name-based)
- Custom assertion helper implementation details
- Whether create-fixture requires --model flag or uses default

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Extraction pipeline (fixture generation uses this)
- `policy_extractor/extraction/__init__.py` — `extract_policy()` returns 3-tuple; fixture generation calls this
- `policy_extractor/schemas/poliza.py` — `PolicyExtraction` Pydantic model; `model_dump(mode='json')` is the fixture format

### Existing test infrastructure
- `tests/create_fixtures.py` — Existing fixture creation script (for ingestion test PDFs); pattern to follow
- `tests/conftest.py` — Shared fixtures and engine/session setup
- `pyproject.toml` `[tool.pytest.ini_options]` — pytest configuration; needs `markers` and potentially `addopts` update

### CLI to extend
- `policy_extractor/cli.py` — Add `create-fixture` subcommand

### Test PDFs
- `pdfs-to-test/` — 8 real poliza PDFs from various insurers (gitignored)

### Requirements
- `.planning/REQUIREMENTS.md` §Regression Testing — REG-01 through REG-04

### Project decisions
- `.planning/STATE.md` §Pending Todos — "Before Phase 11: Audit pdfs-to-test/ directory for PII before committing any fixture PDFs"

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `extract_policy(ingestion_result)` — Full extraction pipeline; fixture generation runs this on real PDFs
- `PolicyExtraction.model_dump(mode='json')` — Serialization to fixture format
- `ingest_pdf(path, session)` — Ingestion for fixture generation
- `compute_file_hash(path)` — Hash for fixture identification
- `tests/create_fixtures.py` — Existing PyMuPDF fixture generation script; pattern reference

### Established Patterns
- Typer CLI with Rich console
- Lazy imports inside CLI commands
- `_setup_db()` at command start
- `@pytest.mark.parametrize` for data-driven tests

### Integration Points
- `cli.py` — Add `create-fixture` subcommand
- `pyproject.toml` — Add `regression` marker, exclude from default runs
- `tests/fixtures/golden/` — New directory for fixture JSONs
- `.gitignore` — Ensure `pdfs-to-test/` is listed

</code_context>

<specifics>
## Specific Ideas

- Each insurer/policy type combination should have a known set of campos_adicionales keys — the fixture captures the exact expected key set for that insurer
- The agency processes PDFs from ~10 insurers with 5-7 types each — the initial fixture set should cover at least one PDF per insurer present in pdfs-to-test/

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 11-regression-suite*
*Context gathered: 2026-03-19*
