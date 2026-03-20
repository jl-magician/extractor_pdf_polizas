# Phase 13: Extraction Pipeline Fixes - Research

**Researched:** 2026-03-20
**Domain:** Python PDF extraction pipeline — prompt engineering, post-extraction validation, OCR fallback, field exclusion
**Confidence:** HIGH (all findings drawn from existing codebase + established patterns in project)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Prompt improvement strategy**
- D-01: Add explicit field-mapping rules to the prompt (not few-shot examples) to prevent known value swaps — financiamiento/otros_servicios, folio/clave, subsecuentes/primer_pago
- D-02: Per-insurer prompt overlay system — base prompt with insurer-specific rules appended. Auto-detect insurer from PDF text in a lightweight first pass, then route to the appropriate overlay
- D-03: Start with base prompt + 1 Zurich overlay as proof of concept. Framework supports adding more overlays later
- D-04: Target all prompt-fixable errors from v2-extraction-errors.md: value swaps (#3-4, #6-7), wrong source (#1, #5), hallucination (#2), and irrelevant fields (#8)
- D-05: Add page-level hints — tag pages containing financial breakdown tables with `[FINANCIAL BREAKDOWN TABLE BELOW]` before the page text
- D-06: Bump prompt version to v2.0.0 (major) — clear break from v1.x prompts, aligns with milestone version

**Post-extraction validation**
- D-07: New `validation_warnings` JSON column on polizas table via Alembic migration — stores list of `{field, message, severity}` objects
- D-08: Validation is annotate-only — always save the extraction, never block. Better to have data with warnings than no data
- D-09: Financial cross-check: primer_pago + subsecuentes must be within 1% of prima_total. Strict tolerance — flags even small rounding differences
- D-10: Build an extensible validator registry so new checks can be added easily. Start with financial invariants + date logic (inicio_vigencia < fin_vigencia, fecha_emision <= inicio_vigencia)

**Field exclusion list**
- D-11: Per-insurer configuration file (YAML/JSON) mapping insurer name to excluded field names
- D-12: Exclusion applies to ALL campos_adicionales — poliza, asegurado, and cobertura level
- D-13: Start with empty default list — user configures what to exclude. No risk of dropping useful fields
- D-14: Excluded fields are silently dropped before save — no logging, no warnings

**Auto-OCR fallback**
- D-15: Per-page reclassification: any "digital" page with fewer than configurable threshold characters is reclassified as "scanned" and OCR is applied
- D-16: Whole-PDF retry: if extraction returns all-null core fields after per-page reclassification, re-run the entire PDF through OCR pipeline regardless of classification
- D-17: Fix the ocrmypdf call bug (error #10) — likely needs path quoting for filenames with spaces. Add try/except around OCR calls so a single PDF failure doesn't crash the batch
- D-18: Update page classification from "digital" to "scanned (auto-reclassified)" in the ingestion result — preserves audit trail
- D-19: Character threshold configurable via `OCR_MIN_CHARS_THRESHOLD` in config.py Settings

### Claude's Discretion
- Exact implementation of insurer auto-detection (regex on aseguradora names vs text pattern matching)
- Validator registry pattern (class-based, decorator-based, or simple function list)
- YAML vs JSON for per-insurer config file format
- Exact wording of financial validation warning messages
- How to detect financial table pages for tagging

### Deferred Ideas (OUT OF SCOPE)
- Per-insurer prompt overlays for AXA, MAPFRE, and remaining 7 insurers — expand after Zurich overlay proves the pattern (Phase 17 or backlog)
- Confidence-based field flagging from Claude self-reported confidence — needs empirical validation against correction log (Phase 15+)
- Prompt improvement for coberturas extraction accuracy — not in documented errors, revisit if issues emerge
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXT-01 | System improves extraction prompts to prevent financial value swaps in breakdown tables | D-01 through D-06: v2.0.0 prompt with explicit field-mapping rules + Zurich overlay + financial page tagging. Reference fixture: 112234653_Poliza.pdf errors #3-4, #6-7 |
| EXT-02 | System validates extracted financial fields cross-referentially (primer_pago + subsecuentes ~ prima_total) and flags mismatches as warnings | D-07 through D-10: new validation_warnings JSON column via Alembic migration 003, validator registry, financial invariant check at 1% tolerance |
| EXT-03 | System auto-reclassifies "digital" PDF pages with <10 extractable characters as scanned and applies OCR | D-15 through D-19: per-page char count gate in ingest_pdf(), OCR_MIN_CHARS_THRESHOLD in settings, whole-PDF retry on all-null result, ocrmypdf call bug fix |
| EXT-04 | User can configure a field exclusion list to prevent extraction of irrelevant campos_adicionales | D-11 through D-14: per-insurer YAML config file, exclusion applied at all three campos_adicionales levels in upsert_policy() |
</phase_requirements>

---

## Summary

Phase 13 fixes four systematic extraction errors documented during real-world testing of v1.0 against actual insurance PDFs. All four fixes are surgical — each touches a narrow, well-defined layer of the existing pipeline with no cross-cutting concerns. The codebase already has all the infrastructure needed: Alembic migration chain (001 → 002), a settings class in config.py, clear integration points in ingest_pdf() and extract_policy() and upsert_policy(), and 263 passing tests with established patterns for mocking the Anthropic API.

The four deliverables in dependency order: (1) Alembic migration 003 adds `validation_warnings` JSON column; (2) prompt v2.0.0 with Zurich overlay and financial page tagging; (3) auto-OCR fallback with per-page char count gate and whole-PDF retry; (4) per-insurer field exclusion config file with exclusion applied in the writer. The validation module is the only entirely new module — everything else extends existing files.

**Primary recommendation:** Implement in four isolated tasks that can be planned and verified independently. The Alembic migration must land first (task 0) since other tasks reference the new column. All other tasks are independent of each other.

---

## Standard Stack

### Core (all already in pyproject.toml)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.86.0 | Claude API calls for extraction | Already used; prompt is passed in `system=` parameter |
| pydantic | >=2.12.5 | Schema validation, Settings | Already used throughout |
| sqlalchemy | >=2.0.48 | ORM, session management | Already used; Poliza model extended |
| alembic | >=1.13.0 | SQLite schema migrations | Already used; migration 003 follows 002 pattern exactly |
| pymupdf (fitz) | >=1.27.2 | PDF text extraction, page.get_text() | Already used in ingest_pdf() |
| ocrmypdf | >=17.3.0 | OCR for scanned pages | Already used in ocr_runner.py |
| loguru | >=0.7 | Structured logging | Already used throughout |
| PyYAML | stdlib `yaml` module or PyYAML | Per-insurer config file parsing | Python stdlib `tomllib` or PyYAML — decide in implementation |

### New Addition: YAML Config
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyYAML | >=6.0 | Parse per-insurer exclusion config | If YAML format chosen over JSON — JSON is stdlib, YAML needs a dep |

**Decision guidance (Claude's Discretion):** Use JSON (stdlib `json`) for the per-insurer config file. Avoids a new dependency. The config is machine-generated-friendly and the structure is simple (flat dict of string arrays). YAML is more human-readable but not worth the added dependency for this use case.

**Installation:** No new packages needed if JSON chosen. If YAML: `pip install pyyaml`.

**Version verification:** All packages already installed and passing 263 tests — versions are current.

---

## Architecture Patterns

### Recommended File Layout for New Code

```
policy_extractor/
├── extraction/
│   ├── prompt.py              # SYSTEM_PROMPT_V2, PROMPT_VERSION_V2 = "v2.0.0"
│   │                          # add: ZURICH_OVERLAY, detect_insurer(), assemble_text_v2()
│   ├── validation.py          # NEW — validator registry + financial + date checks
│   ├── client.py              # update: use SYSTEM_PROMPT_V2
│   └── __init__.py            # update: call validate_extraction() after verify_no_hallucination
├── ingestion/
│   ├── __init__.py            # update: per-page char count gate, whole-PDF retry
│   └── classifier.py          # update: "scanned (auto-reclassified)" classification label
├── storage/
│   ├── writer.py              # update: apply field exclusion before saving campos_adicionales
│   └── models.py              # update: add validation_warnings column
├── config.py                  # update: add OCR_MIN_CHARS_THRESHOLD = 10
└── insurer_config.json        # NEW — per-insurer exclusion lists (empty default)
alembic/versions/
└── 003_validation_warnings.py # NEW — adds validation_warnings column
```

### Pattern 1: Alembic Migration 003 (following established 002 pattern)

**What:** Add `validation_warnings` JSON column to polizas table.
**When to use:** Always when adding a nullable column to polizas.

```python
# alembic/versions/003_validation_warnings.py
# Source: existing 002_evaluation_columns.py pattern
revision: str = "003"
down_revision: Union[str, None] = "002"

def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("polizas")}

    with op.batch_alter_table("polizas") as batch_op:
        if "validation_warnings" not in existing_cols:
            batch_op.add_column(sa.Column("validation_warnings", sa.JSON(), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table("polizas") as batch_op:
        batch_op.drop_column("validation_warnings")
```

**Critical:** Inspector guard (`if "validation_warnings" not in existing_cols`) is mandatory — prevents duplicate column error on fresh DBs where create_all already created it. This is an established project pattern from migration 002.

### Pattern 2: Validator Registry (simple function list — recommended)

**What:** Extensible list of validator functions, each receiving a PolicyExtraction and returning a list of warning dicts.
**When to use:** Prefer simplicity over abstraction — the registry starts with 2-3 validators.

```python
# policy_extractor/extraction/validation.py
from __future__ import annotations
from decimal import Decimal
from typing import Callable
from policy_extractor.schemas.poliza import PolicyExtraction

# Type alias: validator takes a PolicyExtraction, returns list of warning dicts
ValidatorFn = Callable[[PolicyExtraction], list[dict]]

# Registry — append new validators here
_VALIDATORS: list[ValidatorFn] = []

def register(fn: ValidatorFn) -> ValidatorFn:
    """Decorator: register a validator function."""
    _VALIDATORS.append(fn)
    return fn

def validate_extraction(policy: PolicyExtraction) -> list[dict]:
    """Run all registered validators, return combined warnings list."""
    warnings = []
    for fn in _VALIDATORS:
        warnings.extend(fn(policy))
    return warnings

@register
def check_financial_invariant(policy: PolicyExtraction) -> list[dict]:
    """primer_pago + subsecuentes must be within 1% of prima_total."""
    # Implementation: see Code Examples section
    ...

@register
def check_date_logic(policy: PolicyExtraction) -> list[dict]:
    """inicio_vigencia < fin_vigencia and fecha_emision <= inicio_vigencia."""
    ...
```

**Why function list over class-based:** Two validators don't need class hierarchy. The `@register` decorator is self-documenting and adding a new validator is one line. Class-based registry would be over-engineering.

### Pattern 3: Per-Insurer Prompt Overlay System

**What:** Base prompt (v2.0.0) + insurer-specific addendum appended at call time.
**When to use:** Insurer is detected in assembled text before API call.

```python
# policy_extractor/extraction/prompt.py additions
PROMPT_VERSION_V2 = "v2.0.0"

SYSTEM_PROMPT_V2 = """...(updated base prompt with field-mapping rules)..."""

ZURICH_OVERLAY = """
## Zurich-Specific Extraction Rules

The following field pairs are commonly confused in Zurich auto policy breakdown tables.
Map them precisely by column position, not by proximity to adjacent values:

- `financiamiento`: The financing charge row. Value is 0.0 when no financing plan is active.
- `otros_servicios_contratados`: Additional contracted services charge. NOT the same as financiamiento.
- `folio`: The folio identifier (typically null for standard auto policies). Do NOT populate with clave values.
- `clave`: The clave identifier (typically a 5-digit numeric code like "75534"). NOT the same as folio.
- `subsecuentes`: Subsequent payment amount. Returns 0.0 when payment is annual (single payment).
  Do NOT copy primer_pago value into subsecuentes.
"""

# Insurer name patterns for detection
_INSURER_OVERLAYS: dict[str, str] = {
    "zurich": ZURICH_OVERLAY,
}

def detect_insurer(assembled_text: str) -> str | None:
    """Lightweight first-pass insurer detection from assembled PDF text."""
    text_lower = assembled_text.lower()
    for insurer_key in _INSURER_OVERLAYS:
        if insurer_key in text_lower:
            return insurer_key
    return None

def get_system_prompt(assembled_text: str) -> str:
    """Return base prompt + insurer overlay if detected."""
    insurer = detect_insurer(assembled_text)
    if insurer and insurer in _INSURER_OVERLAYS:
        return SYSTEM_PROMPT_V2 + "\n\n" + _INSURER_OVERLAYS[insurer]
    return SYSTEM_PROMPT_V2
```

**Integration point:** `call_extraction_api()` in client.py currently hardcodes `system=SYSTEM_PROMPT_V1`. Change to `system=get_system_prompt(assembled_text)` and pass `assembled_text` as a parameter.

### Pattern 4: Auto-OCR Fallback in ingest_pdf()

**What:** Per-page char count gate after `get_text()` for digital pages; whole-PDF retry on all-null result.
**When to use:** Any digital page where `len(text.strip()) < settings.OCR_MIN_CHARS_THRESHOLD`.

```python
# In ingest_pdf(), modified digital-only branch (lines 113-119 of ingestion/__init__.py)
# BEFORE: all digital — extract text directly
# AFTER: check char count, reclassify if below threshold

OCR_MIN_CHARS = settings.OCR_MIN_CHARS_THRESHOLD  # default 10

pages_needing_ocr = []
for page_num, classification in classifications:
    text = doc[page_num - 1].get_text()
    if classification == "digital" and len(text.strip()) < OCR_MIN_CHARS:
        # Auto-reclassify: too few chars for a digital page
        classification = "scanned (auto-reclassified)"
        pages_needing_ocr.append(page_num)
        logger.info(
            f"Auto-reclassify page {page_num}: {len(text.strip())} chars < threshold {OCR_MIN_CHARS}"
        )
    pages.append(PageResult(page_num=page_num, text=text, classification=classification))

if pages_needing_ocr:
    # Trigger OCR on full PDF, override text for reclassified pages
    ocr_output_path, ocr_language = ocr_with_fallback(pdf_path)
    ocr_texts = extract_text_by_page(ocr_output_path)
    ocr_text_map = {pn: txt for pn, txt in ocr_texts}
    for page in pages:
        if page.page_num in pages_needing_ocr:
            page = page.model_copy(update={"text": ocr_text_map.get(page.page_num, "")})
    # clean up temp file...
```

**Whole-PDF retry gate** — run in `extract_policy()` after initial extraction:

```python
# In extract_policy() after verify_no_hallucination():
_CORE_FIELDS = ["numero_poliza", "aseguradora", "prima_total", "inicio_vigencia", "fin_vigencia"]
all_null = all(getattr(policy, f) is None for f in _CORE_FIELDS[2:])
if all_null:
    logger.warning("All core fields null — retrying full PDF through OCR pipeline")
    ingestion_result = ingest_pdf(ingestion_result.file_path, force_reprocess=True, force_ocr=True)
    # re-run extraction on OCR result
```

**Note:** The PageResult model uses `Literal["digital", "scanned"]` — adding "scanned (auto-reclassified)" requires updating the Literal type or using a plain str field. Check the ingestion schema and downstream consumers before changing.

### Pattern 5: Field Exclusion in upsert_policy()

**What:** Load per-insurer exclusion list at save time, strip excluded keys from all three campos_adicionales dicts.
**When to use:** Every upsert_policy() call — the config is loaded once and cached.

```python
# policy_extractor/storage/writer.py additions

import json
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def _load_exclusion_config() -> dict[str, list[str]]:
    """Load insurer_config.json — returns dict of insurer -> [excluded_fields]."""
    config_path = Path(__file__).parent.parent / "insurer_config.json"
    if not config_path.exists():
        return {}
    with config_path.open() as f:
        return json.load(f)

def _apply_exclusions(campos: dict, insurer: str) -> dict:
    """Drop excluded field names from campos dict. Silent drop (D-14)."""
    config = _load_exclusion_config()
    excluded = set(config.get(insurer.lower(), []) + config.get("*", []))
    if not excluded:
        return campos
    return {k: v for k, v in campos.items() if k not in excluded}
```

**Integration:** Call `_apply_exclusions()` in `upsert_policy()` before building the `merged` dict and before setting `campos_adicionales` on each Asegurado and Cobertura row.

### Pattern 6: Financial Invariant Check (Decimal arithmetic)

**What:** Cross-check primer_pago + subsecuentes against prima_total with 1% tolerance.
**Note:** These fields currently live in `campos_adicionales` (not top-level Poliza schema columns). The validator must look them up there.

```python
@register
def check_financial_invariant(policy: PolicyExtraction) -> list[dict]:
    """primer_pago + subsecuentes within 1% of prima_total (D-09)."""
    warnings = []
    prima_total = policy.prima_total
    campos = policy.campos_adicionales

    primer_pago = campos.get("primer_pago")
    subsecuentes = campos.get("subsecuentes")

    if prima_total is None or primer_pago is None or subsecuentes is None:
        return []  # Cannot validate — missing data, not an error

    try:
        total = Decimal(str(prima_total))
        pago = Decimal(str(primer_pago)) + Decimal(str(subsecuentes))
        if total == 0:
            return []
        diff_pct = abs(total - pago) / total
        if diff_pct > Decimal("0.01"):  # 1% tolerance (D-09)
            warnings.append({
                "field": "prima_total",
                "message": (
                    f"Financial invariant violated: primer_pago ({primer_pago}) + "
                    f"subsecuentes ({subsecuentes}) = {pago}, "
                    f"but prima_total = {total} "
                    f"(difference: {float(diff_pct)*100:.2f}%)"
                ),
                "severity": "warning",
            })
    except (TypeError, ValueError):
        pass  # Non-numeric values — skip silently

    return warnings
```

**Use Decimal arithmetic throughout** — financial values are stored as Decimal in the schema. Mixing float and Decimal causes silent precision errors. The project already uses `Decimal` everywhere (see `_json_serializer` in writer.py and `Numeric(precision=15, scale=2)` columns in models.py).

### Anti-Patterns to Avoid

- **Blocking on validation failure:** D-08 is explicit — always save. Never raise an exception from the validator that prevents upsert.
- **Logging exclusion drops:** D-14 is explicit — silently drop, no log. A log call here would spam output for every batch.
- **OCR without the gate:** Running OCR unconditionally on digital pages multiplies batch time 10x (Pitfall v2-6 from PITFALLS.md). The per-page char count check must gate the OCR trigger.
- **Changing PageResult.classification Literal carelessly:** `PageResult` schema uses `Literal["digital", "scanned"]`. Adding "scanned (auto-reclassified)" requires either relaxing the type (use `str`) or extending the Literal. Downstream code that pattern-matches on classification must handle the new value.
- **Hardcoding PROMPT_VERSION_V2 in parse_and_validate():** The version is injected from `PROMPT_VERSION_V1` in client.py line 77. Update the constant name to `PROMPT_VERSION_V2` and update client.py import.
- **lru_cache on mutable config:** `_load_exclusion_config()` is cached with `lru_cache(maxsize=1)`. This is correct for production but makes tests that want to swap configs awkward — tests should patch `_load_exclusion_config` directly or clear the cache between runs.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Decimal tolerance comparison | Custom float subtraction | `abs(a - b) / b > threshold` with Decimal | Float subtraction has precision errors; Decimal is already in schema |
| Config file caching | Manual cache dict | `functools.lru_cache(maxsize=1)` | Built-in, thread-safe for single-process use, trivially invalidated in tests |
| DB column addition | Raw SQL ALTER TABLE | Alembic batch_alter_table + inspector guard | SQLite requires copy-and-rename for ALTER TABLE; batch_alter_table handles this; guard prevents duplicate column error |
| OCR call with spaces in path | String concatenation | `str(Path)` — already done in run_ocr() | Existing code already uses `str(input_path)` — the bug is likely an API call signature mismatch, not path quoting |

**Key insight:** The ocrmypdf bug (#10) — "ocr() missing 1 required positional argument: 'input_file_or_options'" — is an API signature error, not a path quoting problem. Looking at `run_ocr()` in ocr_runner.py, the call uses keyword arguments (`input_file=str(input_path), output_file=...`) which is the correct API. The bug occurred for `Poliza - 001_LGS-RCGRA_07013104_01_0.pdf` specifically — this file may have triggered a code path that called `ocrmypdf.ocr()` differently. Reproduce the bug first by running ingest on that file before attempting to fix it.

---

## Common Pitfalls

### Pitfall 1: PageResult.classification Literal Breaks with New Value

**What goes wrong:** Adding "scanned (auto-reclassified)" to a page's classification violates the `Literal["digital", "scanned"]` constraint in `PageResult`, causing a Pydantic ValidationError at `IngestionResult` construction time.

**Why it happens:** The schema is strict by design. Adding a new classification value mid-pipeline silently corrupts if not updated everywhere.

**How to avoid:** Update `PageResult.classification` to `Literal["digital", "scanned", "scanned (auto-reclassified)"]` or change to `str` (simpler, less strict). Update the ingestion cache deserialization if needed. Check `ingestion/cache.py` for how PageResult is reconstructed from the cache.

**Warning signs:** `ValidationError: Input should be 'digital' or 'scanned'` raised inside `ingest_pdf()`.

### Pitfall 2: validation_warnings Not Persisted Without Writer Update

**What goes wrong:** Migration 003 adds the column. The validator runs and returns warnings. But `upsert_policy()` in writer.py is never updated to write them to the column. Warnings are computed and silently discarded.

**Why it happens:** Three separate files need to change for validation_warnings to reach the DB: models.py (ORM column), writer.py (write the value), and extraction/__init__.py (call the validator). Missing any one link breaks the chain silently — no error, just null in the column.

**How to avoid:** Trace the data flow in extract_policy() → upsert_policy() explicitly in the plan. The validator runs in extract_policy(), returns a list, which must be stored in a field on PolicyExtraction (or passed separately), which upsert_policy() writes to poliza.validation_warnings.

**Warning signs:** `poliza.validation_warnings` is always null after extraction even when financial invariant is violated.

### Pitfall 3: Financial Fields in campos_adicionales vs Top-Level Schema

**What goes wrong:** The validator assumes `primer_pago` and `subsecuentes` are top-level fields on `PolicyExtraction`. They are not — they are in `campos_adicionales` (the overflow dict). The financial validator returns no warnings because `policy.primer_pago` doesn't exist.

**Why it happens:** The `PolicyExtraction` schema has `prima_total` as a top-level field but the payment breakdown fields (`primer_pago`, `subsecuentes`, `financiamiento`) are extracted into `campos_adicionales` by Claude.

**How to avoid:** The validator must look up `policy.campos_adicionales.get("primer_pago")` not `policy.primer_pago`. Validate this assumption against a real extraction result (or the fixture in `tests/test_extraction.py`) before writing the validator.

**Warning signs:** Validator always returns empty warnings list even with known-bad values.

### Pitfall 4: lru_cache Sticks Between Tests for Exclusion Config

**What goes wrong:** Test A patches `insurer_config.json` to have exclusions. Test B runs with an empty config. But `_load_exclusion_config()` was cached by Test A and returns its results for Test B.

**Why it happens:** `lru_cache(maxsize=1)` is module-level and persists across test function calls in the same pytest session.

**How to avoid:** Either (a) patch `_load_exclusion_config` directly with `unittest.mock.patch` in tests that need specific config, or (b) add `_load_exclusion_config.cache_clear()` in test teardown. Option (a) is simpler and follows the existing pattern in `test_extraction.py`.

**Warning signs:** Test ordering matters — a test passes in isolation but fails when run after another test.

### Pitfall 5: Whole-PDF OCR Retry Triggers Infinite Loop

**What goes wrong:** The whole-PDF retry runs, produces an extraction with all-null fields again (e.g., OCR also fails), triggers another retry, and loops. Or: the retry logic calls `ingest_pdf()` with `force_reprocess=True` which bypasses cache but still classifies the same pages as "digital" — causing identical results.

**Why it happens:** The retry is implemented without a "retry flag" that forces OCR regardless of classification. The per-page gate checks char count — but after OCR, page.text may still be < 10 chars if OCR quality is poor.

**How to avoid:** The whole-PDF retry must use a `force_ocr=True` parameter that bypasses both the cache AND the per-page char count gate — it runs `ocr_with_fallback()` unconditionally. One retry only — no loop. If the OCR retry also fails, log and return the null result. Protect with `if not already_retried` flag.

**Warning signs:** Logs show "Retrying full PDF through OCR pipeline" repeating more than once for the same file.

### Pitfall 6: ocrmypdf Bug Root Cause May Not Be Path Quoting

**What goes wrong:** CONTEXT.md (D-17) suggests the bug is "likely needs path quoting for filenames with spaces." But `run_ocr()` already uses `str(input_path)` with keyword arguments — the actual `ocrmypdf.ocr()` call in ocr_runner.py looks correct. The bug may be in a different code path (e.g., a call to `ocr()` with positional args somewhere else, or an ocrmypdf version API change).

**Why it happens:** The error message "ocr() missing 1 required positional argument: 'input_file_or_options'" indicates `ocrmypdf.ocr()` was called with 0 positional args, not with a path as first arg.

**How to avoid:** Before fixing, reproduce the bug: run `python -m policy_extractor.cli extract "Poliza - 001_LGS-RCGRA_07013104_01_0.pdf"` and capture the full traceback — not just the error message. The traceback will show which line triggered the `ocr()` call. The fix may be in ocr_runner.py, or it may be a missing `try/except` around the call that surfaces an underlying error differently.

**Warning signs:** Fix appears to work in testing (on simple filenames) but the specific file `Poliza - 001_LGS-RCGRA_07013104_01_0.pdf` still fails.

---

## Code Examples

### Migration 003: validation_warnings column

```python
# alembic/versions/003_validation_warnings.py
# Source: established project pattern from 002_evaluation_columns.py
revision: str = "003"
down_revision: Union[str, None] = "002"

def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("polizas")}
    with op.batch_alter_table("polizas") as batch_op:
        if "validation_warnings" not in existing_cols:
            batch_op.add_column(sa.Column("validation_warnings", sa.JSON(), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table("polizas") as batch_op:
        batch_op.drop_column("validation_warnings")
```

### ORM model update (models.py)

```python
# Add to Poliza class after evaluation columns:
validation_warnings: Mapped[Optional[list]] = mapped_column(sa.JSON, nullable=True)
```

### PolicyExtraction schema update (poliza.py)

```python
# Add to PolicyExtraction:
validation_warnings: list[dict] = Field(default_factory=list)
```

### validate_extraction() integration in extract_policy()

```python
# In policy_extractor/extraction/__init__.py, after verify_no_hallucination:
from policy_extractor.extraction.validation import validate_extraction

warnings = validate_extraction(verified_policy)
verified_policy = verified_policy.model_copy(update={"validation_warnings": warnings})
```

### upsert_policy() writer update

```python
# In upsert_policy(), after all existing column assignments:
poliza.validation_warnings = extraction.validation_warnings or None
```

### insurer_config.json (empty default — D-13)

```json
{
  "_comment": "Per-insurer field exclusion list. Keys are lowercase insurer names or '*' for all.",
  "_example": {"zurich": ["agencia_responsable"]},
  "default": []
}
```

### assemble_text_v2() with financial page tagging (D-05)

```python
def assemble_text_v2(ingestion: IngestionResult) -> str:
    """Assemble pages with financial breakdown table hints."""
    FINANCIAL_KEYWORDS = [
        "prima", "pago", "financiamiento", "desglose", "breakdown",
        "importe", "subtotal", "recargo", "derecho de poliza"
    ]
    parts = []
    for page in ingestion.pages:
        text_lower = page.text.lower()
        has_financial = any(kw in text_lower for kw in FINANCIAL_KEYWORDS)
        parts.append(f"--- Page {page.page_num} ---")
        if has_financial:
            parts.append("[FINANCIAL BREAKDOWN TABLE BELOW]")
        parts.append(page.text)
    return "\n\n".join(parts)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| v1.0.0 single monolithic prompt | v2.0.0 base + per-insurer overlays | Phase 13 | Zurich-specific errors fixed without polluting base prompt |
| No post-extraction validation | validator registry with financial + date checks | Phase 13 | validation_warnings column surfaces mismatches |
| All-or-nothing OCR (only if page classified scanned) | Per-page char count gate + whole-PDF retry | Phase 13 | Zero-text digital PDFs correctly OCR'd |
| No field exclusion | Per-insurer config JSON | Phase 13 | User controls what goes into campos_adicionales |

**Deprecated by this phase:**
- `SYSTEM_PROMPT_V1` and `PROMPT_VERSION_V1` — replaced by V2. Keep V1 constants for historical reference but mark as deprecated. The `parse_and_validate()` function injects `prompt_version` — update the import from `PROMPT_VERSION_V1` to `PROMPT_VERSION_V2`.
- `assemble_text()` — superseded by `assemble_text_v2()`. Keep old function if needed for tests but route production calls through v2.

---

## Open Questions

1. **Where exactly is the ocrmypdf bug?**
   - What we know: Error is "ocr() missing 1 required positional argument: 'input_file_or_options'" on `Poliza - 001_LGS-RCGRA_07013104_01_0.pdf`
   - What's unclear: The existing `run_ocr()` call looks syntactically correct with keyword args. The bug must be in a different code path. Traceback is needed.
   - Recommendation: Reproduce first (run the CLI on that specific file), capture full traceback, then fix.

2. **Does PageResult.classification need to become a str or extend the Literal?**
   - What we know: Current schema is `Literal["digital", "scanned"]`. Auto-reclassified pages need a new value.
   - What's unclear: Whether "scanned (auto-reclassified)" propagates to the ingestion cache and causes deserialization issues.
   - Recommendation: Change to `Literal["digital", "scanned", "scanned (auto-reclassified)"]` — explicit, discoverable, forward-compatible. Check `ingestion/cache.py` for the cache serialization.

3. **Should validation_warnings be stored as a separate column or inside campos_adicionales?**
   - What we know: D-07 locks this as a new JSON column on polizas.
   - What's unclear: Nothing — D-07 is a locked decision. Separate column.
   - Recommendation: Implement as separate column per D-07. This allows SQL queries like `WHERE json_array_length(validation_warnings) > 0` when the UI needs to filter flagged policies.

4. **Does the whole-PDF OCR retry need a new ingest_pdf() parameter?**
   - What we know: `ingest_pdf()` already has `force_reprocess=True` to bypass cache. The retry needs to force OCR regardless of page classification.
   - What's unclear: Whether `force_reprocess=True` alone is sufficient, or if a new `force_ocr=True` parameter is needed.
   - Recommendation: Add `force_ocr: bool = False` parameter to `ingest_pdf()`. When True, skip the per-page char count gate and go directly to `ocr_with_fallback()`.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (no config file — options in pyproject.toml `[tool.pytest.ini_options]`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `addopts = "-m 'not regression'"` |
| Quick run command | `python -m pytest tests/ -q --no-header` |
| Full suite command | `python -m pytest tests/ -v` |
| Regression excluded | `addopts = "-m 'not regression'"` — regression tests need real PDFs |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXT-01 | SYSTEM_PROMPT_V2 contains field-mapping rules; assemble_text_v2() adds [FINANCIAL BREAKDOWN TABLE BELOW] for financial pages; detect_insurer() returns "zurich" for Zurich text; Zurich overlay is appended to system prompt | unit | `python -m pytest tests/test_prompt.py -x -q` | ❌ Wave 0 |
| EXT-01 | client.py uses SYSTEM_PROMPT_V2 via get_system_prompt(); PROMPT_VERSION_V2 injected in parse_and_validate() | unit | `python -m pytest tests/test_extraction.py -x -q` | ✅ (extend existing) |
| EXT-02 | validate_extraction() returns warning when primer_pago + subsecuentes > 1% off prima_total; returns empty list when within tolerance; returns empty list when any value is None | unit | `python -m pytest tests/test_validation.py -x -q` | ❌ Wave 0 |
| EXT-02 | Date logic: warning when fin_vigencia <= inicio_vigencia | unit | `python -m pytest tests/test_validation.py -x -q` | ❌ Wave 0 |
| EXT-02 | Migration 003 adds validation_warnings column; downgrade removes it; data preserved | unit | `python -m pytest tests/test_migrations.py -x -q` | ✅ (extend existing) |
| EXT-02 | upsert_policy() writes validation_warnings list to DB column | unit | `python -m pytest tests/test_storage_writer.py -x -q` | ✅ (extend existing) |
| EXT-03 | ingest_pdf() auto-reclassifies page with 3-char text when classified digital; does not reclassify page with 500 chars; classification is "scanned (auto-reclassified)"; OCR_MIN_CHARS_THRESHOLD=10 default in settings | unit | `python -m pytest tests/test_ingestion.py -x -q` | ✅ (extend existing) |
| EXT-03 | OCR trigger logged with char count | unit | `python -m pytest tests/test_ingestion.py -x -q` | ✅ (extend existing) |
| EXT-04 | _apply_exclusions() drops configured fields from campos dict; does not drop unconfigured fields; applies "*" global exclusions | unit | `python -m pytest tests/test_storage_writer.py -x -q` | ✅ (extend existing) |
| EXT-04 | insurer_config.json empty default loads without error | unit | `python -m pytest tests/test_storage_writer.py -x -q` | ✅ (extend existing) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -q --no-header` (full suite, < 15 seconds)
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_prompt.py` — covers EXT-01 prompt v2.0.0 structure, detect_insurer(), assemble_text_v2(), overlay appending
- [ ] `tests/test_validation.py` — covers EXT-02 validator registry, financial invariant, date logic, warning structure

*(tests/test_ingestion.py, tests/test_storage_writer.py, tests/test_migrations.py, tests/test_extraction.py all exist and will be extended in-place)*

---

## Sources

### Primary (HIGH confidence)
- Direct codebase reading — all files listed in CONTEXT.md canonical_refs section
- `policy_extractor/extraction/prompt.py` — current SYSTEM_PROMPT_V1, assemble_text()
- `policy_extractor/extraction/client.py` — extract_with_retry(), call_extraction_api(), parse_and_validate()
- `policy_extractor/extraction/__init__.py` — extract_policy() orchestration
- `policy_extractor/extraction/verification.py` — verify_no_hallucination() pattern for validator
- `policy_extractor/ingestion/__init__.py` — ingest_pdf() flow, integration points
- `policy_extractor/ingestion/classifier.py` — classify_page(), PAGE_SCAN_THRESHOLD
- `policy_extractor/ingestion/ocr_runner.py` — run_ocr(), ocr_with_fallback()
- `policy_extractor/schemas/poliza.py` — PolicyExtraction, campos_adicionales, financial fields
- `policy_extractor/storage/models.py` — Poliza ORM, JSON columns
- `policy_extractor/storage/writer.py` — upsert_policy() merge pattern
- `policy_extractor/config.py` — Settings class, pattern for OCR_MIN_CHARS_THRESHOLD
- `alembic/versions/002_evaluation_columns.py` — migration pattern with inspector guard
- `.planning/v2-extraction-errors.md` — all 10 documented errors, root causes, expected values
- `.planning/research/PITFALLS.md` (v2-4, v2-6) — LLM field swap pitfall, auto-OCR gate pitfall
- `.planning/phases/13-extraction-pipeline-fixes/13-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)
- Existing test suite (263 passing tests) — confirms infrastructure patterns, mock patterns, fixture patterns
- pyproject.toml — confirmed dependency versions on installed system

### Tertiary (LOW confidence)
- None — all findings sourced directly from codebase

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and in use
- Architecture: HIGH — all patterns derived from existing code in same project
- Pitfalls: HIGH — pitfalls v2-4 and v2-6 from PITFALLS.md verified; others derived from direct code inspection
- Validation architecture: HIGH — existing test infrastructure fully inventoried

**Research date:** 2026-03-20
**Valid until:** 2026-06-20 (stable stack, 90 days)
