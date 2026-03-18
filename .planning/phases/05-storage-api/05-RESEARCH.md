# Phase 5: Storage & API - Research

**Researched:** 2026-03-18
**Domain:** SQLAlchemy 2.0 upsert, FastAPI + SQLAlchemy dependency injection, Typer subcommand extension, Pydantic v2 JSON serialization
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Auto-persist after extraction in CLI — after successful extraction in extract/batch commands, automatically save PolicyExtraction to SQLite. User gets JSON output AND data is stored.
- Also provide an `import` subcommand to load previously exported JSON files into DB.
- Dedup strategy: upsert by (numero_poliza, aseguradora) — if same policy number from same insurer exists, update the existing record. Different policy number = new record.
- Mapping: PolicyExtraction (Pydantic) → Poliza + Asegurado + Cobertura (ORM models). Delete existing child rows on upsert, re-create from extraction.
- New `export` subcommand: `poliza-extractor export` — dumps all policies by default; supports filters: `--insurer`, `--agent`, `--from-date`, `--to-date`, `--type`. Output to stdout by default, `--output file.json` for file. Format: array of PolicyExtraction-shaped objects.
- FastAPI full CRUD routes: GET /polizas (list + filters + pagination), GET /polizas/{id}, POST /polizas, PUT /polizas/{id}, DELETE /polizas/{id}
- Response format: PolicyExtraction-shaped JSON with nested asegurados/coberturas.
- Server start: both `poliza-extractor serve --port 8000` CLI subcommand AND standard `uvicorn policy_extractor.api:app` works.
- Swagger/OpenAPI docs enabled at `/docs` and `/redoc` (FastAPI defaults).
- Skip Alembic for v1 — keep using `Base.metadata.create_all()`. Add Alembic in v2 when schema evolves.

### Claude's Discretion
- Pydantic → ORM mapping function implementation details
- FastAPI dependency injection for DB sessions
- Pagination defaults (skip=0, limit=50 suggested)
- Error response format for API
- How to handle Decimal serialization in JSON responses
- FastAPI app structure (single file vs router modules)

### Deferred Ideas (OUT OF SCOPE)
- Alembic migrations — v2 when schema evolves
- Export to Excel (RPT-01) — v2, builds on the JSON export
- Dashboard with statistics (RPT-03) — v2
- Authentication/multi-user (WEB-03) — v2+
- Pagination with cursor-based approach — v2 if dataset grows large
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STOR-01 | All extracted data is persisted in a local SQLite database | Upsert pattern, writer module, auto-persist wiring in CLI |
| STOR-02 | User can export extracted policy data as JSON | Export subcommand with filters, Pydantic model_dump_json |
| STOR-03 | System exposes a REST API (FastAPI) for querying stored policies | FastAPI app, SQLAlchemy session dependency, CRUD routes |
| STOR-04 | API supports filtering by insurer, date range, agent, and policy type | Query filter pattern with SQLAlchemy .where() clauses, pagination |
</phase_requirements>

---

## Summary

Phase 5 wires together the fully-built storage layer (Phase 1) with the fully-built extraction output (Phase 3) and CLI (Phase 4). The ORM models (Poliza, Asegurado, Cobertura) and Pydantic schemas (PolicyExtraction, AseguradoExtraction, CoberturaExtraction) already share field names exactly — the mapping function is mechanical, not architectural. No schema changes are required.

The three new concerns are: (1) a writer module that maps PolicyExtraction to ORM rows and upserts them; (2) three new Typer subcommands (export, import, serve) added to the existing `cli.py`; and (3) a FastAPI app in `policy_extractor/api/__init__.py` that serves CRUD endpoints with SQLAlchemy session injection. The existing `SessionLocal` and `init_db()` patterns are reused for both CLI and API contexts.

The primary risk is Decimal serialization in FastAPI JSON responses — FastAPI's default JSON encoder does not handle `Decimal` natively. The fix is a custom Pydantic response model or a pre-serialization step using `model_dump(mode="json")` which converts Decimal to str/float before the JSON layer touches it.

