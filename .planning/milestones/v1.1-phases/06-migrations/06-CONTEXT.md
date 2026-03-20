# Phase 6: Migrations - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Schema versioning via Alembic so any future column addition or structural change is managed safely through a migration chain. Includes baseline migration for existing schema and evaluation columns migration for Phase 10. No new application features — purely infrastructure.

</domain>

<decisions>
## Implementation Decisions

### init_db transition
- Keep both `create_all()` and Alembic with a guard: if no `alembic_version` table exists (fresh DB), `init_db()` calls `create_all()` then stamps as current head; existing DBs use `alembic upgrade head`
- CLI auto-runs pending migrations on startup before any command executes — user never needs to run `alembic upgrade head` manually
- Tests use `create_all()` for speed; a dedicated `test_migrations.py` verifies the full migration chain end-to-end
- Alembic directory and `alembic.ini` live at the project root (standard convention)

### Evaluation columns design
- `evaluation_score`: REAL, nullable, stores float 0.0–1.0 (normalized score)
- `evaluation_json`: TEXT (JSON), nullable, stores structured assessment only (field scores, flags, summary — not raw Sonnet API response)
- `evaluated_at`: DATETIME, nullable, tracks when evaluation was run (supports re-evaluation workflows)
- `evaluated_model_id`: TEXT, nullable, tracks which Sonnet model produced the evaluation
- All four columns added to the `polizas` table in migration 002

### WAL mode handling
- WAL mode enabled via `PRAGMA journal_mode=WAL` in Alembic's `env.py` before running migrations
- Also set in `database.py` `get_engine()` for non-migration paths — belt-and-suspenders, PRAGMA is idempotent
- WAL mode required by Phase 9 (Async Batch) for concurrent write safety

### Existing DB safety
- Baseline migration (001) detects existing tables via inspector: if `polizas` table exists, just stamps revision; if fresh DB, creates all tables
- Auto-migrate creates a backup (`polizas.db.bak`) before applying any pending migrations
- Brief log line per migration applied (e.g., "Applied migration: 002_evaluation_columns"); silent when already at head

### Claude's Discretion
- Alembic revision ID format and naming conventions
- env.py configuration details beyond WAL and batch mode
- Auto-migrate implementation details (where in CLI startup to hook it)
- Exact backup file naming if multiple backups needed

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Database schema
- `policy_extractor/storage/models.py` — Current SQLAlchemy ORM models (Poliza, Asegurado, Cobertura, IngestionCache) that define the baseline schema
- `policy_extractor/storage/database.py` — Current `init_db()` with `create_all()` that must be augmented with guard logic

### Requirements
- `.planning/REQUIREMENTS.md` §Migrations & Infrastructure — MIG-01 (Alembic init with batch mode), MIG-02 (baseline stamp), MIG-03 (evaluation columns)
- `.planning/REQUIREMENTS.md` §Quality Evaluation — QAL-03 (evaluation results stored in DB columns) defines what Phase 10 needs from the evaluation columns

### Project decisions
- `.planning/STATE.md` §Accumulated Context — Documents `render_as_batch=True` requirement, WAL mode concern, and `alembic stamp head` todo

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Base` (DeclarativeBase) in `models.py`: Alembic's `env.py` needs `target_metadata = Base.metadata` — already defined
- `get_engine()` in `database.py`: Returns configured SQLAlchemy engine — can be reused for Alembic's engine config
- `SessionLocal` sessionmaker in `database.py`: Unchanged by migrations

### Established Patterns
- SQLAlchemy 2.0 mapped_column style: All models use `Mapped[T]` with `mapped_column()` — migrations must match this
- JSON columns use `sa.JSON` type: `campos_adicionales` on all three main tables
- Numeric(15,2) for monetary values: Established precision pattern
- String(64) for hashes, String(3) for currency codes: Established size patterns

### Integration Points
- `init_db()` is called by CLI commands and test fixtures — migration guard hooks in here
- `conftest.py` creates test engines with `create_all()` — stays as-is, separate migration test added
- CLI entry points (Typer commands) — auto-migrate hooks before command execution

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard Alembic setup with the decisions captured above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 06-migrations*
*Context gathered: 2026-03-19*
