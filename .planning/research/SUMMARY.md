# Project Research Summary

**Project:** extractor_pdf_polizas v1.1 — API & Quality Milestone
**Domain:** Insurance PDF extraction pipeline (LLM-powered, Python CLI + REST API, local-first)
**Researched:** 2026-03-18
**Confidence:** HIGH — all sources verified against official documentation and v1.0 source code

## Executive Summary

This project is a production v1.1 upgrade to a shipped insurance policy PDF extractor. The v1.0 system already handles the hard problems: per-page digital/scanned classification, OCR fallback via Tesseract/ocrmypdf, Claude Haiku structured extraction via tool_use, SQLite persistence, and a FastAPI CRUD API. v1.1 adds six targeted features — PDF upload via HTTP, concurrent batch processing, schema migrations, Excel export, a golden dataset regression suite, and an optional Sonnet quality evaluator — none of which require replacing any v1.0 component. The recommended approach is strictly additive: wrap existing sync functions in asyncio executors, extend the CLI with new flags, add new modules for evaluation and export, and wire Alembic to manage the existing schema going forward.

The recommended build sequence is dictated by dependency order, not feature priority. Alembic must be initialized first because any subsequent feature that adds DB columns requires a migration framework to be in place. Excel export and the PDF upload endpoint can then be built sequentially before tackling async concurrency. The Sonnet evaluator and golden dataset suite follow, as they depend on a stable extraction pipeline and optionally on evaluation columns added via Alembic.

The most important risk in v1.1 is not architectural — the architecture is well-understood — but operational: silent failure modes introduced by concurrency. SQLite locking errors under async writes, UploadFile objects closed before background tasks read them, and Anthropic rate limit storms that return None without retrying are all patterns that fail quietly and only surface during integration testing at realistic concurrency levels. All three are preventable with established techniques (WAL mode + busy_timeout, read-bytes-before-returning, semaphore + exponential backoff) that are thoroughly documented in the pitfalls research.

## Key Findings

### Recommended Stack

The v1.0 stack (Python 3.11+, anthropic, pymupdf, pydantic v2, sqlalchemy 2.0, fastapi, uvicorn, typer, rich, ocrmypdf, loguru) requires only four new production dependencies for v1.1. Everything else needed is already installed or ships as a transitive dependency of the Anthropic SDK.

**New production dependencies:**
- `alembic>=1.18.4` — schema migrations; mandatory for SQLite ALTER TABLE support via `render_as_batch=True`; v1.18.4 fully verified on SQLAlchemy 2.0
- `python-multipart>=0.0.22` — FastAPI UploadFile support; FastAPI raises 422 at startup without it
- `openpyxl>=3.1.5` — Excel workbook creation; pure Python, no binary deps, supports both read and write
- `aiofiles>=25.1.0` — async-safe file I/O for saving uploaded PDFs without blocking the event loop

**New dev dependencies:**
- `pytest-asyncio>=1.3.0` — async test harness; set `asyncio_mode = "auto"` in pyproject.toml to avoid per-test decorators
- `httpx>=0.28.1` — FastAPI async test client via `ASGITransport`; already a transitive dependency of the `anthropic` SDK

**What NOT to add:** celery/redis (overkill for 200 PDFs/month on a local machine), pandas (30 MB binary dependency for a 50-line openpyxl operation), aiosqlite/asyncpg (the bottleneck is Claude API calls not SQLite writes), sqlmodel (would require rewriting all ORM models and 153 tests), xlsxwriter (write-only — cannot read or modify existing files).

### Expected Features

All six v1.1 features are explicitly defined. Four are P1 (milestone incomplete without them); two are P2 (high value, can slip to v1.2 if time-constrained).

**Must have (P1 — table stakes):**
- Alembic migrations — unblocks all schema evolution; `alembic stamp head` on existing DB must precede everything else
- PDF Upload API (`POST /polizas/upload`) — HTTP-native PDF integration; returns 202 + job ID; tempfile cleanup in `finally` block
- Async/concurrent batch (`--concurrency N`, default 3) — fixes throughput bottleneck at 200+ PDFs/month; 4x wall-clock improvement
- Excel export (`export --format xlsx`) — multi-sheet workbook (Polizas/Asegurados/Coberturas); immediate agency value; low complexity

**Should have (P2 — differentiators):**
- Golden dataset regression suite — field-level fuzzy comparison against fixture JSON; `@pytest.mark.regression` marker; hash-keyed fixtures, no absolute paths, no PII
- Sonnet quality evaluator — second-pass LLM scoring via `evaluate_extraction(policy, source_text)`; opt-in via `--evaluate` flag; Sonnet costs ~20x Haiku, must never be in the default extraction path