**Primary recommendation:** Implement a `policy_extractor/storage/writer.py` module with a single `upsert_policy(session, extraction)` function; wire it into CLI after extraction; build the FastAPI app as a single-file router in `policy_extractor/api/__init__.py` using the `Annotated[Session, Depends(get_db)]` pattern.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.135.1 | REST API framework with Pydantic v2 and OpenAPI auto-docs | De facto standard for Python async APIs; native Pydantic v2 support since 0.100 |
| uvicorn | 0.42.0 | ASGI server for FastAPI | Official recommended server in FastAPI docs |
| sqlalchemy | 2.0.48 (already installed) | ORM + session management | Already used in project; 2.0 style in use |
| pydantic | 2.12.5 (already installed) | Response models, input validation | Already the extraction schema layer |
| typer | 0.9.0 (already installed) | CLI subcommand extension | Already the CLI framework |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uvicorn[standard] | 0.42.0 | Uvicorn with watchfiles, httptools, websockets | Use for the serve subcommand; gives --reload support |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI | Flask + flask-restful | FastAPI gives OpenAPI docs, Pydantic integration, and async for free; Flask requires all of this manually |
| Uvicorn | Hypercorn | Uvicorn is the FastAPI-recommended default; Hypercorn adds no value here |

**Installation:**
```bash
pip install "fastapi>=0.135.1" "uvicorn[standard]>=0.42.0"
```

**pyproject.toml addition (dependencies list):**
```toml
"fastapi>=0.135.1",
"uvicorn[standard]>=0.42.0",
```

**Version verification:** Confirmed current latest as of 2026-03-18 via `pip index versions` on this machine: fastapi 0.135.1, uvicorn 0.42.0.

---

## Architecture Patterns

### Recommended Project Structure
```
policy_extractor/
├── storage/
│   ├── models.py          # Poliza, Asegurado, Cobertura, IngestionCache (EXISTING)
│   ├── database.py        # get_engine(), init_db(), SessionLocal (EXISTING)
│   ├── __init__.py        # (EXISTING)
│   └── writer.py          # NEW: upsert_policy(session, extraction) -> Poliza
├── api/
│   └── __init__.py        # NEW: FastAPI app, routers, DB dependency
├── cli.py                 # MODIFY: add export, import, serve subcommands
└── cli_helpers.py         # EXISTING: unchanged
```

### Pattern 1: Pydantic → ORM Upsert (writer.py)

**What:** A function that takes a `PolicyExtraction` and a `Session`, finds an existing `Poliza` row by `(numero_poliza, aseguradora)`, updates it in place (or creates a new one), then deletes and recreates child `Asegurado` and `Cobertura` rows.

**When to use:** Called after every successful `extract_policy()` call in both `extract` and `batch` CLI commands.

**Key implementation detail:** Use `session.query(Poliza).filter_by(numero_poliza=..., aseguradora=...).first()` to check for existing row. If found, update columns in place. If not, create new. Then delete all `Asegurado` and `Cobertura` children and recreate them. SQLAlchemy's `cascade="all, delete-orphan"` on the relationships handles child deletion when the parent's collections are cleared.

**Decimal handling:** Pydantic v2 `Decimal` fields map directly to SQLAlchemy `Numeric` columns — no conversion needed for writes. For FastAPI JSON responses, use `model.model_dump(mode="json")` which serializes Decimal as a string, or configure `json_encoders` in the response model.

