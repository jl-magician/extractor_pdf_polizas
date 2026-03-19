# Architecture Research

**Domain:** Insurance PDF extraction + LLM structured data pipeline (v1.1 integration)
**Researched:** 2026-03-18
**Confidence:** HIGH — all integration points derived directly from v1.0 source code

---

## Context: v1.0 Architecture Baseline

v1.0 delivered a working synchronous pipeline with a clear layered structure:

```
policy_extractor/
├── config.py               # Settings (env vars, model, DB path)
├── schemas/                # Pydantic v2 models (PolicyExtraction, Asegurado, Cobertura)
├── ingestion/              # ingest_pdf() → IngestionResult
│   ├── classifier.py       # Per-page digital/scanned detection
│   ├── ocr_runner.py       # ocrmypdf + fallback OCR
│   └── cache.py            # IngestionCache table (hash → result)
├── extraction/             # extract_policy(IngestionResult) → PolicyExtraction
│   ├── client.py           # call_extraction_api(), parse_and_validate(), extract_with_retry()
│   ├── prompt.py           # SYSTEM_PROMPT_V1, assemble_text()
│   ├── schema_builder.py   # build_extraction_tool()
│   └── verification.py     # verify_no_hallucination()
├── storage/                # SQLAlchemy ORM + SQLite
│   ├── database.py         # get_engine(), init_db(), SessionLocal
│   ├── models.py           # Poliza, Asegurado, Cobertura, IngestionCache
│   └── writer.py           # upsert_policy(), orm_to_schema()
├── api/                    # FastAPI
│   └── __init__.py         # GET/POST/PUT/DELETE /polizas (no file upload)
└── cli.py                  # Typer: extract, batch, export, import, serve
```

**Sync pipeline (one PDF):**
```
ingest_pdf(path, session) → IngestionResult
    ↓
extract_policy(ingestion_result, model) → (PolicyExtraction, Usage)
    ↓
upsert_policy(session, extraction) → Poliza (SQLite)
```

**Current state of each new feature:**
- PDF Upload API: FastAPI exists but only accepts JSON body — no file upload endpoint
- Async/concurrent batch: CLI batch is a sequential `for` loop — one PDF at a time
- Golden dataset regression: no test fixtures with known-good expected outputs
- Sonnet quality evaluator: no second-pass LLM evaluation; Haiku extracts, that's it
- Alembic migrations: `Base.metadata.create_all()` only — no migration history
- Excel export: `export` CLI command writes JSON only; no `.xlsx` output

---

## v1.1 System Overview