**Defer to v1.x after validation:**
- Async job status polling (`GET /jobs/{job_id}/status`) — add when UI integration is scoped
- Excel export from API endpoint — validate CLI Excel first
- Evaluator auto-sampling in batch runs (e.g., 10% of PDFs) — add once evaluator is calibrated

**Defer to v2+:**
- Celery/Redis distributed job queue — only relevant at >10,000 PDFs/month or multi-tenant scale
- Web UI — explicitly out of scope per project requirements

### Architecture Approach

v1.1 extends the existing three-layer architecture (Entry Layer → Pipeline Layer → Storage Layer) without restructuring it. Only four existing files are modified: `database.py` (remove `create_all()` from production startup), `api/__init__.py` (add upload route), `cli.py` (add `--concurrent` and `--format` flags), and `pyproject.toml` (add four dependencies). Five new modules are created. The ingestion, extraction, storage writer, and schema modules are untouched.

**Major components:**
1. **Async batch orchestrator** (`pipeline.py`) — wraps existing sync `ingest_pdf()` + `extract_policy()` in `ThreadPoolExecutor` via `run_in_executor`; `asyncio.Semaphore(N)` gates concurrent Claude calls; each worker creates its own `SessionLocal()` since Session is not thread-safe
2. **PDF upload endpoint** (added to `api/__init__.py`) — reads file bytes before returning response, saves to UUID-named tempfile, runs pipeline via `BackgroundTasks`, returns job ID in 202 response, deletes tempfile in `finally`
3. **Sonnet evaluator** (`evaluation/__init__.py`) — separate opt-in module; sends assembled PDF text + Haiku extraction to Sonnet with rubric prompt via `tool_use`; returns `EvaluationResult` with overall score, per-field assessment, and token cost
4. **Alembic migration chain** (`alembic/versions/`) — migration 001 baseline-stamps existing schema; migration 002 adds evaluation columns to `polizas`; `render_as_batch=True` mandatory for SQLite column modifications
5. **Excel exporter** (`storage/exporter.py`) — routes all export through `orm_to_schema()` + `.model_dump(mode="json")` to get JSON-serializable primitives before writing to openpyxl; multi-sheet workbook with `poliza_id` as join key
6. **Golden regression suite** (`tests/golden/`) — parametrized pytest over hash-keyed fixture pairs; field-level comparison with tolerance (±$0.01 for monetary, case-insensitive exact for strings, ISO 8601 exact for dates)

### Critical Pitfalls

1. **UploadFile closed before background task reads it** — FastAPI >= 0.106.0 closes `UploadFile` after the response is sent. Always call `pdf_bytes = await file.read()` inside the route handler and pass `bytes` (not the `UploadFile` object) to the background task. Failure is silent: policy never appears in DB, no 500 returned to client.

2. **SQLite "database is locked" under async writes** — Default DELETE journal mode immediately raises on lock contention when multiple background tasks write simultaneously. Enable WAL mode and `busy_timeout=5000` via SQLAlchemy `connect` event on engine creation. Keep async batch semaphore at 3-5 workers maximum.

3. **Alembic stamp head skipped — schema drift forever** — `alembic autogenerate` on an existing `create_all()` database produces an empty migration because tables already exist, and `alembic_version` is never created. Run `alembic stamp head` immediately after installing Alembic, before generating any migration. Remove `create_all()` from production startup at the same time.

4. **Anthropic rate limit storm in async batch** — `asyncio.gather()` without a semaphore fires all requests simultaneously, triggers 429s, and returns `None` for every task if `RateLimitError` is not caught with retry logic. Add `asyncio.Semaphore(3)` and catch `anthropic.RateLimitError` with exponential backoff before any concurrent extraction is tested.

5. **Sonnet evaluator wired into default extraction path** — Sonnet costs ~20x Haiku. Evaluating 200 PDFs/month at Sonnet rates multiplies API costs by 20x and adds 10-30 seconds per PDF. The evaluator must be triggered exclusively by an explicit flag (`--evaluate`) or API parameter (`?evaluate=true`). Never embed in `extract_with_retry` or the upload handler.

6. **Excel Decimal/Date types serialized as text** — SQLAlchemy ORM returns `Decimal` and `datetime.date` objects that openpyxl cannot serialize as Excel numeric/date cells. Always route export through `orm_to_schema()` + `.model_dump(mode="json")` to get Python `float` and `str` before writing. Without this, SUM formulas on `prima_total` return 0.

## Implications for Roadmap

Based on research, the build order is dictated by hard dependencies, not subjective priority. All four research files converge on the same sequence.