```python
# policy_extractor/storage/writer.py
from sqlalchemy.orm import Session
from policy_extractor.schemas.poliza import PolicyExtraction
from policy_extractor.storage.models import Asegurado, Cobertura, Poliza


def upsert_policy(session: Session, extraction: PolicyExtraction) -> Poliza:
    """Persist a PolicyExtraction to the DB. Upserts by (numero_poliza, aseguradora).

    Children (asegurados, coberturas) are always deleted and recreated on upsert.
    """
    poliza = (
        session.query(Poliza)
        .filter_by(
            numero_poliza=extraction.numero_poliza,
            aseguradora=extraction.aseguradora,
        )
        .first()
    )

    scalar_fields = {
        "tipo_seguro", "fecha_emision", "inicio_vigencia", "fin_vigencia",
        "nombre_contratante", "nombre_agente", "prima_total", "moneda",
        "forma_pago", "frecuencia_pago", "source_file_hash", "model_id",
        "prompt_version", "extracted_at", "campos_adicionales",
    }

    if poliza is None:
        poliza = Poliza(
            numero_poliza=extraction.numero_poliza,
            aseguradora=extraction.aseguradora,
        )
        session.add(poliza)
    else:
        # Clear existing children — cascade handles deletion
        poliza.asegurados.clear()
        poliza.coberturas.clear()
        session.flush()  # Flush deletions before re-creating

    for field in scalar_fields:
        setattr(poliza, field, getattr(extraction, field, None))

    for a in extraction.asegurados:
        poliza.asegurados.append(
            Asegurado(
                tipo=a.tipo,
                nombre_descripcion=a.nombre_descripcion,
                fecha_nacimiento=a.fecha_nacimiento,
                rfc=a.rfc,
                curp=a.curp,
                direccion=a.direccion,
                parentesco=a.parentesco,
                campos_adicionales=a.campos_adicionales,
            )
        )

    for c in extraction.coberturas:
        poliza.coberturas.append(
            Cobertura(
                nombre_cobertura=c.nombre_cobertura,
                suma_asegurada=c.suma_asegurada,
                deducible=c.deducible,
                moneda=c.moneda,
                campos_adicionales=c.campos_adicionales,
            )
        )

    session.commit()
    return poliza
```

### Pattern 2: FastAPI Session Dependency (api/__init__.py)

**What:** A generator function yielding a `Session` that FastAPI injects per request. Ensures session is closed after each request regardless of success/failure.

**When to use:** All API route functions that need DB access.

```python
# policy_extractor/api/__init__.py
from typing import Annotated, Generator
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session
from policy_extractor.storage.database import SessionLocal, init_db
from policy_extractor.config import settings

app = FastAPI(title="Poliza Extractor API", version="1.0.0")


@app.on_event("startup")
def on_startup() -> None:
    engine = init_db(settings.DB_PATH)
    SessionLocal.configure(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbDep = Annotated[Session, Depends(get_db)]
```

**Note on `on_event("startup")`:** This is the FastAPI 0.93+ lifespan pattern alternative. The older `@app.on_event("startup")` decorator still works in 0.135.1 but is soft-deprecated in favor of `lifespan` context manager. For v1 simplicity, `on_event` is acceptable.

### Pattern 3: Filtering Query (STOR-04)

**What:** Build the `GET /polizas` query by conditionally appending `.where()` clauses based on which filter parameters are non-None.

```python
from datetime import date
from typing import Optional
from sqlalchemy import select
from policy_extractor.storage.models import Poliza

def query_polizas(
    db: Session,
    aseguradora: Optional[str] = None,
    tipo_seguro: Optional[str] = None,
    nombre_agente: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Poliza]:
    stmt = select(Poliza)
    if aseguradora:
        stmt = stmt.where(Poliza.aseguradora == aseguradora)
    if tipo_seguro:
        stmt = stmt.where(Poliza.tipo_seguro == tipo_seguro)
    if nombre_agente:
        stmt = stmt.where(Poliza.nombre_agente == nombre_agente)
    if desde:
        stmt = stmt.where(Poliza.inicio_vigencia >= desde)
    if hasta:
        stmt = stmt.where(Poliza.fin_vigencia <= hasta)
    stmt = stmt.offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())
```

### Pattern 4: ORM → Pydantic Response

**What:** Convert `Poliza` ORM rows (with loaded relationships) back to `PolicyExtraction`-shaped dicts for API responses.

**Key detail:** SQLAlchemy lazy-loads relationships by default. Either eager-load with `options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))` or access within the session. For simplicity with small datasets, access within session before closing.

```python
from sqlalchemy.orm import selectinload

stmt = select(Poliza).where(Poliza.id == poliza_id).options(
    selectinload(Poliza.asegurados),
    selectinload(Poliza.coberturas),
)
```

### Pattern 5: Typer subcommand addition

**What:** Add new `@app.command()` decorated functions to the existing `cli.py`. The three new subcommands are `export`, `import_json` (avoid shadowing `import` built-in), and `serve`.

