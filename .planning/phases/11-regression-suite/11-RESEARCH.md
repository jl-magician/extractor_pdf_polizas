# Phase 11: Regression Suite - Research

**Researched:** 2026-03-19
**Domain:** pytest golden-dataset regression testing, PII redaction, field-level diff reporting
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Real PDFs in `pdfs-to-test/` are `.gitignored` — never committed to repo
- Fixture JSON files use `PolicyExtraction.model_dump(mode='json')` format — full Pydantic model dump, same as CLI JSON output
- PII fields (nombre_contratante, nombre_descripcion, RFC, CURP, direccion, parentesco) are redacted to `"[REDACTED]"` in fixture JSONs
- Redacted fixture JSONs are committed to `tests/fixtures/golden/` — safe for version control
- Regression tests require real PDFs to be present locally in `pdfs-to-test/`; tests skip gracefully if PDFs missing (CI-safe)
- **Exact match** for all fields — no numeric or date tolerance. LLM extraction should produce deterministic results from the same PDF text
- **Redacted fields skipped** — any field with value `"[REDACTED]"` in the fixture is excluded from comparison
- **campos_adicionales: compare all known keys** — all fixture keys must match; extra keys in the extraction are acceptable, missing keys are failures
- Asegurados and coberturas compared by count and field values (order-independent matching by nombre_descripcion or nombre_cobertura)
- **Structured diff table** on failure: `Field | Expected | Actual | Status` for each drifted field
- Uses pytest's built-in assertion message formatting + custom diff helper
- On success: fixture count only (e.g., "8 fixtures passed")
- Per-fixture pass/fail via `@pytest.mark.parametrize`
- **CLI command `poliza-extractor create-fixture file.pdf --output tests/fixtures/golden/`** — extracts, redacts PII fields, saves JSON fixture
- No auto-update flag on test runner — all fixture changes are intentional
- Fixture naming: `golden_{insurer}_{type}.json` (e.g., `golden_axa_auto.json`)
- Tests marked with `@pytest.mark.regression`
- Default test runs (`pytest`) exclude regression tests via `addopts = "-m 'not regression'"` in `pyproject.toml`
- Regression suite runs explicitly with `pytest -m regression`

### Claude's Discretion
- Exact PII field detection logic (hardcoded field list vs pattern matching)
- How to match asegurados/coberturas when order differs (hash-based vs name-based)
- Custom assertion helper implementation details
- Whether create-fixture requires --model flag or uses default

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REG-01 | Golden dataset fixtures exist with known-good extraction results | Fixture JSON format confirmed: `PolicyExtraction.model_dump(mode='json')`; PII redaction list defined; storage in `tests/fixtures/golden/` |
| REG-02 | Regression tests compare extractions field-by-field with tolerance (not exact match) | Decision overrides to exact match per CONTEXT.md; redacted fields skipped; campos_adicionales partial match |
| REG-03 | Regression tests are marked with `@pytest.mark.regression` and excluded from default test runs | `addopts = "-m 'not regression'"` pattern confirmed via pyproject.toml inspection; marker registration required |
| REG-04 | Regression test failures identify which specific fields drifted | Custom diff helper produces `Field \| Expected \| Actual \| Status` table; pytest assertion rewriting provides line-level context |
</phase_requirements>

---

## Summary

Phase 11 adds a golden-dataset regression harness on top of the existing, fully functional extraction pipeline. The implementation has three logical units: (1) fixture creation — a new `create-fixture` CLI subcommand that runs the real extraction pipeline on a PDF, redacts a known PII field list, and writes a versioned JSON to `tests/fixtures/golden/`; (2) the regression test module — a parametrized pytest suite that loads each fixture JSON, locates the corresponding real PDF, runs extraction, and compares output field-by-field; and (3) pytest configuration — marker registration plus `addopts` to keep regression tests out of the default run.

All infrastructure already exists. `extract_policy()` and `ingest_pdf()` are stable. The Typer CLI follows an established lazy-import, `_setup_db()` at start pattern. The conftest already provides in-memory engine and session fixtures. The only new production code is the `create-fixture` CLI subcommand, a `PiiRedactor` helper, and a `FieldDiffer` helper. Tests live in a single new file `tests/test_regression.py`.