### Phase 1: Alembic Foundation

**Rationale:** Every subsequent v1.1 feature that changes the DB schema (evaluation columns, optional job tracking table) requires a migration framework to be in place first. This phase has no dependencies and unblocks everything else. `alembic stamp head` is the single most important action to take on the existing database before any other work begins.

**Delivers:** Schema version control; `alembic.ini` + `alembic/env.py` configured with `render_as_batch=True` and `target_metadata = Base.metadata`; migration 001 (baseline snapshot of existing schema, stamped on live DB); migration 002 (evaluation_score + evaluation_json columns on polizas table); `create_all()` removed from production `init_db()`; `create_tables_for_tests()` helper created for in-memory test DBs.

**Addresses:** P1 table-stakes feature "Alembic migrations"

**Avoids:** Schema drift with empty autogenerated migrations (Pitfall 3), SQLite ALTER TABLE failures (Pitfall 4)

**Research flag:** Standard patterns — Alembic + SQLite is thoroughly documented. No phase-level research needed. Follow `render_as_batch=True` and `alembic stamp head` requirements exactly.

### Phase 2: Excel Export

**Rationale:** Standalone feature with no dependency on async infrastructure or new API surface. Low complexity, high immediate agency value. Building this second creates a working export module that validates the full ORM-to-file serialization path cleanly before async complexity is introduced.

**Delivers:** `policy_extractor/storage/exporter.py` with `export_to_excel(polizas, path)`; `--format xlsx` flag on existing `export` CLI command (default `json` preserved for backward compatibility); multi-sheet workbook (Polizas/Asegurados/Coberturas) with `poliza_id` as join key; correct Decimal/date serialization via `model_dump(mode="json")`.

**Uses:** `openpyxl>=3.1.5` (new dependency); existing `orm_to_schema()` from `storage/writer.py`

**Addresses:** P1 table-stakes feature "Excel export"

**Avoids:** Decimal/date text serialization (Pitfall 8), Excel SUM formula breakage

**Research flag:** Standard patterns — openpyxl multi-sheet workbooks are well-documented. The serialization pitfall is explicitly addressed; no additional research needed.

### Phase 3: PDF Upload API

**Rationale:** Touches only `api/__init__.py` and adds two small dependencies. Pipeline functions are reused as-is. Building this before async batch establishes the concurrency primitives (BackgroundTasks, job ID pattern) that the batch command will mirror.

**Delivers:** `POST /polizas/upload` endpoint accepting `multipart/form-data`; synchronous extraction path via `BackgroundTasks`; UUID job ID returned in 202 response; in-memory `job_store` dict for status polling; `GET /jobs/{job_id}` status endpoint; UUID-named tempfile with `finally` cleanup; file size (50 MB) and MIME type validation; `python-multipart` + `aiofiles` dependencies.

**Addresses:** P1 table-stakes feature "PDF Upload API"

**Avoids:** UploadFile closed before background task reads it (Pitfall 1), no job ID for polling (Pitfall 9), path traversal via original filename (security), uploaded file disk accumulation (Architecture anti-pattern 4)

**Research flag:** Standard patterns — FastAPI UploadFile + BackgroundTasks is well-documented. The UploadFile-closed pitfall is explicitly documented in GitHub issues. No additional research needed.

### Phase 4: Async/Concurrent Batch

**Rationale:** Depends on the sync pipeline being stable (established in v1.0) and the SQLite WAL/concurrency patterns being clear. Builds `pipeline.py` as a reusable async orchestrator. The semaphore + executor pattern here is the same primitive used by the upload endpoint's background task path.

**Delivers:** `policy_extractor/pipeline.py` with `batch_async()` and `process_pdf_async()`; `--concurrent N` flag on `batch` CLI command (default 3); `asyncio.Semaphore(N)` + `ThreadPoolExecutor` + `run_in_executor` wrapping existing sync pipeline; WAL mode + `busy_timeout=5000` on SQLite engine; `anthropic.RateLimitError` catch with exponential backoff (capped at 60s); per-worker `SessionLocal()` creation (not shared); preserved Rich progress bar and summary table.

**Addresses:** P1 table-stakes feature "Async/concurrent batch processing"

**Avoids:** SQLite locking under concurrent writes (Pitfall 2), rate limit storm with no backoff (Pitfall 5), shared Session across async workers (Architecture anti-pattern 1), sync blocking inside async def (Architecture anti-pattern 2)

**Research flag:** Low-risk patterns — `run_in_executor` + semaphore is established Python async idiom. WAL mode and RateLimitError handling are specific but thoroughly documented.