```python
@app.command(name="export")
def export_policies(
    insurer: Optional[str] = typer.Option(None, "--insurer"),
    agent: Optional[str] = typer.Option(None, "--agent"),
    from_date: Optional[str] = typer.Option(None, "--from-date"),
    to_date: Optional[str] = typer.Option(None, "--to-date"),
    policy_type: Optional[str] = typer.Option(None, "--type"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    ...

@app.command(name="import")
def import_json(
    file: Path = typer.Argument(..., help="JSON file to import"),
) -> None:
    ...

@app.command()
def serve(
    port: int = typer.Option(8000, "--port"),
    host: str = typer.Option("127.0.0.1", "--host"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    import uvicorn
    uvicorn.run("policy_extractor.api:app", host=host, port=port, reload=reload)
```

### Anti-Patterns to Avoid

- **Lazy-loading after session close:** Loading `poliza.asegurados` after `session.close()` will raise `DetachedInstanceError`. Always use `selectinload` or access within session scope.
- **Float for money:** Never use Python `float` for `prima_total` or `suma_asegurada`. The ORM uses `Numeric`, Pydantic uses `Decimal`. FastAPI's JSON serialization of `Decimal` must be handled (see pitfalls).
- **Shadowing Python `import` keyword:** The CLI import subcommand function must be named `import_json` (or similar), with `@app.command(name="import")`.
- **Modifying existing `extract`/`batch` command signatures:** Only add the persistence call after the existing extraction call. Do not change function signatures or existing option names.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OpenAPI docs | Custom documentation | FastAPI built-in `/docs` and `/redoc` | Automatic from route type hints and docstrings |
| Request validation | Manual type checking in routes | Pydantic query parameter models | FastAPI handles this with `Query()` and type annotations |
| ASGI server | Custom HTTP server | uvicorn | Handles ASGI protocol, keep-alive, graceful shutdown |
| Session lifecycle | Manual open/close in each route | FastAPI `Depends(get_db)` generator | Guarantees close on error; no session leaks |
| JSON encoder for Decimal | Custom `json.dumps` with encoder | `model_dump(mode="json")` on Pydantic v2 | Converts Decimal to str cleanly; zero custom code |

**Key insight:** FastAPI + Pydantic v2's native integration means route parameters, response serialization, and API docs all derive from the same type annotations. Writing manual validation or documentation defeats the framework's core value.

---

## Common Pitfalls

### Pitfall 1: Decimal Not JSON-Serializable by Default

**What goes wrong:** FastAPI's internal JSON serialization calls `json.dumps()` which cannot handle Python `Decimal`. Routes returning `Poliza` data with `prima_total` will raise `TypeError: Object of type Decimal is not JSON serializable`.

**Why it happens:** Python's `json` module only handles `str`, `int`, `float`, `list`, `dict`, `None`, `bool`. `Decimal` is not in that list.

**How to avoid:** Two options:
1. Return `dict` from routes via `model_dump(mode="json")` — Pydantic v2 converts `Decimal` to `str` automatically. Mark route with `response_model=None` or use `JSONResponse`.
2. Define a `PolizaResponse` Pydantic model with `prima_total: Optional[str]` converted at construction time.

The recommended approach for this project: build an `orm_to_schema(poliza: Poliza) -> PolicyExtraction` helper that reconstructs a `PolicyExtraction` from ORM columns (Decimal stays as Decimal in Pydantic), then use `response.model_dump(mode="json")` which gives `str` for Decimal fields in the final JSON output. Return a `JSONResponse(content=...)` from the route.

**Warning signs:** `500 Internal Server Error` with `TypeError: Object of type Decimal is not JSON serializable` in uvicorn logs.

### Pitfall 2: SQLAlchemy Relationship Lazy Loading After Session Close

**What goes wrong:** Accessing `poliza.asegurados` or `poliza.coberturas` after `session.close()` raises `sqlalchemy.orm.exc.DetachedInstanceError: Instance is not bound to a Session`.

**Why it happens:** SQLAlchemy ORM models with default lazy-loading issue a new SQL query when the relationship attribute is first accessed. After the session closes, this is impossible.

**How to avoid:** Always use `selectinload` when fetching `Poliza` rows that need nested data:
```python
from sqlalchemy.orm import selectinload
stmt = select(Poliza).options(
    selectinload(Poliza.asegurados),
    selectinload(Poliza.coberturas),
)
```