```
┌───────────────────────────────────────────────────────────────────┐
│                         Entry Layer                                │
├────────────────────────┬──────────────────────────────────────────┤
│   CLI (Typer)          │   HTTP API (FastAPI)                      │
│  extract / batch       │  GET/POST/PUT/DELETE /polizas             │
│  export --format xlsx  │  POST /polizas/upload  [NEW]             │
│  batch --concurrent N  │  POST /batch/submit    [NEW - optional]  │
└────────────┬───────────┴──────────────┬───────────────────────────┘
             │                          │
┌────────────▼──────────────────────────▼───────────────────────────┐
│                     Pipeline Layer                                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Async Pipeline Orchestrator  [NEW]                          │   │
│  │  asyncio.gather() over asyncio-wrapped ingest+extract calls  │   │
│  └──────────────────────────────┬──────────────────────────────┘   │
│                                  │                                  │
│  ┌────────────────┐  ┌───────────▼──────────┐  ┌───────────────┐  │
│  │  ingestion/    │  │  extraction/          │  │  evaluation/  │  │
│  │  ingest_pdf()  │  │  extract_policy()     │  │  [NEW]        │  │
│  │  (unchanged)   │  │  (unchanged sync fn)  │  │  evaluate_    │  │
│  └────────────────┘  └──────────────────────┘  │  with_sonnet()│  │
│                                                  └───────────────┘  │
└────────────────────────────────────────────────────────────────────┘
             │                          │
┌────────────▼──────────────────────────▼───────────────────────────┐
│                     Storage Layer                                   │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  SQLite (managed by Alembic)  [UPGRADED from create_all]   │    │
│  │  polizas / asegurados / coberturas / ingestion_cache       │    │
│  │  + new columns added via Alembic migration scripts         │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌──────────────────────┐  ┌─────────────────────────────────┐    │
│  │  tests/golden/       │  │  Export layer  [NEW]            │    │
│  │  [NEW — regression   │  │  export_to_excel() in           │    │
│  │   fixture store]     │  │  storage/exporter.py            │    │
│  └──────────────────────┘  └─────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### Existing Components (v1.0 — unchanged or minimally modified)

| Component | v1.0 Responsibility | v1.1 Change |
|-----------|---------------------|-------------|
| `ingestion/` | PDF classification, OCR, caching | None — stays synchronous; wrapped in executor for async batch |
| `extraction/client.py` | Anthropic API calls, validation, retry | None — stays synchronous |
| `extraction/__init__.py` | `extract_policy()` orchestrator | None |
| `storage/models.py` | ORM models (Poliza, Asegurado, Cobertura, IngestionCache) | Additive columns via Alembic migration (evaluation fields) |
| `storage/writer.py` | `upsert_policy()`, `orm_to_schema()` | None |
| `storage/database.py` | Engine, SessionLocal, `init_db()` | Remove `create_all()` call from `init_db()`; Alembic takes over |
| `api/__init__.py` | GET/POST/PUT/DELETE /polizas | Add `POST /polizas/upload` endpoint |
| `cli.py` | extract, batch, export, import, serve | Modify `batch` to support `--concurrent N`; modify `export` to support `--format xlsx` |

### New Components (v1.1)

| Component | Responsibility | Location |
|-----------|---------------|----------|
| Async batch orchestrator | Run N concurrent ingest+extract+persist pipelines using `asyncio` + `ThreadPoolExecutor` | `policy_extractor/pipeline.py` (new module) |
| PDF upload endpoint | Accept `multipart/form-data` file upload, save to temp file, run pipeline, return JSON | Added to `policy_extractor/api/__init__.py` |
| Sonnet evaluator | Second-pass LLM call comparing Haiku extraction against source text; returns quality score + field-level corrections | `policy_extractor/evaluation/__init__.py` (new module) |
| Golden dataset runner | Pytest parametrized test that runs extraction on fixture PDFs and diffs against stored expected JSON | `tests/golden/` (new directory) |
| Alembic migrations | Schema versioning — replaces `create_all()` as sole DDL mechanism | `alembic/` (new directory at project root) |
| Excel exporter | Read poliza rows from DB, build `openpyxl` workbook with one sheet per entity type | `policy_extractor/storage/exporter.py` (new file) |

---

## Integration Points Per Feature

### 1. PDF Upload API

**Integration type:** New endpoint added to existing FastAPI app.

**Integration point:** `policy_extractor/api/__init__.py` — add one new route using FastAPI's `UploadFile`.

**Data flow:**
```
POST /polizas/upload  (multipart/form-data, field: "file")
    ↓
FastAPI saves upload to tempfile.NamedTemporaryFile (suffix=".pdf")
    ↓
Existing: ingest_pdf(temp_path, session)   ← same function, new caller
    ↓
Existing: extract_policy(ingestion_result, model)  ← same function
    ↓
Existing: upsert_policy(session, policy)   ← same function
    ↓
Return: PolicyExtraction JSON (201 Created)
    ↓