The 8 real PDFs in `pdfs-to-test/` are already present locally but NOT in `.gitignore` yet — that entry must be added as part of this phase (STATE.md pending todo). Fixture JSONs (redacted) are safe to commit.

**Primary recommendation:** Implement in two waves — Wave 1: fixture infrastructure (PiiRedactor, create-fixture CLI command, golden/ directory, gitignore update, pytest config); Wave 2: regression test harness (parametrized test, FieldDiffer, conftest skip logic).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | already in dev deps | Test runner, marker system, parametrize | Already used across all 14 test files |
| pydantic | >=2.12.5 (installed) | `model_dump(mode='json')` fixture serialization | ProjectExtraction uses it; fixture format follows this |
| json (stdlib) | stdlib | Read/write fixture JSON files | No additional dep needed |
| typer | >=0.9.0 (installed) | `create-fixture` CLI subcommand | Established CLI framework in project |
| pathlib (stdlib) | stdlib | PDF discovery, fixture path resolution | Used throughout codebase |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| rich | >=13.0.0 (installed) | Console output for create-fixture | Matches existing CLI style |
| pytest-parametrize (built-in) | n/a | Per-fixture test cases | `@pytest.mark.parametrize` with fixture file list |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hardcoded PII field list | pattern matching / Pydantic field introspection | Hardcoded list is explicit and auditable; patterns risk false positives on domain-specific field names |
| name-based asegurado matching | hash-based or index-based | Name is stable across re-extractions of the same PDF; index breaks on reorder |

**Installation:** No new packages required — all dependencies are already in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure
```
tests/
├── fixtures/
│   ├── golden/                  # Committed fixture JSONs (PII-redacted)
│   │   ├── golden_axa_auto.json
│   │   └── golden_gnp_vida.json
│   ├── digital_sample.pdf       # Existing synthetic fixture
│   └── scanned_sample.pdf       # Existing synthetic fixture
├── test_regression.py           # New: parametrized regression suite
└── conftest.py                  # Existing: engine/session fixtures (no changes needed)

policy_extractor/
├── cli.py                       # Add create-fixture subcommand
└── regression/                  # New package
    ├── __init__.py
    ├── pii_redactor.py          # PiiRedactor class
    └── field_differ.py          # FieldDiffer + DriftReport
```

### Pattern 1: pytest marker registration + addopts exclusion
**What:** Register custom marker in pyproject.toml; exclude from default run with addopts
**When to use:** Any test category that should not run on every `pytest` call

```toml
# pyproject.toml [tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "regression: golden dataset regression suite (requires real PDFs in pdfs-to-test/)",
]
addopts = "-m 'not regression'"
```

The `addopts` approach is the canonical way to exclude tests from the default run — confirmed by pytest docs. It is transparent (visible in config), overridable (`pytest -m regression`), and does not require any conftest hook.

### Pattern 2: Parametrized test with per-fixture skip
**What:** Discover fixture files at collection time; skip individually if PDF missing
**When to use:** Data-driven tests where the input set grows without code changes

```python
# tests/test_regression.py
import json
from pathlib import Path
import pytest
from policy_extractor.ingestion import ingest_pdf
from policy_extractor.extraction import extract_policy
from policy_extractor.regression.field_differ import FieldDiffer

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"
PDFS_DIR = Path(__file__).parent.parent / "pdfs-to-test"

def _fixture_params():
    """Collect (fixture_path, pdf_stem) pairs at collection time."""
    return [p for p in sorted(GOLDEN_DIR.glob("*.json"))]

@pytest.mark.regression
@pytest.mark.parametrize("fixture_path", _fixture_params(), ids=lambda p: p.stem)
def test_regression_fixture(fixture_path, session):
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    pdf_stem = fixture.get("_source_pdf")  # stored in fixture by create-fixture
    pdf_path = PDFS_DIR / pdf_stem
    if not pdf_path.exists():
        pytest.skip(f"Real PDF not found: {pdf_path.name}")

    ingestion_result = ingest_pdf(pdf_path, session=session)
    policy, _usage, _retries = extract_policy(ingestion_result)
    assert policy is not None, "Extraction returned None"

    actual = policy.model_dump(mode="json")
    differ = FieldDiffer(fixture, actual)
    drift = differ.compare()
    assert not drift.has_failures, drift.format_table()
```