**Warning signs:** `DetachedInstanceError` raised in route handlers or after session scope exits.

### Pitfall 3: Auto-Persist Breaks CLI `--quiet` / stdout Contract

**What goes wrong:** Adding persistence to the `extract` and `batch` commands might inadvertently print DB error messages to stdout, breaking the pipe contract (JSON data on stdout only, Rich output on stderr).

**Why it happens:** If `upsert_policy()` raises an exception and the exception is caught and printed to stdout, downstream pipes (`| jq`) break.

**How to avoid:** All persistence errors must be caught and logged to the `console` (which writes to stderr). The main JSON output (`print(policy.model_dump_json(...))`) must occur before or separately from the persistence call. If persistence fails, warn on stderr but still exit with code 0 for the extraction (extraction succeeded; storage is a secondary concern for CLI).

**Warning signs:** `jq` parse errors when piping `poliza-extractor extract` output.

### Pitfall 4: `SessionLocal` Not Bound When FastAPI Starts Independently

**What goes wrong:** `SessionLocal` is configured with `bind=engine` in `_setup_db()` inside CLI commands. When FastAPI starts via `uvicorn policy_extractor.api:app` directly (not via CLI), `_setup_db()` never runs. Routes that call `SessionLocal()` get an unbound session.

**Why it happens:** `SessionLocal = sessionmaker(autocommit=False, autoflush=False)` in `database.py` has no engine binding at module load time.

**How to avoid:** The FastAPI `startup` event (or lifespan context) in `api/__init__.py` must call `init_db()` and `SessionLocal.configure(bind=engine)`. This ensures the API works standalone as well as via `serve` subcommand.

**Warning signs:** `sqlalchemy.exc.UnboundExecutionError` when hitting any API endpoint started with `uvicorn policy_extractor.api:app`.

### Pitfall 5: Import Subcommand Round-Trip Requires Strict JSON Parsing

**What goes wrong:** When re-importing previously exported JSON, date fields like `fecha_emision`, `inicio_vigencia`, `fin_vigencia` arrive as ISO strings (e.g., `"2024-01-15"`). If the import code creates `PolicyExtraction` from raw dicts without going through Pydantic, date fields remain as strings, causing SQLAlchemy type errors on insert.

**How to avoid:** Always parse imported JSON through `PolicyExtraction.model_validate(record)` for each entry. Pydantic's `normalize_date` validator handles ISO strings correctly.

---

## Code Examples

### Upsert Integration in CLI extract command

```python
# In cli.py extract() after: policy, usage = extract_policy(...)
if policy is not None:
    # Persist to DB (auto-persist, STOR-01)
    try:
        from policy_extractor.storage.writer import upsert_policy
        upsert_policy(session, policy)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]WARN[/yellow] Persistence failed: {exc}")

    # JSON to stdout (unchanged)
    print(policy.model_dump_json(indent=2))
```

### Export subcommand core logic

```python
@app.command(name="export")
def export_policies(...) -> None:
    _setup_db()
    session = SessionLocal()
    try:
        from policy_extractor.storage.reader import query_polizas
        polizas = query_polizas(session, ...)  # returns list[Poliza]
        results = [orm_to_schema(p).model_dump(mode="json") for p in polizas]
        json_str = json.dumps(results, indent=2, ensure_ascii=False)
        if output:
            Path(output).write_text(json_str, encoding="utf-8")
        else:
            print(json_str)
    finally:
        session.close()
```

### FastAPI GET /polizas with filters and pagination

```python
@router.get("/polizas")
def list_polizas(
    db: DbDep,
    aseguradora: Optional[str] = Query(None),
    tipo_seguro: Optional[str] = Query(None),
    nombre_agente: Optional[str] = Query(None),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> JSONResponse:
    polizas = query_polizas(db, aseguradora, tipo_seguro, nombre_agente, desde, hasta, skip, limit)
    data = [orm_to_schema(p).model_dump(mode="json") for p in polizas]
    return JSONResponse(content=data)
```

### ORM → PolicyExtraction schema conversion (orm_to_schema)