Cleanup: temp file deleted in finally block
```

**What changes:**
- `api/__init__.py`: add `POST /polizas/upload` route (15-20 lines)
- `pyproject.toml`: add `python-multipart` dependency (FastAPI requires it for `UploadFile`)
- Nothing else changes — the pipeline functions are reused as-is

**Constraint:** The sync pipeline (ingest + extract) can take 5-60 seconds per PDF (OCR + API call). FastAPI will block the event loop on this route unless an async wrapper is added. For v1.1 at low concurrency (single user, local), blocking is acceptable. If async is needed, wrap in `asyncio.get_event_loop().run_in_executor(None, ...)`.

---

### 2. Async/Concurrent Batch Processing

**Integration type:** New async orchestration layer wrapping existing sync functions.

**Core pattern:** `ingest_pdf()` and `extract_policy()` are synchronous and call blocking I/O (OCR subprocess, Anthropic HTTP). The correct approach is `ThreadPoolExecutor` + `asyncio.run_in_executor()`, not rewriting them as async. Python's GIL is not a bottleneck here because both functions spend time waiting on I/O (disk for OCR, network for Anthropic).

**New file:** `policy_extractor/pipeline.py`

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

async def process_pdf_async(pdf: Path, session, model: str | None) -> tuple[str, bool]:
    """Run the full pipeline for one PDF in a thread pool."""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = await loop.run_in_executor(executor, _process_sync, pdf, session, model)
    return result

async def batch_async(pdfs: list[Path], session, model: str | None, concurrency: int = 4):
    """Process up to `concurrency` PDFs simultaneously."""
    semaphore = asyncio.Semaphore(concurrency)
    async def bounded(pdf):
        async with semaphore:
            return await process_pdf_async(pdf, session, model)
    return await asyncio.gather(*[bounded(pdf) for pdf in pdfs], return_exceptions=True)
```

**Integration point in `cli.py`:** The existing `batch` command calls `_process_sync` in a loop. Add `--concurrent N` flag. When `N > 1`, call `asyncio.run(batch_async(pdfs, session, model, N))` instead of the loop.

**SQLAlchemy session concern:** SQLAlchemy `Session` is not thread-safe. Each concurrent worker needs its own session. The orchestrator must create one `Session` per task, not share a global session. The existing `SessionLocal()` factory is already set up to create independent sessions — just call it inside each worker function.

**Expected throughput improvement:** The main bottleneck is the Anthropic API call (~3-15 seconds per policy). With concurrency=4, 4 PDFs are in-flight simultaneously. For 200 policies/month in a nightly batch, this reduces wall-clock time from ~40 min to ~10 min with concurrency=4.

---

### 3. Golden Dataset Regression Suite

**Integration type:** New pytest test directory — no production code changes.

**What it is:** A set of real (anonymized) PDF fixtures paired with known-good expected `PolicyExtraction` JSON files. Pytest runs extraction on each fixture and compares the result to the expected output.

**New directory:** `tests/golden/`

```
tests/golden/
├── conftest.py              # Parametrize over fixture pairs
├── fixtures/
│   ├── axa_auto_digital.pdf          # Real PDF (anonymized)
│   ├── axa_auto_digital.expected.json
│   ├── gnp_gmm_scanned.pdf
│   ├── gnp_gmm_scanned.expected.json
│   └── ...
└── test_golden.py           # Parametrized extraction comparison
```

**Key design decisions:**

1. Golden tests are marked `@pytest.mark.integration` (or `@pytest.mark.golden`) and excluded from the default test run (`pytest -m "not golden"`). They require real Anthropic API calls and should run in CI only on demand or before releases.

2. Comparison strategy: do not do exact string equality on all fields. Use field-by-field comparison with tolerance for confidence scores and `campos_adicionales` ordering. The critical assertion is that `numero_poliza`, `aseguradora`, `tipo_seguro`, `inicio_vigencia`, `fin_vigencia`, and `prima_total` match exactly (or within ±$0.01 for monetary).

3. Expected JSON files are committed to git and updated intentionally when prompt changes are made. This makes prompt regressions visible in code review.

4. The test fixture PDFs must be either synthetic or fully anonymized (remove all real personal data — names, RFC, CURP, addresses). Use PyMuPDF to redact before committing.

**Integration with evaluator (optional):** When the Sonnet evaluator is enabled, golden tests can also assert that the Sonnet evaluation score for the fixture extraction is above a threshold (e.g., >0.85).

---

### 4. Sonnet Quality Evaluator

