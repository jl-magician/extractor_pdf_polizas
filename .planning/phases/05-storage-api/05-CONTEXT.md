# Phase 5: Storage & API - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Persist all extracted policy data in SQLite and make it queryable via JSON export and a REST API. Wire persistence into the existing CLI (auto-save after extraction), add an export subcommand, add an import subcommand, and create FastAPI endpoints with full CRUD and filtering. No schema changes to existing models — only add persistence logic, export, and API layer.

</domain>

<decisions>
## Implementation Decisions

### Persistence strategy
- Auto-persist after extraction in CLI — after successful extraction in extract/batch commands, automatically save PolicyExtraction to SQLite. User gets JSON output AND data is stored.
- Also provide an `import` subcommand to load previously exported JSON files into DB
- Dedup strategy: upsert by (numero_poliza, aseguradora) — if same policy number from same insurer exists, update the existing record. Different policy number = new record.
- Mapping: PolicyExtraction (Pydantic) → Poliza + Asegurado + Cobertura (ORM models). Delete existing child rows on upsert, re-create from extraction.

### JSON export
- New `export` subcommand: `poliza-extractor export`
- Dumps all policies by default; supports filters: `--insurer`, `--agent`, `--from-date`, `--to-date`, `--type`
- Output to stdout by default, `--output file.json` for file
- Format: array of PolicyExtraction-shaped objects — same Pydantic schema as extraction output, consistent and familiar
- Includes asegurados and coberturas nested in each policy object

### FastAPI endpoints
- Full CRUD routes:
  - `GET /polizas` — list with filters (aseguradora, tipo_seguro, nombre_agente, desde, hasta) + pagination (skip, limit)
  - `GET /polizas/{id}` — single policy with asegurados + coberturas
  - `POST /polizas` — create policy from JSON
  - `PUT /polizas/{id}` — update existing policy
  - `DELETE /polizas/{id}` — delete policy and children
- Response format: PolicyExtraction-shaped JSON with nested asegurados/coberturas
- Server start: both `poliza-extractor serve --port 8000` CLI subcommand AND standard `uvicorn policy_extractor.api:app` works
- Swagger/OpenAPI docs enabled at `/docs` and `/redoc` (FastAPI defaults)

### Alembic migrations
- Skip Alembic for v1 — keep using `Base.metadata.create_all()`
- Schema is stable, DB can be recreated from scratch in v1
- Add Alembic in v2 when schema evolves

### Claude's Discretion
- Pydantic → ORM mapping function implementation details
- FastAPI dependency injection for DB sessions
- Pagination defaults (skip=0, limit=50 suggested)
- Error response format for API
- How to handle Decimal serialization in JSON responses
- FastAPI app structure (single file vs router modules)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing storage layer (Phase 1)
- `policy_extractor/storage/models.py` — Poliza, Asegurado, Cobertura, IngestionCache ORM models. These are the persistence targets.
- `policy_extractor/storage/database.py` — `get_engine()`, `init_db()`, `SessionLocal`. Reuse for DB access.
- `policy_extractor/storage/__init__.py` — Exports all models and DB functions.

### Extraction output (Phase 3)
- `policy_extractor/schemas/poliza.py` — PolicyExtraction model (the source for persistence mapping)
- `policy_extractor/schemas/asegurado.py` — AseguradoExtraction (maps to Asegurado ORM)
- `policy_extractor/schemas/cobertura.py` — CoberturaExtraction (maps to Cobertura ORM)

### CLI (Phase 4)
- `policy_extractor/cli.py` — Existing Typer app where `export`, `import`, and `serve` subcommands will be added
- `policy_extractor/cli_helpers.py` — Existing helpers (is_already_extracted, estimate_cost)

### API stub
- `policy_extractor/api/__init__.py` — Stub module where FastAPI app will live

### Project scope
- `.planning/REQUIREMENTS.md` — STOR-01 through STOR-04
- `.planning/ROADMAP.md` — Phase 5 success criteria (4 criteria that must be TRUE)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Poliza`, `Asegurado`, `Cobertura` ORM models — already have all columns, FK relationships, cascade delete
- `PolicyExtraction`, `AseguradoExtraction`, `CoberturaExtraction` — Pydantic schemas with matching field names
- `get_engine()` / `init_db()` / `SessionLocal` — DB access pattern established
- `policy_extractor/cli.py` — Typer app to extend with new subcommands
- `Settings.DB_PATH` — configured DB path

### Established Patterns
- Pydantic v2 models for all data contracts
- SQLAlchemy 2.0 Mapped[] with DeclarativeBase
- Typer CLI with Rich for display
- Console(stderr=True) for progress, stdout for data
- pytest with in-memory SQLite for DB tests

### Integration Points
- CLI extract/batch commands need to call persistence after extraction (modify existing flow)
- `policy_extractor/api/__init__.py` — stub exists, FastAPI app lives here
- `pyproject.toml` — add `fastapi` and `uvicorn` dependencies
- `poliza-extractor serve` — new CLI subcommand starts uvicorn

</code_context>

<specifics>
## Specific Ideas

- Upsert by (numero_poliza, aseguradora) handles re-extraction: same policy from new prompt version replaces the old record
- The export format should match extraction output so exported JSON can be re-imported via the import command (round-trip)
- Full CRUD gives the agency team flexibility to correct extraction mistakes via API before v2 web UI
- Auto-persist means the happy path (extract → store → query) requires no extra steps

</specifics>

<deferred>
## Deferred Ideas

- Alembic migrations — v2 when schema evolves
- Export to Excel (RPT-01) — v2, builds on the JSON export
- Dashboard with statistics (RPT-03) — v2
- Authentication/multi-user (WEB-03) — v2+
- Pagination with cursor-based approach — v2 if dataset grows large

</deferred>

---

*Phase: 05-storage-api*
*Context gathered: 2026-03-18*