```python
# policy_extractor/storage/writer.py (or a reader.py)
from policy_extractor.schemas.poliza import PolicyExtraction
from policy_extractor.schemas.asegurado import AseguradoExtraction
from policy_extractor.schemas.cobertura import CoberturaExtraction

def orm_to_schema(poliza: Poliza) -> PolicyExtraction:
    """Convert a fully-loaded Poliza ORM row to PolicyExtraction Pydantic model."""
    return PolicyExtraction(
        numero_poliza=poliza.numero_poliza,
        aseguradora=poliza.aseguradora,
        tipo_seguro=poliza.tipo_seguro,
        fecha_emision=poliza.fecha_emision,
        inicio_vigencia=poliza.inicio_vigencia,
        fin_vigencia=poliza.fin_vigencia,
        nombre_contratante=poliza.nombre_contratante,
        nombre_agente=poliza.nombre_agente,
        prima_total=poliza.prima_total,
        moneda=poliza.moneda,
        forma_pago=poliza.forma_pago,
        frecuencia_pago=poliza.frecuencia_pago,
        source_file_hash=poliza.source_file_hash,
        model_id=poliza.model_id,
        prompt_version=poliza.prompt_version,
        extracted_at=poliza.extracted_at,
        campos_adicionales=poliza.campos_adicionales or {},
        asegurados=[
            AseguradoExtraction(
                tipo=a.tipo,
                nombre_descripcion=a.nombre_descripcion,
                fecha_nacimiento=a.fecha_nacimiento,
                rfc=a.rfc,
                curp=a.curp,
                direccion=a.direccion,
                parentesco=a.parentesco,
                campos_adicionales=a.campos_adicionales or {},
            )
            for a in poliza.asegurados
        ],
        coberturas=[
            CoberturaExtraction(
                nombre_cobertura=c.nombre_cobertura,
                suma_asegurada=c.suma_asegurada,
                deducible=c.deducible,
                moneda=c.moneda,
                campos_adicionales=c.campos_adicionales or {},
            )
            for c in poliza.coberturas
        ],
    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan` async context manager | FastAPI 0.93 | on_event still works but lifespan is preferred; v1 can use on_event |
| SQLAlchemy 1.x `Session.query()` style | SQLAlchemy 2.0 `select()` + `execute().scalars()` | SQLAlchemy 2.0 | Both styles coexist in 2.0; project already uses 2.0 style in cli_helpers.py |
| `pydantic.BaseModel.dict()` | `pydantic.BaseModel.model_dump()` | Pydantic v2 | `.dict()` is removed in Pydantic v2; use `model_dump()` |

**Deprecated/outdated:**
- `pydantic.BaseModel.dict()`: removed in Pydantic v2 — always use `.model_dump()` or `.model_dump(mode="json")`
- `pydantic.BaseModel.parse_obj()`: removed in Pydantic v2 — use `.model_validate()`
- SQLAlchemy `session.query(Model)`: still works in 2.0 but `select(Model)` + `session.execute().scalars()` is the 2.0 idiomatic style (both acceptable in this project)

---

## Open Questions

1. **`serve` subcommand: should `uvicorn.run()` block the CLI process?**
   - What we know: `uvicorn.run()` is synchronous and blocks until the server stops.
   - What's unclear: Whether Typer/Click has any issue with a blocking command (it does not — this is normal for server subcommands).
   - Recommendation: Call `uvicorn.run()` directly. Add `--reload` as an option for development. Document that Ctrl+C stops the server cleanly.

2. **`confianza` field round-trip through ORM**
   - What we know: `confianza` is stored in `campos_adicionales` JSON (it is not a separate column). The Phase 3 decision was that `campos_adicionales['_raw_response']` stores the raw Claude response.
   - What's unclear: Whether `confianza` is stored inside `campos_adicionales` or as a top-level key in the Poliza row.
   - Recommendation: Store `confianza` inside `campos_adicionales` dict (key `"confianza"`) alongside `_raw_response`. This avoids adding a new column. The `upsert_policy` function should put it there when building `campos_adicionales`.

3. **`import` subcommand: handle single object vs array JSON**
   - What we know: Export produces an array. A user might also try to import a single extracted JSON.
   - What's unclear: Whether to require array format only or handle both.
   - Recommendation: Support both. If the top-level JSON value is a dict, wrap it in a list. If it's a list, iterate as-is.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already configured) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` with `testpaths = ["tests"]` |