**Integration type:** New module called optionally after extraction — does not replace Haiku extraction.

**New module:** `policy_extractor/evaluation/__init__.py`

**Architecture:** The evaluator is a second Anthropic API call that takes:
- The assembled PDF text (already available from `IngestionResult`)
- The Haiku extraction result (`PolicyExtraction` as JSON)

And returns a structured quality assessment:
- Per-field confidence scores
- A list of suspected errors with corrections
- An overall quality score (0.0–1.0)

**Pydantic schema for evaluation result:**
```python
class FieldEvaluation(BaseModel):
    field_name: str
    haiku_value: str | None
    assessment: Literal["correct", "incorrect", "unverifiable"]
    correction: str | None = None
    explanation: str | None = None

class EvaluationResult(BaseModel):
    overall_score: float  # 0.0–1.0
    fields_evaluated: list[FieldEvaluation]
    summary: str
    evaluator_model: str
    evaluated_at: datetime
```

**Integration options (in order of invasiveness):**

| Option | When | How |
|--------|------|-----|
| CLI flag `--evaluate` on `extract` command | Single PDF evaluation | After `extract_policy()`, call `evaluate_extraction()`, print score to stderr |
| CLI flag `--evaluate` on `batch` command | Batch evaluation | Run evaluation on each result; include score in summary table |
| Stored evaluation column in DB | Persistent quality tracking | Alembic migration adds `evaluation_score REAL`, `evaluation_json JSON` columns to `polizas` table |
| Separate `evaluate` subcommand | Re-evaluate stored extractions | Read existing poliza from DB, re-call Sonnet, update evaluation columns |

**Recommended for v1.1:** Start with the CLI flag approach. The evaluator is expensive (Sonnet costs ~5x Haiku) and should be opt-in. Store evaluation results in `campos_adicionales` initially — add dedicated columns only if evaluation data becomes a query target.

**Integration point with golden tests:** The golden dataset runner can use the evaluator to generate baseline quality scores for each fixture. This makes regression tracking objective: if a prompt change drops the average evaluation score below the baseline, it's a regression.

---

### 5. Alembic Migrations

**Integration type:** Replace `init_db()` as the DDL mechanism. Alembic runs migrations; `init_db()` is kept for tests only.

**Why needed now:** v1.1 adds new columns (evaluation fields on `polizas`). Without Alembic, the only option is to drop and recreate the database — destroying all extracted data. Alembic handles additive schema changes non-destructively.

**Setup:**
```
alembic/
├── env.py                    # Points to policy_extractor.storage.models.Base
├── script.py.mako            # Migration file template
└── versions/
    └── 001_initial_schema.py    # Baseline: polizas, asegurados, coberturas, ingestion_cache
    └── 002_add_evaluation_cols.py  # v1.1: evaluation_score, evaluation_json on polizas
```

**Key `env.py` configuration:**

```python
# alembic/env.py
from policy_extractor.storage.models import Base
from policy_extractor.config import settings

target_metadata = Base.metadata

def get_url():
    return f"sqlite:///{settings.DB_PATH}"
```

**Migration for production databases:** Users with existing v1.0 databases need to run `alembic upgrade head` before using v1.1. The migration script must handle the case where tables already exist (use `autogenerate` comparison or manual `op.add_column` with `IF NOT EXISTS` guard).

**Migration 002 example:**
```python
# alembic/versions/002_add_evaluation_cols.py
def upgrade():
    op.add_column('polizas', sa.Column('evaluation_score', sa.Numeric(4, 3), nullable=True))
    op.add_column('polizas', sa.Column('evaluation_json', sa.JSON, nullable=True))

def downgrade():
    op.drop_column('polizas', 'evaluation_score')
    op.drop_column('polizas', 'evaluation_json')
```

**`init_db()` change:** Remove `Base.metadata.create_all(engine)` from the production code path. Keep it only in `tests/conftest.py` for in-memory test databases where Alembic is not used. The application startup sequence becomes: `alembic upgrade head` (one-time or deploy-time) → `python -m policy_extractor.cli serve`.