**Key insight:** `_fixture_params()` runs at collection time. If `tests/fixtures/golden/` is empty the parametrize list is empty and the test is silently skipped — safe with no golden fixtures yet.

### Pattern 3: PII Redaction helper
**What:** Traverse the fixture dict and replace known PII fields with `"[REDACTED]"`
**When to use:** Before writing a fixture JSON to disk

```python
# policy_extractor/regression/pii_redactor.py
PII_FIELDS = frozenset({
    "nombre_contratante",
    "nombre_descripcion",  # on AseguradoExtraction
    "rfc",
    "curp",
    "direccion",
    "parentesco",
})

class PiiRedactor:
    def redact(self, data: dict) -> dict:
        """Return a deep copy of data with PII fields replaced by '[REDACTED]'."""
        import copy
        result = copy.deepcopy(data)
        self._redact_recursive(result)
        return result

    def _redact_recursive(self, node):
        if isinstance(node, dict):
            for k in list(node.keys()):
                if k.lower() in PII_FIELDS:
                    node[k] = "[REDACTED]"
                else:
                    self._redact_recursive(node[k])
        elif isinstance(node, list):
            for item in node:
                self._redact_recursive(item)
```

### Pattern 4: Field-level diff helper
**What:** Compare fixture vs actual dict; produce structured drift report
**When to use:** `assert` body in regression test; output drives REG-04

```python
# policy_extractor/regression/field_differ.py
from dataclasses import dataclass, field
from rich.table import Table
from rich.console import Console

@dataclass
class DriftReport:
    rows: list[tuple[str, str, str, str]] = field(default_factory=list)  # field, expected, actual, status

    @property
    def has_failures(self) -> bool:
        return any(r[3] == "FAIL" for r in self.rows)

    def format_table(self) -> str:
        """Return a plain-text drift table for pytest assertion output."""
        lines = ["\nField | Expected | Actual | Status"]
        lines.append("-" * 60)
        for f, exp, act, status in self.rows:
            lines.append(f"{f} | {exp!r} | {act!r} | {status}")
        return "\n".join(lines)
```

Comparison logic:
- Top-level scalar fields: `expected[k] == actual[k]` (skip if expected value is `"[REDACTED]"`)
- `campos_adicionales`: for each key in fixture dict → assert present and equal in actual; extra keys in actual are PASS
- `asegurados`: match by `nombre_descripcion` value (order-independent); compare all non-REDACTED fields
- `coberturas`: match by `nombre_cobertura`; compare all non-REDACTED fields
- `confianza`: skip entirely (not compared — varies per run)
- Provenance fields (`source_file_hash`, `model_id`, `prompt_version`, `extracted_at`): skip (not in fixture)

### Pattern 5: create-fixture CLI subcommand
**What:** New Typer command that runs the pipeline and writes a redacted fixture JSON
**When to use:** After adding a new insurer PDF to pdfs-to-test/

```python
# policy_extractor/cli.py — new subcommand
@app.command(name="create-fixture")
def create_fixture(
    file: Path = typer.Argument(..., help="Path to real PDF", exists=True),
    output: Path = typer.Option(
        Path("tests/fixtures/golden"), "--output", "-o", help="Output directory"
    ),
    insurer: str = typer.Option(..., "--insurer", help="Insurer slug, e.g. axa"),
    policy_type: str = typer.Option(..., "--type", help="Policy type slug, e.g. auto"),
    model: Optional[str] = typer.Option(None, "--model", help="Override extraction model"),
) -> None:
    """Extract, redact PII, and save a golden fixture JSON."""
    from policy_extractor.regression.pii_redactor import PiiRedactor
    _setup_db()
    session = SessionLocal()
    try:
        ingestion_result = ingest_pdf(file, session=session)
        policy, usage, _retries = extract_policy(ingestion_result, model=model)
        if policy is None:
            console.print("[red]Extraction failed — cannot create fixture[/red]")
            raise typer.Exit(1)
        raw = policy.model_dump(mode="json")
        raw["_source_pdf"] = file.name  # provenance: links fixture to its PDF
        redacted = PiiRedactor().redact(raw)
        output.mkdir(parents=True, exist_ok=True)
        out_file = output / f"golden_{insurer}_{policy_type}.json"
        out_file.write_text(
            json.dumps(redacted, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        console.print(f"[green]Fixture written:[/green] {out_file}")
        if usage:
            _print_cost(model or settings.EXTRACTION_MODEL, usage.input_tokens, usage.output_tokens)
    finally:
        session.close()
```

