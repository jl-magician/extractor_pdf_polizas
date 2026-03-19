# Stack Research

**Domain:** Insurance PDF data extraction system (LLM-powered, local-first, Python CLI + API)
**Researched:** 2026-03-18 (updated for v1.1)
**Confidence:** HIGH — all versions verified against PyPI; async patterns verified against official FastAPI docs

---

## v1.0 Stack (Shipped — Do Not Re-add)

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| `anthropic` | >=0.86.0 | Claude API client (sync `Anthropic` + ships `AsyncAnthropic`) |
| `pymupdf` | >=1.27.2 | PDF parsing, per-page text extraction |
| `pydantic` | >=2.12.5 | Data validation + output schema |
| `sqlalchemy` | >=2.0.48 | ORM for SQLite storage |
| `fastapi` | >=0.135.1 | CRUD REST API |
| `uvicorn[standard]` | >=0.42.0 | ASGI server |
| `typer` | >=0.9.0 | CLI interface |
| `rich` | >=13.0.0 | Terminal output formatting |
| `ocrmypdf` | >=17.3.0 | OCR preprocessing for scanned PDFs |
| `pytesseract` | >=0.3.13 | Tesseract OCR direct calls |
| `pdf2image` | >=1.17.0 | PDF page to PIL image |
| `python-dotenv` | >=1.0.1 | Environment variable management |
| `loguru` | >=0.7 | Structured logging |
| `pytest` | (dev) | Test runner |
| `ruff` | (dev) | Linter + formatter |

---

## v1.1 Stack Additions

These are the **only new dependencies** needed for the six v1.1 features. Existing libraries cover everything else.

### Core Additions (Production)

| Technology | Version | Feature | Why |
|------------|---------|---------|-----|
| `alembic` | `>=1.18.4` | Alembic migrations | The canonical SQLAlchemy migration tool. v1.18.4 is current stable (Feb 2026). Batch mode handles SQLite's ALTER TABLE limitations natively via move-and-copy — mandatory for SQLite schema evolution. Autogenerates migration scripts from `Base.metadata` with zero model changes. |
| `python-multipart` | `>=0.0.22` | PDF Upload API | FastAPI's `UploadFile` will raise a 422 error at startup if this is missing. Required for `multipart/form-data` file parsing. v0.0.22 released Jan 2026. |
| `openpyxl` | `>=3.1.5` | Excel export | Read/write `.xlsx` without an Excel installation. Supports formatting, multiple sheets, column widths. No pandas/numpy dependency — direct workbook manipulation in ~50 lines for the poliza schema. Pure Python, no C extensions beyond lxml. |
| `aiofiles` | `>=25.1.0` | PDF Upload API | Async-safe file I/O. Required when saving uploaded PDFs to disk inside an `async def` endpoint — without it, `open()` blocks the event loop and kills concurrent throughput. v25.1.0 (Oct 2025) supports Python 3.9+. |

### Dev / Test Additions

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest-asyncio` | `>=1.3.0` | Async test harness | Required to `await` coroutines inside pytest test functions. v1.3.0 (Nov 2025). Set `asyncio_mode = "auto"` in `pyproject.toml` to avoid per-test `@pytest.mark.asyncio` decorators. |
| `httpx` | `>=0.28.1` | FastAPI async test client | FastAPI's official tool for testing async endpoints. `httpx.AsyncClient` with `ASGITransport` exercises the full ASGI stack without a live server. v0.28.1 (Dec 2024). Note: httpx is already a transitive dependency of the `anthropic` SDK — this pins a minimum. |

---

## What NOT to Add for v1.1

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `celery` + `redis` | Adds external broker infrastructure, worker processes, and operational complexity entirely disproportionate to 200 polizas/month on a local Windows machine. | `asyncio.Semaphore` + `asyncio.gather` inside the existing batch command. No external dependencies. |
| `xlsxwriter` | Write-only — cannot read or modify existing `.xlsx` files. If "update existing export" is needed later, it must be replaced. | `openpyxl` (reads and writes) |
| `pandas` | Pulls in ~30MB of numpy + pandas just to write rows. The poliza schema is a flat Pydantic model; direct openpyxl row writes are 50 lines and have no binary dependency. | Direct `openpyxl` workbook manipulation |
| `sqlmodel` | Dual-inheritance model conflicts with existing plain SQLAlchemy `Base`. Migration requires rewriting all ORM models, the storage writer, and ~153 tests. Zero benefit. | Keep existing `sqlalchemy.orm` + separate Pydantic schemas |
| `aiosqlite` / `asyncpg` | Async DB drivers require converting all sessions to `AsyncSession`. The extraction bottleneck is the Claude API call (1–3 s per PDF), not SQLite writes. Converting session layer is a large refactor for negligible gain. | Existing synchronous `SessionLocal`; offload to `run_in_executor` if needed |
| `alembic_utils` | Adds PostgreSQL-specific helpers (views, stored functions) not applicable to SQLite. | Plain `alembic` with `render_as_batch=True` |
| `pytest-httpx` | Mocks `httpx` calls at a low level — useful for testing code that makes external HTTP calls. The evaluator calls the real Anthropic SDK (`anthropic.Anthropic`), not bare `httpx`. Mock the SDK client directly. | `unittest.mock.patch` on `anthropic.Anthropic` or `AsyncAnthropic` |

---

## Integration Details per Feature

### PDF Upload API

**Dependencies added:** `python-multipart`, `aiofiles`

**Pattern:**
```python
# New route added to existing policy_extractor/api/__init__.py app
from fastapi import UploadFile, File, BackgroundTasks
import aiofiles, tempfile, asyncio