**`database.py` change:** Replace `init_db()` body with a function that just creates the engine and configures `SessionLocal`. The `create_all()` call moves to a `create_tables_for_tests()` helper used only in `conftest.py`.

---

### 6. Excel Export

**Integration type:** New exporter module + new `--format` flag on the existing `export` CLI command.

**New file:** `policy_extractor/storage/exporter.py`

**New dependency:** `openpyxl` (pure Python, no binary deps, Windows-native).

**Output structure (one workbook, multiple sheets):**

| Sheet | Columns | One row per |
|-------|---------|-------------|
| Polizas | id, numero_poliza, aseguradora, tipo_seguro, inicio_vigencia, fin_vigencia, prima_total, moneda, nombre_contratante, nombre_agente, forma_pago, extracted_at | Policy |
| Asegurados | poliza_id, numero_poliza, tipo, nombre_descripcion, fecha_nacimiento, rfc, curp, parentesco | Insured party |
| Coberturas | poliza_id, numero_poliza, nombre_cobertura, suma_asegurada, deducible, moneda | Coverage |

**Design rationale for multi-sheet:** A flat single-sheet export collapses the one-to-many relationships, either duplicating policy data for each asegurado/cobertura or losing coverage detail. Multi-sheet with `poliza_id` as the join key matches how the data is actually structured and how Excel users (pivot tables, VLOOKUP) expect to consume relational data.

**Integration with existing `export` command:**

```python
# cli.py — existing export command modification
@app.command(name="export")
def export_policies(
    ...
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    format: str = typer.Option("json", "--format", help="json or xlsx"),  # NEW
) -> None:
    ...
    if format == "xlsx":
        if output is None:
            output = Path("polizas_export.xlsx")
        from policy_extractor.storage.exporter import export_to_excel
        export_to_excel(rows, output)
    else:
        # existing JSON path unchanged
```

**`export_to_excel()` function signature:**
```python
def export_to_excel(polizas: list[Poliza], output_path: Path) -> None:
    """Write polizas + children to a multi-sheet .xlsx workbook."""
```

**Why openpyxl over xlsxwriter:** openpyxl supports both reading and writing; xlsxwriter is write-only. Either works for this use case, but openpyxl is the more common choice in the Python ecosystem and has better cross-platform compatibility.

---

## Data Flow Changes

### v1.0 Single PDF Flow (unchanged)

```
CLI extract <file>
    ↓
ingest_pdf(path, session) → IngestionResult
    ↓
extract_policy(ingestion_result) → (PolicyExtraction, Usage)
    ↓
upsert_policy(session, policy) → Poliza
    ↓
JSON to stdout
```

### v1.1 PDF Upload API Flow (new)

```
POST /polizas/upload (multipart PDF)
    ↓
Save to tempfile
    ↓
ingest_pdf(temp_path, session)     ← same fn
    ↓
extract_policy(ingestion_result)   ← same fn
    ↓
upsert_policy(session, policy)     ← same fn
    ↓
Delete tempfile
    ↓
Return 201 + PolicyExtraction JSON
```

### v1.1 Concurrent Batch Flow (modified)

```
CLI batch <folder> --concurrent 4
    ↓
Glob PDFs → list[Path]
    ↓
asyncio.run(batch_async(pdfs, concurrency=4))
    ↓                   ↓                   ↓                   ↓
Worker 1               Worker 2            Worker 3            Worker 4
session=SessionLocal() session=SessionLocal() ...               ...
ingest_pdf()           ingest_pdf()         ...
extract_policy()       extract_policy()
upsert_policy()        upsert_policy()
    ↓                   ↓                   ↓                   ↓
asyncio.gather() collects results
    ↓
Rich summary table (succeeded / failed / skipped / cost)
```

### v1.1 Evaluation Flow (optional, per-PDF)

