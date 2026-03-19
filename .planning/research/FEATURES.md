# Feature Research

**Domain:** PDF extraction pipeline — v1.1 API & Quality addons (insurance policy system)
**Researched:** 2026-03-18
**Confidence:** HIGH

---

## Context: What Already Exists (v1.0, NOT in scope here)

The following are fully shipped and stable:

- PDF ingestion with per-page digital/scanned classification (PyMuPDF + image coverage ratio)
- OCR fallback via ocrmypdf + Tesseract for scanned pages
- Claude Haiku extraction with tool_use forced structured output
- CLI subcommands: extract / batch / export / import-json / serve
- SQLite persistence with upsert dedup on (numero_poliza, aseguradora)
- FastAPI CRUD: GET/POST/PUT/DELETE /polizas — JSON body only, no PDF upload

This document covers only the **six new features** for v1.1.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the milestone explicitly requires. Missing any makes the v1.1 milestone incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| PDF Upload API endpoint | External integrations require HTTP-native PDF upload, not CLI-only; the current API accepts JSON bodies only | MEDIUM | POST /polizas/upload multipart/form-data; UploadFile parameter; calls existing ingest_pdf -> extract_policy -> upsert_policy pipeline |
| Async/concurrent batch processing | Current batch is sequential; 200+ PDFs/month creates a throughput bottleneck with no parallelism | MEDIUM | asyncio.Semaphore(N) wrapping extract_policy via run_in_executor; configurable concurrency; Windows asyncio event loop must be confirmed |
| Alembic migrations | create_all() silently skips columns on existing DBs; schema must evolve safely as features land | LOW | alembic init; render_as_batch=True in env.py for SQLite ALTER TABLE support; initial revision stamps current schema |
| Excel export from stored polizas | Agency team works in Excel; JSON is not their native format for reporting and sharing | LOW | pandas + openpyxl; multi-sheet workbook: Polizas / Asegurados / Coberturas sheets; Spanish column names |

### Differentiators (Competitive Advantage)

Features that improve extraction quality — the core value of the product.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Golden dataset regression suite | Catch prompt regressions before they reach production; validate any extraction change against known-good PDFs | MEDIUM | JSON fixture files with expected field subsets; pytest parametrize; field-level fuzzy scoring (not exact full-match) |
| Sonnet quality evaluator | Haiku occasionally misses fields or produces plausible-but-wrong values; Sonnet-as-judge detects this without human review | HIGH | Second Anthropic API call with structured rubric (completeness, accuracy, no hallucination); tool_use forced output; opt-in via flag or config |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full async FastAPI with async SQLAlchemy | "FastAPI is async, use it everywhere" | SQLAlchemy sync sessions with SQLite gain nothing from async I/O at local scale; adds significant complexity | Keep sync endpoints; use BackgroundTasks only for the long-running PDF upload path |
| Celery + Redis job queue for async batch | "Proper" distributed background job pattern | Redis is an operational dependency that does not belong in a local Windows desktop app; overkill for 200 PDFs/month | asyncio.gather + semaphore in CLI batch; FastAPI BackgroundTasks for single-file HTTP upload |
| Permanent storage of uploaded PDFs via API | "Re-process any time from the server" | Disk management complexity; dedup is already hash-based via ingestion_cache | Write UploadFile to tempfile, extract, delete tempfile; re-uploading same PDF is idempotent via hash cache |
| Real-time SSE progress stream for batch | "Show progress in future UI" | Premature for a CLI-first tool; stateful server complexity | Return job_id on async POST /upload; poll GET /upload/{job_id}/status if async path is ever added |
| Sonnet evaluator as a separate microservice | "Decouple quality from extraction" | Network hop latency + deployment complexity for a local tool | Run evaluator as in-process function after Haiku extraction, gated by --evaluate flag |
| Auto-running evaluator on every extraction | "Always know extraction quality" | Sonnet costs ~20x Haiku; evaluating 200 PDFs/month would multiply API costs by 20x | Opt-in via flag (--evaluate) or env var; run on demand for spot-checks and regression fixtures |
| Alembic on every dev iteration | "Always use migrations" | Autogenerate is not perfect; manual review required; slows inner dev loop | Generate migrations only when shipping schema changes; dev flow uses alembic upgrade head |

---

## Feature Dependencies