### Anti-Patterns to Avoid
- **Auto-updating fixtures on test run:** Never add `--update-fixtures` to the test runner. All fixture changes must be explicit `create-fixture` re-runs followed by manual diff review.
- **Comparing provenance fields:** `source_file_hash`, `model_id`, `prompt_version`, `extracted_at` change every run — exclude from comparison.
- **Comparing `confianza` dict:** Confidence values may drift without indicating a real regression — skip.
- **Exact list order comparison for asegurados/coberturas:** Insurers may reorder items in PDF — use name-based matching.
- **`addopts = "-m not regression"` without quotes:** Must be `"-m 'not regression'"` (with inner quotes) or the marker expression fails to parse.
- **Running regression tests in CI without PDF gate:** Tests must `pytest.skip()` cleanly if PDF missing, not error or fail.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Marker exclusion from default run | Custom conftest hook that inspects marks | `addopts = "-m 'not regression'"` in pyproject.toml | Pytest built-in; visible in config; zero code |
| Fixture parametrization | Hand-rolled test loop | `@pytest.mark.parametrize` with glob discovery | pytest manages IDs, failure isolation, re-run support |
| Deep dict diff | Custom recursive comparator | Custom `FieldDiffer` (thin wrapper over equality) with structured output | The complexity is in the reporting, not the comparison logic itself |
| JSON serialization of Decimal/date | Custom encoder | `model_dump(mode='json')` | Pydantic already converts Decimal→str, date→str in 'json' mode |

**Key insight:** The hardest part of this phase is the FieldDiffer reporting format, not the comparison logic itself. Python `==` handles dict equality; the value-add is the structured `Field | Expected | Actual | Status` output that tells the developer exactly what drifted.

---

## Common Pitfalls

### Pitfall 1: `addopts` quoting on Windows
**What goes wrong:** `addopts = -m not regression` (without quotes) fails on Windows because the shell doesn't interpret it the same way.
**Why it happens:** pytest passes addopts through shlex on some platforms.
**How to avoid:** Always write `addopts = "-m 'not regression'"` — the inner single quotes are part of the marker expression string.
**Warning signs:** `ERROR: not recognized as a pytest marker` or `KeyError` on collection.

### Pitfall 2: `_fixture_params()` called at import time
**What goes wrong:** If `tests/fixtures/golden/` doesn't exist yet, `glob("*.json")` raises or returns nothing, breaking collection.
**Why it happens:** `@pytest.mark.parametrize` evaluates the list at module import time.
**How to avoid:** Guard with `GOLDEN_DIR.mkdir(parents=True, exist_ok=True)` at module level, or return `[]` if dir doesn't exist — parametrize with empty list skips silently.
**Warning signs:** `ERRORS` during test collection, not during test run.

### Pitfall 3: Decimal serialization in fixture JSON
**What goes wrong:** `json.dumps` of a dict containing `Decimal` objects raises `TypeError`.
**Why it happens:** stdlib `json` doesn't serialize `Decimal`.
**How to avoid:** Use `policy.model_dump(mode='json')` (not `model_dump()`) — Pydantic's `mode='json'` converts Decimal to str and date to ISO string. Then `json.dumps` succeeds without a custom encoder.
**Warning signs:** `TypeError: Object of type Decimal is not JSON serializable` in create-fixture.