| Quick run command | `pytest tests/test_storage_writer.py tests/test_api.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STOR-01 | `upsert_policy()` saves PolicyExtraction to DB; re-extract same (numero_poliza, aseguradora) updates row not creates new | unit | `pytest tests/test_storage_writer.py -x -q` | ❌ Wave 0 |
| STOR-01 | CLI `extract` command persists to DB after extraction succeeds | unit (CLI mock) | `pytest tests/test_cli_persistence.py -x -q` | ❌ Wave 0 |
| STOR-02 | `export` subcommand outputs valid JSON array with all fields | unit (CLI) | `pytest tests/test_cli_export.py -x -q` | ❌ Wave 0 |
| STOR-02 | Exported JSON can be re-imported via `import` subcommand (round-trip) | integration | `pytest tests/test_cli_import.py -x -q` | ❌ Wave 0 |
| STOR-03 | FastAPI app starts and `GET /polizas` returns 200 with JSON array | unit (TestClient) | `pytest tests/test_api.py::test_list_polizas -x -q` | ❌ Wave 0 |
| STOR-03 | `GET /polizas/{id}` returns 200 with nested asegurados/coberturas; 404 for missing | unit (TestClient) | `pytest tests/test_api.py::test_get_poliza_by_id -x -q` | ❌ Wave 0 |
| STOR-03 | `POST /polizas` creates a new record, `PUT /polizas/{id}` updates, `DELETE` removes | unit (TestClient) | `pytest tests/test_api.py::test_crud -x -q` | ❌ Wave 0 |
| STOR-04 | `GET /polizas?aseguradora=X` returns only policies matching that insurer | unit (TestClient) | `pytest tests/test_api.py::test_filter_aseguradora -x -q` | ❌ Wave 0 |
| STOR-04 | `GET /polizas?desde=2024-01-01&hasta=2024-12-31` filters by date range | unit (TestClient) | `pytest tests/test_api.py::test_filter_dates -x -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_storage_writer.py tests/test_api.py -x -q`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_storage_writer.py` — covers STOR-01 (upsert, update, round-trip)
- [ ] `tests/test_cli_persistence.py` — covers STOR-01 CLI wiring (can extend test_cli.py)
- [ ] `tests/test_cli_export.py` — covers STOR-02 export subcommand
- [ ] `tests/test_cli_import.py` — covers STOR-02 import round-trip
- [ ] `tests/test_api.py` — covers STOR-03 and STOR-04 (FastAPI TestClient, in-memory DB)
- [ ] Framework install: `pip install "fastapi>=0.135.1" "uvicorn[standard]>=0.42.0"` — not yet installed

**FastAPI TestClient pattern (for test files):**
```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from policy_extractor.api import app
from policy_extractor.storage.database import SessionLocal
from policy_extractor.storage.models import Base

def override_get_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()
    try:
        yield db
    finally:
        db.close()

from policy_extractor.api import get_db
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)
```

---

## Sources

### Primary (HIGH confidence)
- PyPI registry (via `pip index versions` on this machine, 2026-03-18) — fastapi 0.135.1, uvicorn 0.42.0 verified as current latest
- Existing codebase — ORM models, Pydantic schemas, CLI structure, database.py patterns all read directly from source files in this repo
- SQLAlchemy 2.0 documentation (selectinload, session.execute, scalars) — patterns match what is already used in `cli_helpers.py`

### Secondary (MEDIUM confidence)
- FastAPI official documentation patterns — dependency injection with `Depends(get_db)`, `startup` event, `TestClient` — standard FastAPI patterns stable across 0.100+ versions
- Pydantic v2 `model_dump(mode="json")` for Decimal serialization — well-documented behavior in Pydantic v2 migration guide

### Tertiary (LOW confidence)
- None — all findings verified against source code or version registry

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified via pip registry on this machine
- Architecture: HIGH — based on direct reading of existing ORM models and Pydantic schemas; field names match exactly
- Pitfalls: HIGH — Decimal serialization and DetachedInstanceError are well-known FastAPI+SQLAlchemy integration issues, verified against project's Numeric column usage

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (FastAPI releases frequently but 0.135.x is stable; SQLAlchemy 2.0 patterns are stable)