### Phase 5: Sonnet Quality Evaluator

**Rationale:** Depends on Alembic (evaluation columns via migration 002 from Phase 1) and a stable extraction pipeline. Building after async batch means the evaluator can be integrated into the concurrent batch path without rework. Must be implemented as an opt-in, isolated module from the start.

**Delivers:** `policy_extractor/evaluation/__init__.py` with `evaluate_extraction(policy, source_text, model)`; `EvaluationResult` + `FieldEvaluation` Pydantic models in `schemas/evaluation.py`; opt-in `--evaluate` flag on `extract` and `batch` CLI commands; evaluation results stored in `polizas.evaluation_score` + `polizas.evaluation_json` (from migration 002); Sonnet token cost logged separately from Haiku extraction cost; evaluator never triggered in default path.

**Addresses:** P2 feature "Sonnet quality evaluator"

**Avoids:** Evaluator cost doubling per-PDF by default (Pitfall 6), evaluator in the hot extraction path (technical debt)

**Research flag:** Low-risk patterns — LLM-as-judge with `tool_use` reuses the same pattern as v1.0 extraction. Cost management gating is the primary concern, not technical difficulty.

### Phase 6: Golden Dataset Regression Suite

**Rationale:** Best built last because it validates all preceding features end-to-end. The fixture set requires anonymized real PDFs and working extraction — both stable after Phases 1-5. The optional Sonnet evaluator (Phase 5) can score fixtures automatically, enriching regression signals.

**Delivers:** `tests/golden/` directory with hash-keyed fixture pairs (`{sha256}.expected.json`); `tests/golden/conftest.py` with fixture discovery; `tests/golden/test_golden.py` with parametrized extraction + comparison; `@pytest.mark.regression` marker (excluded from default CI run); field-level comparison with tolerance; anonymized PDF fixtures with no absolute paths and no real PII.

**Addresses:** P2 feature "Golden dataset regression suite"

**Avoids:** Absolute path fragility across machines (Pitfall 7), exact string equality brittleness in LLM outputs (Architecture anti-pattern 5), PII in committed test fixtures (security)

**Research flag:** Needs deliberate setup — fixture PDF anonymization and hash-keyed design must be established before any fixture is created. Audit `pdfs-to-test/` directory for PII before committing any files. Comparison tolerance logic (monetary ±$0.01, case-insensitive strings, ISO 8601 dates) must be implemented correctly to avoid flaky tests.

### Phase Ordering Rationale

- Alembic first because schema evolution is a hard prerequisite for evaluation columns and any future job tracking table; it has no upstream dependencies.
- Excel export second because it is independent, low-risk, and validates the ORM serialization layer cleanly before async complexity is introduced.
- Upload API third because it establishes the BackgroundTasks + job ID pattern that async batch mirrors, and its concurrency footprint is smaller (one file at a time).
- Async batch fourth because it builds on the concurrency patterns established conceptually in Phase 3 and requires SQLite WAL mode (which also benefits the upload API).
- Sonnet evaluator fifth because it optionally stores results in evaluation columns (requiring Phase 1 Alembic) and is richer when concurrent batch infrastructure is in place.
- Golden dataset last because it validates the complete system end-to-end and requires stable extraction to produce reliable, trustworthy fixtures.

### Research Flags

**Phases likely needing deeper research during planning:** None — all six features have HIGH-confidence research with specific implementation patterns, code examples, and file-level change inventories. The research files include concrete code snippets for every integration point.