@app.post("/upload", status_code=202)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files accepted")
    # Write to temp file asynchronously — does not block event loop
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    async with aiofiles.open(tmp.name, "wb") as f:
        await f.write(await file.read())
    # Kick off extraction in threadpool (extraction is sync/blocking)
    background_tasks.add_task(run_extraction_sync, tmp.name)
    return {"status": "accepted", "filename": file.filename}
```

The existing sync `extract_with_retry` pipeline runs inside `background_tasks.add_task` without modification. For synchronous response (wait for result), use `await asyncio.get_event_loop().run_in_executor(None, run_extraction_sync, tmp_path)` instead.

### Async/Concurrent Batch

**Dependencies added:** none

The `anthropic` SDK (already installed) ships `AsyncAnthropic` — the async counterpart of the existing `Anthropic` client with identical API except `async/await`:

```python
from anthropic import AsyncAnthropic
import asyncio

async def extract_batch_concurrent(pdf_paths: list[str], concurrency: int = 3):
    client = AsyncAnthropic()
    sem = asyncio.Semaphore(concurrency)  # Cap concurrent Claude calls

    async def extract_one(path: str):
        async with sem:
            # async version of call_extraction_api
            message = await client.messages.create(...)
            ...

    await asyncio.gather(*[extract_one(p) for p in pdf_paths])
```

Use `concurrency=3` as default. Anthropic Haiku rate limits are generous, but SQLite requires serialized writes — use a `threading.Lock` around the `upsert_policy` call or route all DB writes through a serial asyncio queue.

### Golden Dataset Regression Suite

**Dependencies added:** none

Directory structure:
```
tests/golden/
  pdfs/           # Reference PDFs (one per insurer+type combination)
  expected/       # Corresponding JSON files (PolicyExtraction.model_dump())
  test_golden.py  # Pytest module
```

Gate behind a custom pytest mark to avoid burning tokens in CI:
```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = ["golden: runs live Claude API calls (deselect with -m 'not golden')"]
```

Run in full: `pytest -m golden`. Run without: `pytest -m "not golden"` (default CI).

### Sonnet Quality Evaluator

**Dependencies added:** none

New module `policy_extractor/extraction/evaluator.py`. Reuses existing `Anthropic` sync client (or `AsyncAnthropic` for batch evaluation):

```python
from pydantic import BaseModel

class QualityScore(BaseModel):
    completeness: float          # 0.0–1.0
    field_scores: dict[str, str] # field_name → "ok" | "missing" | "wrong"
    notes: str

def evaluate_extraction(policy: PolicyExtraction, source_text: str) -> QualityScore:
    # Sends policy JSON + source text to claude-sonnet-4-5 with rubric prompt
    # Returns structured QualityScore via tool_use (same pattern as extraction)
    ...
```

No new library — reuses Pydantic + `anthropic` SDK + `tool_use` pattern already established in `extraction/client.py`.

### Alembic Migrations

**Dependencies added:** `alembic`

**Critical SQLite requirement:** `render_as_batch=True` in `env.py` is mandatory. SQLite does not support `ALTER TABLE DROP COLUMN` or `ALTER TABLE ALTER COLUMN` natively; Alembic batch mode handles this via recreate-and-copy.

Setup:
```bash
alembic init alembic   # Creates alembic/ dir + alembic.ini in project root
```

`alembic/env.py` changes:
```python
from policy_extractor.storage.models import Base
from policy_extractor.config import settings

target_metadata = Base.metadata

def run_migrations_online():
    connectable = create_engine(f"sqlite:///{settings.DB_PATH}")
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,   # Required for SQLite
        )
        with context.begin_transaction():
            context.run_migrations()
```

First migration:
```bash
alembic revision --autogenerate -m "initial_schema_snapshot"
alembic upgrade head
```

Startup strategy: keep `init_db()` for new installs (creates tables), add `alembic upgrade head` for existing installs that need migration. The `create_all()` is idempotent and safe alongside Alembic.

### Excel Export

**Dependencies added:** `openpyxl`

New function in `policy_extractor/cli_helpers.py`:
```python
import openpyxl
from openpyxl.styles import Font