### Pitfall 4: `_source_pdf` key missing causes KeyError in test
**What goes wrong:** Fixture files created before the `_source_pdf` field was added can't be mapped to their real PDF.
**Why it happens:** Fixture format changed mid-development.
**How to avoid:** Use `.get("_source_pdf")` with a fallback derivation from the fixture filename stem, or fail clearly with a descriptive error message.

### Pitfall 5: `campos_adicionales` contains `_raw_response`
**What goes wrong:** `_raw_response` is stored in `campos_adicionales` by `extract_policy()` (see extraction `__init__.py` line 66-68). This is a large dict that changes per run.
**Why it happens:** Auditing key added in Phase 3.
**How to avoid:** Strip `_raw_response` from `campos_adicionales` before writing the fixture, and always skip it during comparison. PiiRedactor or a post-serialization step should remove this key explicitly.
**Warning signs:** Fixture JSON files are unexpectedly large; comparison always drifts on `_raw_response`.

### Pitfall 6: pdfs-to-test/ not in .gitignore
**What goes wrong:** Real PDFs with PII get committed to version control.
**Why it happens:** `.gitignore` currently does not contain `pdfs-to-test/` (verified by inspection).
**How to avoid:** Add `pdfs-to-test/` to `.gitignore` as part of Wave 1 — this is a STATE.md pending todo. Do it before any fixture creation work.

### Pitfall 7: session fixture scope conflict
**What goes wrong:** Regression tests use the `session` fixture from `conftest.py` (in-memory SQLite). Ingestion saves cache to the in-memory session, but the session is function-scoped — no cross-test contamination. This is correct behavior but needs to be understood.
**Why it happens:** Each test function gets its own engine + session.
**How to avoid:** Use the existing `session` fixture from conftest.py as-is. Do not attempt to share one session across parametrized cases.

---

## Code Examples

Verified patterns from existing codebase:

### Existing `pytest.mark.skipif` pattern (from test_ingestion.py)
```python
# Source: tests/test_ingestion.py line 15
requires_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="Tesseract OCR not installed",
)
```
The regression PDF-missing skip follows the same pattern but uses `pytest.skip()` inside the test body (runtime check after parametrize).

### extract_policy return signature (from extraction/__init__.py)
```python
# Source: policy_extractor/extraction/__init__.py
def extract_policy(
    ingestion_result: IngestionResult, model: str | None = None
) -> tuple[PolicyExtraction | None, anthropic.types.Usage | None, int]:
    ...
    return (verified_policy, usage, rl_retries)
```

### CLI lazy import + _setup_db pattern (from cli.py)
```python
# Source: policy_extractor/cli.py — established pattern for all subcommands
@app.command(name="create-fixture")
def create_fixture(...) -> None:
    from policy_extractor.regression.pii_redactor import PiiRedactor  # lazy import
    _setup_db()
    session = SessionLocal()
    try:
        ...
    finally:
        session.close()
```

### campos_adicionales _raw_response stripping
```python
# policy_extractor/regression/pii_redactor.py — must strip this key
SKIP_CAMPOS_KEYS = frozenset({"_raw_response"})

def redact(self, data: dict) -> dict:
    result = copy.deepcopy(data)
    # Strip _raw_response before saving fixture
    if "campos_adicionales" in result and isinstance(result["campos_adicionales"], dict):
        for key in SKIP_CAMPOS_KEYS:
            result["campos_adicionales"].pop(key, None)
    self._redact_recursive(result)
    return result
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pytest.ini` / `setup.cfg` for config | `pyproject.toml [tool.pytest.ini_options]` | pytest 6+ | Already used in this project; add `markers` and `addopts` here |
| `pytest.mark` without registration | Registered markers with descriptions | pytest 5+ | Unregistered marks emit warnings on `pytest --strict-markers` |
| Tolerance-based numeric comparison in regression | Exact match (LLM extraction is deterministic per PDF text) | Project decision | Simpler; if model changes, all fixtures must be regenerated anyway |

---

## Open Questions