**Phases with standard patterns (safe to skip phase-level research):**
- **Phase 1 (Alembic):** official documentation is definitive; `render_as_batch=True` and `stamp head` are the only non-obvious requirements
- **Phase 2 (Excel):** openpyxl multi-sheet workbooks are thoroughly documented; the Decimal serialization pitfall is explicitly addressed
- **Phase 3 (Upload API):** FastAPI UploadFile is well-documented; the UploadFile-closed pitfall is the only non-obvious requirement
- **Phase 4 (Async batch):** run_in_executor + semaphore is established idiom; WAL + RateLimitError handling are specific but documented
- **Phase 5 (Sonnet evaluator):** reuses existing extraction patterns; cost gating is the primary concern, not technical difficulty
- **Phase 6 (Golden dataset):** fixture anonymization and hash-keying require deliberate design but no novel technology; PII audit of existing PDFs is the main upfront task

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All four new package versions verified against PyPI; compatibility matrix checked; no version conflicts identified; transitive dependency paths confirmed |
| Features | HIGH | Six features explicitly defined with MVP scope, dependency order, anti-feature rationale, and field-level implementation notes |
| Architecture | HIGH | All integration points derived directly from v1.0 source code; explicit file-level modified/created/unchanged inventory provided |
| Pitfalls | HIGH | Critical pitfalls verified against official FastAPI docs, GitHub discussions (#10936, #11177), SQLite WAL docs, and Anthropic SDK source; each pitfall has a tested prevention pattern and "looks done but isn't" checklist |

**Overall confidence:** HIGH

### Gaps to Address

- **Exact Anthropic Haiku rate limits for the specific account tier:** Research recommends semaphore of 3 as a safe default. The actual account-level RPM and TPM limits depend on the Anthropic plan. Validate against the Anthropic console before raising the default concurrency in production.
- **PDF fixture availability for golden dataset:** The `pdfs-to-test/` directory exists in the repo but its contents and anonymization status are unknown. Audit before Phase 6 to determine which PDFs can be committed and what anonymization is needed.
- **WAL mode migration on existing DB file:** Enabling WAL mode on a database created without it requires a one-time `PRAGMA journal_mode=WAL` call that Alembic does not manage. Verify that the existing `polizas.db` transitions cleanly before Phase 4 adds concurrent writers.
- **In-memory job_store limitations:** The job ID pattern recommended for Phase 3 uses an in-memory dict (acceptable for single-user local use). If the server is ever restarted mid-extraction, job status is lost. Document this limitation explicitly; address with a `jobs` DB table if async upload is extended post-v1.1.

## Sources

### Primary (HIGH confidence)

- [FastAPI docs: Request Files](https://fastapi.tiangolo.com/tutorial/request-files/) — UploadFile, File(), python-multipart requirement
- [FastAPI docs: Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) — BackgroundTasks pattern for post-upload processing
- [FastAPI docs: Async Tests](https://fastapi.tiangolo.com/advanced/async-tests/) — httpx.AsyncClient + ASGITransport pattern
- [Alembic docs: Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html) — stamp, upgrade, autogenerate
- [Alembic docs: Batch Mode](https://alembic.sqlalchemy.org/en/latest/batch.html) — render_as_batch, SQLite ALTER TABLE workaround
- [Alembic docs: Cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html) — working with existing databases
- [SQLite docs: WAL](https://www.sqlite.org/wal.html) — WAL concurrency model, busy_timeout
- [Anthropic SDK GitHub](https://github.com/anthropics/anthropic-sdk-python) — AsyncAnthropic ships in existing package
- [FastAPI GitHub Discussion #10936](https://github.com/fastapi/fastapi/discussions/10936) — UploadFile closed before background task
- [FastAPI GitHub Discussion #11177](https://github.com/fastapi/fastapi/discussions/11177) — reading file into background task
- [PyPI: alembic 1.18.4](https://pypi.org/project/alembic/) — verified Feb 2026
- [PyPI: openpyxl 3.1.5](https://pypi.org/project/openpyxl/) — verified
- [PyPI: python-multipart 0.0.22](https://pypi.org/project/python-multipart/) — verified Jan 2026
- [PyPI: aiofiles 25.1.0](https://pypi.org/project/aiofiles/) — verified Oct 2025
- [PyPI: pytest-asyncio 1.3.0](https://pypi.org/project/pytest-asyncio/) — verified Nov 2025
- [PyPI: httpx 0.28.1](https://pypi.org/project/httpx/) — verified Dec 2024
- v1.0 source code (direct inspection) — all architecture integration points derived from actual codebase

### Secondary (MEDIUM confidence)

- [dida.do: Patching uploaded files for FastAPI background tasks](https://dida.do/blog/patching-uploaded-files-for-usage-in-fastapi-background-tasks) — UploadFile workaround (consistent with official docs)
- [tenthousandmeters.com: SQLite concurrent writes](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/) — WAL + busy_timeout guidance (consistent with SQLite docs)
- [getmaxim.ai: Building a golden dataset for AI evaluation](https://www.getmaxim.ai/articles/building-a-golden-dataset-for-ai-evaluation-a-step-by-step-guide/) — hash-keyed fixture design
- [Evidently AI: LLM-as-a-Judge guide](https://www.evidentlyai.com/llm-guide/llm-as-a-judge) — evaluator rubric structure
- [drdroid.io: Anthropic concurrency limit reached](https://drdroid.io/integration-diagnosis-knowledge/anthropic-concurrency-limit-reached) — rate limit behavior with concurrent requests

### Tertiary (reference only)

- Medium articles on asyncio semaphore patterns — consistent with official Python asyncio docs; used for examples only
- statsig.com: Prompt regression testing — consistent with golden dataset design principles

---
*Research completed: 2026-03-18*
*Ready for roadmap: yes*