```
[PDF Upload API]
    └──requires──> [existing ingest_pdf()]
    └──requires──> [existing extract_policy()]
    └──requires──> [existing upsert_policy()]
    └──optional──> [Async background task (for non-blocking upload)]

[Async Batch Processing]
    └──requires──> [existing extract_policy() callable]
    └──shares──>   [same semaphore concurrency pattern as PDF Upload async path]

[Golden Dataset Regression Suite]
    └──requires──> [fixture PDF files (or stored ingestion text) + expected JSON subsets]
    └──requires──> [existing extract_policy() callable from tests]
    └──enhances──> [Sonnet Quality Evaluator] (goldens define what "correct" means for calibration)

[Sonnet Quality Evaluator]
    └──requires──> [existing PolicyExtraction Pydantic schema]
    └──requires──> [Anthropic SDK already in dependencies]
    └──requires──> [assembled_text from ingestion (source to evaluate against)]
    └──enhances──> [Golden Dataset Regression Suite] (evaluator scores goldens automatically)

[Alembic Migrations]
    └──requires──> [existing SQLAlchemy models in storage/models.py]
    └──must precede──> [any feature that adds DB columns in v1.1]

[Excel Export]
    └──requires──> [existing SQLAlchemy ORM query layer]
    └──requires──> [existing orm_to_schema() in storage/writer.py]
    └──independent of all other v1.1 features]
```

### Dependency Notes

- **Alembic must be set up first.** Any v1.1 feature that adds DB columns (e.g., upload job tracking table) needs Alembic already wired in, or those columns must bypass it and create an inconsistency.
- **Golden dataset enables Sonnet evaluator calibration.** You cannot trust evaluator scores without ground-truth examples to validate against. Build goldens before relying on evaluator output.
- **PDF Upload API reuses all v1.0 pipeline components.** No new extraction logic is needed — only HTTP plumbing (multipart parsing, tempfile I/O, error mapping to HTTP status codes).
- **Async batch and PDF upload share concurrency logic.** Build the semaphore-controlled async runner once; use it from both CLI batch command and API upload endpoint.
- **Sonnet evaluator requires assembled_text.** The evaluator must compare the Haiku output against the source document text. The ingestion pipeline produces this text; it must be passed through or retrievable from ingestion_cache.

---

## MVP Definition

### Launch With (v1.1)

Minimum to deliver the milestone goals with no shortcuts that create future debt:

- [ ] Alembic initialized: `alembic init`, `env.py` configured, initial revision stamps current schema — unblocks schema evolution
- [ ] PDF Upload API: `POST /polizas/upload` (multipart/form-data); synchronous path (blocks until extraction done); returns PolicyExtraction JSON 201; returns 422 with error detail on failure; tempfile deleted after processing
- [ ] Async/concurrent batch CLI: `--concurrency N` option (default 3); asyncio.Semaphore wrapping run_in_executor calls; preserves existing Rich progress bar and summary table
- [ ] Excel export CLI: `poliza-extractor export --format xlsx --output polizas.xlsx`; multi-sheet workbook (Polizas / Asegurados / Coberturas); same filter flags as existing JSON export
- [ ] Golden dataset regression suite: `tests/regression/fixtures/` directory with `{name}.expected.json` files keyed to PDFs or ingestion text; pytest parametrize; field-level comparison with tolerance; `@pytest.mark.regression` marker for selective run
- [ ] Sonnet quality evaluator: `evaluate_extraction(policy, source_text, model) -> EvaluationResult`; EvaluationResult has score (0.0-1.0), issues (list[str]), model_id, tokens_used; invoked with `--evaluate` flag in CLI extract

### Add After Validation (v1.x)

Add once v1.1 core is stable and tested:

- [ ] Async PDF upload with job status polling (`GET /upload/{job_id}/status`) — add when UI integration is scoped
- [ ] Excel export from API (`GET /polizas/export?format=xlsx`) — add after CLI Excel is validated by users
- [ ] Evaluator auto-triggered selectively in batch (e.g., sample 10% of extractions) — add once evaluator is calibrated against goldens
- [ ] Expanded golden dataset (20+ fixtures covering all 10 insurers) — add incrementally as real PDFs are confirmed correct

### Future Consideration (v2+)

Defer until product-market fit for the API layer is validated:

- [ ] Celery/Redis distributed job queue — only relevant at >10,000 PDFs/month or multi-tenant scale
- [ ] Web UI for upload and review — explicitly out of scope per PROJECT.md
- [ ] Automated golden dataset expansion from production data — needs human review workflow first
- [ ] Policy comparison and analytics (coverage gap analysis across insurers) — requires stable schema and UI

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Alembic migrations | LOW (infrastructure) | LOW | P1 — unblocks schema evolution; set up first |
| PDF Upload API (sync) | HIGH | MEDIUM | P1 — core integration use case for v1.1 |
| Async concurrent batch | HIGH | MEDIUM | P1 — throughput fix needed at 200+ PDFs/month |
| Excel export | HIGH | LOW | P1 — immediate agency value; low complexity |
| Golden dataset regression | MEDIUM (dev quality) | MEDIUM | P2 — quality safety net; high dev value, low end-user visibility |
| Sonnet quality evaluator | MEDIUM | HIGH | P2 — quality improvement; opt-in; high API cost makes it non-default |

**Priority key:**
- P1: Must have for v1.1 launch — milestone incomplete without it
- P2: Should have — high value but can slip to v1.2 if time constrained
- P3: Nice to have, future consideration

---

## Implementation Notes by Feature

### PDF Upload API

**Expected behavior:** `POST /polizas/upload` accepts `file: UploadFile` via multipart/form-data. The server:
1. Validates content_type is `application/pdf`; returns 415 if not
2. Validates file size <= configurable max (default 50 MB); returns 413 if exceeded
3. Writes bytes to `tempfile.NamedTemporaryFile(suffix=".pdf")`
4. Calls `ingest_pdf(tmp_path, session)` -> `extract_policy(result)` -> `upsert_policy(session, policy)`
5. Returns PolicyExtraction as JSON with status 201
6. Deletes tempfile in a `finally` block regardless of outcome

Re-uploading the same PDF is idempotent: ingestion_cache hash check skips re-OCR; upsert dedup skips duplicate DB write.

**FastAPI pattern:**
```python
from fastapi import UploadFile, File
@app.post("/polizas/upload", status_code=201)
async def upload_pdf(file: UploadFile = File(...), db: DbDep = Depends(get_db)):
    ...
```

Note: `python-multipart` must be added to dependencies for UploadFile to work in FastAPI.

### Async/Concurrent Batch Processing

**Expected behavior:** The CLI `batch` command gains `--concurrency N` (default 3). Internally, asyncio.gather runs N PDFs simultaneously. Each slot calls `asyncio.get_event_loop().run_in_executor(None, process_one_pdf, pdf)` since `ingest_pdf` and `extract_policy` are synchronous. An `asyncio.Semaphore(N)` gates concurrent Claude API calls.

**Key constraints:**
- Claude API rate limits: Haiku tier is ~50 RPM / 50K TPM for free tier; 3-5 concurrent is safe
- OCR (Tesseract) is CPU-bound; do not set concurrency > number of CPU cores
- Windows asyncio: Python 3.11+ on Windows uses ProactorEventLoop by default, which works with run_in_executor; no special policy needed
- Rich Progress: thread-safe for advances from executor threads via `progress.advance(task_id)` in thread callbacks

### Golden Dataset Regression Suite

**Expected behavior:** Directory structure:
```
tests/regression/
    fixtures/
        gnp_auto_sample.pdf          (or: gnp_auto_sample.txt — pre-extracted ingestion text)
        gnp_auto_sample.expected.json
        qualitas_gmm_sample.expected.json
        ...
    conftest.py                       (fixture discovery + parametrize)
    test_regression.py                (test body)
```

Each `.expected.json` contains only the fields that must match (not the full PolicyExtraction). Tests compare with tolerance:
- Dates: exact match on YYYY-MM-DD string
- Amounts (prima_total, suma_asegurada): within 1% relative tolerance
- Strings (numero_poliza, aseguradora): case-insensitive exact match
- Optional fields missing from extraction: warning only, not failure

Tests are marked `@pytest.mark.regression` to allow fast unit test runs to exclude them:
```
pytest -m "not regression"   # fast CI
pytest -m regression         # full quality check
```

**Important design choice:** Do not require storing actual PDFs in the test suite if they contain real policyholder data. Store pre-extracted `assembled_text` strings instead (output of ingestion pipeline), which contain no original PII beyond what the LLM would see anyway. This avoids GDPR/data concerns in a team repository.

### Sonnet Quality Evaluator

**Expected behavior:**
```python
def evaluate_extraction(
    policy: PolicyExtraction,
    source_text: str,
    model: str = "claude-sonnet-4-5",
) -> EvaluationResult:
    ...

@dataclass
class EvaluationResult:
    score: float           # 0.0 (bad) to 1.0 (perfect)
    issues: list[str]      # human-readable problem descriptions
    model_id: str
    tokens_used: int
```