```
extract_policy(ingestion_result) → (PolicyExtraction, Usage)
    ↓ [if --evaluate flag]
evaluate_extraction(
    assembled_text,       ← from ingestion_result
    policy_json,          ← PolicyExtraction.model_dump_json()
    model="claude-sonnet-4-5"
) → EvaluationResult
    ↓
Store evaluation_score + evaluation_json in poliza.campos_adicionales
    ↓ [or dedicated columns after migration 002]
```

---

## Recommended Build Order

Dependencies between new features determine this sequence:

| Step | Feature | Depends On | Rationale |
|------|---------|-----------|-----------|
| 1 | Alembic setup + migration 001 (baseline) | Nothing new — just formalizes existing schema | Must be first so all subsequent schema changes go through migrations |
| 2 | Excel export (`storage/exporter.py` + CLI flag) | Alembic (DB must be stable before adding exporter) | Standalone, no new API surface; fast win |
| 3 | PDF upload API endpoint | Existing FastAPI + `python-multipart` | Touches only `api/__init__.py`; isolated |
| 4 | Async batch orchestrator (`pipeline.py`) | Existing `ingest_pdf` + `extract_policy` | No model changes; pure orchestration; enables throughput |
| 5 | Alembic migration 002 (evaluation columns) | Alembic (step 1) | Schema must exist before evaluator writes to it |
| 6 | Sonnet evaluator (`evaluation/__init__.py`) | Migration 002 + extraction module | Needs schema columns and extraction to evaluate |
| 7 | Golden dataset suite (`tests/golden/`) | Evaluator (optional) + working extraction | Needs real PDFs; can run without evaluator but richer with it |

---

## Modified vs New: Explicit Inventory

### Files MODIFIED in v1.1

| File | What Changes |
|------|-------------|
| `policy_extractor/storage/database.py` | Remove `create_all()` from production path; keep for tests via helper |
| `policy_extractor/api/__init__.py` | Add `POST /polizas/upload` route; add `python-multipart` handling |
| `policy_extractor/cli.py` | `batch` gets `--concurrent N` flag; `export` gets `--format xlsx` flag |
| `pyproject.toml` | Add `openpyxl`, `python-multipart`, `alembic` dependencies |

### Files CREATED in v1.1

| File | Purpose |
|------|---------|
| `alembic/env.py` | Alembic environment config pointing to existing models |
| `alembic/versions/001_initial_schema.py` | Baseline migration (polizas, asegurados, coberturas, ingestion_cache) |
| `alembic/versions/002_add_evaluation_cols.py` | Adds evaluation_score + evaluation_json to polizas |
| `policy_extractor/pipeline.py` | Async batch orchestrator with ThreadPoolExecutor |
| `policy_extractor/storage/exporter.py` | `export_to_excel(polizas, path)` using openpyxl |
| `policy_extractor/evaluation/__init__.py` | `evaluate_extraction()` via Sonnet API call |
| `policy_extractor/schemas/evaluation.py` | `EvaluationResult`, `FieldEvaluation` Pydantic models |
| `tests/golden/` | Directory with fixture PDFs + expected JSON + parametrized test |
| `tests/golden/test_golden.py` | Pytest golden regression test |
| `alembic.ini` | Alembic CLI config file |

### Files UNCHANGED in v1.1

Everything in `ingestion/`, `extraction/`, `storage/writer.py`, `storage/models.py` (except via Alembic migration), `schemas/poliza.py`, `schemas/asegurado.py`, `schemas/cobertura.py`, `config.py`.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Shared SQLAlchemy Session Across Async Workers

**What happens:** The async batch orchestrator creates one `Session` and passes it to all concurrent workers.

**Why it's wrong:** `Session` is not thread-safe. Concurrent commits from multiple threads cause either silent data corruption or SQLite locking errors ("database is locked").

**Do this instead:** Each worker function calls `SessionLocal()` independently. Sessions are created inside the worker, used for one PDF, then closed. The `SessionLocal` factory is thread-safe.

### Anti-Pattern 2: Using `asyncio.sleep(0)` to Yield in Sync-Wrapped Code

**What happens:** Developer wraps sync functions in `async def` with `await asyncio.sleep(0)` between calls, believing this gives concurrency.