def export_to_excel(polizas: list[Poliza], output_path: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Polizas"
    headers = ["ID", "Numero", "Aseguradora", "Tipo", "Contratante", "Prima", ...]
    ws.append(headers)
    for row in headers:
        ws.cell(1, col+1).font = Font(bold=True)
    for poliza in polizas:
        ws.append([poliza.id, poliza.numero_poliza, ...])
    wb.save(output_path)
```

The existing Typer `export` subcommand gains an `--excel / --json` flag (default json to preserve backward compat).

---

## Installation

Update `pyproject.toml`:

```toml
[project]
dependencies = [
    # Existing v1.0 deps ...
    "alembic>=1.18.4",
    "python-multipart>=0.0.22",
    "openpyxl>=3.1.5",
    "aiofiles>=25.1.0",
]

[project.optional-dependencies]
dev = ["pytest", "ruff", "pytest-asyncio>=1.3.0", "httpx>=0.28.1"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = ["golden: runs live Claude API calls (deselect with -m 'not golden')"]
```

Install:
```bash
pip install alembic>=1.18.4 python-multipart>=0.0.22 openpyxl>=3.1.5 aiofiles>=25.1.0
pip install --upgrade pytest-asyncio httpx   # dev only
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `openpyxl` | `xlsxwriter` | Only if producing heavily formatted reports with charts and no need to ever read/modify existing files |
| `asyncio.Semaphore` + `AsyncAnthropic` | `celery` + `redis` | Only at 10,000+ PDFs/month or when cross-machine distributed workers are required |
| `alembic` batch mode | Raw `CREATE TABLE / INSERT / DROP` scripts | Never — Alembic tracks revision history and handles rollback; hand-rolled scripts do not |
| `httpx.AsyncClient` in tests | `requests.Session` + `TestClient` | `TestClient` is fine for sync endpoints; async upload endpoint requires `httpx.AsyncClient` |
| FastAPI `BackgroundTasks` | `asyncio.create_task` | `create_task` for fire-and-forget within request; `BackgroundTasks` runs after response is sent — both work; `BackgroundTasks` is simpler |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `alembic>=1.18.4` | `sqlalchemy>=2.0.48` | Alembic 1.15+ required for SQLAlchemy 2.0; 1.18.x fully verified on SA 2.0 |
| `alembic>=1.18.4` | Python 3.10+ | Project uses Python 3.11+; compatible |
| `openpyxl>=3.1.5` | Python 3.8+ | No conflicts with project stack |
| `aiofiles>=25.1.0` | Python 3.9+ | No conflicts with Python 3.11+ |
| `pytest-asyncio>=1.3.0` | Python 3.10+ | Compatible with Python 3.11+ |
| `httpx>=0.28.1` | `fastapi>=0.135.1` | FastAPI's `TestClient` is built on httpx internally; both use the same httpx version — no conflict |
| `python-multipart>=0.0.22` | `fastapi>=0.135.1` | FastAPI declares python-multipart as a soft dependency; installing it unlocks `UploadFile` support |

---

## Sources

- [PyPI: alembic](https://pypi.org/project/alembic/) — v1.18.4 verified Feb 2026
- [Alembic batch docs](https://alembic.sqlalchemy.org/en/latest/batch.html) — SQLite `render_as_batch` requirement confirmed HIGH confidence
- [PyPI: openpyxl](https://pypi.org/project/openpyxl/) — v3.1.5 verified
- [PyPI: python-multipart](https://pypi.org/project/python-multipart/) — v0.0.22 verified Jan 2026
- [PyPI: aiofiles](https://pypi.org/project/aiofiles/) — v25.1.0 verified Oct 2025
- [PyPI: pytest-asyncio](https://pypi.org/project/pytest-asyncio/) — v1.3.0 verified Nov 2025
- [PyPI: httpx](https://pypi.org/project/httpx/) — v0.28.1 verified Dec 2024
- [FastAPI docs: Request Files](https://fastapi.tiangolo.com/tutorial/request-files/) — `python-multipart` requirement confirmed HIGH confidence
- [FastAPI docs: Async Tests](https://fastapi.tiangolo.com/advanced/async-tests/) — `httpx.AsyncClient` + `ASGITransport` pattern confirmed HIGH confidence
- [FastAPI docs: Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) — `BackgroundTasks` pattern for post-upload processing
- [Anthropic SDK GitHub](https://github.com/anthropics/anthropic-sdk-python) — `AsyncAnthropic` ships in existing `anthropic` package; no extra install needed HIGH confidence

---

*Stack research for: extractor_pdf_polizas v1.1 (PDF Upload API, async batch, golden dataset, Sonnet evaluator, Alembic migrations, Excel export)*
*Researched: 2026-03-18*