The evaluator sends a second Anthropic API call with:
- Source text (the assembled PDF text from ingestion)
- The Haiku-extracted PolicyExtraction as JSON
- A rubric asking Sonnet to score: completeness (all visible fields captured), accuracy (values match source text), hallucination (values not present in source)

Uses `tool_use` with forced tool call for structured EvaluationResult output — same pattern as extraction.

The evaluator does NOT block persistence. It runs after `upsert_policy()` completes. A score below threshold logs a warning but does not rollback the saved record.

**Cost awareness:** Sonnet costs approximately 20x Haiku per token. A typical policy extraction uses ~3K-8K input tokens. Evaluating every extraction at Sonnet rates would cost $0.15-$0.40 per policy vs. $0.001-0.003 for Haiku extraction. The `--evaluate` flag must default to off.

### Alembic Migrations

**Expected behavior:**
1. `alembic init alembic` creates `alembic/` directory and `alembic.ini`
2. `alembic/env.py` configured with `target_metadata = Base.metadata` and DB URL from settings
3. SQLite requires `render_as_batch=True` in `env.py` context to handle ALTER TABLE via batch recreate
4. `alembic revision --autogenerate -m "initial_schema"` generates the initial migration (manually reviewed before committing)
5. `alembic upgrade head` stamps the existing DB and becomes the baseline for all future changes

The `alembic upgrade head` call is added to app startup (alongside existing `init_db()`) so the API server always runs on the latest schema.

**SQLite-specific:** SQLite does not support `ALTER TABLE ADD COLUMN ... NOT NULL` or dropping columns natively. Alembic's batch mode wraps changes as: copy table -> recreate with new schema -> copy data back -> drop old. This is automatic when `render_as_batch=True` is set.

### Excel Export

**Expected behavior:** `poliza-extractor export --format xlsx --output polizas.xlsx` (extends existing `export` subcommand with `--format` flag).

Multi-sheet workbook:
- **"Polizas"**: one row per policy; columns = all Poliza scalar fields in Spanish; `campos_adicionales` serialized as compact JSON string
- **"Asegurados"**: one row per insured; columns = poliza_id + all Asegurado fields; `campos_adicionales` as JSON string
- **"Coberturas"**: one row per coverage; columns = poliza_id + all Cobertura fields; `campos_adicionales` as JSON string

Date columns formatted as YYYY-MM-DD strings. Decimal columns as Python float (Excel native number). Boolean columns as 1/0.

**Dependencies to add to pyproject.toml:**
```
pandas>=2.0
openpyxl>=3.1
```

`python-multipart` must also be added for UploadFile support:
```
python-multipart>=0.0.9
```

---

## Sources

- [FastAPI Request Files — official docs](https://fastapi.tiangolo.com/tutorial/request-files/)
- [FastAPI Background Tasks — official docs](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [File Uploading and Background Tasks on FastAPI — Medium](https://medium.com/@marcelo.benencase/file-uploading-and-background-tasks-on-fastapi-883d73f5ea61)
- [Limit concurrency with semaphore in Python asyncio — Redowan's Reflections](https://rednafi.com/python/limit-concurrency-with-semaphore/)
- [Processing Files with Controlled Concurrency Using AsyncIO and Semaphores — Medium](https://medium.com/@WamiqRaza/processing-files-with-controlled-concurrency-using-python-asyncio-and-semaphores-7cc09abe5954)
- [Alembic batch migrations for SQLite — official docs](https://alembic.sqlalchemy.org/en/latest/batch.html)
- [Alembic autogenerate — official docs](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [LLM-as-a-Judge evaluation — Langfuse docs](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)
- [LLM-as-a-judge complete guide — Evidently AI](https://www.evidentlyai.com/llm-guide/llm-as-a-judge)
- [Benchmarking LLM-as-a-Judge for 5W1H Extraction Evaluation — MDPI Electronics 2025](https://www.mdpi.com/2079-9292/15/3/659)
- [Building a golden dataset for AI evaluation — Maxim AI](https://www.getmaxim.ai/articles/building-a-golden-dataset-for-ai-evaluation-a-step-by-step-guide/)
- [pytest-regressions overview — official docs](https://pytest-regressions.readthedocs.io/en/latest/overview.html)
- [pandas DataFrame.to_excel — official docs](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_excel.html)
- [Excel writing showdown: Pandas, XlsxWriter, Openpyxl — Medium](https://medium.com/@badr.t/excel-file-writing-showdown-pandas-xlsxwriter-and-openpyxl-29ff5bcb4fcd)

---

*Feature research for: extractor-pdf-polizas v1.1 API & Quality milestone*
*Researched: 2026-03-18*