**Why it's wrong:** Synchronous blocking I/O (file reads, subprocess calls for OCR, `requests`-based HTTP) does not yield the event loop regardless of `await`. The GIL is held for sync I/O operations, so other coroutines cannot run.

**Do this instead:** Use `loop.run_in_executor(executor, sync_fn, *args)`. This actually offloads the sync call to a thread, releasing the event loop for other coroutines.

### Anti-Pattern 3: Running Alembic `upgrade head` in Application Code

**What happens:** `startup` event or `init_db()` calls `alembic upgrade head` programmatically every time the app starts.

**Why it's wrong:** Safe for development, dangerous in production. If a migration contains a bug, every app restart triggers the broken migration. Multiple process restarts can run the same migration concurrently.

**Do this instead:** Run `alembic upgrade head` explicitly as a setup step (documented in README, run once per deployment). `init_db()` only creates the engine and configures `SessionLocal`; it does not run DDL.

### Anti-Pattern 4: Saving Uploaded PDFs to the Uploads Folder Without Cleanup

**What happens:** The upload endpoint writes the PDF to `data/uploads/` and forgets to delete it after processing.

**Why it's wrong:** On a local machine processing 200+ PDFs/month, the uploads folder accumulates gigabytes of data. The source PDF is already captured via `source_file_hash` in the database; keeping the file offers no benefit.

**Do this instead:** Use `tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)` and delete the file in a `finally` block after `ingest_pdf()` completes. The ingestion cache stores the content hash — the file is not needed again.

### Anti-Pattern 5: Exact String Equality in Golden Tests

**What happens:** Golden test asserts `policy.model_dump_json() == expected_json` (byte-for-byte).

**Why it's wrong:** LLM outputs have non-deterministic formatting in string fields (whitespace, punctuation differences), floating-point representation differences in `prima_total`, and `campos_adicionales` key ordering variation. Tests fail constantly despite correct extraction.

**Do this instead:** Compare field-by-field with tolerance: string fields use case-insensitive contains or normalized comparison; monetary fields allow ±0.01; dates use `==` on `date` objects; `campos_adicionales` is excluded from strict comparison.

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Current: 200 policies/month, 1 user, local | Concurrency=4, SQLite WAL mode, sync API upload (blocking is fine) |
| 2,000 policies/month, 1 user | Increase concurrency to 8-16; consider Anthropic Batch API (50% cost reduction, async 24h results) |
| Multi-user web access | Move SessionLocal to per-request scope (already done); enable SQLite WAL; add nginx reverse proxy |
| PostgreSQL migration | Change only `get_engine()` URL; SQLAlchemy 2.0 + Alembic handle the rest |

---

## Sources

- FastAPI File Upload official docs: https://fastapi.tiangolo.com/tutorial/request-files/ — `UploadFile`, `File()`, `python-multipart` requirement (HIGH confidence)
- Alembic official docs — Getting Started: https://alembic.sqlalchemy.org/en/latest/tutorial.html — `env.py`, `upgrade`, `autogenerate` (HIGH confidence)
- SQLAlchemy 2.0 + Alembic compatibility: https://alembic.sqlalchemy.org/en/latest/changelog.html — Alembic 1.13+ required for SQLAlchemy 2.0 (HIGH confidence)
- openpyxl official docs: https://openpyxl.readthedocs.io/en/stable/ — multi-sheet workbooks, column types (HIGH confidence)
- Python asyncio + ThreadPoolExecutor pattern: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor — blocking I/O in async context (HIGH confidence)
- SQLite thread safety and WAL mode: https://www.sqlite.org/wal.html — concurrent readers, single writer, WAL vs journal mode (HIGH confidence)
- v1.0 source code analysis (direct inspection): policy_extractor/ — all integration points derived from actual codebase (HIGH confidence)

---

*Architecture research for: extractor_pdf_polizas v1.1 (PDF Upload API, async batch, golden dataset, Sonnet evaluator, Alembic, Excel export)*
*Researched: 2026-03-18*