1. **Insurer slug derivation**
   - What we know: Fixture naming is `golden_{insurer}_{type}.json`; insurer and type come from CLI flags `--insurer` / `--type`
   - What's unclear: Whether to auto-derive from the `aseguradora` field in the extraction result vs. require explicit CLI flags
   - Recommendation: Require explicit `--insurer` and `--type` flags; auto-derivation from free-text `aseguradora` field is fragile (e.g., "GNP Seguros, S.A. de C.V." vs "gnp")

2. **campos_adicionales key set per insurer**
   - What we know: Fixture captures the exact expected key set for that insurer/policy type
   - What's unclear: Whether the test should fail on MISSING fixture keys only, or also on EXTRA keys (policy changed to produce more data)
   - Recommendation: Extra keys = PASS (improvement), missing keys = FAIL; this matches CONTEXT.md locked decision

3. **confianza field**
   - What we know: `PolicyExtraction.confianza` is a `dict` populated by the extraction layer
   - What's unclear: Whether confidence values are deterministic enough to compare
   - Recommendation: Skip `confianza` entirely in comparison — it's a quality signal, not a regression signal

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already in dev deps) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_regression.py -m regression -x` |
| Full suite command | `pytest -m regression -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REG-01 | Fixture files exist in `tests/fixtures/golden/` with correct format | integration | `pytest tests/test_regression.py::test_fixture_format_valid -x` | Wave 0 |
| REG-02 | Field-by-field comparison skips REDACTED, partial-matches campos_adicionales | unit | `pytest tests/test_regression.py::test_field_differ_* -x` | Wave 0 |
| REG-03 | `pytest` (no marker) does NOT run regression tests; `pytest -m regression` DOES | integration | `pytest --collect-only -q` (verify no regression tests in list) | Wave 0 |
| REG-04 | On drift, output shows `Field \| Expected \| Actual \| Status` table | unit | `pytest tests/test_regression.py::test_field_differ_reports_drift -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_regression.py -m "not regression" -x` (unit tests for helpers)
- **Per wave merge:** `pytest -m regression -v` (full golden suite — requires real PDFs present)
- **Phase gate:** Full unit suite green + `pytest -m regression` green (or all-skipped if no PDFs) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_regression.py` — covers REG-01 through REG-04 (main test file, does not exist yet)
- [ ] `tests/fixtures/golden/` — directory must exist (empty dir, no fixture JSONs yet)
- [ ] `policy_extractor/regression/__init__.py` — package init
- [ ] `policy_extractor/regression/pii_redactor.py` — PiiRedactor class (REG-01, REG-02)
- [ ] `policy_extractor/regression/field_differ.py` — FieldDiffer + DriftReport (REG-02, REG-04)
- [ ] pyproject.toml — add `markers` and `addopts` entries (REG-03)
- [ ] `.gitignore` — add `pdfs-to-test/` entry (REG-01 safety gate)

---

## Sources

### Primary (HIGH confidence)
- Codebase direct inspection — `policy_extractor/extraction/__init__.py`, `policy_extractor/schemas/poliza.py`, `tests/conftest.py`, `tests/test_ingestion.py`, `policy_extractor/cli.py`, `pyproject.toml`
- `tests/create_fixtures.py` — existing fixture creation pattern
- `.planning/phases/11-regression-suite/11-CONTEXT.md` — locked decisions from user discussion
- `.planning/STATE.md` — pending todos (pdfs-to-test/ gitignore)

### Secondary (MEDIUM confidence)
- pytest official docs: `addopts` with marker expression, custom marker registration in pyproject.toml — standard pytest 7/8 patterns, stable API
- Pydantic v2 docs: `model_dump(mode='json')` behavior for Decimal and date serialization — confirmed via codebase usage patterns

### Tertiary (LOW confidence)
- None — all findings are grounded in direct codebase inspection or well-established pytest/Pydantic APIs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; no new deps
- Architecture: HIGH — patterns derived directly from existing codebase conventions
- Pitfalls: HIGH — most identified from direct code inspection (campos_adicionales/_raw_response, gitignore gap, Decimal serialization)

**Research date:** 2026-03-19
**Valid until:** 2026-06-19 (stable stack; pytest marker API is 6+ years stable)
